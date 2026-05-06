# 战场模拟数据更新规格文档 - 2026 美伊战争场景

## Why
当前战场模拟数据使用虚构的 "Blue Force/Red Force" 等名称，与真实的 2026 年中东战争场景不符。需要更新为真实的参战方、军事单位和武器系统数据，以便更准确地模拟战场态势。

## What Changes

### 1. 更新交战方（Factions）
- **美国 (US)**: 主导联军行动，提供空中支援和精确打击
- **以色列 (Israel)**: 地面行动主力，打击伊朗核设施
- **伊朗 (Iran)**: 主要对手，使用导弹和无人机反击
- **黎巴嫩真主党 (Hezbollah)**: 伊朗代理人，从黎巴嫩向以色列发射火箭弹
- **伊拉克民兵 (IRGC-Iraq)**: 伊朗支持的什叶派武装
- **也门胡塞武装 (Houthis)**: 伊朗代理人，在红海发起袭击

### 2. 更新区域划分（Areas）
- **A区 (波斯湾)**: 美军海军部署区，伊朗海军活动区
- **B区 (伊朗西部)**: 以色列空袭目标区，伊朗核设施集中区
- **C区 (伊拉克)**: 美伊边境，IRGC 活动区
- **D区 (黎巴嫩/以色列北部)**: 真主党火箭弹发射区
- **E区 (红海/也门)**: 胡塞武装袭击区

### 3. 更新参战兵种
- 美军：F-35 战机、航母战斗群、陆军第 82 空降师
- 以色列：梅卡瓦坦克、f-16 战机、步兵
- 伊朗：弹道导弹、无人机群、海岸警卫队
- 真主党：火箭弹、隧道网络、反坦克导弹

### 4. 更新武器系统
- 雷达系统：宙斯盾雷达、萨德雷达
- 导弹系统：伊朗弹道导弹（Shahed）、铁穹拦截系统
- 无人机：MQ-9 死神、Shahed-136 无人机
- 海军：艾森豪威尔号航母、伊朗革命卫队快艇

### 5. 更新民用设施
- 油罐区、发电厂、医院、学校
- 难民营、补给线、后勤仓库

### 6. 更新战场事件类型
- 空袭、导弹拦截、无人机侦察
- 电子战、网络攻击、情报更新
- 人道主义事件、平民伤亡

### 7. 更新任务类型
- 防空任务、精确打击任务
- 侦察监视任务、后勤补给任务
- 电子干扰任务、人道主义救援

## Impact

### Affected Files
- `ontology/battlefield_ontology.py`: 更新 BATTLEFIELD_CONFIG
- `data/simulation_data.py`: 更新 generate_simulation_data 函数
- `data/simulation_data.json`: 重新生成模拟数据 JSON

### Affected Capabilities
- FR-7: 战场实体模拟数据构建
- FR-9: 多交战方模拟和随机事件生成

## ADDED Requirements

### Requirement: 2026 美伊战争场景模拟
系统 SHALL 基于 2026 年美伊战争场景提供战场模拟数据，包括：
- 6 个真实参战方
- 5 个地理区域
- 各类型军事单位、武器系统、民用设施
- 基于真实战术的战损评估

#### Scenario: 系统初始化
- **WHEN** 系统启动并加载模拟数据
- **THEN** 加载 2026 美伊战争场景数据，包含所有定义的参战方和实体

#### Scenario: 指挥官查询战场态势
- **WHEN** 指挥官询问 "当前伊朗导弹威胁"
- **THEN** 返回基于模拟数据的伊朗导弹阵地、发射记录、拦截统计

#### Scenario: 打击推荐
- **WHEN** 指挥官请求打击推荐
- **THEN** 基于模拟数据中的伊朗核设施、导弹阵地、雷达站等生成推荐目标

## MODIFIED Requirements

### Requirement: BATTLEFIELD_CONFIG 配置更新
将虚构的 Blue Force/Red Force 更新为 2026 美伊战争真实参战方

**Migration**: 自动迁移，原有代码引用的 faction 名称需要更新

### Requirement: 参战兵种数据更新
更新 MilitaryUnit 类型中的兵种名称和编制

**Migration**: 更新 generate_simulation_data 中的兵种生成逻辑

## REMOVED Requirements

### Requirement: 虚构 Blue Force/Red Force 场景
**Reason**: 与新的 2026 美伊战争场景冲突
**Migration**: 替换为 US/Israel/Iran/Hezbollah 等真实参战方