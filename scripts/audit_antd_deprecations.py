#!/usr/bin/env python3
"""Audit frontend/src for usage of antd v6 @deprecated APIs.

Parses node_modules/antd/es/**/*.d.ts for `@deprecated` annotations to learn
the authoritative (component, prop, replacement) list, then scans the codebase
for JSX usages of those props on the matching antd components.
"""
import os
import re
import json

BASE = r"E:\DEMO\AI\ontology-graphiti\frontend"
ANTD_ES = os.path.join(BASE, "node_modules", "antd", "es")
SRC = os.path.join(BASE, "src")

# folder-name -> JSX tag (PascalCase). Most are mechanical; list exceptions.
FOLDER_TO_TAG = {
    "date-picker": "DatePicker",
    "time-picker": "TimePicker",
    "auto-complete": "AutoComplete",
    "input-number": "InputNumber",
    "tree-select": "TreeSelect",
    "float-button": "FloatButton",
    "config-provider": "ConfigProvider",
    "color-picker": "ColorPicker",
    "tree": "Tree",
    "grid": "Grid",  # Row/Col; handled loosely
}


def folder_to_tag(folder: str) -> str:
    if folder in FOLDER_TO_TAG:
        return FOLDER_TO_TAG[folder]
    # generic: Foo-bar -> FooBar, foo -> Foo
    parts = folder.split("-")
    return "".join(p[:1].upper() + p[1:] for p in parts)


def parse_deprecations():
    """Return dict: tag -> list of (prop, replacement_text)."""
    result = {}
    for root, _dirs, files in os.walk(ANTD_ES):
        for fn in files:
            if not fn.endswith(".d.ts"):
                continue
            rel = os.path.relpath(root, ANTD_ES)
            top = rel.split(os.sep)[0]
            tag = folder_to_tag(top)
            path = os.path.join(root, fn)
            try:
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    lines = fh.readlines()
            except Exception:
                continue
            for i, line in enumerate(lines):
                if "@deprecated" not in line:
                    continue
                repl = line.split("@deprecated", 1)[1].strip().strip("*").strip()
                j = i + 1
                while j < len(lines):
                    s = lines[j].strip()
                    if s == "" or s.startswith("*") or s.startswith("//") or s.startswith("/**"):
                        j += 1
                        continue
                    break
                prop_line = lines[j] if j < len(lines) else ""
                m = re.search(r"^\s*([A-Za-z_$][\w$]*)\??\s*[:?]", prop_line)
                prop = m.group(1) if m else None
                if prop and prop not in ("Please", "use", "instead"):
                    result.setdefault(tag, []).append((prop, repl))
    return result


def scan_src(deprecations):
    findings = []
    tag_re = re.compile(r"<([A-Z][\w.]*)\b")
    prop_re = re.compile(r"\b([A-Za-z_$][\w$]*)\s*=")
    for root, _dirs, files in os.walk(SRC):
        for fn in files:
            if not fn.endswith((".tsx", ".ts")):
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except Exception:
                continue
            # split into lines for reporting
            lines = content.splitlines()
            # find each JSX opening tag with its attributes block
            for m in re.finditer(r"<([A-Z][\w.]*)\b([^>]*?)(/?>)", content, re.S):
                tag = m.group(1)
                attrs = m.group(2)
                # Only inspect antd components we have deprecations for
                if tag not in deprecations:
                    continue
                # For shared types (Grid -> Row/Col) skip; too noisy
                for prop, repl in deprecations[tag]:
                    # match prop= as a standalone attribute
                    if re.search(r"(?<![\w.])" + re.escape(prop) + r"\s*=", attrs):
                        line_no = content.count("\n", 0, m.start()) + 1
                        # snippet
                        snippet = lines[line_no - 1].strip() if line_no - 1 < len(lines) else ""
                        findings.append({
                            "file": os.path.relpath(path, BASE),
                            "line": line_no,
                            "tag": tag,
                            "prop": prop,
                            "replacement": repl,
                            "snippet": snippet[:160],
                        })
    return findings


def main():
    deps = parse_deprecations()
    print(f"[info] parsed {sum(len(v) for v in deps.values())} deprecated (component,prop) pairs "
          f"across {len(deps)} components")
    findings = scan_src(deps)
    print(f"[info] found {len(findings)} potential deprecated usages in src\n")
    # group by file
    by_file = {}
    for f in findings:
        by_file.setdefault(f["file"], []).append(f)
    for file, items in sorted(by_file.items()):
        print(f"### {file}")
        for it in items:
            print(f"  L{it['line']}: <{it['tag']} {it['prop']}=>  ({it['replacement']})")
            print(f"        {it['snippet']}")
        print()
    # also dump json
    with open(os.path.join(BASE, "antd_deprecation_audit.json"), "w", encoding="utf-8") as fh:
        json.dump(findings, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
