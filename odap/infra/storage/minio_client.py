import os
import io
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional
from odap.infra.config_composer import get_config

logger = logging.getLogger("minio_client")

try:
    from minio import Minio
    from minio.error import S3Error

    MINIO_SDK_AVAILABLE = True
except ImportError:
    MINIO_SDK_AVAILABLE = False
    Minio = object
    S3Error = Exception


class MinIOClient:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        secure: Optional[bool] = None,
    ):
        if hasattr(self, "_initialized"):
            return

        self._endpoint = endpoint or get_config("object_storage.endpoint", "minio:9000")
        # P0-8 fix: NEVER use hardcoded "minioadmin" defaults. Resolve via
        # env vars and fail-closed if not set in production.
        self._access_key = self._resolve_minio_credential(
            "MINIO_ACCESS_KEY", access_key,
            min_length=8,
        )
        self._secret_key = self._resolve_minio_credential(
            "MINIO_SECRET_KEY", secret_key,
            min_length=8,
        )
        self._secure = secure if secure is not None else get_config("object_storage.secure", False)

        self._client: Optional[Any] = None
        if MINIO_SDK_AVAILABLE:
            try:
                self._client = Minio(
                    self._endpoint,
                    access_key=self._access_key,
                    secret_key=self._secret_key,
                    secure=self._secure,
                )
                # 主动探测连通性（Minio() 构造器是惰性的，不实际连接）
                self._ping_ok = self._ping()
                if self._ping_ok:
                    logger.info("MinIO client initialized and reachable: %s", self._endpoint)
                else:
                    logger.warning(
                        "MinIO client initialized but server unreachable: %s "
                        "(uploads will fall back to local disk)", self._endpoint,
                    )
            except Exception as e:
                logger.warning("MinIO client init failed: %s", e)
                self._client = None
                self._ping_ok = False
        else:
            logger.warning("MinIO SDK not available (pip install minio), using fallback mode")
            self._ping_ok = False

        self._initialized = True

    @staticmethod
    def _resolve_minio_credential(env_var: str, explicit_value, min_length: int = 8) -> str:
        """Resolve a MinIO credential.

        Priority:
          1. Explicit constructor argument
          2. Configuration Composer (env var mapped via get_config)
          3. In dev/test: accept any value from env (including "minioadmin")
          4. In production: refuse default/weak credentials
        """
        if explicit_value:
            return explicit_value
        # Map env var names to config composer keys
        _env_to_config_key = {
            "MINIO_ACCESS_KEY": "object_storage.access_key",
            "MINIO_SECRET_KEY": "object_storage.secret_key",
        }
        config_key = _env_to_config_key.get(env_var)
        value = (get_config(config_key, "") if config_key else os.environ.get(env_var, "")).strip()

        is_production = os.environ.get("ENV", "").lower() in ("production", "prod", "live")

        # 生产环境：拒绝弱密码
        if is_production and value.lower() in ("minioadmin", "minio", "admin", "admin123", "password", ""):
            raise RuntimeError(
                f"SECURITY: {env_var} must be set to a non-default value "
                f"of at least {min_length} characters in production. "
                f"Set {env_var} in your secrets manager."
            )

        # 开发/测试环境：接受任何显式配置的值（包括 minioadmin）
        if value and len(value) >= min_length:
            return value

        # 值过短或未设置：dev 模式使用 placeholder
        if not is_production:
            if value:
                logger.warning(
                    f"{env_var} 长度不足 {min_length} 字符，"
                    f"开发环境将使用原值。生产环境请务必更换强密码。"
                )
                return value
            logger.warning(
                f"{env_var} is not set. Using placeholder for dev. "
                f"Set {env_var} in production."
            )
            return "dev-placeholder"

        raise RuntimeError(
            f"SECURITY: {env_var} must be set in production. "
            f"Set {env_var} in your secrets manager."
        )

    @property
    def available(self) -> bool:
        """True only when SDK loaded AND server is reachable."""
        return self._client is not None and getattr(self, "_ping_ok", False)

    def _ping(self) -> bool:
        """Lightweight connectivity check — calls list_buckets() which forces a real TCP round-trip."""
        if not self._client:
            return False
        try:
            self._client.list_buckets()
            return True
        except Exception as e:
            logger.debug("MinIO ping failed: %s", e)
            return False

    def ping(self) -> Dict[str, Any]:
        """Public connectivity diagnostic for admin/health endpoints."""
        if not MINIO_SDK_AVAILABLE:
            return {"status": "error", "message": "minio SDK not installed (pip install minio)"}
        if not self._client:
            return {"status": "error", "message": "client not initialized"}
        try:
            self._client.list_buckets()
            self._ping_ok = True
            return {"status": "success", "endpoint": self._endpoint}
        except Exception as e:
            self._ping_ok = False
            return {"status": "error", "endpoint": self._endpoint, "message": str(e)}

    def upload_object(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        length: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not self._client:
            return {"status": "error", "message": "MinIO client not available"}

        try:
            data_stream = io.BytesIO(data)
            data_length = length if length is not None else len(data)
            self._client.put_object(
                bucket,
                key,
                data_stream,
                data_length,
                content_type=content_type,
            )
            return {
                "status": "success",
                "bucket": bucket,
                "key": key,
                "size": data_length,
                "content_type": content_type,
            }
        except S3Error as e:
            return {"status": "error", "message": f"S3 error: {e}"}
        except Exception as e:
            logger.warning(f"MinIO operation failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def download_object(self, bucket: str, key: str) -> Dict[str, Any]:
        if not self._client:
            return {"status": "error", "message": "MinIO client not available"}

        try:
            response = self._client.get_object(bucket, key)
            data = response.read()
            response.close()
            response.release_conn()
            return {
                "status": "success",
                "bucket": bucket,
                "key": key,
                "data": data,
                "size": len(data),
            }
        except S3Error as e:
            return {"status": "error", "message": f"S3 error: {e}"}
        except Exception as e:
            logger.warning(f"MinIO operation failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def get_presigned_url(
        self, bucket: str, key: str, expires: timedelta = timedelta(hours=1)
    ) -> Dict[str, Any]:
        if not self._client:
            return {"status": "error", "message": "MinIO client not available"}

        try:
            url = self._client.presigned_get_object(bucket, key, expires=expires)
            return {
                "status": "success",
                "bucket": bucket,
                "key": key,
                "url": url,
                "expires_seconds": int(expires.total_seconds()),
            }
        except S3Error as e:
            return {"status": "error", "message": f"S3 error: {e}"}
        except Exception as e:
            logger.warning(f"MinIO operation failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def delete_object(self, bucket: str, key: str) -> Dict[str, Any]:
        if not self._client:
            return {"status": "error", "message": "MinIO client not available"}

        try:
            self._client.remove_object(bucket, key)
            return {"status": "success", "bucket": bucket, "key": key}
        except S3Error as e:
            return {"status": "error", "message": f"S3 error: {e}"}
        except Exception as e:
            logger.warning("MinIO delete_object failed: %s", e, exc_info=True)
            return {"status": "error", "message": str(e)}

    def ensure_bucket(self, bucket: str) -> Dict[str, Any]:
        if not self._client:
            return {"status": "error", "message": "MinIO client not available"}

        try:
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)
                return {"status": "success", "bucket": bucket, "created": True}
            return {"status": "success", "bucket": bucket, "created": False}
        except S3Error as e:
            return {"status": "error", "message": f"S3 error: {e}"}
        except Exception as e:
            logger.warning(f"MinIO operation failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def list_objects(self, bucket: str, prefix: Optional[str] = None) -> Dict[str, Any]:
        if not self._client:
            return {"status": "error", "message": "MinIO client not available"}

        try:
            objects = self._client.list_objects(bucket, prefix=prefix, recursive=True)
            result = []
            for obj in objects:
                result.append(
                    {
                        "name": obj.object_name,
                        "size": obj.size,
                        "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                        "content_type": obj.content_type,
                        "is_dir": obj.is_dir,
                    }
                )
            return {"status": "success", "bucket": bucket, "objects": result, "count": len(result)}
        except S3Error as e:
            return {"status": "error", "message": f"S3 error: {e}"}
        except Exception as e:
            logger.warning(f"MinIO operation failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}


def get_minio_client() -> MinIOClient:
    return MinIOClient()
