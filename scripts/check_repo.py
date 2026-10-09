"""Check Git-selected files without printing credential contents."""
from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SECRET = re.compile(
    r"(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}|"
    r"AIza[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|"
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)]+)\)")


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def check(staged: bool) -> list[str]:
    names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z") if staged else git("ls-files", "-z")
    errors: list[str] = []
    for raw in names.split(b"\0"):
        if not raw:
            continue
        name = raw.decode("utf-8")
        path = PurePosixPath(name)
        base = path.name.lower()
        if ((base == ".env" or base.startswith(".env.") or base.endswith(".env")) and base != ".env.example") or path.suffix.lower() in {".pem", ".key"} or base == "auth.json" or base.startswith("storage-state") or ".auth" in path.parts:
            errors.append(f"{name}: forbidden credential path")
        if path.parts[0] in {"runs", ".venv"}:
            errors.append(f"{name}: generated/private artifact must not be tracked")
        data = git("show", f":{name}") if staged else (ROOT / name).read_bytes()
        if b"\0" in data:
            continue
        text = data.decode("utf-8", errors="replace")
        if SECRET.search(text):
            errors.append(f"{name}: possible credential content")
        if any(len(secret) >= 12 and secret in text for key, secret in os.environ.items()
               if key.endswith(("_API_KEY", "_TOKEN", "_SECRET"))):
            errors.append(f"{name}: environment credential content")
        if base == ".env.example":
            for line in text.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    if stripped.split("=", 1)[1].strip().strip("\"'"):
                        errors.append(f"{name}: example variables must be empty")
                        break
        if path.suffix.lower() != ".md":
            continue
        # Examples inside fenced code blocks are not actual document navigation.
        visible = re.sub(r"```[\s\S]*?```", "", text)
        for target in LINK.findall(visible):
            target = target.strip().strip("<>").split("#", 1)[0]
            if not target or re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", target) or target.startswith("/"):
                continue
            if not (ROOT / path.parent / unquote(target)).exists():
                errors.append(f"{name}: broken local link {target}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true", help="check staged content instead of tracked worktree files")
    args = parser.parse_args()
    errors = check(args.staged)
    for error in errors:
        print(error)
    print(f"Repository check: {'FAIL' if errors else 'PASS'} ({len(errors)} problems)")
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
