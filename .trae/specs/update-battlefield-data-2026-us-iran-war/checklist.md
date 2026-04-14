# Checklist - 2026 美伊战争场景数据更新

## Code Implementation

- [x] BATTLEFIELD_CONFIG 更新为 6 个真实参战方（US, Israel, Iran, Hezbollah, IRGC-Iraq, Houthis）
- [x] Areas 更新为真实地理位置描述
- [x] Random_events 更新为相关战场事件
- [x] generate_simulation_data 函数使用新的 factions 配置
- [x] 兵种生成包含美军、以色列、伊朗、黎巴嫩等部队
- [x] 武器系统生成包含导弹、无人机、坦克、战机等
- [x] 民用设施生成包含油罐区、发电厂、医院等
- [x] simulation_data.json 重新生成并格式正确

## Verification

- [x] 服务启动成功，无配置加载错误
- [x] /api/graph 返回正确的节点和关系
- [x] /get_stats 返回正确的实体类型统计
- [x] 打击推荐功能正常工作
- [x] 力量对比显示新参战方数据
- [x] 自环关系清理功能仍然正常工作

## Documentation

- [x] TASK_BREAKDOWN.md 无需更新（无战场配置说明）
- [x] README.md 无需更新