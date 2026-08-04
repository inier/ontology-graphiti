"""Iter 3.1: Raw data persistence layer — MinIO-backed raw data storage.

Provides semantic wrappers (``upload_raw`` / ``download_raw`` / ``get_url``)
over the existing ``MinIOClient`` for persisting ingestion raw text and
enabling原文回溯 (raw data traceability).

ADR-074 §2.1: 数据采集层产出后上传 MinIO，OntologyDocument 记录
``raw_data_ref``，HE kb 原文引用指向 MinIO 地址，检索服务可通过
``raw_data_ref`` 回溯原文。

Design:
    - Bucket convention: ``odap-raw-data`` (one bucket for all raw data)
    - Key convention: ``{workspace_id}/{doc_id}/{source_type}_{timestamp}.txt``
    - Graceful degradation: when MinIO is unavailable, falls back to local
      disk at ``data/raw_data_fallback/`` and logs a warning. The
      ``raw_data_ref`` still carries a usable reference.
    - All methods return dicts with ``status``, ``raw_data_ref``, and
      relevant metadata — never raise (caller-safe).
"""

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from odap.infra.config_composer import get_config

logger = logging.getLogger("raw_data_storage")

# Bucket name for all raw data
RAW_DATA_BUCKET = "odap-raw-data"

# Fallback local storage path (when MinIO is unavailable)
FALLBACK_BASE_PATH = "data/raw_data_fallback"


class RawDataStorage:
    """Semantic wrapper over MinIOClient for raw data persistence.

    Provides three key operations:
        - upload_raw: Upload raw text/data, return raw_data_ref
        - download_raw: Download raw data by raw_data_ref
        - get_url: Get a presigned URL for raw data access

    The ``raw_data_ref`` format is: ``minio://{bucket}/{key}`` for MinIO
    storage, or ``file:///{local_path}`` for local fallback.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._minio = None
        self._fallback_base = get_config("storage.raw_data_fallback_path", FALLBACK_BASE_PATH)
        try:
            from odap.infra.storage.minio_client import get_minio_client
            self._minio = get_minio_client()
        except Exception as exc:
            logger.warning("MinIO client init failed, using local fallback: %s", exc)
            self._minio = None

        # Ensure fallback directory exists
        os.makedirs(self._fallback_base, exist_ok=True)
        self._initialized = True

    @property
    def available(self) -> bool:
        """True when MinIO is reachable and ready for uploads."""
        return self._minio is not None and getattr(self._minio, "available", False)

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload_raw(
        self,
        workspace_id: str,
        doc_id: str,
        text: str,
        source_type: str = "news_ingest",
        content_type: str = "text/plain; charset=utf-8",
    ) -> Dict[str, Any]:
        """Upload raw text data and return a raw_data_ref.

        Args:
            workspace_id: Workspace ID for partitioning.
            doc_id: OntologyDocument ID for traceability.
            text: Raw text content to persist.
            source_type: Source type label (e.g., "news_ingest", "manual_input").
            content_type: MIME content type.

        Returns:
            Dict with status, raw_data_ref, size, and storage mode.
            raw_data_ref format: "minio://{bucket}/{key}" or "file:///{path}"
        """
        if not text:
            return {"status": "skipped", "message": "empty text", "raw_data_ref": None}

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        key = f"{workspace_id}/{doc_id}/{source_type}_{timestamp}.txt"
        data = text.encode("utf-8")

        # Try MinIO first
        if self.available:
            try:
                self._minio.ensure_bucket(RAW_DATA_BUCKET)
                result = self._minio.upload_object(
                    bucket=RAW_DATA_BUCKET,
                    key=key,
                    data=data,
                    content_type=content_type,
                )
                if result.get("status") == "success":
                    raw_data_ref = f"minio://{RAW_DATA_BUCKET}/{key}"
                    logger.info(
                        "Raw data uploaded to MinIO: %s (%d bytes)",
                        raw_data_ref, len(data),
                    )
                    return {
                        "status": "success",
                        "raw_data_ref": raw_data_ref,
                        "size": len(data),
                        "storage_mode": "minio",
                        "bucket": RAW_DATA_BUCKET,
                        "key": key,
                        "checksum": self._checksum(data),
                    }
                else:
                    logger.warning("MinIO upload failed: %s, falling back to local", result.get("message"))
            except Exception as exc:
                logger.warning("MinIO upload raised: %s, falling back to local", exc)

        # Local fallback
        return self._upload_local(workspace_id, doc_id, key, data, source_type)

    def _upload_local(
        self,
        workspace_id: str,
        doc_id: str,
        key: str,
        data: bytes,
        source_type: str,
    ) -> Dict[str, Any]:
        """Upload raw data to local filesystem (fallback when MinIO unavailable)."""
        local_path = os.path.join(self._fallback_base, key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        try:
            with open(local_path, "wb") as f:
                f.write(data)
            raw_data_ref = f"file://{local_path}"
            logger.info(
                "Raw data saved to local fallback: %s (%d bytes)",
                raw_data_ref, len(data),
            )
            return {
                "status": "success",
                "raw_data_ref": raw_data_ref,
                "size": len(data),
                "storage_mode": "local_fallback",
                "local_path": local_path,
                "checksum": self._checksum(data),
            }
        except Exception as exc:
            logger.error("Local fallback write failed: %s", exc)
            return {
                "status": "error",
                "message": str(exc),
                "raw_data_ref": None,
            }

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download_raw(self, raw_data_ref: str) -> Dict[str, Any]:
        """Download raw data by raw_data_ref.

        Args:
            raw_data_ref: Reference string from upload_raw (minio:// or file://).

        Returns:
            Dict with status, data (bytes), text (str), and size.
        """
        if not raw_data_ref:
            return {"status": "error", "message": "empty raw_data_ref"}

        # MinIO reference: minio://bucket/key
        if raw_data_ref.startswith("minio://"):
            parts = raw_data_ref[len("minio://"):].split("/", 1)
            if len(parts) != 2:
                return {"status": "error", "message": f"invalid minio ref: {raw_data_ref}"}
            bucket, key = parts
            if not self.available:
                return {"status": "error", "message": "MinIO not available for download"}
            result = self._minio.download_object(bucket, key)
            if result.get("status") == "success":
                data = result["data"]
                return {
                    "status": "success",
                    "data": data,
                    "text": data.decode("utf-8", errors="replace"),
                    "size": len(data),
                    "raw_data_ref": raw_data_ref,
                }
            return result

        # Local reference: file:///path or file://path
        if raw_data_ref.startswith("file://"):
            local_path = raw_data_ref[len("file://"):]
            # Handle Windows paths (file:///C:/... → C:/...)
            if local_path.startswith("/") and len(local_path) > 2 and local_path[2] == ":":
                local_path = local_path[1:]
            try:
                with open(local_path, "rb") as f:
                    data = f.read()
                return {
                    "status": "success",
                    "data": data,
                    "text": data.decode("utf-8", errors="replace"),
                    "size": len(data),
                    "raw_data_ref": raw_data_ref,
                }
            except Exception as exc:
                return {"status": "error", "message": str(exc), "raw_data_ref": raw_data_ref}

        return {"status": "error", "message": f"unsupported ref scheme: {raw_data_ref}"}

    # ------------------------------------------------------------------
    # Presigned URL
    # ------------------------------------------------------------------

    def get_url(
        self,
        raw_data_ref: str,
        expires_hours: int = 1,
    ) -> Dict[str, Any]:
        """Get a presigned URL for raw data access.

        Args:
            raw_data_ref: Reference string from upload_raw.
            expires_hours: URL expiration time in hours (MinIO only).

        Returns:
            Dict with status and url (MinIO) or local_path (fallback).
        """
        if not raw_data_ref:
            return {"status": "error", "message": "empty raw_data_ref"}

        if raw_data_ref.startswith("minio://"):
            parts = raw_data_ref[len("minio://"):].split("/", 1)
            if len(parts) != 2:
                return {"status": "error", "message": f"invalid minio ref: {raw_data_ref}"}
            bucket, key = parts
            if not self.available:
                return {"status": "error", "message": "MinIO not available"}
            from datetime import timedelta
            result = self._minio.get_presigned_url(bucket, key, expires=timedelta(hours=expires_hours))
            if result.get("status") == "success":
                return {
                    "status": "success",
                    "url": result["url"],
                    "expires_seconds": result.get("expires_seconds", expires_hours * 3600),
                    "raw_data_ref": raw_data_ref,
                }
            return result

        if raw_data_ref.startswith("file://"):
            local_path = raw_data_ref[len("file://"):]
            if local_path.startswith("/") and len(local_path) > 2 and local_path[2] == ":":
                local_path = local_path[1:]
            return {
                "status": "success",
                "url": None,
                "local_path": local_path,
                "raw_data_ref": raw_data_ref,
                "message": "local fallback — no presigned URL, use download_raw",
            }

        return {"status": "error", "message": f"unsupported ref scheme: {raw_data_ref}"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _checksum(data: bytes) -> str:
        """Compute SHA-256 checksum for data integrity verification."""
        return hashlib.sha256(data).hexdigest()


# Module-level singleton accessor
def get_raw_data_storage() -> RawDataStorage:
    """Return the singleton RawDataStorage instance."""
    return RawDataStorage()
