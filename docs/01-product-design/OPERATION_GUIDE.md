# ODAP 本体设计系统完整操作指南

## 功能操作顺序

```
1. 工作空间/场景设置
   ↓
2. 本体设计器 (新建实体类型)
   ↓
3. 蓝图设计 (业务流程编排)
   ↓
4. 对象管理 (实体实例管理)
   ↓
5. 数据摄入 / 知识应用
```

---

## 详细操作步骤

### 步骤 1: 设置工作空间与场景

**前端页面:** `/workspace`

1. 登录系统（默认账号：admin/admin123）
2. 在顶部导航栏选择或创建**工作空间**
3. 然后选择或创建**场景**
4. 这是后续所有操作的基础容器

**后端 API:**
- `POST /api/workspace` - 创建工作空间
- `GET /api/workspace` - 获取工作空间列表

**初始化演示数据:**
```bash
python scripts/init_demo_data.py
```

---

### 步骤 2: 本体设计器 - 新建实体类型

**前端页面:** `/ontology/designer`

#### 2.1 创建实体类型

1. 点击右上角"**新增实体类型**"按钮
2. 填写实体类型信息：
   - **名称**: 英文标识，如：`MilitaryUnit`
   - **显示名称**: 中文，如：`作战单元`
   - **描述**: 详细说明
   - **密级**: 安全等级（公开/内部/机密等）
   - **父实体类型**: 选择继承的父类型（可选）
3. 点击"创建"

#### 2.2 添加属性

在左侧列表选择该实体类型，在中间面板添加属性：

**基础属性:**
- `name` - 名称
- `status` - 状态
- `location` - 位置
- `type` - 子类型

**统计属性:**
- `combat_power` - 战斗力
- `morale` - 士气
- `readiness` - 战备等级

**能力属性:**
- `weapons` - 武器装备
- `mobility` - 机动性
- `communication` - 通信能力

#### 2.3 建立关系

在右侧关系面板：
1. 点击"添加关系"
2. 选择关系类型（如：装备、隶属、驻扎）
3. 选择目标实体类型
4. 配置关系属性（如：数量、角色）

#### 2.4 保存与预览

1. 点击"保存"按钮
2. 查看右侧关系图预览
3. 可以导出为 JSON 或图像

**后端 API:**
- `POST /api/ontology/entity-type` - 创建实体类型
- `GET /api/ontology/entity-types` - 获取实体类型列表
- `GET /api/ontology/graph` - 获取图谱可视化

**实体类型层次结构:**
```
BaseEntity (基础实体)
├─ Person (人员)
│  ├─ MilitaryPersonnel (军事人员)
│  └─ CivilianPerson (平民)
├─ Organization (组织)
│  ├─ MilitaryUnit (作战单元)
│  └─ GovernmentAgency (政府机构)
├─ Location (地点)
│  ├─ MilitaryBase (军事基地)
│  └─ City (城市)
├─ WeaponSystem (武器系统)
│  ├─ Aircraft (飞行器)
│  ├─ NavalVessel (舰船)
│  └─ MissileSystem (导弹系统)
└─ Event (事件)
   ├─ MilitaryOperation (军事行动)
   └─ CrisisEvent (危机事件)
```

---

### 步骤 3: 蓝图设计

**前端页面:** `/blueprint`

#### 3.1 创建蓝图

1. 左侧面板点击"新建蓝图"
2. 填写蓝图信息：
   - 名称
   - 描述
   - 关联场景
3. 点击"创建"

#### 3.2 添加节点

从左侧节点面板拖拽节点到画布：

| 节点类型 | 说明 | 用途 |
|---------|------|------|
| **数据源节点** | 数据输入 | 文件、API、数据库 |
| **转换节点** | 数据处理 | 清洗、转换、聚合 |
| **本体节点** | 本体关联 | 与实体类型映射 |
| **动作节点** | 执行操作 | 创建、更新、删除 |
| **Agent节点** | 智能体处理 | LLM 推理、分析 |
| **决策节点** | 分支逻辑 | 条件判断 |
| **验证节点** | 数据校验 | 规则验证 |
| **输出节点** | 结果输出 | 存储、展示 |

#### 3.3 连接节点

1. 从源节点的输出端口拖拽
2. 连接到目标节点的输入端口
3. 设置连接类型：
   - `data_flow` - 数据流
   - `control_flow` - 控制流
   - `dependency` - 依赖关系

#### 3.4 配置节点属性

双击节点或右键选择"编辑"：
- 配置节点参数
- 设置输入输出格式
- 关联本体实体类型

#### 3.5 验证与发布

1. 点击"验证"检查蓝图正确性
2. 查看验证报告（错误/警告）
3. 修复问题后再次验证
4. 点击"保存"
5. 点击"发布"使蓝图生效

**后端 API:**
- `POST /api/blueprint` - 创建蓝图
- `POST /api/blueprint/{id}/node` - 添加节点
- `POST /api/blueprint/{id}/edge` - 添加边
- `POST /api/blueprint/{id}/validate` - 验证蓝图
- `POST /api/blueprint/{id}/publish` - 发布蓝图
- `GET /api/blueprint/{id}/export` - 导出蓝图

**蓝图验证规则:**
- 至少需要1个节点
- 不能有孤立节点（断开连接）
- 不能有循环引用（除非明确允许）
- 所有节点必须有有效的配置
- 数据流必须完整（从输入到输出）

---

### 步骤 4: 对象管理

**前端页面:** `/business/entities`

#### 标签页 1: 对象类型定义

- 管理业务对象类型（与本体实体类型对应）
- 查看类型层次结构
- 编辑类型属性

#### 标签页 2: 实体实例

**功能:**
1. **查看实体列表**
   - 表格展示所有实体
   - 按类型、来源、状态过滤
   - 搜索功能
   - 分页浏览

2. **查看属性分布**
   - 统计图表展示
   - 按属性值分组
   - 趋势分析

3. **查看实体详情**
   - 点击实体行查看详情
   - 按语义类别分组显示属性
   - 查看关联关系
   - 编辑属性

4. **多维度过滤**
   - 按实体类型过滤
   - 按数据来源过滤
   - 按置信度过滤
   - 按时间范围过滤

**后端 API:**
- `GET /api/entities` - 获取实体列表
- `GET /api/entities/{id}` - 获取实体详情
- `PUT /api/entities/{id}` - 更新实体
- `DELETE /api/entities/{id}` - 删除实体

---

### 步骤 5: 数据摄入与应用

#### 5.1 数据摄入

**前端页面:** `/ingest`

1. 上传文档（PDF、Word、文本等）
2. 选择摄入配置
3. 启动摄入任务
4. 查看进度和结果
5. 自动提取实体并添加到知识图谱

**后端 API:**
- `POST /api/ingest` - 上传并处理文档
- `GET /api/ingest/{id}/status` - 查看任务状态

#### 5.2 知识问答

**前端页面:** `/qa`

1. 输入问题
2. 选择智能体
3. 查看回答
4. 查看引用来源

**后端 API:**
- `POST /api/qa/ask` - 提问
- `GET /api/qa/history` - 查看历史

#### 5.3 推演仿真

**前端页面:** `/simulation/deduction`

1. 创建推演场景
2. 设置初始条件
3. 运行推演
4. 查看结果

---

## 测试验证

### 单元测试

运行完整测试套件：

```bash
# 运行所有测试
pytest tests/unit/ -v

# 运行蓝图设计器测试
pytest tests/unit/test_blueprint_designer.py -v

# 运行本体模块测试
pytest tests/unit/test_ontology.py -v

# 生成测试覆盖率报告
pytest tests/unit/ --cov=odap --cov-report=html
```

### 蓝图设计器测试示例

测试文件: `tests/unit/test_blueprint_designer.py`

```python
# 创建蓝图
result = service.create_blueprint(name="情报分析流程", description="军事情报分析")

# 添加节点
source_node = service.add_node(
    blueprint_id, "data_source", "情报数据源",
    position={"x": 100, "y": 100},
    config={"source_type": "api", "url": "http://example.com/api"}
)

transform_node = service.add_node(
    blueprint_id, "transform", "数据清洗",
    position={"x": 300, "y": 100}
)

# 连接节点
service.add_edge(
    blueprint_id,
    source_node["node_id"],
    transform_node["node_id"],
    edge_type="data_flow",
    label="原始数据"
)

# 验证蓝图
validation = service.validate_blueprint(blueprint_id)
assert validation["is_valid"] is True

# 发布蓝图
publish_result = service.publish_blueprint(blueprint_id)
assert publish_result["is_published"] is True
```

### 前端测试

```bash
cd frontend

# 运行测试
npm test

# 监听模式
npm run test:watch

# 生成覆盖率报告
npm run test:coverage

# 代码检查
npm run lint

# 类型检查
npm run typecheck
```

### 端到端测试

```bash
# 运行端到端测试（需要服务运行）
pytest tests/e2e/ -v -m e2e
```

### API 测试示例

使用 curl 测试 API：

```bash
# 1. 登录获取 Token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 2. 使用 Token 创建工作空间
curl -X POST http://localhost:8000/api/workspace \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"测试工作空间","description":"测试"}'

# 3. 创建实体类型
curl -X POST http://localhost:8000/api/ontology/entity-type \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TestEntity",
    "display_name": "测试实体",
    "description": "测试用实体类型",
    "classification": "public",
    "properties": [
      {"name": "name", "type": "string", "required": true},
      {"name": "status", "type": "string", "required": false}
    ]
  }'

# 4. 创建蓝图
curl -X POST http://localhost:8000/api/blueprint \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"测试蓝图","description":"测试"}'
```

---

## 项目启动

### 开发环境（容器）

```bash
# 首次启动
python bootstep.py dev

# 代码修改后重启
python bootstep.py restart

# 查看后端日志
python bootstep.py logs

# 查看前端日志
python bootstep.py logs fe

# 停止服务
python bootstep.py down
```

### 访问地址

- **前端**: http://localhost:5173
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

---

## 常见问题

### Q: 如何重置演示数据？

```bash
# 删除数据库文件
rm -rf data/*.db

# 重新初始化
python scripts/init_demo_data.py
```

### Q: 蓝图验证失败怎么办？

1. 检查是否有孤立节点
2. 确认所有节点配置完整
3. 查看验证报告中的详细错误信息

### Q: 实体类型创建后如何修改？

1. 在本体设计器中选择实体类型
2. 在右侧编辑面板修改
3. 点击"保存"
4. 会创建新版本，可以查看版本历史

### Q: 如何导出本体定义？

在本体设计器页面，点击右上角"导出"按钮，选择格式：
- JSON - 完整定义
- PNG/SVG - 图谱图片
- Markdown - 文档格式

---

## 快速开始示例

### 完整流程演示

```python
# 1. 初始化环境
python scripts/init_demo_data.py

# 2. 启动服务
python bootstep.py dev

# 3. 访问前端
# 打开浏览器: http://localhost:5173

# 4. 使用演示账号登录
# 用户名: admin
# 密码: admin123

# 5. 选择"东部战区情报分析"工作空间

# 6. 进入本体设计器，查看已有的实体类型

# 7. 进入蓝图设计，创建一个简单的情报分析流程

# 8. 进入对象管理，查看演示数据

# 9. 进入问答系统，尝试提问："查询所有武器装备"
```

---

## 技术支持

如有问题，请查看：
- 项目文档: `docs/`
- 设计文档: `docs/03-modules/`
- API 文档: http://localhost:8000/docs
