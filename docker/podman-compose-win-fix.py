#!/usr/bin/env python3
"""
podman-compose Windows 路径修复 wrapper

根本原因：
  podman-compose 的 is_context_git_url() 函数使用 urllib.parse.urlparse()
  检测 Git URL，但 Windows 绝对路径（如 E:\\path）的盘符会被误解析为
  URL scheme（scheme='e'），导致函数误判为 Git URL。
  
  这使得 container_to_build_args() 跳过了 Dockerfile 查找和 -f 参数
  添加，直接把 Windows 路径作为 Git URL 传给 podman build，而 podman
  无法在 context 目录中找到 Dockerfile。

  实际上 Podman CLI 在 Windows 上可以正确处理 Windows 路径（自动转换），
  所以只需修复 is_context_git_url() 的误判即可。

修复方式：
  Monkey-patch is_context_git_url()，在检测前先排除 Windows 绝对路径。

使用方式：
  替代 podman-compose 使用：
    python podman-compose-win-fix.py up -d
    python podman-compose-win-fix.py down
    python podman-compose-win-fix.py build
    python podman-compose-win-fix.py ps
"""

import os
import sys
import re

_WIN_DRIVE_RE = re.compile(r'^[a-zA-Z]:[\\/]')

def _is_win_abs_path(path):
    return bool(_WIN_DRIVE_RE.match(path))

def main():
    compose_module_path = None
    for sp in sys.path:
        candidate = os.path.join(sp, "podman_compose.py")
        if os.path.isfile(candidate):
            compose_module_path = candidate
            break

    if not compose_module_path:
        print("Error: podman_compose.py not found in Python path", file=sys.stderr)
        sys.exit(1)

    import importlib.util
    spec = importlib.util.spec_from_file_location("podman_compose", compose_module_path)
    mod = importlib.util.module_from_spec(spec)

    # 必须在 exec_module 前注册到 sys.modules，否则 Python 3.13 的
    # dataclass._is_type() 通过 sys.modules.get(cls.__module__) 查找
    # 模块时会拿到 None，触发 AttributeError。
    sys.modules["podman_compose"] = mod

    spec.loader.exec_module(mod)

    original_is_context_git_url = mod.is_context_git_url

    def patched_is_context_git_url(path):
        if _is_win_abs_path(path):
            return False
        return original_is_context_git_url(path)

    mod.is_context_git_url = patched_is_context_git_url

    sys.argv = [compose_module_path] + sys.argv[1:]

    try:
        mod.main()
    except SystemExit as e:
        sys.exit(e.code)

if __name__ == "__main__":
    main()
