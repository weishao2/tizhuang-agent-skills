#!/usr/bin/env python3
"""Stdlib-only preflight for the local question bank. Safe to run before anything is installed.

Usage: python doctor.py [--vault <dir>]
Prints one JSON object: ok / checks / next_steps. Never modifies anything.
"""
import argparse
import importlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

REQUIRED = (("yaml", "PyYAML"), ("markdown", "Markdown"), ("latex2mathml", "latex2mathml"),
            ("pdfplumber", "pdfplumber"), ("pypdfium2", "pypdfium2"), ("PIL", "Pillow"),
            ("docx", "python-docx"), ("mathml2omml", "mathml2omml"))


def pip_command(python, requirements):
    """A command that survives paths with spaces (e.g. C:\\Program Files\\Python312) when pasted into a terminal."""
    if os.name == "nt":  # PowerShell needs the call operator before a quoted path
        return f'& "{python}" -m pip install -r "{requirements}"'
    return f"{shlex.quote(python)} -m pip install -r {shlex.quote(requirements)}"


def check(name, ok, detail="", fix=""):
    return {"name": name, "ok": bool(ok), "detail": detail, "fix": "" if ok else fix}


def main():
    parser = argparse.ArgumentParser(description="题庄本地题库环境体检（只读）")
    parser.add_argument("--vault")
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    checks = [check("Python 3.10+", sys.version_info >= (3, 10), sys.version.split()[0],
                    "安装 Python 3.10 或更新版本，并为本 skill 建立独立虚拟环境。")]
    missing = []
    for module, package in REQUIRED:
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(package)
    checks.append(check("运行依赖", not missing, "齐全" if not missing else "缺少：" + "、".join(missing),
                        pip_command(sys.executable, str(here / "requirements.txt"))))
    result = {"checks": checks, "python": sys.executable, "status": None}
    if args.vault:
        vault = Path(args.vault)
        initialized = (vault / ".bank/config.json").is_file()
        checks.append(check("题库目录", initialized, str(vault),
                            "题库尚未初始化：python local_bank.py --vault <目录> init；不要对已有的其他资料目录直接初始化。"))
        if initialized and not missing:
            run = subprocess.run([sys.executable, str(here / "local_bank.py"), "--vault", str(vault), "status"],
                                 capture_output=True, text=True, encoding="utf-8", timeout=120)
            try:
                result["status"] = json.loads(run.stdout)
            except ValueError:
                result["status"] = {"ok": False, "error": (run.stderr or run.stdout)[-400:]}
    status = result["status"]
    if args.vault and status is not None and not status.get("ok"):
        checks.append(check("题库读取", False, str(status.get("error", ""))[:300],
                            status.get("hint") or "题库无法读取：先确认目录正确，再运行 local_bank.py status 查看原因。"))
    ok = all(c["ok"] for c in checks)
    steps = [c["fix"] for c in checks if not c["ok"]]
    if isinstance(result["status"], dict) and result["status"].get("ok"):
        steps += result["status"]["result"].get("next_steps", [])
    result.update(ok=ok, next_steps=steps)
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
