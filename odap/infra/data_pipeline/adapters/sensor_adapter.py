import uuid
import random
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Iterator, Optional

from ..data_pipeline import DataSourceConnector, DataRecord, DataFormat

logger = logging.getLogger(__name__)


class SensorAdapter(DataSourceConnector):
    SENSOR_TYPES = ["temperature", "pressure", "humidity", "location", "radar", "sonar"]

    def __init__(self, sensor_ids: Optional[List[str]] = None, source_id: str = "sensor"):
        self.source_id = source_id
        self._sensor_ids = sensor_ids or [f"sensor_{i}" for i in range(1, 6)]
        self._connected = False
        self._sensor_state: Dict[str, Dict] = {}

    def connect(self) -> bool:
        for sid in self._sensor_ids:
            self._sensor_state[sid] = {
                "type": random.choice(self.SENSOR_TYPES),
                "status": "active",
                "last_reading": None,
            }
        self._connected = True
        logger.info(f"SensorAdapter connected: {len(self._sensor_ids)} sensors")
        return True

    def read(self, **kwargs) -> Iterator[DataRecord]:
        if not self._connected:
            self.connect()

        limit = kwargs.get("limit", 0)
        count = 0

        for sid, state in self._sensor_state.items():
            if limit and count >= limit:
                break

            reading = self._generate_reading(sid, state)
            state["last_reading"] = reading

            yield DataRecord(
                id=str(uuid.uuid4())[:12],
                source_id=self.source_id,
                content=reading,
                format=DataFormat.JSON,
                metadata={"sensor_id": sid, "sensor_type": state["type"]},
            )
            count += 1

    def _generate_reading(self, sensor_id: str, state: Dict) -> Dict[str, Any]:
        sensor_type = state["type"]
        base = {
            "sensor_id": sensor_id,
            "sensor_type": sensor_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "active",
        }

        if sensor_type == "temperature":
            base["value"] = round(random.uniform(-20, 50), 1)
            base["unit"] = "celsius"
        elif sensor_type == "pressure":
            base["value"] = round(random.uniform(900, 1100), 1)
            base["unit"] = "hPa"
        elif sensor_type == "humidity":
            base["value"] = round(random.uniform(10, 100), 1)
            base["unit"] = "percent"
        elif sensor_type == "location":
            base["latitude"] = round(random.uniform(20, 50), 6)
            base["longitude"] = round(random.uniform(40, 80), 6)
            base["altitude"] = round(random.uniform(0, 2000), 1)
        elif sensor_type == "radar":
            base["range_km"] = round(random.uniform(10, 200), 1)
            base["targets_detected"] = random.randint(0, 10)
        elif sensor_type == "sonar":
            base["depth_m"] = round(random.uniform(0, 500), 1)
            base["contacts"] = random.randint(0, 5)

        return base

    def close(self):
        self._sensor_state.clear()
        self._connected = False
        logger.info("SensorAdapter disconnected")
