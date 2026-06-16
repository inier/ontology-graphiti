"""
ODAP 系统指南 Demo 示例
========================

按照系统指南 (/) 的 5 个步骤，演示完整的端到端创建过程：

  步骤 1: 工作空间设置  - 创建工作空间 + 场景
  步骤 2: 本体设计器    - 创建本体 + 3 个实体类型
  步骤 3: 蓝图设计      - 创建 2 个关系类型 (LinkType)
  步骤 4: 对象管理      - 自然语言摄入 + 实体实例查询
  步骤 5: 数据摄入与应用 - 知识问答

运行前确保:
  1. 后端服务已启动: python -m odap.web.app  (端口 8000)
  2. pip install requests

使用:  python scripts/guide_demo_e2e.py
"""

import json
import sys
import time
import uuid
from typing import Any, Dict, Optional

import requests

# Windows GBK 兼容: 强制 UTF-8 输出
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "admin123"
TIMEOUT = 15
INGEST_TIMEOUT = 60  # 摄入需要更长时间（可能涉及 LLM 抽取）


class Colors:
    """控制台彩色输出"""
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


def step_banner(num: int, title: str) -> None:
    print()
    print("=" * 70)
    print(f"{Colors.BOLD}{Colors.HEADER}  步骤 {num}: {title}{Colors.END}")
    print("=" * 70)


def ok(msg: str) -> None:
    print(f"  {Colors.GREEN}✓{Colors.END} {msg}")


def info(msg: str) -> None:
    print(f"  {Colors.CYAN}ℹ{Colors.END} {msg}")


def warn(msg: str) -> None:
    print(f"  {Colors.YELLOW}!{Colors.END} {msg}")


def err(msg: str) -> None:
    print(f"  {Colors.RED}✗{Colors.END} {msg}")


def show(payload: Any, indent: int = 4) -> None:
    """格式化显示 JSON 响应"""
    text = json.dumps(payload, ensure_ascii=False, indent=indent, default=str)
    for line in text.splitlines()[:8]:
        print(f"      {line}")
    if len(text.splitlines()) > 8:
        print(f"      ... ({len(text.splitlines()) - 8} more lines)")


class ODAPClient:
    """ODAP API 客户端封装"""

    def __init__(self, base_url: str = BASE):
        self.base = base_url
        self.token: Optional[str] = None
        self.headers = {"Content-Type": "application/json"}

    def _url(self, path: str) -> str:
        return f"{self.base}{path}"

    def _auth(self) -> Dict[str, str]:
        if not self.token:
            raise RuntimeError("Not authenticated. Call login() first.")
        return {"Authorization": f"Bearer {self.token}"}

    def _check(self, r: requests.Response, action: str) -> Dict[str, Any]:
        if r.status_code >= 400:
            err(f"{action} 失败: HTTP {r.status_code}")
            err(f"响应: {r.text[:300]}")
            raise SystemExit(1)
        try:
            return r.json()
        except json.JSONDecodeError:
            return {"_raw": r.text}

    # ----------------------------------------------------------------
    # 认证
    # ----------------------------------------------------------------
    def login(self, username: str, password: str) -> str:
        r = requests.post(
            self._url("/api/auth/login"),
            json={"username": username, "password": password},
            timeout=TIMEOUT,
        )
        data = self._check(r, "登录")
        self.token = data["access_token"]
        self.headers["Authorization"] = f"Bearer {self.token}"
        return self.token

    # ----------------------------------------------------------------
    # 工作空间 / 场景
    # ----------------------------------------------------------------
    def create_workspace(self, name: str, description: str = "") -> Dict[str, Any]:
        r = requests.post(
            self._url("/api/workspaces"),
            json={"name": name, "description": description, "type": "default", "owner": "demo"},
            headers=self.headers,
            timeout=TIMEOUT,
        )
        return self._check(r, "创建工作空间")

    def create_scenario(
        self, workspace_id: str, name: str, description: str = ""
    ) -> Dict[str, Any]:
        r = requests.post(
            self._url(f"/api/workspaces/{workspace_id}/scenarios"),
            json={"name": name, "description": description, "status": "draft"},
            headers=self.headers,
            timeout=TIMEOUT,
        )
        return self._check(r, "创建场景")

    # ----------------------------------------------------------------
    # 本体 / 实体类型 / 关系类型
    # ----------------------------------------------------------------
    def create_ontology(
        self, name: str, description: str, workspace_id: str, scenario_id: str
    ) -> Dict[str, Any]:
        r = requests.post(
            self._url("/api/ontologies"),
            json={
                "name": name,
                "description": description,
                "workspace_id": workspace_id,
                "scenario_id": scenario_id,
            },
            headers=self.headers,
            timeout=TIMEOUT,
        )
        return self._check(r, "创建本体")

    def create_object_type(
        self, ontology_id: str, type_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        r = requests.post(
            self._url(f"/api/ontologies/{ontology_id}/object-types"),
            json=type_def,
            headers=self.headers,
            timeout=INGEST_TIMEOUT,
        )
        return self._check(r, f"创建实体类型 {type_def.get('name')}")

    def create_link_type(
        self, ontology_id: str, link_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        r = requests.post(
            self._url(f"/api/ontologies/{ontology_id}/link-types"),
            json=link_def,
            headers=self.headers,
            timeout=INGEST_TIMEOUT,
        )
        return self._check(r, f"创建关系类型 {link_def.get('name')}")

    # ----------------------------------------------------------------
    # 数据摄入
    # ----------------------------------------------------------------
    def ingest_natural_language(
        self, text: str, workspace_id: str, scenario_id: str
    ) -> Dict[str, Any]:
        r = requests.post(
            self._url("/api/ingest/unified"),
            json={
                "source_type": "natural_language",
                "text": text,
                "workspace_id": workspace_id,
                "scenario_id": scenario_id,
            },
            headers=self.headers,
            timeout=INGEST_TIMEOUT,
        )
        return self._check(r, "自然语言摄入")

    # ----------------------------------------------------------------
    # 知识问答
    # ----------------------------------------------------------------
    def ask(
        self, question: str, workspace_id: str, scenario_id: Optional[str] = None
    ) -> Dict[str, Any]:
        payload = {
            "question": question,
            "workspace_id": workspace_id,
        }
        if scenario_id:
            payload["scenario_id"] = scenario_id
        r = requests.post(
            self._url("/api/qa/ask"),
            json=payload,
            headers=self.headers,
            timeout=30,
        )
        return self._check(r, "问答")


# -----------------------------------------------------------------------
# 主流程
# -----------------------------------------------------------------------
def main() -> int:
    print()
    print(f"{Colors.BOLD}╔══════════════════════════════════════════════════════════════════╗")
    print(f"║  ODAP 系统指南 Demo  -  端到端完整流程测试                          ║")
    print(f"║  演示场景: 'AI 研发团队' (3 类实体 + 2 类关系)                       ║")
    print(f"╚══════════════════════════════════════════════════════════════════╝{Colors.END}")

    # 唯一标识符，避免重名冲突
    demo_id = uuid.uuid4().hex[:6]
    ws_name = f"Demo工作空间-{demo_id}"
    sc_name = f"Demo场景-{demo_id}"
    ont_name = f"AI研发团队本体-{demo_id}"

    client = ODAPClient()

    # ----------------------------------------------------------------
    # 步骤 0: 登录
    # ----------------------------------------------------------------
    step_banner(0, "登录认证")
    info(f"使用 {USERNAME} 登录 {BASE}")
    try:
        client.login(USERNAME, PASSWORD)
    except Exception as e:
        err(f"登录失败: {e}")
        err("请确保后端服务已启动: python -m odap.web.app")
        return 1
    ok(f"登录成功，Token 前缀: {client.token[:20]}...")

    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
    ontology_id: Optional[str] = None

    try:
        # ----------------------------------------------------------------
        # 步骤 1: 工作空间设置
        # ----------------------------------------------------------------
        step_banner(1, "工作空间设置")
        info("POST /api/workspaces - 创建工作空间")
        ws = client.create_workspace(ws_name, "演示用工作空间")
        workspace_id = ws.get("workspace_id")
        ok(f"工作空间已创建: {workspace_id}")
        show(ws)

        info(f"POST /api/workspaces/{{id}}/scenarios - 创建场景")
        sc = client.create_scenario(workspace_id, sc_name, "演示场景")
        scenario_id = sc.get("scenario_id")
        ok(f"场景已创建: {scenario_id}")
        show(sc)

        # ----------------------------------------------------------------
        # 步骤 2: 本体设计器
        # ----------------------------------------------------------------
        step_banner(2, "本体设计器")
        info("POST /api/ontologies - 创建本体")
        ont = client.create_ontology(
            ont_name,
            "AI 研发团队本体：包含成员、组织、活动三类实体",
            workspace_id,
            scenario_id,
        )
        ontology_id = ont.get("ontology_id")
        ok(f"本体已创建: {ontology_id}")
        show(ont)

        # 创建 3 个实体类型
        entity_types = [
            {
                "name": "TeamMember",
                "display_name": "团队成员",
                "description": "AI 研发团队的成员",
                "attributes": [
                    {"name": "name", "type": "string", "required": True},
                    {"name": "role", "type": "string", "required": True},
                    {"name": "expertise", "type": "string", "required": False},
                ],
            },
            {
                "name": "Project",
                "display_name": "项目",
                "description": "AI 研发项目",
                "attributes": [
                    {"name": "name", "type": "string", "required": True},
                    {"name": "status", "type": "string", "required": True},
                ],
            },
            {
                "name": "Milestone",
                "display_name": "里程碑",
                "description": "项目关键节点",
                "attributes": [
                    {"name": "name", "type": "string", "required": True},
                    {"name": "date", "type": "string", "required": False},
                ],
            },
        ]

        type_ids: Dict[str, str] = {}
        for et in entity_types:
            info(f"POST /api/ontologies/{{id}}/object-types - 创建实体类型 {et['name']}")
            r = client.create_object_type(ontology_id, et)
            type_ids[et["name"]] = r.get("type_id", r.get("object_type_id", ""))
            ok(f"实体类型 {et['name']}: {type_ids[et['name']]}")

        # ----------------------------------------------------------------
        # 步骤 3: 蓝图设计 (关系类型)
        # ----------------------------------------------------------------
        step_banner(3, "蓝图设计 - 关系类型")
        link_types = [
            {
                "name": "works_on",
                "display_name": "参与项目",
                "description": "团队成员参与项目",
                "source_type": "TeamMember",
                "target_type": "Project",
            },
            {
                "name": "has_milestone",
                "display_name": "拥有里程碑",
                "description": "项目的关键节点",
                "source_type": "Project",
                "target_type": "Milestone",
            },
        ]

        for lt in link_types:
            info(f"POST /api/ontologies/{{id}}/link-types - 创建关系类型 {lt['name']}")
            r = client.create_link_type(ontology_id, lt)
            ok(f"关系类型 {lt['name']} 已创建")

        # ----------------------------------------------------------------
        # 步骤 4: 数据摄入 (自然语言)
        # ----------------------------------------------------------------
        step_banner(4, "数据摄入 - 自然语言")
        sample_text = """
        张三是智能体团队的负责人，专门研究大语言模型推理优化。
        李四是算法工程师，擅长分布式训练和强化学习。
        王五是数据工程师，负责知识图谱构建与向量检索。
        他们正在合作开发"通用智能助手"项目，状态为进行中。
        这个项目计划在 Q4 达到 1.0 版本，关键里程碑包括:
        1. 推理性能优化完成
        2. 多模态能力集成
        3. 内测版本发布。
        """

        info("POST /api/ingest/unified (source_type=natural_language)")
        ingest = client.ingest_natural_language(sample_text.strip(), workspace_id, scenario_id)
        ok(f"摄入完成: status={ingest.get('status')}")
        show(ingest)

        # 等待后台处理
        info("等待实体抽取完成 (3s)...")
        time.sleep(3)

        # ----------------------------------------------------------------
        # 步骤 5: 知识问答
        # ----------------------------------------------------------------
        step_banner(5, "数据应用 - 知识问答")
        questions = [
            "团队中有哪些成员？",
            "他们正在做什么项目？",
            "项目有哪些关键里程碑？",
        ]

        for q in questions:
            info(f"POST /api/qa/ask - 提问: {q}")
            ans = client.ask(q, workspace_id, scenario_id)
            answer = ans.get("answer", "")
            sources = ans.get("sources", [])
            print(f"      {Colors.BOLD}回答:{Colors.END} {answer[:200]}{'...' if len(answer) > 200 else ''}")
            print(f"      {Colors.BOLD}引用:{Colors.END} {len(sources)} 条来源")
            print()

        # ----------------------------------------------------------------
        # 总结
        # ----------------------------------------------------------------
        print()
        print("=" * 70)
        print(f"{Colors.BOLD}{Colors.GREEN}  Demo 执行完毕！{Colors.END}")
        print("=" * 70)
        print()
        print(f"  工作空间 ID: {workspace_id}")
        print(f"  场景 ID:     {scenario_id}")
        print(f"  本体 ID:     {ontology_id}")
        print()
        print("  接下来可以在前端系统指南 (/) 中:")
        print(f"    - 查看创建的工作空间 '{ws_name}'")
        print(f"    - 在对象管理页面查看抽取出的实体实例")
        print(f"    - 在问答系统继续提问验证")
        print()
        return 0

    except SystemExit:
        return 1
    except Exception as e:
        err(f"未预期异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
