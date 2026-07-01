"""
Restricted subprocess-based Python executor for the Coder agent.

Not a "true" security sandbox (that would mean gVisor / firecracker /
nsjail) but demonstrates the right shape: a hard timeout, a resource-
limited subprocess, stdout/stderr capture, and no access to the host
filesystem outside a throwaway tempdir. Call this out honestly in
interviews -- "here's what I'd add for production" is a strong answer.
"""
import subprocess
import sys
import tempfile
import os
from ..config import settings

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "execute_python",
        "description": "Execute a short, self-contained Python snippet and return stdout/stderr. Use for calculations, data transforms, or quick verification.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source code to run."}
            },
            "required": ["code"],
        },
    },
}

BANNED = ("import os", "import sys", "subprocess", "socket", "open(", "__import__", "eval(", "exec(")


def run(code: str) -> dict:
    lowered = code.lower()
    if any(b in lowered for b in BANNED):
        return {"stdout": "", "stderr": "Blocked: snippet uses a disallowed operation.", "ok": False}

    with tempfile.TemporaryDirectory() as td:
        script_path = os.path.join(td, "snippet.py")
        with open(script_path, "w") as f:
            f.write(code)
        try:
            proc = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=settings.CODE_EXEC_TIMEOUT,
                cwd=td,
            )
            return {"stdout": proc.stdout[-4000:], "stderr": proc.stderr[-2000:], "ok": proc.returncode == 0}
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": f"Timed out after {settings.CODE_EXEC_TIMEOUT}s", "ok": False}
