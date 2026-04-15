"""
基于命令行的对话界面
实现领域态势对话功能
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.biz.agent.orchestrator import SelfCorrectingOrchestrator

class DomainDialogInterface:
    """
    领域对话界面
    """

    def __init__(self, user_role="pilot"):
        """
        初始化对话界面

        Args:
            user_role: 用户角色
        """
        self.user_role = user_role
        self.orchestrator = SelfCorrectingOrchestrator(user_role=user_role)
        self.conversation_history = []
        print(f"对话界面初始化成功，用户角色: {user_role}")

    def start_dialog(self):
        """
        开始对话
        """
        print("\n" + "=" * 50)
        print("🚀 领域指挥系统对话界面")
        print("=" * 50)
        print("输入您的命令，系统将智能路由到对应技能")
        print("输入 'help' 查看可用命令")
        print("输入 'exit' 退出")
        print("输入 'history' 查看对话历史")
        print("=" * 50 + "\n")

        while True:
            try:
                user_input = input("您: ").strip()

                if not user_input:
                    continue

                if user_input.lower() == "exit":
                    print("系统: 再见！")
                    break

                if user_input.lower() == "help":
                    self._show_help()
                    continue

                if user_input.lower() == "history":
                    self._show_history()
                    continue

                if user_input.lower() == "clear":
                    self.conversation_history = []
                    print("系统: 对话历史已清除")
                    continue

                # 使用编排器处理用户输入
                result = self.orchestrator.run(user_input)

                # 保存对话历史
                self.conversation_history.append({
                    "user": user_input,
                    "result": result
                })

                # 显示结果
                self._display_result(result)

            except KeyboardInterrupt:
                print("\n系统: 再见！")
                break
            except Exception as e:
                print(f"系统错误: {e}")

    def _show_help(self):
        """
        显示帮助信息
        """
        print("""
系统支持以下类型的命令:

1. 情报查询:
   - "帮我看看B区有没有雷达"
   - "分析当前领域态势"
   - "查看A区的军事单位"

2. 执行命令:
   - "攻击 RADAR_01" (需要指挥官权限)
   - "指挥 UNIT_01 执行任务"

3. 任务管理:
   - "预留一个侦察任务"
   - "查看我的任务"

4. 分析报告:
   - "生成领域态势报告"
   - "分析力量对比"
   - "推荐打击目标"

5. 切换角色:
   - "/role pilot" - 切换到飞行员
   - "/role commander" - 切换到指挥官
""")

    def _show_history(self):
        """
        显示对话历史
        """
        if not self.conversation_history:
            print("系统: 暂无对话历史")
            return

        print("\n--- 对话历史 ---")
        for i, item in enumerate(self.conversation_history, 1):
            print(f"\n[{i}] 您: {item['user']}")
            result = item['result']
            if isinstance(result, list):
                print(f"    系统: 找到 {len(result)} 个结果")
            elif isinstance(result, dict):
                status = result.get("status", "unknown")
                message = result.get("message", "")
                print(f"    系统: {status} - {message}")
        print("\n--- 历史结束 ---\n")

    def _display_result(self, result):
        """
        显示结果

        Args:
            result: 执行结果
        """
        print("系统: ")

        if isinstance(result, list):
            # 列表结果（如搜索雷达）
            if len(result) == 0:
                print("  未找到匹配的结果")
            else:
                print(f"  找到 {len(result)} 个结果:")
                for item in result:
                    if isinstance(item, dict) and "properties" in item:
                        props = item["properties"]
                        name = props.get("name", "未知目标")
                        type_name = props.get("type", "")
                        status = props.get("status", "")
                        area = props.get("area", "")
                        print(f"  - {name} ({type_name})")
                        if status:
                            print(f"    状态: {status}")
                        if area:
                            print(f"    区域: {area}")
                    else:
                        print(f"  - {item}")
        elif isinstance(result, dict):
            # 字典结果（如攻击结果）
            status = result.get("status", "unknown")
            message = result.get("message", "")
            print(f"  状态: {status}")
            print(f"  消息: {message}")

            if "target" in result:
                target_name = result["target"]["properties"].get("name", "未知目标")
                print(f"  目标: {target_name}")

            if "total_entities" in result:
                print(f"  实体总数: {result['total_entities']}")

            if "entity_types" in result:
                print("  实体类型分布:")
                for entity_type, count in result["entity_types"].items():
                    print(f"    - {entity_type}: {count}")

            if "recommendations" in result:
                print("  建议:")
                for rec in result["recommendations"]:
                    print(f"    • {rec}")
        else:
            # 其他类型结果
            print(f"  {result}")

        print()

    def set_role(self, role):
        """
        设置用户角色

        Args:
            role: 角色名称
        """
        if role in ["pilot", "commander", "intelligence_analyst"]:
            self.user_role = role
            self.orchestrator = SelfCorrectingOrchestrator(user_role=role)
            print(f"系统: 已切换到角色: {role}")
        else:
            print(f"系统: 未知角色: {role}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="领域指挥系统对话界面")
    parser.add_argument("--role", "-r", default="pilot",
                       choices=["pilot", "commander", "intelligence_analyst"],
                       help="选择用户角色 (默认: pilot)")

    args = parser.parse_args()

    dialog = DomainDialogInterface(user_role=args.role)
    dialog.start_dialog()