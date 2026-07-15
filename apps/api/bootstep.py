#!/usr/bin/env python3
"""
Bootstep - Graphiti 一键启动/停止脚本 (Python CLI)

用法:
    python bootstep.py dev         启动开发模式（前端热重载）← 推荐日常开发
    python bootstep.py up          启动所有服务（生产模式）
    python bootstep.py down        停止所有服务（dev + prod 全部清理）
    python bootstep.py restart     重启所有服务（生产模式）
    python bootstep.py restart-dev 重启开发环境（先 down 再 dev）
    python bootstep.py rebuild [target]  只重建镜像，不启动（完成后提示 dev/up）
        target 可选: node-base | main | frontend | frontend-prod | all（默认 all）
    python bootstep.py status      查看服务状态
    python bootstep.py logs        查看后端日志
    python bootstep.py logs fe     查看前端日志
    python bootstep.py pull        拉取基础镜像
    python bootstep.py clean       清理重复/dangling 镜像和未使用资源

环境隔离:
  dev 使用独立的 docker-compose.dev.yml（项目名 graphiti-dev），生产用 docker-compose.yml（项目名 graphiti）。
  容器命名: 生产 graphiti-{svc}，开发 graphiti-dev-{svc}，通过 -p 项目名 + 容器名前缀双重隔离。
  启动 dev 会自动停止 prod 容器，反之亦然。down 同时清理两个环境。
"""

import os
import sys
import time
import subprocess

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
MONOREPO_ROOT = os.path.dirname(os.path.dirname(APP_DIR))
DOCKER_DIR = os.path.join(MONOREPO_ROOT, "docker")
COMPOSE_FILE = os.path.join(DOCKER_DIR, "docker-compose.yml")
COMPOSE_DEV = os.path.join(DOCKER_DIR, "docker-compose.dev.yml")
WIN_FIX = os.path.join(DOCKER_DIR, "podman-compose-win-fix.py")
MIRROR = "docker.m.daocloud.io"

IMAGES = [
    (f"{MIRROR}/library/redis:6",                     "localhost/redis:6"),
    (f"{MIRROR}/library/neo4j:latest",                "localhost/neo4j:latest"),
    (f"{MIRROR}/openpolicyagent/opa:0.58.0",           "localhost/openpolicyagent/opa:0.58.0"),
    (f"{MIRROR}/library/python:3.10-slim",             "localhost/python:3.10-slim"),
    (f"{MIRROR}/library/python:3.11-slim",             "localhost/python:3.11-slim"),
    (f"{MIRROR}/library/node:24-alpine",               "localhost/node:24-alpine"),
    (f"{MIRROR}/library/nginx:alpine",                 "localhost/nginx:alpine"),
    (f"{MIRROR}/minio/minio:latest",                   "localhost/minio:latest"),
]

# 上游拉取后需要再构建的自定义基础镜像（其他 Dockerfile 的 FROM 目标）
BASE_BUILD_IMAGES = [
    {
        "tag": "localhost/node-base:24",
        "dockerfile": "docker/Dockerfile.node-base",
        "context": ".",
        "from": "localhost/node:24-alpine",  # 依赖的上游镜像（需先拉取）
        "desc": "Node 24 基础镜像 (含 python3/make/g++/pnpm9)",
    },
]

CONTAINERS = [
    # 生产环境
    "graphiti-frontend",
    "graphiti-main-app",
    "graphiti-policy-service",
    "graphiti-neo4j",
    "graphiti-cache",
    "graphiti-minio",
    # 开发环境
    "graphiti-dev-frontend",
    "graphiti-dev-app",
    "graphiti-dev-opa",
    "graphiti-dev-neo4j",
    "graphiti-dev-redis",
    "graphiti-dev-minio",
]


def run(cmd, cwd=None, silent=False):
    """运行命令并返回 (returncode, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd if isinstance(cmd, list) else cmd,
            cwd=cwd or MONOREPO_ROOT,
            capture_output=True,
            text=True,
            shell=isinstance(cmd, str),
        )
        if not silent and result.stdout:
            print(result.stdout.strip())
        if not silent and result.stderr and "SyntaxWarning" not in result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        return result.returncode
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return 1


def run_stream(cmd, cwd=None):
    """运行命令并实时输出"""
    proc = subprocess.Popen(
        cmd if isinstance(cmd, list) else cmd,
        cwd=cwd or MONOREPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=isinstance(cmd, str),
    )
    for line in proc.stdout:
        line = line.strip()
        if line and "SyntaxWarning" not in line:
            print(f"    {line}")
    proc.wait()
    return proc.returncode


def get_local_images():
    """获取本地镜像列表"""
    result = subprocess.run(
        ["podman", "images", "--format", "{{.Repository}}:{{.Tag}}"],
        capture_output=True, text=True
    )
    return set(result.stdout.strip().split("\n")) if result.stdout.strip() else set()


def get_compose_cmd(*args, dev=False):
    """构建 podman-compose 命令

    dev=False: 生产模式 → docker-compose.yml, project=graphiti
    dev=True:  开发模式 → docker-compose.dev.yml, project=graphiti-dev
    """
    python_exe = sys.executable
    if dev:
        compose_file = COMPOSE_DEV if os.path.exists(COMPOSE_DEV) else COMPOSE_FILE
        files = [compose_file]
        project_name = "graphiti-dev"
    else:
        files = [COMPOSE_FILE]
        project_name = "graphiti"
    cmd = [python_exe, WIN_FIX]
    for f in files:
        cmd.extend(["-f", f])
    cmd.extend(["-p", project_name])
    cmd.extend(args)
    return cmd


# ── 容器名称常量 ──
# 已通过 -p 项目名隔离，不再有共享容器；这里仅用于 stop_opposing_env 和兜底清理

_PROD_CONTAINERS = [
    "graphiti-frontend", "graphiti-main-app",
    "graphiti-policy-service", "graphiti-neo4j",
    "graphiti-cache", "graphiti-minio",
]
_DEV_CONTAINERS = [
    "graphiti-dev-frontend", "graphiti-dev-app",
    "graphiti-dev-opa", "graphiti-dev-neo4j",
    "graphiti-dev-redis", "graphiti-dev-minio",
]


def stop_containers(container_names, silent=True):
    """强制停止并移除指定容器（忽略不存在的情况）"""
    for name in container_names:
        run(f"podman rm -f {name}", silent=silent)


def stop_opposing_env(mode):
    """停止对方环境的所有容器，防止端口冲突

    mode='dev'  → 停止 prod 容器 (graphiti-frontend, graphiti-main-app, ...)
    mode='prod' → 停止 dev 容器 (graphiti-dev-*)
    """
    if mode == "dev":
        targets = _PROD_CONTAINERS
        label = "生产环境"
    else:
        targets = _DEV_CONTAINERS
        label = "开发环境"

    result = subprocess.run(
        ["podman", "ps", "-a", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    )
    running = set(result.stdout.strip().split("\n")) if result.stdout.strip() else set()
    active = [c for c in targets if c in running]

    if active:
        print(f"  停止 {label} 容器: {', '.join(active)}")
        stop_containers(active)


def title(text):
    print(f"\n{'='*40}")
    print(f"  {text}")
    print(f"{'='*40}\n")


def step(num, text):
    print(f"[{num}] {text}")


def ok(text):
    print(f"  OK: {text}")


def warn(text):
    print(f"  WARN: {text}")


def pull_images():
    title("拉取基础镜像 (DaoCloud 镜像源)")

    # 确保未限定镜像名也走 DaoCloud（如 compose 文件中的 minio/minio）
    _ensure_registries_config()

    local = get_local_images()
    for i, (pull_url, local_tag) in enumerate(IMAGES, 1):
        if local_tag in local:
            print(f"[{i}] {local_tag} - already exists, skipped")
        else:
            print(f"[{i}] Pulling {local_tag} ...")
            run(f"podman pull {pull_url}")
            run(f"podman tag {pull_url} {local_tag}", silent=True)
            ok(f"{local_tag} pulled")
    print()


def _ensure_registries_config():
    """验证所有 compose 文件的 image 引用是否使用 localhost/ 标签。

    localhost/ 镜像由 IMAGES 列表提前从 DaoCloud 拉取并打标，无需在 compose
    启动时联网。如果是未限定镜像名（如 minio/minio），Podman 会 fallback 到
    docker.io 导致 GFW 超时。

    此函数只检查、不写入 —— 修复应直接在 compose 文件中把镜像名改为 localhost/ 前缀。
    """
    import glob as _glob
    compose_dir = os.path.join(MONOREPO_ROOT, "docker")
    external_refs = []
    for yml in _glob.glob(os.path.join(compose_dir, "*.yml")):
        with open(yml, encoding="utf-8") as f:
            for num, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped.startswith("image:") and ":" in stripped:
                    img = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                    if img and not img.startswith("localhost/") and not img.startswith("${"):
                        external_refs.append(f"  {os.path.basename(yml)}:{num} → image: {img}")
    if external_refs:
        warn("以下 compose 文件引用了未限定镜像名（不走 DaoCloud）:")
        for ref in external_refs:
            print(ref)
        warn("请在 compose 文件中改为 localhost/ 前缀（如 minio/minio → localhost/minio）")
    else:
        ok("所有 compose 镜像引用均使用 localhost/ 标签（优先走 DaoCloud）")


def check_missing_images():
    local = get_local_images()
    missing = [tag for _, tag in IMAGES if tag not in local]
    if missing:
        warn(f"缺少镜像: {', '.join(missing)}")
        print("  正在拉取...")
        pull_images()
    # 检查自定义基础镜像是否存在，不存在则构建
    build_base_images()


def build_base_images(force=False):
    """构建自定义基础镜像（如 node-base:24）

    这些镜像在上游镜像之上加装工具链（python3/make/g++/pnpm），
    供其他项目的 Dockerfile 作为 FROM 目标使用。
    """
    local = get_local_images()
    for item in BASE_BUILD_IMAGES:
        tag = item["tag"]
        if not force and tag in local:
            continue
        print(f"  构建基础镜像: {tag} ({item['desc']})")
        rc = _build_image(tag, os.path.join(MONOREPO_ROOT, item["dockerfile"]),
                          os.path.join(MONOREPO_ROOT, item["context"]))
        if rc == 0:
            ok(f"{tag} 构建成功")
        else:
            warn(f"{tag} 构建失败 (返回码 {rc})")


def show_status():
    title("容器状态")
    run(["podman", "ps", "-a", "--filter", "name=graphiti",
         "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"])


def show_urls():
    print(f"{'='*40}")
    print(f"  服务访问地址")
    print(f"{'='*40}")
    print(f"""
  前端界面:  http://localhost:80
  后端 API:  http://localhost:8000
  API 文档:  http://localhost:8000/docs
  健康检查:  http://localhost:8000/health
  Neo4j:     http://localhost:7474
  OPA:       http://localhost:8181
  Redis:     localhost:6379
  MinIO 控制台: http://localhost:9001
  MinIO API:    http://localhost:9000
""")


def cmd_up():
    title("启动 Graphiti 服务 (生产模式)")

    step(1, "检查并停止开发环境冲突容器")
    stop_opposing_env("prod")
    ok("开发环境已清理")

    step(2, "检查基础镜像")
    check_missing_images()
    if not any(c not in get_local_images() for _, c in IMAGES):
        ok("所有基础镜像已就绪")

    step(3, "构建并启动服务 (podman-compose + Windows 路径修复)")
    rc = run_stream(get_compose_cmd("up", "-d", "--build"))
    if rc == 0:
        ok("build 成功")
    else:
        warn(f"返回码 {rc}，继续...")

    step(4, "清理 dangling 镜像")
    _prune_dangling_images()

    step(5, "等待服务就绪 (15秒)")
    time.sleep(15)

    show_status()
    show_urls()


def cmd_dev():
    title("启动 Graphiti 服务 (开发模式 - 热重载)")

    step(1, "检查并停止生产环境冲突容器")
    stop_opposing_env("dev")
    ok("生产环境已清理")

    step(2, "检查基础镜像")
    check_missing_images()
    if not any(c not in get_local_images() for _, c in IMAGES):
        ok("所有基础镜像已就绪")

    step(3, "启动服务 (开发模式 - 独立 compose + 跳过 build 复用本地镜像)")
    # 跳过 --build: 复用本地 docker_app:latest + docker_frontend:dev 镜像
    # 通过 bind mount 源代码实现热重载，启动速度 < 30s
    rc = run_stream(get_compose_cmd("up", "-d", dev=True))
    if rc == 0:
        ok("启动成功")
    else:
        warn(f"返回码 {rc}，继续...")

    step(4, "清理 dangling 镜像")
    _prune_dangling_images()

    step(5, "等待服务就绪 (10秒)")
    time.sleep(10)

    show_status()
    print(f"{'='*40}")
    print(f"  开发模式服务访问地址")
    print(f"{'='*40}")
    print(f"""
  前端界面:  http://localhost:5173  (支持热重载)
  后端 API:  http://localhost:8000
  API 文档:  http://localhost:8000/docs
  健康检查:  http://localhost:8000/health
  Neo4j:     http://localhost:7474
  OPA:       http://localhost:8181
  Redis:     localhost:6379

  开发模式特性:
  - 前端代码修改后自动刷新浏览器
  - 后端代码修改后 uvicorn --reload 自动重载
  - 无需重新构建镜像
  - 适合日常开发调试

  代码修改后:
  - 前端: 无需操作，Vite 自动 HMR
  - 后端: uvicorn --reload 检测文件变化自动重启
""")


def cmd_down():
    title("停止 Graphiti 服务")
    # 停止开发环境
    run(get_compose_cmd("down", dev=True))
    # 同时停止生产环境
    run(get_compose_cmd("down", dev=False), silent=True)
    # 兜底：强制移除所有已知容器（清理 compose down 遗留的网络错误容器）
    stop_containers(CONTAINERS, silent=True)
    ok("所有服务已停止")


def cmd_restart(dev_mode=False):
    cmd_down()
    if dev_mode:
        cmd_dev()
    else:
        cmd_up()


def cmd_restart_dev():
    """重启开发环境"""
    cmd_down()
    cmd_dev()


def _prune_dangling_images(silent=True):
    """清理 dangling 镜像（<none>:<none>），防止构建时旧镜像失去 tag 后堆积"""
    result = subprocess.run(
        ["podman", "images", "--filter", "dangling=true", "--format", "{{.ID}}"],
        capture_output=True, text=True
    )
    dangling_ids = result.stdout.strip().split("\n") if result.stdout.strip() else []
    if dangling_ids:
        for img_id in dangling_ids:
            run(f"podman rmi -f {img_id}", silent=silent)
        if not silent:
            ok(f"已清理 {len(dangling_ids)} 个 dangling 镜像")


def _build_image(image_tag, dockerfile, context_dir):
    """构建单个 Podman 镜像，返回 returncode"""
    return run_stream([
        "podman", "build",
        "-t", image_tag,
        "-f", dockerfile,
        context_dir,
    ])


_REBUILD_TARGETS = {
    "node-base": {
        "tag": "localhost/node-base:24",
        "dockerfile": "docker/Dockerfile.node-base",
        "context": ".",
        "desc": "Node 24 基础镜像 (含 python3/make/g++/pnpm9)",
    },
    "main": {
        "tag": "localhost/docker_app:latest",
        "dockerfile": "docker/Dockerfile",
        "context": ".",
        "desc": "后端镜像 (dev/prod 共用)",
    },
    "frontend": {
        "tag": "localhost/docker_frontend:dev",
        "dockerfile": "frontend/Dockerfile.dev",
        "context": "frontend",
        "desc": "前端 dev 镜像 (Vite 热重载)",
    },
    "frontend-prod": {
        "tag": "localhost/docker_frontend:latest",
        "dockerfile": "frontend/Dockerfile",
        "context": "frontend",
        "desc": "前端 prod 镜像 (Nginx 静态)",
    },
}


def cmd_rebuild(target=""):
    """重建镜像（只构建，不启动）

    target 指定构建哪个镜像，构建完成后提示用户自行执行 dev / up 启动。

    可用 target:
        main            重建后端镜像 docker_app:latest (dev/prod 共用)
        frontend        重建前端 dev 镜像 docker_frontend:dev (Vite 热重载)
        frontend-prod   重建前端 prod 镜像 docker_frontend:latest (Nginx 静态)
        all             重建以上全部三个镜像
        "" (无参数)     等同 all
    """
    target = (target or "all").lower()

    if target == "all":
        targets = ["main", "frontend", "frontend-prod"]
    elif target in _REBUILD_TARGETS:
        targets = [target]
    else:
        print(f"[ERROR] 未知 rebuild 目标: {target!r}")
        print(f"  可用: {', '.join(_REBUILD_TARGETS.keys())}, all")
        sys.exit(1)

    title(f"重建镜像 ({', '.join(targets)})")

    step(1, "停止运行中的容器")
    cmd_down()

    step(2, "清理旧镜像")
    for t in targets:
        tag = _REBUILD_TARGETS[t]["tag"]
        run(f"podman rmi {tag}", silent=True)
    _prune_dangling_images(silent=True)
    ok("旧镜像已清理")

    for i, t in enumerate(targets, 1):
        info = _REBUILD_TARGETS[t]
        step(2 + i, f"构建 {t}: {info['desc']}")
        rc = _build_image(
            info["tag"],
            os.path.join(MONOREPO_ROOT, info["dockerfile"]),
            os.path.join(MONOREPO_ROOT, info["context"]),
        )
        if rc != 0:
            warn(f"{t} 构建失败 (返回码 {rc})，中止")
            return
        ok(f"{info['tag']} 构建成功")

    _prune_dangling_images(silent=True)

    print()
    print(f"{'='*40}")
    print(f"  镜像构建完成")
    print(f"{'='*40}")
    print(f"""
  启动开发模式:  python bootstep.py dev
  启动生产模式:  python bootstep.py up
""")


def cmd_status():
    show_status()
    show_urls()


def cmd_logs(service=""):
    svc_lower = service.lower()
    if svc_lower in ("fe", "frontend", "fedev", "fe-dev"):
        target = "graphiti-dev-frontend"
    elif svc_lower in ("feprod", "fe-prod"):
        target = "graphiti-frontend"
    elif svc_lower in ("be", "backend", "app"):
        target = "graphiti-dev-app"
    elif svc_lower in ("beprod", "be-prod", "app-prod"):
        target = "graphiti-main-app"
    elif svc_lower in ("neo4j",):
        target = "graphiti-dev-neo4j"
    elif svc_lower in ("redis", "cache"):
        target = "graphiti-dev-redis"
    elif svc_lower in ("opa", "policy"):
        target = "graphiti-dev-opa"
    elif svc_lower in ("minio", "storage"):
        target = "graphiti-dev-minio"
    else:
        target = "graphiti-dev-app"

    print(f"[INFO] Showing logs for {target} (Ctrl+C to exit)...")
    run_stream(["podman", "logs", "-f", "--tail", "50", target])


def cmd_pull():
    pull_images()


def cmd_clean():
    title("清理 Podman 镜像和资源")

    step(1, "检查 docker.m.daocloud.io 重复镜像")
    result = subprocess.run(
        ["podman", "images", "--format", "{{.Repository}}:{{.Tag}}"],
        capture_output=True, text=True
    )
    all_images = result.stdout.strip().split("\n") if result.stdout.strip() else []
    dao_images = [img for img in all_images if "daocloud" in img]

    if dao_images:
        for img in dao_images:
            print(f"  删除: {img}")
            run(f'podman rmi -f "{img}"', silent=True)
        ok(f"已删除 {len(dao_images)} 个 DaoCloud 重复镜像")
    else:
        ok("无 DaoCloud 重复镜像")

    step(2, "清理 dangling 镜像 (<none>:<none>)")
    result = subprocess.run(
        ["podman", "images", "--filter", "dangling=true", "--format", "{{.ID}}"],
        capture_output=True, text=True
    )
    dangling_ids = result.stdout.strip().split("\n") if result.stdout.strip() else []
    if dangling_ids:
        for img_id in dangling_ids:
            print(f"  删除: {img_id}")
            run(f"podman rmi -f {img_id}", silent=True)
        ok(f"已删除 {len(dangling_ids)} 个 dangling 镜像")
    else:
        ok("无 dangling 镜像")

    step(3, "清理未使用的容器和网络 (prune)")
    run("podman container prune -f", silent=True)
    run("podman network prune -f", silent=True)
    ok("prune 完成")

    step(4, "当前镜像列表")
    run(["podman", "images", "--format", "table {{.Repository}}:{{.Tag}}\t{{.Size}}"])


def print_help():
    print("""
Bootstep - Graphiti 一键启动/停止脚本

用法: python bootstep.py <action> [service]

  up          启动所有服务（生产模式）
  dev         启动开发模式（前端热重载，无需重新构建）
  down        停止所有服务（同时清理 dev + prod 容器）
  restart     重启所有服务（生产模式）
  restart-dev 重启开发环境（先 down 再 dev）
  rebuild     只重建镜像，不启动。可选 target:
                node-base      重建 Node 24 基础镜像 (含 python3/make/g++/pnpm9)
                main           重建后端镜像 (docker_app, dev/prod 共用)
                frontend       重建前端 dev 镜像 (Vite 热重载)
                frontend-prod  重建前端 prod 镜像 (Nginx 静态)
                all            重建以上全部（默认）
  status      查看服务状态
  logs        查看日志（可用: fe/fedev/neo4j/redis/opa/app）
  pull        拉取基础镜像
  clean       清理重复/dangling 镜像和未使用资源

环境隔离说明:
  dev 和 up 使用独立的 compose 文件，互不干扰。
  启动 dev 会自动停止 prod 前端容器，反之亦然。
  down 会同时停止两个环境的所有容器。

示例:
  python bootstep.py dev               # 开发模式启动（推荐日常开发）
  python bootstep.py restart-dev       # 重启开发环境
  python bootstep.py up                # 生产模式启动
  python bootstep.py down              # 停止所有
  python bootstep.py logs fe           # 查看前端日志
  python bootstep.py rebuild frontend  # 重建前端镜像（不启动）
  python bootstep.py rebuild main      # 重建后端镜像（不启动）
  python bootstep.py rebuild           # 重建全部镜像（不启动）
  # rebuild 完成后，执行 dev 或 up 启动服务

开发模式 vs 生产模式:
  开发模式: 前端 Vite 热重载 (http://localhost:5173)，后端 uvicorn --reload
  生产模式: 前端 Nginx 静态 (http://localhost:80)，需 rebuild 更新
""")


def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    action = sys.argv[1].lower()
    extra = sys.argv[2] if len(sys.argv) > 2 else ""

    commands = {
        "up": lambda: cmd_up(),
        "dev": lambda: cmd_dev(),
        "down": lambda: cmd_down(),
        "restart": lambda: cmd_restart(),
        "restart-dev": lambda: cmd_restart_dev(),
        "rebuild": lambda: cmd_rebuild(extra),
        "status": lambda: cmd_status(),
        "logs": lambda: cmd_logs(extra),
        "pull": lambda: cmd_pull(),
        "clean": lambda: cmd_clean(),
    }

    if action in commands:
        commands[action]()
    else:
        print(f"[ERROR] Unknown action: {action}\n")
        print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()