#!/usr/bin/env python3
"""Fix antd v6 @deprecated API usages in frontend/src.

Scopes each rename to the correct antd component's opening JSX tag using a
brace-aware tag scanner, so nested children / other components are untouched.
Run the sibling audit script afterwards to confirm zero remaining findings.
"""
import os
import re

BASE = r"E:\DEMO\AI\ontology-graphiti\frontend"
SRC = os.path.join(BASE, "src")

# ---- brace-aware opening-tag span finder -------------------------------
def tag_spans(text, tag):
    """Return list of (start, end_exclusive) for each `<tag ...>` opening tag."""
    spans = []
    pat = re.compile(r"<" + re.escape(tag) + r"(?!\.)")  # exclude tag.Child
    for m in pat.finditer(text):
        depth = 0
        in_str = None
        k = m.end()
        while k < len(text):
            c = text[k]
            if in_str:
                if c == in_str and text[k - 1] != "\\":
                    in_str = None
                k += 1
                continue
            if c in "\"'`":
                in_str = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            elif c == ">" and depth == 0:
                break
            k += 1
        spans.append((m.start(), k + 1))
    return spans


def simple_rename(span_text, old, new):
    """Rename `old=` -> `new=` inside a single opening tag span."""
    return re.sub(r"\b" + re.escape(old) + r"\s*=", new + "=", span_text)


def fix_alert(span_text):
    t = span_text
    # message= -> title=
    t = simple_rename(t, "message", "title")
    # onClose= -> closable.onClose. Handle `closable onClose={expr}` (boolean shorthand)
    def onclose_sub(m):
        expr = m.group(2)
        # remove the matched onClose, return closable={{ onClose: expr }}
        return "closable={{ onClose: " + expr + " }}"
    # match: closable (bool) followed by onClose={...}  (brace-balanced expr)
    # first isolate the onClose expr with balanced braces
    mo = re.search(r"onClose=(\{)", t)
    if mo:
        start = mo.start() + len("onClose=")
        depth = 0
        j = start
        while j < len(t):
            if t[j] == "{":
                depth += 1
            elif t[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        expr = t[start : j + 1]  # includes braces, e.g. {() => setError('')}
        # strip the outer braces so the handler is the value, not a block
        expr_inner = expr[1:-1] if expr.startswith("{") and expr.endswith("}") else expr
        # remove the onClose={...} token
        t = t[: mo.start()] + t[j + 1 :]
        # now insert into closable
        mc = re.search(r"\bclosable\b(?!\s*=)", t)
        if mc:
            t = t[: mc.start()] + "closable={{ onClose: " + expr_inner + " }}" + t[mc.end() :]
        else:
            mco = re.search(r"closable=\{\s*", t)
            if mco:
                t = t[: mco.end()] + "onClose: " + expr_inner + ", " + t[mco.end() :]
            else:
                # insert before closing '>'
                t = t[:-1].rstrip() + " closable={{ onClose: " + expr_inner + " }} >"
    return t


def fix_card_bodystyle(span_text):
    def repl(m):
        content = m.group(1)
        return "styles={{ body: {" + content + "}}}"
    return re.sub(r"bodyStyle=\{\{(.*?)\}\}", repl, span_text, flags=re.S)


def process_file(path):
    with open(path, encoding="utf-8") as fh:
        original = fh.read()
    text = original
    changed = False

    # Alert: message->title, onClose->closable.onClose
    for s, e in sorted(tag_spans(text, "Alert"), reverse=True):
        new = fix_alert(text[s:e])
        if new != text[s:e]:
            text = text[:s] + new + text[e:]
            changed = True

    # Spin: tip->description
    for s, e in sorted(tag_spans(text, "Spin"), reverse=True):
        new = simple_rename(text[s:e], "tip", "description")
        if new != text[s:e]:
            text = text[:s] + new + text[e:]
            changed = True

    # Card: bodyStyle->styles.body
    for s, e in sorted(tag_spans(text, "Card"), reverse=True):
        new = fix_card_bodystyle(text[s:e])
        if new != text[s:e]:
            text = text[:s] + new + text[e:]
            changed = True

    # Steps / Space: direction->orientation
    for tag in ("Steps", "Space"):
        for s, e in sorted(tag_spans(text, tag), reverse=True):
            new = simple_rename(text[s:e], "direction", "orientation")
            if new != text[s:e]:
                text = text[:s] + new + text[e:]
                changed = True

    if changed:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return True
    return False


def main():
    count = 0
    for root, _d, files in os.walk(SRC):
        for fn in files:
            if not fn.endswith((".tsx", ".ts")):
                continue
            p = os.path.join(root, fn)
            if process_file(p):
                count += 1
                print("FIXED:", os.path.relpath(p, BASE))
    print(f"\nDone. {count} file(s) modified.")


if __name__ == "__main__":
    main()
