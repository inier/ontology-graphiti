# MCP协议集成模块设计文档

> **优先级**: P1 | **相关 ADR**: ADR-026

## 1. 模块概述

**版本**: 1.0.0 | **日期**: 2026-04-12 | **作者**: 平台架构组

### 1.1 核心定位

MCP（Model Context Protocol）协议集成模块是Graphiti系统与外部领域仿真系统（领域仿真器、雷达模拟器、气象数据源）的标准接口层。基于MCP v1.0标准，为OpenHarness Agent提供统一的第三方服务接入能力，支持**协议标准化、扩展性、安全性**的领域数据集成。

### 1.2 核心价值

| 维度 | 价值 | 说明 |
|------|------|------|
| **标准化集成** | 统一协议 | 所有外部系统都通过MCP协议接入，避免接口碎片化 |
| **可扩展性** | 热插拔 | 支持运行时动态添加/移除MCP Server，无需系统重启 |
| **安全性** | 沙箱隔离 | 外部MCP Server在独立进程中运行，实现安全边界 |
| **性能** | 异步流式 | 支持大流量传感器数据的流式传输 |
| **调试友好** | 协议探查 | 内置MCP Inspector工具，可视化调试协议消息 |

### 1.3 架构位置

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OpenHarness Agent 基础设施层                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐           │
│  │ Commander Agent │  │Intelligence Agent│  │Operations Agent │           │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘           │
│           │                    │                    │                    │
│           └────────────────────┼────────────────────┘                    │
│                                ▼                                            │
│                    ┌─────────────────────┐                                  │
│                    │  Swarm Coordinator  │                                  │
│                    │    (OpenHarness)    │                                  │
│                    └──────────┬──────────┘                                  │
│                               │                                              │
│         ┌─────────────────────┼─────────────────────┐                       │
│         ▼                     ▼                     ▼                       │
│  ┌─────────────┐      ┌─────────────┐       ┌─────────────┐                │
│  │Tool Registry│      │Hook System │       │Permission   │                │
│  │  (43+工具)  │      │(Pre/Post)  │       │  Checker    │                │
│  └─────────────┘      └─────────────┘       └─────────────┘                │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Python Skills  │    │   Graphiti      │    │     OPA         │
│  (领域工具层)    │    │ (双时态图谱层)   │    │  (策略治理层)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │     MCP Protocol        │
                    │ (本模块：外部系统集成)    │
                    │ • 领域仿真器             │
                    │ • 雷达模拟器             │
                    │ • 气象数据源             │
                    │ • 卫星影像               │
                    │ • 友军位置更新           │
                    └─────────────────────────┘
                                 │
           ┌─────────────────────┼─────────────────────┐
           ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   领域仿真器      │  │   雷达模拟器     │  │   气象数据源     │
│  (Unreal Engine)  │  │  (模拟信号生成)  │  │  (气象API聚合)  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## 2. 架构设计

### 2.1 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          MCP协议集成模块 (MCP Protocol Integration)                   │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │                    MCP Server 管理器 (MCPServerManager)                       │    │
│  │  • 注册/注销 Server                                                          │    │
│  │  • 生命周期管理                                                              │    │
│  │  • 健康检查 & 熔断                                                           │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                                │
│         ┌────────────────────────────┼────────────────────────────┐                  │
│         ▼                            ▼                            ▼                  │
│  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐              │
│  │  协议适配器  │          │  协议路由    │          │  协议转换    │              │
│  │ (Protocol   │          │  (Message    │          │  (Data       │              │
│  │  Adapter)   │          │   Router)    │          │   Transformer)│              │
│  │  • MCP v1.0 │          │  • 消息分发  │          │  • 格式转换  │              │
│  │  • HTTP     │          │  • 负载均衡  │          │  • 数据映射  │              │
│  │  • WebSocket│          │  • 故障转移  │          │  • 协议升级  │              │
│  └──────────────┘          └──────────────┘          └──────────────┘              │
│                                      │                                                │
│         ┌────────────────────────────┼────────────────────────────┐                  │
│         ▼                            ▼                            ▼                  │
│  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐              │
│  │  数据缓存层  │          │  安全层      │          │  监控层      │              │
│  │ (Data Cache) │          │  (Security)  │          │  (Monitoring)│              │
│  │  • Redis     │          │  • 认证鉴权  │          │  • 指标收集  │              │
│  │  • 本地缓存  │          │  • 权限控制  │          │  • 日志记录  │              │
│  │  • 数据预取  │          │  • 数据加密  │          │  • 告警规则  │              │
│  └──────────────┘          └──────────────┘          └──────────────┘              │
│                                      │                                                │
│                                      ▼                                                │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │                        外部系统接口 (External System Interfaces)                │    │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐│    │
│  │  │ 领域仿真器  │ │雷达模拟器  │ │气象数据源  │ │卫星影像    │ │友军位置    ││    │
│  │  │ (Battle-   │ │(Radar      │ │(Weather   │ │(Satellite │ │(Friendly  ││    │
│  │  │  field     │ │ Simulator) │ │ Data)     │ │ Imagery) │ │ Position) ││    │
│  │  │  Simulator)│ │            │ │           │ │          │ │ Update)   ││    │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └────────────┘│    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                       │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### 2.2.1 MCP Server 管理器 (MCPServerManager)
- **职责**: 管理所有注册的MCP Server，提供统一的注册、发现、健康检查接口
- **功能**:
  - 动态加载/卸载MCP Server配置
  - 实现Server健康检查和熔断机制
  - 管理Server生命周期（启动/停止/重启）
  - 提供Server发现和服务注册功能

#### 2.2.2 协议适配器 (ProtocolAdapter)
- **职责**: 实现MCP v1.0协议栈，支持多种传输协议
- **功能**:
  - HTTP/HTTPS协议支持
  - WebSocket实时双向通信
  - STDIO进程间通信
  - 协议版本协商和升级

#### 2.2.3 协议路由 (MessageRouter)
- **职责**: 消息分发、负载均衡和故障转移
- **功能**:
  - 基于内容的路由（按消息类型、优先级、目标系统）
  - 负载均衡策略（轮询、权重、最少连接）
  - 故障检测和自动切换
  - 消息重试和死信队列

#### 2.2.4 协议转换 (DataTransformer)
- **职责**: 数据格式转换和协议适配
- **功能**:
  - 外部数据格式 → MCP标准格式
  - MCP标准格式 → Graphiti本体模型
  - 协议版本兼容性处理
  - 数据验证和清洗

### 2.3 数据流设计

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   OpenHarness    │    │  MCP协议集成层    │    │   外部数据源     │
│    Agent/Tool    │    │                  │    │                  │
└─────────┬────────┘    └─────────┬────────┘    └─────────┬────────┘
          │                       │                       │
          │  1. 请求调用           │                       │
          │──────────────────────►│                       │
          │                       │                       │
          │                       │  2. 协议转换 + 路由    │
          │                       │──────────────────────►│
          │                       │                       │
          │                       │                       │  3. 调用外部API
          │                       │                       │─────────────────►
          │                       │                       │
          │                       │                       │  4. 获取响应数据
          │                       │◄──────────────────────│
          │                       │                       │
          │                       │  5. 数据清洗 + 转换    │
          │                       │                       │
          │  6. 返回标准化结果     │                       │
          │◄──────────────────────│                       │
          │                       │                       │
```

---

## 3. 技术实现

### 3.1 核心接口设计

#### 3.1.1 MCP Server 接口
```python
# core/mcp/server_manager.py
from typing import Dict, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import asyncio

class MCPServerStatus(Enum):
    """MCP Server状态枚举"""
    REGISTERED = "registered"      # 已注册但未启动
    STARTING = "starting"          # 启动中
    RUNNING = "running"            # 运行正常
    DEGRADED = "degraded"          # 降级运行
    STOPPED = "stopped"            # 已停止
    ERROR = "error"                # 错误状态

@dataclass
class MCPServerConfig:
    """MCP Server配置"""
    name: str                      # 服务器名称
    server_type: str               # 服务器类型 (domain_simulator, radar_simulator, weather_source)
    transport: str                 # 传输协议 (http, websocket, stdio)
    endpoint: str                  # 端点地址
    capabilities: List[str]        # 支持的能力列表
    health_check_interval: int = 30  # 健康检查间隔(秒)
    timeout: int = 10              # 请求超时时间(秒)
    retry_count: int = 3           # 重试次数
    auth_token: Optional[str] = None  # 认证令牌

@dataclass
class MCPServerInfo:
    """MCP Server信息"""
    config: MCPServerConfig
    status: MCPServerStatus
    last_health_check: datetime
    latency_ms: float
    error_count: int
    success_rate: float

class MCPServerManager:
    """MCP Server管理器"""
    
    def __init__(self, cache_enabled: bool = True):
        self.servers: Dict[str, MCPServerInfo] = {}
        self.cache_enabled = cache_enabled
        
    async def register_server(self, config: MCPServerConfig) -> str:
        """注册MCP Server"""
        # 实现注册逻辑
        pass
        
    async def unregister_server(self, server_name: str) -> bool:
        """注销MCP Server"""
        # 实现注销逻辑
        pass
        
    async def get_server(self, server_type: str, 
                        capabilities: Optional[List[str]] = None) -> Optional[MCPServerInfo]:
        """获取指定类型的可用Server"""
        # 实现Server发现和选择逻辑
        pass
        
    async def health_check_all(self):
        """对所有Server进行健康检查"""
        # 实现健康检查逻辑
        pass
```

#### 3.1.2 MCP 协议适配器
```python
# core/mcp/protocol_adapter.py
from typing import Any, Dict, Union
import aiohttp
import json
from enum import Enum

class MCPMessageType(Enum):
    """MCP消息类型"""
    LIST_TOOLS = "tools/list"
    CALL_TOOL = "tools/call"
    LIST_RESOURCES = "resources/list"
    READ_RESOURCE = "resources/read"
    NOTIFICATIONS = "notifications"

class MCPProtocolAdapter:
    """MCP协议适配器"""
    
    def __init__(self, transport: str = "http"):
        self.transport = transport
        self.session = None
        
    async def connect(self, endpoint: str):
        """连接到MCP Server"""
        if self.transport == "http":
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        elif self.transport == "websocket":
            # WebSocket连接逻辑
            pass
            
    async def send_message(self, 
                          message_type: MCPMessageType,
                          params: Dict[str, Any]) -> Dict[str, Any]:
        """发送MCP消息"""
        message = {
            "jsonrpc": "2.0",
            "method": message_type.value,
            "params": params,
            "id": self._generate_message_id()
        }
        
        if self.transport == "http":
            async with self.session.post(
                self.endpoint, 
                json=message,
                headers={"Content-Type": "application/json"}
            ) as response:
                return await response.json()
                
    async def stream_messages(self, callback: Callable):
        """流式接收消息（WebSocket模式）"""
        pass
        
    def _generate_message_id(self) -> str:
        """生成消息ID"""
        import uuid
        return str(uuid.uuid4())
```

### 3.2 领域仿真器集成

#### 3.2.1 领域仿真器MCP Server
```python
# external/domain_simulator/mcp_server.py
from typing import List, Dict, Any
from mcp.server import Server, NotificationOptions
from mcp.server.models import TextContent
import mcp.types as types
import asyncio

class DomainSimulatorMCPServer:
    """领域仿真器MCP Server实现"""
    
    def __init__(self):
        self.server = Server("domain-simulator")
        
        # 注册MCP Tools
        self.server.tool.list_tools = self.list_tools
        self.server.tool.call_tool = self.call_tool
        
        # 注册MCP Resources
        self.server.resources.list_resources = self.list_resources
        self.server.resources.read_resource = self.read_resource
        
    async def list_tools(self) -> List[types.Tool]:
        """列出可用的领域仿真工具"""
        return [
            types.Tool(
                name="domain.get_scenario",
                description="获取领域场景信息",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scenario_id": {
                            "type": "string",
                            "description": "场景ID"
                        }
                    },
                    "required": ["scenario_id"]
                }
            ),
            types.Tool(
                name="domain.simulate_attack",
                description="模拟攻击行动",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "attacker_id": {"type": "string"},
                        "target_id": {"type": "string"},
                        "weapon_type": {"type": "string"},
                        "strategy": {"type": "string", "enum": ["direct", "flank", "ambush"]}
                    },
                    "required": ["attacker_id", "target_id", "weapon_type"]
                }
            ),
            types.Tool(
                name="domain.update_unit_position",
                description="更新单位位置",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "unit_id": {"type": "string"},
                        "position": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "number"},
                                "y": {"type": "number"},
                                "z": {"type": "number"}
                            }
                        },
                        "heading": {"type": "number"}
                    },
                    "required": ["unit_id", "position"]
                }
            )
        ]
        
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
        """调用领域仿真工具"""
        if name == "domain.get_scenario":
            return await self._get_scenario(arguments["scenario_id"])
        elif name == "domain.simulate_attack":
            return await self._simulate_attack(
                arguments["attacker_id"],
                arguments["target_id"],
                arguments["weapon_type"],
                arguments.get("strategy", "direct")
            )
        # ... 其他工具实现
            
    async def list_resources(self) -> List[types.Resource]:
        """列出可用的资源"""
        return [
            types.Resource(
                uri="domain://scenarios",
                name="领域场景列表",
                description="所有可用的领域仿真场景",
                mimeType="application/json"
            ),
            types.Resource(
                uri="domain://units/status",
                name="单位状态",
                description="所有作战单位的实时状态",
                mimeType="application/json"
            ),
            types.Resource(
                uri="domain://terrain/map",
                name="地形地图",
                description="领域地形高程图",
                mimeType="image/png"
            )
        ]
        
    async def read_resource(self, uri: str) -> types.ResourceContents:
        """读取资源内容"""
        if uri == "domain://scenarios":
            scenarios = await self._get_all_scenarios()
            return types.ResourceContents(
                contents=[
                    types.TextContent(
                        type="text",
                        text=json.dumps(scenarios, indent=2)
                    )
                ]
            )
        # ... 其他资源读取实现
```

### 3.3 雷达模拟器集成

#### 3.3.1 雷达数据格式
```python
# core/mcp/radar_simulator.py
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class RadarDetectionType(Enum):
    """雷达探测类型"""
    PRIMARY = "primary"      # 主雷达探测
    SECONDARY = "secondary"  # 二次雷达（IFF）
    PASSIVE = "passive"      # 被动雷达
    ESM = "esm"              # 电子支援措施

@dataclass
class RadarDetection:
    """雷达探测数据"""
    detection_id: str
    timestamp: datetime
    position: Dict[str, float]  # {x, y, z}
    velocity: Dict[str, float]  # {vx, vy, vz}
    rcs: float                  # 雷达截面积 (m²)
    confidence: float           # 置信度 (0-1)
    detection_type: RadarDetectionType
    source_radar: str
    target_id: Optional[str] = None
    
@dataclass
class RadarCoverage:
    """雷达覆盖范围"""
    radar_id: str
    position: Dict[str, float]
    max_range: float            # 最大探测距离 (km)
    min_range: float            # 最小探测距离 (km)
    azimuth_range: List[float]  # 方位角范围 [min, max]
    elevation_range: List[float] # 俯仰角范围 [min, max]
    update_rate: float          # 更新频率 (Hz)

class RadarSimulatorAdapter:
    """雷达模拟器适配器"""
    
    def __init__(self, mcp_endpoint: str):
        self.mcp_adapter = MCPProtocolAdapter("websocket")
        self.mcp_endpoint = mcp_endpoint
        
    async def connect(self):
        """连接到雷达模拟器"""
        await self.mcp_adapter.connect(self.mcp_endpoint)
        
    async def get_detections(self, 
                            radar_id: str,
                            time_window: Optional[Dict[str, datetime]] = None) -> List[RadarDetection]:
        """获取雷达探测数据"""
        params = {"radar_id": radar_id}
        if time_window:
            params["start_time"] = time_window["start"].isoformat()
            params["end_time"] = time_window["end"].isoformat()
            
        response = await self.mcp_adapter.send_message(
            MCPMessageType.CALL_TOOL,
            {
                "name": "radar.get_detections",
                "arguments": params
            }
        )
        
        # 解析响应并转换为RadarDetection对象
        detections = []
        for detection_data in response.get("result", []):
            detection = RadarDetection(
                detection_id=detection_data["id"],
                timestamp=datetime.fromisoformat(detection_data["timestamp"]),
                position=detection_data["position"],
                velocity=detection_data.get("velocity", {}),
                rcs=detection_data.get("rcs", 0.0),
                confidence=detection_data.get("confidence", 0.5),
                detection_type=RadarDetectionType(detection_data["type"]),
                source_radar=detection_data["radar_id"],
                target_id=detection_data.get("target_id")
            )
            detections.append(detection)
            
        return detections
        
    async def simulate_radar_jamming(self,
                                    jammer_position: Dict[str, float],
                                    jammer_power: float,
                                    frequency_range: List[float]) -> Dict[str, Any]:
        """模拟雷达干扰效果"""
        response = await self.mcp_adapter.send_message(
            MCPMessageType.CALL_TOOL,
            {
                "name": "radar.simulate_jamming",
                "arguments": {
                    "jammer_position": jammer_position,
                    "jammer_power": jammer_power,
                    "frequency_range": frequency_range
                }
            }
        )
        
        return response.get("result", {})
```

### 3.4 气象数据源集成

#### 3.4.1 气象数据模型
```python
# core/mcp/weather_source.py
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class WeatherCondition(Enum):
    """天气状况"""
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    SNOW = "snow"
    FOG = "fog"
    STORM = "storm"

@dataclass
class WeatherData:
    """气象数据"""
    timestamp: datetime
    location: Dict[str, float]  # {latitude, longitude, altitude}
    temperature: float          # 温度 (°C)
    humidity: float            # 湿度 (%)
    pressure: float            # 气压 (hPa)
    wind_speed: float          # 风速 (m/s)
    wind_direction: float      # 风向 (°)
    visibility: float          # 能见度 (km)
    cloud_cover: float         # 云量 (0-1)
    condition: WeatherCondition
    precipitation: float       # 降水量 (mm/h)

@dataclass
class WeatherForecast:
    """天气预报"""
    location: Dict[str, float]
    forecast_period: Dict[str, datetime]  # {start, end}
    hourly_data: List[WeatherData]
    confidence: float

class WeatherSourceAdapter:
    """气象数据源适配器"""
    
    def __init__(self, mcp_endpoint: str, api_key: Optional[str] = None):
        self.mcp_adapter = MCPProtocolAdapter("http")
        self.endpoint = mcp_endpoint
        self.api_key = api_key
        
    async def get_current_weather(self, 
                                 location: Dict[str, float]) -> WeatherData:
        """获取当前天气数据"""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        response = await self.mcp_adapter.send_message(
            MCPMessageType.CALL_TOOL,
            {
                "name": "weather.get_current",
                "arguments": {"location": location},
                "headers": headers
            }
        )
        
        weather_data = response.get("result", {})
        return WeatherData(
            timestamp=datetime.fromisoformat(weather_data["timestamp"]),
            location=weather_data["location"],
            temperature=weather_data["temperature"],
            humidity=weather_data["humidity"],
            pressure=weather_data["pressure"],
            wind_speed=weather_data["wind_speed"],
            wind_direction=weather_data["wind_direction"],
            visibility=weather_data["visibility"],
            cloud_cover=weather_data["cloud_cover"],
            condition=WeatherCondition(weather_data["condition"]),
            precipitation=weather_data.get("precipitation", 0.0)
        )
        
    async def get_forecast(self,
                          location: Dict[str, float],
                          hours: int = 24) -> WeatherForecast:
        """获取天气预报"""
        response = await self.mcp_adapter.send_message(
            MCPMessageType.CALL_TOOL,
            {
                "name": "weather.get_forecast",
                "arguments": {
                    "location": location,
                    "hours": hours
                }
            }
        )
        
        forecast_data = response.get("result", {})
        
        hourly_data = []
        for hour_data in forecast_data.get("hourly", []):
            weather = WeatherData(
                timestamp=datetime.fromisoformat(hour_data["timestamp"]),
                location=location,
                temperature=hour_data["temperature"],
                humidity=hour_data["humidity"],
                pressure=hour_data["pressure"],
                wind_speed=hour_data["wind_speed"],
                wind_direction=hour_data["wind_direction"],
                visibility=hour_data["visibility"],
                cloud_cover=hour_data["cloud_cover"],
                condition=WeatherCondition(hour_data["condition"]),
                precipitation=hour_data.get("precipitation", 0.0)
            )
            hourly_data.append(weather)
            
        return WeatherForecast(
            location=location,
            forecast_period={
                "start": datetime.fromisoformat(forecast_data["start_time"]),
                "end": datetime.fromisoformat(forecast_data["end_time"])
            },
            hourly_data=hourly_data,
            confidence=forecast_data.get("confidence", 0.8)
        )
```

---

## 4. 安全设计

### 4.1 认证与授权

#### 4.1.1 认证机制
```python
# core/mcp/security/auth_manager.py
from typing import Optional, Dict, Any
import jwt
from datetime import datetime, timedelta
from enum import Enum

class AuthMethod(Enum):
    """认证方法"""
    TOKEN = "token"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    MTLS = "mtls"

class MCPAuthManager:
    """MCP认证管理器"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.token_cache: Dict[str, Dict[str, Any]] = {}
        
    def generate_token(self, 
                      user_id: str,
                      roles: List[str],
                      expires_in: int = 3600) -> str:
        """生成JWT令牌"""
        payload = {
            "user_id": user_id,
            "roles": roles,
            "exp": datetime.utcnow() + timedelta(seconds=expires_in),
            "iat": datetime.utcnow()
        }
        
        return jwt.encode(payload, self.secret_key, algorithm="HS256")
        
    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证JWT令牌"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
            
    async def authenticate_request(self, 
                                  request: Dict[str, Any]) -> bool:
        """认证请求"""
        auth_header = request.get("headers", {}).get("Authorization")
        if not auth_header:
            return False
            
        # Bearer令牌认证
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = self.validate_token(token)
            if not payload:
                return False
                
            # 检查角色权限
            request["user"] = payload
            return self._check_permissions(payload["roles"], request)
            
        return False
        
    def _check_permissions(self, roles: List[str], request: Dict[str, Any]) -> bool:
        """检查角色权限"""
        # 实现基于角色的权限检查
        required_role = request.get("required_role", "user")
        return required_role in roles
```

### 4.2 数据加密

#### 4.2.1 传输层加密
```python
# core/mcp/security/encryption.py
from typing import Union
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class DataEncryptor:
    """数据加密器"""
    
    def __init__(self, password: str, salt: bytes):
        self.password = password.encode()
        self.salt = salt
        
    def _derive_key(self) -> bytes:
        """派生加密密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.password))
        return key
        
    def encrypt(self, data: Union[str, bytes]) -> str:
        """加密数据"""
        if isinstance(data, str):
            data = data.encode()
            
        key = self._derive_key()
        f = Fernet(key)
        encrypted = f.encrypt(data)
        return base64.urlsafe_b64encode(encrypted).decode()
        
    def decrypt(self, encrypted_data: str) -> str:
        """解密数据"""
        key = self._derive_key()
        f = Fernet(key)
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
        decrypted = f.decrypt(encrypted_bytes)
        return decrypted.decode()
```

### 4.3 访问控制

#### 4.3.1 基于属性的访问控制 (ABAC)
```python
# core/mcp/security/abac.py
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum

class AccessDecision(Enum):
    """访问决策"""
    ALLOW = "allow"
    DENY = "deny"
    INDETERMINATE = "indeterminate"

@dataclass
class AccessRequest:
    """访问请求"""
    subject: Dict[str, Any]    # 主体属性（用户、角色等）
    resource: Dict[str, Any]   # 资源属性
    action: str               # 操作类型
    environment: Dict[str, Any] # 环境属性
    
@dataclass
class PolicyRule:
    """策略规则"""
    rule_id: str
    effect: AccessDecision
    conditions: List[Dict[str, Any]]  # 条件表达式
    priority: int = 0

class ABACPolicyEngine:
    """ABAC策略引擎"""
    
    def __init__(self):
        self.rules: List[PolicyRule] = []
        
    def add_rule(self, rule: PolicyRule):
        """添加策略规则"""
        self.rules.append(rule)
        self.rules.sort(key=lambda x: x.priority, reverse=True)
        
    def evaluate(self, request: AccessRequest) -> AccessDecision:
        """评估访问请求"""
        for rule in self.rules:
            if self._match_conditions(rule.conditions, request):
                return rule.effect
                
        return AccessDecision.DENY  # 默认拒绝
        
    def _match_conditions(self, 
                         conditions: List[Dict[str, Any]], 
                         request: AccessRequest) -> bool:
        """匹配条件"""
        for condition in conditions:
            if not self._evaluate_condition(condition, request):
                return False
        return True
        
    def _evaluate_condition(self, 
                           condition: Dict[str, Any], 
                           request: AccessRequest) -> bool:
        """评估单个条件"""
        # 实现条件评估逻辑
        attribute = condition["attribute"]
        operator = condition["operator"]
        value = condition["value"]
        
        # 从请求中获取属性值
        request_value = self._get_attribute_value(attribute, request)
        
        # 应用操作符
        if operator == "equals":
            return request_value == value
        elif operator == "greater_than":
            return request_value > value
        elif operator == "less_than":
            return request_value < value
        elif operator == "in":
            return request_value in value
        # ... 其他操作符
            
        return False
        
    def _get_attribute_value(self, 
                           attribute_path: str, 
                           request: AccessRequest) -> Any:
        """从请求中获取属性值"""
        # 解析属性路径（如 subject.role, resource.type）
        parts = attribute_path.split(".")
        obj_name = parts[0]
        attr_name = parts[1]
        
        if obj_name == "subject":
            return request.subject.get(attr_name)
        elif obj_name == "resource":
            return request.resource.get(attr_name)
        elif obj_name == "environment":
            return request.environment.get(attr_name)
            
        return None
```

---

## 5. 监控与运维

### 5.1 监控指标

#### 5.1.1 性能指标
```python
# core/mcp/monitoring/metrics.py
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"

@dataclass
class Metric:
    """监控指标"""
    name: str
    type: MetricType
    value: float
    labels: Dict[str, str]
    timestamp: datetime

class MCPMetricsCollector:
    """MCP指标收集器"""
    
    def __init__(self):
        self.metrics: Dict[str, List[Metric]] = {}
        
    def record_latency(self, 
                      server_type: str,
                      operation: str,
                      latency_ms: float):
        """记录延迟指标"""
        metric = Metric(
            name="mcp_request_latency",
            type=MetricType.HISTOGRAM,
            value=latency_ms,
            labels={
                "server_type": server_type,
                "operation": operation
            },
            timestamp=datetime.utcnow()
        )
        self._store_metric(metric)
        
    def record_success_rate(self,
                           server_type: str,
                           success_count: int,
                           total_count: int):
        """记录成功率指标"""
        success_rate = success_count / total_count if total_count > 0 else 0
        
        metric = Metric(
            name="mcp_success_rate",
            type=MetricType.GAUGE,
            value=success_rate,
            labels={"server_type": server_type},
            timestamp=datetime.utcnow()
        )
        self._store_metric(metric)
        
    def record_connection_status(self,
                                server_name: str,
                                status: str):
        """记录连接状态"""
        status_value = 1 if status == "connected" else 0
        
        metric = Metric(
            name="mcp_connection_status",
            type=MetricType.GAUGE,
            value=status_value,
            labels={"server_name": server_name},
            timestamp=datetime.utcnow()
        )
        self._store_metric(metric)
        
    def _store_metric(self, metric: Metric):
        """存储指标"""
        if metric.name not in self.metrics:
            self.metrics[metric.name] = []
        self.metrics[metric.name].append(metric)
        
        # 限制历史记录数量
        if len(self.metrics[metric.name]) > 1000:
            self.metrics[metric.name] = self.metrics[metric.name][-500:]
```

### 5.2 告警规则

#### 5.2.1 告警配置
```yaml
# config/mcp_alerts.yaml
alerts:
  - name: "mcp_high_latency"
    description: "MCP请求延迟过高"
    metric: "mcp_request_latency"
    condition: "value > 1000"  # 延迟超过1秒
    duration: "5m"            # 持续5分钟
    severity: "warning"
    labels:
      component: "mcp_protocol"
      
  - name: "mcp_low_success_rate"
    description: "MCP请求成功率过低"
    metric: "mcp_success_rate"
    condition: "value < 0.95"  # 成功率低于95%
    duration: "10m"
    severity: "critical"
    labels:
      component: "mcp_protocol"
      
  - name: "mcp_server_down"
    description: "MCP Server服务不可用"
    metric: "mcp_connection_status"
    condition: "value == 0"    # 连接状态为0
    duration: "2m"
    severity: "critical"
    labels:
      component: "mcp_server"
      
  - name: "mcp_auth_failure"
    description: "MCP认证失败率过高"
    metric: "mcp_auth_failures"
    condition: "rate_5m > 10"  # 5分钟内失败超过10次
    duration: "5m"
    severity: "high"
    labels:
      component: "mcp_security"
```

### 5.3 日志记录

#### 5.3.1 结构化日志
```python
# core/mcp/logging/mcp_logger.py
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

class LogLevel(Enum):
    """日志级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class MCPStructuredLogger:
    """MCP结构化日志记录器"""
    
    def __init__(self, name: str = "mcp"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # 添加JSON格式化处理器
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)
        
    def log_request(self,
                   server_type: str,
                   operation: str,
                   status: str,
                   latency_ms: float,
                   metadata: Optional[Dict[str, Any]] = None):
        """记录请求日志"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": LogLevel.INFO.value,
            "component": "mcp_request",
            "server_type": server_type,
            "operation": operation,
            "status": status,
            "latency_ms": latency_ms,
            "metadata": metadata or {}
        }
        
        self.logger.info(json.dumps(log_data))
        
    def log_error(self,
                 error_type: str,
                 error_message: str,
                 server_type: Optional[str] = None,
                 operation: Optional[str] = None):
        """记录错误日志"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": LogLevel.ERROR.value,
            "component": "mcp_error",
            "error_type": error_type,
            "error_message": error_message,
            "server_type": server_type,
            "operation": operation
        }
        
        self.logger.error(json.dumps(log_data))
        
    def log_security_event(self,
                          event_type: str,
                          user_id: Optional[str] = None,
                          ip_address: Optional[str] = None,
                          details: Optional[Dict[str, Any]] = None):
        """记录安全事件日志"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": LogLevel.WARNING.value,
            "component": "mcp_security",
            "event_type": event_type,
            "user_id": user_id,
            "ip_address": ip_address,
            "details": details or {}
        }
        
        self.logger.warning(json.dumps(log_data))

class JSONFormatter(logging.Formatter):
    """JSON格式日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        log_data = json.loads(record.getMessage())
        return json.dumps(log_data)
```

---

## 6. 部署与配置

### 6.1 Docker部署配置

#### 6.1.1 Docker Compose配置
```yaml
# docker-compose.mcp.yaml
version: '3.8'

services:
  # MCP协议集成服务
  mcp-integration:
    build:
      context: .
      dockerfile: docker/mcp/Dockerfile
    container_name: mcp-integration
    ports:
      - "8080:8080"    # HTTP API端口
      - "8081:8081"    # WebSocket端口
    environment:
      - MCP_LOG_LEVEL=INFO
      - MCP_CACHE_ENABLED=true
      - MCP_REDIS_HOST=redis
      - MCP_SECRET_KEY=${MCP_SECRET_KEY}
    volumes:
      - ./config/mcp:/app/config
      - ./logs/mcp:/app/logs
    depends_on:
      - redis
      - opa
    networks:
      - domain-network
      
  # Redis缓存
  redis:
    image: redis:7-alpine
    container_name: mcp-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes
    networks:
      - domain-network
      
  # 领域仿真器MCP Server
  domain-simulator:
    build:
      context: ./external/domain_simulator
      dockerfile: Dockerfile
    container_name: domain-simulator-mcp
    environment:
      - SIMULATOR_DATA_PATH=/data/scenarios
      - MCP_SERVER_PORT=9000
    volumes:
      - ./data/scenarios:/data/scenarios
    ports:
      - "9000:9000"
    networks:
      - domain-network
      
  # 雷达模拟器MCP Server
  radar-simulator:
    build:
      context: ./external/radar_simulator
      dockerfile: Dockerfile
    container_name: radar-simulator-mcp
    environment:
      - RADAR_CONFIG_PATH=/config/radars.yaml
      - MCP_SERVER_PORT=9001
    volumes:
      - ./config/radars.yaml:/config/radars.yaml
    ports:
      - "9001:9001"
    networks:
      - domain-network
      
  # 气象数据源MCP Server
  weather-source:
    image: weather-mcp-server:latest
    container_name: weather-mcp-server
    environment:
      - WEATHER_API_KEY=${WEATHER_API_KEY}
      - MCP_SERVER_PORT=9002
    ports:
      - "9002:9002"
    networks:
      - domain-network

volumes:
  redis-data:

networks:
  domain-network:
    driver: bridge
```

### 6.2 配置管理

#### 6.2.1 MCP配置文件
```yaml
# config/mcp_config.yaml
mcp:
  # 通用配置
  log_level: "INFO"
  cache_enabled: true
  cache_ttl: 300  # 缓存TTL（秒）
  
  # 传输配置
  http:
    timeout: 30
    max_retries: 3
    retry_delay: 1
    
  websocket:
    ping_interval: 30
    reconnect_delay: 5
    max_reconnect_attempts: 10
    
  # 服务器配置
  servers:
    domain_simulator:
      name: "domain-simulator"
      type: "domain_simulator"
      transport: "websocket"
      endpoint: "ws://domain-simulator:9000"
      capabilities:
        - "scenario_management"
        - "unit_simulation"
        - "combat_outcome"
      health_check_interval: 30
      timeout: 15
      
    radar_simulator:
      name: "radar-simulator"
      type: "radar_simulator"
      transport: "websocket"
      endpoint: "ws://radar-simulator:9001"
      capabilities:
        - "detection_generation"
        - "jamming_simulation"
        - "coverage_analysis"
      health_check_interval: 20
      timeout: 10
      
    weather_source:
      name: "weather-source"
      type: "weather_source"
      transport: "http"
      endpoint: "http://weather-source:9002"
      capabilities:
        - "current_weather"
        - "weather_forecast"
        - "historical_data"
      health_check_interval: 60
      timeout: 5
      
  # 安全配置
  security:
    auth_enabled: true
    auth_method: "token"
    token_expiry: 3600
    encryption_enabled: true
    allowed_origins:
      - "http://localhost:3000"
      - "https://domain.example.com"
      
  # 监控配置
  monitoring:
    metrics_enabled: true
    metrics_port: 9090
    alerts_enabled: true
    log_retention_days: 30
```

---

## 7. 性能优化

### 7.1 缓存策略

#### 7.1.1 多级缓存架构
```python
# core/mcp/cache/multilevel_cache.py
from typing import Optional, Any
import asyncio
from datetime import datetime, timedelta
from enum import Enum

class CacheLevel(Enum):
    """缓存级别"""
    MEMORY = "memory"
    REDIS = "redis"
    DISK = "disk"

class CacheEntry:
    """缓存条目"""
    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.created_at = datetime.utcnow()
        self.expires_at = self.created_at + timedelta(seconds=ttl)
        
    def is_expired(self) -> bool:
        """检查是否过期"""
        return datetime.utcnow() > self.expires_at

class MultiLevelCache:
    """多级缓存"""
    
    def __init__(self):
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.redis_client = None
        self.disk_cache_path = "/tmp/mcp_cache"
        
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        # 1. 检查内存缓存
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            if not entry.is_expired():
                return entry.value
            else:
                del self.memory_cache[key]
                
        # 2. 检查Redis缓存
        if self.redis_client:
            redis_value = await self.redis_client.get(key)
            if redis_value:
                # 回写到内存缓存
                self.memory_cache[key] = CacheEntry(redis_value, ttl=60)
                return redis_value
                
        # 3. 检查磁盘缓存
        disk_value = self._read_from_disk(key)
        if disk_value:
            # 回写到内存和Redis缓存
            self.memory_cache[key] = CacheEntry(disk_value, ttl=300)
            if self.redis_client:
                await self.redis_client.setex(key, 300, disk_value)
            return disk_value
            
        return None
        
    async def set(self, key: str, value: Any, ttl: int):
        """设置缓存值"""
        # 1. 写入内存缓存（短期）
        memory_ttl = min(ttl, 60)  # 内存缓存最多60秒
        self.memory_cache[key] = CacheEntry(value, memory_ttl)
        
        # 2. 写入Redis缓存（中期）
        if self.redis_client and ttl > 60:
            redis_ttl = min(ttl, 3600)  # Redis缓存最多1小时
            await self.redis_client.setex(key, redis_ttl, value)
            
        # 3. 写入磁盘缓存（长期）
        if ttl > 3600:
            self._write_to_disk(key, value)
```

### 7.2 连接池管理

#### 7.2.1 智能连接池
```python
# core/mcp/connection_pool.py
from typing import Dict, List, Optional
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

class ConnectionState(Enum):
    """连接状态"""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    CLOSED = "closed"

@dataclass
class Connection:
    """连接对象"""
    connection_id: str
    endpoint: str
    state: ConnectionState
    created_at: datetime
    last_used: datetime
    error_count: int = 0

class SmartConnectionPool:
    """智能连接池"""
    
    def __init__(self, 
                 max_connections: int = 100,
                 idle_timeout: int = 300):
        self.max_connections = max_connections
        self.idle_timeout = idle_timeout
        self.connections: Dict[str, Connection] = {}
        self.available_connections: List[str] = []
        
    async def acquire_connection(self, endpoint: str) -> Optional[Connection]:
        """获取连接"""
        # 1. 查找可用连接
        for conn_id in self.available_connections:
            conn = self.connections[conn_id]
            if conn.endpoint == endpoint and conn.state == ConnectionState.IDLE:
                # 检查连接是否过期
                idle_time = (datetime.utcnow() - conn.last_used).total_seconds()
                if idle_time > self.idle_timeout:
                    await self._close_connection(conn_id)
                    continue
                    
                conn.state = ConnectionState.BUSY
                conn.last_used = datetime.utcnow()
                self.available_connections.remove(conn_id)
                return conn
                
        # 2. 创建新连接
        if len(self.connections) < self.max_connections:
            conn = await self._create_connection(endpoint)
            if conn:
                conn.state = ConnectionState.BUSY
                return conn
                
        # 3. 等待连接释放
        return await self._wait_for_connection(endpoint)
        
    async def release_connection(self, connection_id: str):
        """释放连接"""
        if connection_id in self.connections:
            conn = self.connections[connection_id]
            
            # 根据错误计数决定连接状态
            if conn.error_count > 3:
                conn.state = ConnectionState.ERROR
                await self._close_connection(connection_id)
            else:
                conn.state = ConnectionState.IDLE
                conn.last_used = datetime.utcnow()
                self.available_connections.append(connection_id)
                
    async def _create_connection(self, endpoint: str) -> Optional[Connection]:
        """创建新连接"""
        try:
            # 实际连接创建逻辑
            conn_id = f"conn_{len(self.connections)}"
            conn = Connection(
                connection_id=conn_id,
                endpoint=endpoint,
                state=ConnectionState.IDLE,
                created_at=datetime.utcnow(),
                last_used=datetime.utcnow()
            )
            
            self.connections[conn_id] = conn
            return conn
            
        except Exception as e:
            print(f"创建连接失败: {e}")
            return None
            
    async def _close_connection(self, connection_id: str):
        """关闭连接"""
        if connection_id in self.connections:
            del self.connections[connection_id]
            if connection_id in self.available_connections:
                self.available_connections.remove(connection_id)
                
    async def _wait_for_connection(self, endpoint: str, timeout: int = 10) -> Optional[Connection]:
        """等待连接释放"""
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            # 定期检查是否有连接可用
            for conn_id in self.available_connections:
                conn = self.connections[conn_id]
                if conn.endpoint == endpoint:
                    conn.state = ConnectionState.BUSY
                    conn.last_used = datetime.utcnow()
                    self.available_connections.remove(conn_id)
                    return conn
                    
            await asyncio.sleep(0.1)
            
        return None
```

---

## 8. 集成测试

### 8.1 测试策略

#### 8.1.1 测试金字塔
```
        ┌─────────────────┐
        │   端到端测试     │
        │   (10%)         │
        └────────┬────────┘
                 │
        ┌────────┴────────┐
        │   集成测试       │
        │   (20%)         │
        └────────┬────────┘
                 │
        ┌────────┴────────┐
        │   单元测试       │
        │   (70%)         │
        └─────────────────┘
```

#### 8.1.2 测试覆盖范围
```yaml
# tests/mcp/coverage.yaml
test_coverage:
  unit_tests:
    - protocol_adapter: 90%
    - server_manager: 95%
    - cache_layer: 85%
    - security: 90%
    
  integration_tests:
    - mcp_server_communication: 80%
    - data_transformation: 85%
    - error_handling: 75%
    
  e2e_tests:
    - domain_simulator_scenario: 70%
    - radar_detection_pipeline: 65%
    - weather_data_integration: 60%
    
  performance_tests:
    - latency_under_load: 1000 req/sec
    - memory_usage: < 500MB
    - connection_scalability: 1000 concurrent
```

### 8.2 测试用例示例

#### 8.2.1 单元测试
```python
# tests/mcp/test_protocol_adapter.py
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from core.mcp.protocol_adapter import MCPProtocolAdapter, MCPMessageType

class TestMCPProtocolAdapter:
    
    @pytest.fixture
    def adapter(self):
        return MCPProtocolAdapter(transport="http")
        
    @pytest.mark.asyncio
    async def test_send_message_success(self, adapter):
        """测试成功发送消息"""
        with patch.object(adapter.session, 'post') as mock_post:
            mock_response = AsyncMock()
            mock_response.json.return_value = {
                "jsonrpc": "2.0",
                "result": {"status": "success"},
                "id": "test-id"
            }
            mock_response.status = 200
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # 设置适配器端点
            adapter.endpoint = "http://test-server:8080"
            
            result = await adapter.send_message(
                MCPMessageType.LIST_TOOLS,
                {"filter": "all"}
            )
            
            assert result["result"]["status"] == "success"
            mock_post.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_send_message_timeout(self, adapter):
        """测试消息发送超时"""
        with patch.object(adapter.session, 'post') as mock_post:
            mock_post.side_effect = asyncio.TimeoutError("Request timeout")
            
            adapter.endpoint = "http://test-server:8080"
            
            with pytest.raises(asyncio.TimeoutError):
                await adapter.send_message(
                    MCPMessageType.LIST_TOOLS,
                    {"filter": "all"}
                )
```

#### 8.2.2 集成测试
```python
# tests/mcp/integration/test_domain_simulator.py
import pytest
import json
from httpx import AsyncClient
from core.mcp.domain_simulator import DomainSimulatorAdapter

class TestDomainSimulatorIntegration:
    
    @pytest.fixture
    async def simulator_adapter(self):
        """创建领域仿真器适配器"""
        adapter = DomainSimulatorAdapter("ws://localhost:9000")
        await adapter.connect()
        yield adapter
        await adapter.disconnect()
        
    @pytest.mark.integration
    async def test_get_scenario(self, simulator_adapter):
        """测试获取领域场景"""
        scenario = await simulator_adapter.get_scenario("test-scenario-001")
        
        assert scenario is not None
        assert scenario.id == "test-scenario-001"
        assert "units" in scenario
        assert "terrain" in scenario
        assert len(scenario.units) > 0
        
    @pytest.mark.integration
    async def test_simulate_attack(self, simulator_adapter):
        """测试模拟攻击"""
        result = await simulator_adapter.simulate_attack(
            attacker_id="unit-001",
            target_id="unit-002",
            weapon_type="missile",
            strategy="direct"
        )
        
        assert result is not None
        assert "success" in result
        assert "damage" in result
        assert "casualties" in result
        assert result["success"] is True
        
    @pytest.mark.integration
    async def test_update_unit_position(self, simulator_adapter):
        """测试更新单位位置"""
        success = await simulator_adapter.update_unit_position(
            unit_id="unit-001",
            position={"x": 100.0, "y": 200.0, "z": 50.0},
            heading=45.0
        )
        
        assert success is True
```

---

## 9. API文档

### 9.1 REST API

#### 9.1.1 服务器管理API
```
GET    /api/v1/mcp/servers           # 获取所有服务器列表
POST   /api/v1/mcp/servers          # 注册新服务器
GET    /api/v1/mcp/servers/{name}   # 获取服务器详情
PUT    /api/v1/mcp/servers/{name}   # 更新服务器配置
DELETE /api/v1/mcp/servers/{name}   # 注销服务器
POST   /api/v1/mcp/servers/{name}/health  # 手动健康检查
```

#### 9.1.2 数据访问API
```
POST   /api/v1/mcp/query            # 执行MCP查询
GET    /api/v1/mcp/resources/{uri}  # 读取资源
GET    /api/v1/mcp/tools            # 获取可用工具列表
POST   /api/v1/mcp/tools/{name}     # 调用工具
GET    /api/v1/mcp/metrics          # 获取监控指标
```

### 9.2 WebSocket API

#### 9.2.1 实时数据流
```javascript
// WebSocket连接示例
const ws = new WebSocket('ws://localhost:8081/mcp/ws');

ws.onopen = () => {
  // 订阅雷达数据
  ws.send(JSON.stringify({
    type: 'subscribe',
    channel: 'radar_detections',
    filter: { radar_id: 'radar-001' }
  }));
  
  // 订阅领域事件
  ws.send(JSON.stringify({
    type: 'subscribe',
    channel: 'domain_events',
    filter: { event_type: ['attack', 'movement'] }
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('收到数据:', data);
  
  // 处理不同类型的消息
  switch(data.type) {
    case 'radar_detection':
      updateRadarDisplay(data.payload);
      break;
    case 'domain_event':
      handleDomainEvent(data.payload);
      break;
    case 'weather_update':
      updateWeatherDisplay(data.payload);
      break;
  }
};
```

#### 9.2.2 命令执行
```javascript
// 通过WebSocket执行命令
function executeToolViaWebSocket(toolName, arguments) {
  const message = {
    type: 'execute_tool',
    tool: toolName,
    arguments: arguments,
    request_id: generateRequestId()
  };
  
  ws.send(JSON.stringify(message));
  
  // 等待响应
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error('请求超时'));
    }, 10000);
    
    // 监听响应
    const listener = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'tool_response' && data.request_id === message.request_id) {
        clearTimeout(timeout);
        ws.removeEventListener('message', listener);
        
        if (data.success) {
          resolve(data.result);
        } else {
          reject(new Error(data.error));
        }
      }
    };
    
    ws.addEventListener('message', listener);
  });
}

// 使用示例
async function simulateAttack() {
  try {
    const result = await executeToolViaWebSocket('domain.simulate_attack', {
      attacker_id: 'unit-001',
      target_id: 'unit-002',
      weapon_type: 'missile'
    });
    
    console.log('攻击模拟结果:', result);
    return result;
  } catch (error) {
    console.error('攻击模拟失败:', error);
    throw error;
  }
}
```

---

## 10. 版本历史

### 10.1 核心价值总结

1. **标准化集成**: 通过MCP v1.0协议统一所有外部系统接入，消除接口碎片化
2. **高性能**: 支持WebSocket实时数据流，多级缓存优化，智能连接池管理
3. **高安全性**: 完整的认证、授权、加密、审计安全体系
4. **可观测性**: 全面的监控、日志、告警、指标收集能力
5. **可扩展性**: 插件化架构，支持动态添加/移除MCP Server
6. **生产就绪**: Docker部署、配置管理、健康检查、故障恢复

### 10.2 未来演进方向

1. **协议升级**: 支持MCP v2.0新特性（如流式资源、通知订阅）
2. **AI增强**: 集成LLM进行协议自动适配和智能路由
3. **边缘计算**: 支持边缘节点的MCP Server部署和协同
4. **区块链集成**: 使用区块链技术确保数据不可篡改和审计追踪
5. **5G优化**: 针对5G网络特性优化数据传输协议

### 10.3 成功指标

| 指标 | 目标值 | 测量方法 |
|------|--------|----------|
| 请求成功率 | > 99.9% | 监控指标收集 |
| 平均延迟 | < 100ms | 性能测试 |
| 并发连接数 | > 1000 | 压力测试 |
| 系统可用性 | > 99.99% | 运维监控 |
| 安全事件数 | 0 | 安全审计 |
| 开发效率提升 | 50% | 团队反馈 |

---

**文档版本历史**:

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| v1.0.0 | 2026-04-12 | 初始版本，完整设计MCP协议集成模块 |
| v0.1.0 | 2026-04-11 | 草案版本，基础架构设计 |

---

**相关文档**:
- [MCP协议规范](https://spec.modelcontextprotocol.io/)
- [OpenHarness领域适配指南](../openharness_bridge/DESIGN.md)
- [安全策略文档](../../security/SECURITY.md)