import os
import io
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

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

        self._endpoint = endpoint or os.environ.get("MINIO_ENDPOINT", "minio:9000")
        self._access_key = access_key or os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
        self._secret_key = secret_key or os.environ.get("MINIO_SECRET_KEY", "minioadmin")
        self._secure = secure if secure is not None else os.environ.get("MINIO_SECURE", "false").lower() == "true"

        self._client: Optional[Any] = None
        if MINIO_SDK_AVAILABLE:
            try:
                self._client = Minio(
                    self._endpoint,
                    access_key=self._access_key,
                    secret_key=self._secret_key,
                    secure=self._secure,
                )
                logger.info("MinIO client initialized: %s", self._endpoint)
            except Exception as e:
                logger.warning("MinIO client init failed: %s", e)
                self._client = None
        else:
            logger.warning("MinIO SDK not available, using fallback mode")

        self._initialized = True

    @property
    def available(self) -> bool:
        return self._client is not None

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
            return {"status": "error", "message": str(e)}


def get_minio_client() -> MinIOClient:
    return MinIOClient()
