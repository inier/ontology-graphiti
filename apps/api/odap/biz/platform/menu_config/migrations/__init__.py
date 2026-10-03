"""菜单配置迁移脚本包。

种子数据（seed_four_steps.py）通过 init_default_menu() 的幂等 skip 只对**全新 code**
生效——改名/移位/改 sort_order/改 path 对**已有数据库无效**（已存在的 code 被直接
skip）。因此每次对既有菜单结构做变更，都需要一支"按 code 就地 UPDATE"的一次性迁移脚本。

约定：
  - 迁移脚本必须**幂等**（可重复执行结果一致）。
  - 必须**保持 code/id 稳定**——role_menus 以菜单 id(=code) 存储授权，改 code 会使
    既有角色授权失效。
  - 只依赖 storage 层的公开方法（save_menu_item / get_menu_item_by_code），
    禁止裸 SQL 或幻影方法（AGENTS 规则 14）。
"""
