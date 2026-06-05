#!/usr/bin/env python3
"""
Bootstep - Graphiti 一键启动/停止脚本 (Python CLI)

用法:
    python bootstep.py up        启动所有服务（生产模式）
    python bootstep.py dev       启动开发模式（前端热重载）
    python bootstep.py down      停止所有服务
    python bootstep.py restart   重启所有服务（生产模式）
    python bootstep.py rebuild   重新构建并启动（生产模式）
    python bootstep.py status    查看服务状态
    python bootstep.py logs      查看后端日志
    python bootstep.py logs fe   查看前端日志
    python bootstep.py pull      拉取基础镜像
    python bootstep.py clean     清理重复/dangling 镜像和未使用资源

开发模式说明:
  - 前端使用 Vite 开发服务器，支持热重载
  - 代码修改后自动刷新浏览器，无需重新构建
  - 前端访问: http://localhost:5173
  - 适合日常开发调试

生产模式说明:
  - 前端使用 Nginx 提供静态文件服务
  - 需要重新构建才能更新前端代码
  - 前端访问: http://localhost:80
  - 适合部署和测试
"""

import os
import sys
import time
import subprocess

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DOCKER_DIR = os.path.join(PROJECT_ROOT, "docker")
COMPOSE_FILE = os.path.join(DOCKER_DIR, "docker-compose.yml")
COMPOSE_OVERRIDE = os.path.join(DOCKER_DIR, "docker-compose.override.yml")
WIN_FIX = os.path.join(DOCKER_DIR, "podman-compose-win-fix.py")
MIRROR = "docker.m.daocloud.io"

IMAGES = [
    (f"{MIRROR}/library/redis:6",                     "localhost/redis:6"),
    (f"{MIRROR}/library/neo4j:latest",                "localhost/neo4j:latest"),
    (f"{MIRROR}/openpolicyagent/opa:0.58.0",           "localhost/openpolicyagent/opa:0.58.0"),
    (f"{MIRROR}/library/python:3.10-slim",             "localhost/python:3.10-slim"),
    (f"{MIRROR}/library/node:20-alpine",               "localhost/node:20-alpine"),
    (f"{MIRROR}/library/nginx:alpine",                 "localhost/nginx:alpine"),
    (f"{MIRROR}/minio/minio:latest",                   "localhost/minio:latest"),
]

CONTAINERS = [
    "graphiti-frontend",
    "graphiti-frontend-dev",
    "graphiti-main-app",
    "graphiti-policy-service",
    "graphiti-neo4j",
    "graphiti-cache",
    "graphiti-minio",
]


def run(cmd, cwd=None, silent=False):
    """运行命令并返回 (returncode, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd if isinstance(cmd, list) else cmd,
            cwd=cwd or PROJECT_ROOT,
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
        cwd=cwd or PROJECT_ROOT,
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
    python_exe = sys.executable
    files = [COMPOSE_FILE]
    if dev:
        files.append(COMPOSE_OVERRIDE)
    cmd = [python_exe, WIN_FIX]
    for f in files:
        cmd.extend(["-f", f])
    cmd.extend(args)
    return cmd


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


def check_missing_images():
    local = get_local_images()
    missing = [tag for _, tag in IMAGES if tag not in local]
    if missing:
        warn(f"缺少镜像: {', '.join(missing)}")
        print("  正在拉取...")
        pull_images()


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

    step(1, "检查基础镜像")
    check_missing_images()
    if not any(c not in get_local_images() for _, c in IMAGES):
        ok("所有基础镜像已就绪")

    step(2, "构建并启动服务 (podman-compose + Windows 路径修复)")
    rc = run_stream(get_compose_cmd("up", "-d", "--build"))
    if rc == 0:
        ok("build 成功")
    else:
        warn(f"返回码 {rc}，继续...")

    step(3, "清理 dangling 镜像")
    _prune_dangling_images()

    step(4, "等待服务就绪 (15秒)")
    time.sleep(15)

    show_status()
    show_urls()


def cmd_dev():
    title("启动 Graphiti 服务 (开发模式 - 热重载)")

    step(1, "检查基础镜像")
    check_missing_images()
    if not any(c not in get_local_images() for _, c in IMAGES):
        ok("所有基础镜像已就绪")

    step(2, "构建并启动服务 (开发模式 - override + --build)")
    rc = run_stream(get_compose_cmd("up", "-d", "--build", dev=True))
    if rc == 0:
        ok("启动成功")
    else:
        warn(f"返回码 {rc}，继续...")

    step(3, "清理 dangling 镜像")
    _prune_dangling_images()

    step(4, "等待服务就绪 (10秒)")
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
  - 无需重新构建镜像
  - 适合日常开发调试
""")


def cmd_down():
    title("停止 Graphiti 服务")
    run(get_compose_cmd("down", dev=True))
    ok("所有服务已停止")


def cmd_restart():
    cmd_down()
    cmd_up()


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


def cmd_rebuild():
    title("重建 Graphiti 服务")
    cmd_down()

    step(1, "清理旧镜像")
    run("podman rmi localhost/docker_app:latest", silent=True)
    run("podman rmi localhost/docker_frontend:latest", silent=True)
    _prune_dangling_images(silent=True)
    ok("旧镜像已清理")

    cmd_up()


def cmd_status():
    show_status()
    show_urls()


def cmd_logs(service=""):
    svc_lower = service.lower()
    if svc_lower in ("fe", "frontend"):
        target = "graphiti-frontend"
    elif svc_lower in ("fedev", "frontend-dev", "fe-dev"):
        target = "graphiti-frontend-dev"
    elif svc_lower in ("neo4j",):
        target = "graphiti-neo4j"
    elif svc_lower in ("redis", "cache"):
        target = "graphiti-cache"
    elif svc_lower in ("opa", "policy"):
        target = "graphiti-policy-service"
    elif svc_lower in ("app", "backend"):
        target = "graphiti-main-app"
    elif svc_lower in ("minio", "storage"):
        target = "graphiti-minio"
    else:
        target = "graphiti-main-app"

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

  up        启动所有服务（生产模式）
  dev       启动开发模式（前端热重载，无需重新构建）
  down      停止所有服务
  restart   重启所有服务（生产模式）
  rebuild   重新构建并启动（生产模式）
  status    查看服务状态
  logs      查看日志（可用: fe/fedev/neo4j/redis/opa/app）
  pull      拉取基础镜像
  clean     清理重复/dangling 镜像和未使用资源

示例:
  python bootstep.py up      # 生产模式启动
  python bootstep.py dev     # 开发模式启动（推荐日常开发）
  python bootstep.py down
  python bootstep.py logs fe
  python bootstep.py clean

开发模式 vs 生产模式:
  开发模式: 前端使用 Vite 热重载，代码修改自动刷新，访问 http://localhost:5173
  生产模式: 前端使用 Nginx 静态服务，需要重新构建，访问 http://localhost:80
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
        "rebuild": lambda: cmd_rebuild(),
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