#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Filesystem Server (safe-by-default)

Tools:
- list_dir, read_text, write_text, mkdir, mv, rm, stat
- run (optional; disabled by default; strict allowlist + timeouts)

Transports:
- STDIO  (default)
- HTTP   (for ngrok/cloud) when MCP_TRANSPORT=http
- SSE    (when MCP_TRANSPORT=sse)

Env:
- MCP_FS_ROOT: sandbox root (default: ./sandbox)
- MCP_TRANSPORT: stdio|http|sse (default: stdio)
- MCP_HTTP_HOST, MCP_HTTP_PORT, MCP_HTTP_PATH (defaults: 0.0.0.0, 8080, /mcp)
- ENABLE_RUN_COMMANDS: "1" to enable run tool (default: disabled)
"""
from __future__ import annotations
import os, io, glob, shutil, time, subprocess
from typing import List, Dict, Any, Optional
from fastmcp import FastMCP

# ---------- Configuration ----------
ROOT_DIR = os.environ.get("MCP_FS_ROOT", os.path.abspath("./sandbox"))
ENABLE_RUN_COMMANDS = os.environ.get("ENABLE_RUN_COMMANDS", "0") == "1"

ALLOW_GLOBS: List[str] = ["**/*"]
DENY_GLOBS:  List[str] = [
    "**/.env*", "**/.ssh/**", "**/.git/**", "**/node_modules/**", "**/id_*"
]

COMMAND_ALLOWLIST: Dict[str, List[str]] = {
    "bash":   ["-lc"],
    "sh":     ["-lc"],
    "python": ["-V"],
    "pip":    ["--version"],
}
RUN_TIMEOUT_SEC = int(os.environ.get("RUN_TIMEOUT_SEC", "30"))
RUN_MAX_STDOUT  = int(os.environ.get("RUN_MAX_STDOUT", "200000"))

# ---------- Helpers ----------
def ensure_root() -> None:
    os.makedirs(ROOT_DIR, exist_ok=True)

def _abs(path: str) -> str:
    base = os.path.abspath(ROOT_DIR)
    target = os.path.abspath(os.path.join(base, path.lstrip("/\\")))
    if not (target.startswith(base + os.sep) or target == base):
        raise PermissionError("Path escapes sandbox root")
    return target

def _deny_check(abs_path: str) -> None:
    rel = os.path.relpath(abs_path, ROOT_DIR)
    for pat in DENY_GLOBS:
        if glob.fnmatch.fnmatch(rel, pat):
            raise PermissionError(f"Denied by policy: {pat}")

def _allow_check(abs_path: str) -> None:
    rel = os.path.relpath(abs_path, ROOT_DIR)
    if not any(glob.fnmatch.fnmatch(rel, pat) for pat in ALLOW_GLOBS):
        raise PermissionError("Not allowed by policy")

def _policy(abs_path: str) -> None:
    _deny_check(abs_path)
    _allow_check(abs_path)

# ---------- MCP ----------
mcp = FastMCP("mcp-filesystem")

@mcp.tool
def list_dir(path: str = ".", glob_pattern: str = "*", include_hidden: bool = False) -> Dict[str, Any]:
    """List directory entries under sandbox root."""
    ensure_root()
    ap = _abs(path)
    if not os.path.isdir(ap):
        raise FileNotFoundError("Not a directory")
    out = []
    for name in sorted(os.listdir(ap)):
        if not include_hidden and name.startswith("."):  # hide dotfiles unless requested
            continue
        if not glob.fnmatch.fnmatch(name, glob_pattern):
            continue
        fp = os.path.join(ap, name)
        try:
            _policy(fp)
            st = os.lstat(fp)
            out.append({
                "name": name,
                "is_dir": os.path.isdir(fp),
                "size": st.st_size,
                "mode": oct(st.st_mode & 0o777),
                "mtime": int(st.st_mtime),
            })
        except PermissionError:
            continue
    return {"path": os.path.relpath(ap, ROOT_DIR), "entries": out}

@mcp.tool
def read_text(path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """Read a text file."""
    ensure_root()
    ap = _abs(path); _policy(ap)
    if not os.path.isfile(ap):
        raise FileNotFoundError("File not found")
    with io.open(ap, "r", encoding=encoding, errors="strict") as f:
        return {"path": os.path.relpath(ap, ROOT_DIR), "content": f.read()}

@mcp.tool
def write_text(path: str, content: str, create_dirs: bool = True, overwrite: bool = True, encoding: str = "utf-8") -> Dict[str, Any]:
    """Write text to a file (safe under ROOT)."""
    ensure_root()
    ap = _abs(path); _policy(ap)
    d = os.path.dirname(ap)
    if create_dirs:
        os.makedirs(d, exist_ok=True)
    if os.path.exists(ap) and not overwrite:
        raise FileExistsError("File exists and overwrite=False")
    with io.open(ap, "w", encoding=encoding) as f:
        f.write(content)
    return {"written": True, "path": os.path.relpath(ap, ROOT_DIR), "bytes": len(content.encode(encoding))}

@mcp.tool
def mkdir(path: str, parents: bool = True, exist_ok: bool = True) -> Dict[str, Any]:
    """Create a directory under ROOT."""
    ensure_root()
    ap = _abs(path); _policy(ap)
    if parents:
        os.makedirs(ap, exist_ok=exist_ok)
    else:
        os.mkdir(ap)
    return {"created": True, "path": os.path.relpath(ap, ROOT_DIR)}

@mcp.tool
def mv(src: str, dst: str, overwrite: bool = False) -> Dict[str, Any]:
    """Move/rename file/dir within ROOT."""
    ensure_root()
    aps = _abs(src); _policy(aps)
    apd = _abs(dst); _policy(apd)
    os.makedirs(os.path.dirname(apd), exist_ok=True)
    if os.path.exists(apd) and not overwrite:
        raise FileExistsError("Destination exists (overwrite=False)")
    if overwrite and os.path.exists(apd):
        if os.path.isdir(apd) and not os.path.islink(apd):
            shutil.rmtree(apd)
        else:
            os.remove(apd)
    shutil.move(aps, apd)
    return {"moved": True, "src": os.path.relpath(aps, ROOT_DIR), "dst": os.path.relpath(apd, ROOT_DIR)}

@mcp.tool
def rm(path: str, recursive: bool = False) -> Dict[str, Any]:
    """Remove file/dir under ROOT."""
    ensure_root()
    ap = _abs(path); _policy(ap)
    if os.path.isdir(ap) and not os.path.islink(ap):
        if not recursive:
            raise IsADirectoryError("Use recursive=True for directories")
        shutil.rmtree(ap)
    else:
        os.remove(ap)
    return {"removed": True, "path": os.path.relpath(ap, ROOT_DIR)}

@mcp.tool
def stat(path: str) -> Dict[str, Any]:
    """Return basic stat() for a path under ROOT."""
    ensure_root()
    ap = _abs(path); _policy(ap)
    st = os.lstat(ap)
    return {
        "path": os.path.relpath(ap, ROOT_DIR),
        "is_dir": os.path.isdir(ap),
        "size": st.st_size,
        "mode": oct(st.st_mode & 0o777),
        "mtime": int(st.st_mtime),
    }

@mcp.tool
def run(cmd: str, args: Optional[list] = None, cwd: str = ".", timeout_sec: int = RUN_TIMEOUT_SEC) -> Dict[str, Any]:
    """(Optional) Run an allowlisted command with timeouts/stdout cap."""
    if not ENABLE_RUN_COMMANDS:
        raise PermissionError("run() is disabled by server policy")
    ensure_root()
    ap_cwd = _abs(cwd); _policy(ap_cwd)
    base = os.path.basename(cmd)
    prefix = COMMAND_ALLOWLIST.get(base)
    if prefix is None:
        raise PermissionError(f"Command '{base}' not in allowlist")
    final_args = list(args or [])
    if not final_args[:len(prefix)] == prefix:
        raise PermissionError(f"Args must start with {prefix} for '{base}'")
    argv = [cmd] + final_args
    start = time.time()
    try:
        proc = subprocess.Popen(
            argv, cwd=ap_cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False
        )
        try:
            out, err = proc.communicate(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
            return {"ok": False, "error": "timeout", "stdout": (out or "")[:RUN_MAX_STDOUT], "stderr": (err or "")[:RUN_MAX_STDOUT], "rc": None}
        return {
            "ok": proc.returncode == 0,
            "rc": proc.returncode,
            "stdout": (out or "")[:RUN_MAX_STDOUT],
            "stderr": (err or "")[:RUN_MAX_STDOUT],
            "elapsed_sec": round(time.time() - start, 3),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    # Choose transport by env:
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport == "http":
        host = os.environ.get("MCP_HTTP_HOST", "0.0.0.0")
        port = int(os.environ.get("MCP_HTTP_PORT", "8080"))
        path = os.environ.get("MCP_HTTP_PATH", "/mcp")
        mcp.run(transport="http", host=host, port=port, path=path)
    elif transport == "sse":
        host = os.environ.get("MCP_HTTP_HOST", "0.0.0.0")
        port = int(os.environ.get("MCP_HTTP_PORT", "8080"))
        mcp.run(transport="sse", host=host, port=port)
    else:
        mcp.run()  # stdio
