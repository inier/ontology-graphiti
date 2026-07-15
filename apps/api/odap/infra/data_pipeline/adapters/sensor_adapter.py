import uuid
import random
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Iterator, Optional

from ..data_pipeline import DataSourceConnector, DataRecord, DataFormat

logger = logging.getLogger(__name__)


class SensorAdapter(DataSourceConnector):
    """传感器适配器 - 根据配置选择真实或模拟适配器"""

    SENSOR_TYPES = ["temperature", "pressure", "humidity", "location", "radar", "sonar"]

    def __init__(self, sensor_ids: Optional[List[str]] = None, source_id: str = "sensor",
                 config: Optional[Dict[str, Any]] = None):
        self.source_id = source_id
        self._sensor_ids = sensor_ids or [f"sensor_{i}" for i in range(1, 6)]
        self._config = config or {}
        self._connected = False
        self._adapter: Optional[DataSourceConnector] = None

    def connect(self) -> bool:
        adapter_type = self._config.get("adapter_type", os.getenv("SENSOR_ADAPTER_TYPE", "simulated"))

        if adapter_type == "mqtt":
            self._adapter = MQTTSensorAdapter(
                sensor_ids=self._sensor_ids,
                source_id=self.source_id,
                broker=self._config.get("mqtt_broker", os.getenv("MQTT_BROKER", "")),
                port=self._config.get("mqtt_port", int(os.getenv("MQTT_PORT", "1883"))),
                topic_prefix=self._config.get("mqtt_topic_prefix", os.getenv("MQTT_TOPIC_PREFIX", "sensors/")),
                username=self._config.get("mqtt_username", os.getenv("MQTT_USERNAME", "")),
                password=self._config.get("mqtt_password", os.getenv("MQTT_PASSWORD", "")),
            )
        else:
            self._adapter = SimulatedSensorAdapter(
                sensor_ids=self._sensor_ids,
                source_id=self.source_id,
            )

        self._connected = self._adapter.connect()
        return self._connected

    def read(self, **kwargs) -> Iterator[DataRecord]:
        if not self._connected or not self._adapter:
            self.connect()
        if not self._adapter:
            return
        yield from self._adapter.read(**kwargs)

    def close(self):
        if self._adapter:
            self._adapter.close()
        self._connected = False
        logger.info("SensorAdapter disconnected")


class SimulatedSensorAdapter(DataSourceConnector):
    """模拟传感器适配器 - 生成随机数据用于测试和开发"""

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
        logger.info(f"SimulatedSensorAdapter connected: {len(self._sensor_ids)} sensors (simulated)")
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
                metadata={"sensor_id": sid, "sensor_type": state["type"], "simulated": True},
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
        logger.info("SimulatedSensorAdapter disconnected")


class MQTTSensorAdapter(DataSourceConnector):
    """MQTT 传感器适配器 - 通过 MQTT 协议连接真实传感器"""

    def __init__(self, sensor_ids: Optional[List[str]] = None, source_id: str = "sensor",
                 broker: str = "", port: int = 1883, topic_prefix: str = "sensors/",
                 username: str = "", password: str = ""):
        self.source_id = source_id
        self._sensor_ids = sensor_ids or []
        self._broker = broker
        self._port = port
        self._topic_prefix = topic_prefix
        self._username = username
        self._password = password
        self._connected = False
        self._client = None
        self._messages: List[Dict[str, Any]] = []

    def connect(self) -> bool:
        if not self._broker:
            logger.error("MQTTSensorAdapter: broker address not configured")
            return False

        try:
            import paho.mqtt.client as mqtt

            self._client = mqtt.Client(client_id=f"odap-sensor-{uuid.uuid4().hex[:8]}")

            if self._username:
                self._client.username_pw_set(self._username, self._password)

            self._client.on_message = self._on_message
            self._client.on_connect = self._on_connect

            self._client.connect(self._broker, self._port, keepalive=60)
            self._client.loop_start()

            import time
            time.sleep(1)

            if not self._connected:
                logger.error(f"MQTTSensorAdapter: failed to connect to {self._broker}:{self._port}")
                return False

            for sid in self._sensor_ids:
                topic = f"{self._topic_prefix}{sid}/data"
                self._client.subscribe(topic)
                logger.info(f"MQTTSensorAdapter: subscribed to {topic}")

            return True

        except ImportError:
            logger.error("MQTTSensorAdapter: paho-mqtt not installed, run: pip install paho-mqtt")
            return False
        except Exception as e:
            logger.error(f"MQTTSensorAdapter: connection failed: {e}")
            return False

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            logger.info(f"MQTTSensorAdapter: connected to {self._broker}:{self._port}")
        else:
            logger.error(f"MQTTSensorAdapter: connection failed with code {rc}")

    def _on_message(self, client, userdata, msg):
        import json
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            payload["_mqtt_topic"] = msg.topic
            payload["_received_at"] = datetime.now(timezone.utc).isoformat()
            self._messages.append(payload)
        except Exception as e:
            logger.warning(f"MQTTSensorAdapter: failed to parse message on {msg.topic}: {e}")

    def read(self, **kwargs) -> Iterator[DataRecord]:
        if not self._connected:
            return

        limit = kwargs.get("limit", 0)
        count = 0

        messages = list(self._messages)
        self._messages.clear()

        for msg in messages:
            if limit and count >= limit:
                break

            sensor_id = msg.get("sensor_id", msg.get("_mqtt_topic", "unknown"))
            yield DataRecord(
                id=str(uuid.uuid4())[:12],
                source_id=self.source_id,
                content=msg,
                format=DataFormat.JSON,
                metadata={"sensor_id": sensor_id, "simulated": False},
            )
            count += 1

    def close(self):
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
        self._connected = False
        self._messages.clear()
        logger.info("MQTTSensorAdapter disconnected")
