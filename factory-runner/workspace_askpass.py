#!/usr/bin/env python3
"""GitHub password helper for a single bounded clone; no command line secrets."""
import os
from pathlib import Path
import sys

prompt = sys.argv[1] if len(sys.argv) > 1 else ""
if "Username" in prompt:
    print("x-access-token")
elif "Password" in prompt:
    target = os.environ.get("FACTORY_GIT_SECRET_FILE", "")
    if not target or not target.startswith("/tmp/factory-git-cred-"):
        raise SystemExit(2)
    path = Path(target)
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise SystemExit(2)
    print(path.read_text(encoding="utf-8"))
else:
    raise SystemExit(2)
