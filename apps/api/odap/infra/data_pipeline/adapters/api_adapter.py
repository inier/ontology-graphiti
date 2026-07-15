import uuid
import logging
from typing import Dict, Any, Iterator, Optional
from urllib.parse import urlparse

from ..data_pipeline import DataSourceConnector, DataRecord, DataFormat

logger = logging.getLogger(__name__)


class APIAdapter(DataSourceConnector):
    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None,
                 source_id: str = "api"):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.source_id = source_id
        self._connected = False
        self._session = None

    def connect(self) -> bool:
        try:
            parsed = urlparse(self.base_url)
            if not parsed.scheme or not parsed.netloc:
                logger.error(f"APIAdapter: invalid URL: {self.base_url}")
                return False
            self._connected = True
            logger.info(f"APIAdapter connected to: {self.base_url}")
            return True
        except Exception as e:
            logger.error(f"APIAdapter connect failed: {e}")
            return False

    def read(self, **kwargs) -> Iterator[DataRecord]:
        if not self._connected:
            self.connect()
        if not self._connected:
            return

        endpoint = kwargs.get("endpoint", "")
        params = kwargs.get("params", {})
        limit = kwargs.get("limit", 0)
        count = 0

        try:
            import requests
        except ImportError:
            logger.error("APIAdapter: requests library not installed, cannot read from API endpoint '%s'", endpoint)
            return

        try:
            url = f"{self.base_url}/{endpoint}".rstrip("/")
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if limit and count >= limit:
                        break
                    yield DataRecord(
                        id=str(uuid.uuid4())[:12],
                        source_id=self.source_id,
                        content=item,
                        format=DataFormat.JSON,
                        metadata={"endpoint": endpoint, "status_code": response.status_code},
                    )
                    count += 1
            else:
                logger.error("APIAdapter: HTTP %d from %s, cannot read data", response.status_code, url)
        except Exception as e:
            logger.error("APIAdapter read failed for endpoint '%s': %s", endpoint, e)

    def close(self):
        self._session = None
        self._connected = False
        logger.info("APIAdapter disconnected")
