"""Daemon IPC plumbing. AF_UNIX socket on POSIX (macOS — only platform we run on for v0).

Adapted from browser-harness/_ipc.py. We dropped Windows TCP+token branch — the
agent that drives a physical iPhone runs on a Mac. If we ever need Linux for a
remote ssh-attached phone, AF_UNIX still works.
"""
import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

# AF_UNIX sun_path on macOS is 104 bytes. /tmp keeps the path short; macOS's
# tempfile.gettempdir() returns /var/folders/... which is too long for AF_UNIX.
IPH_TMP_DIR = os.environ.get("IPH_TMP_DIR")
IPH_RUNTIME_DIR = os.environ.get("IPH_RUNTIME_DIR") or IPH_TMP_DIR
_TMP = Path(IPH_TMP_DIR or "/tmp")
_RUNTIME = Path(IPH_RUNTIME_DIR or "/tmp")
_TMP.mkdir(parents=True, exist_ok=True)
_RUNTIME.mkdir(parents=True, exist_ok=True)
_NAME_RE = re.compile(r"\A[A-Za-z0-9_-]{1,64}\Z")


def _check(name):
    if not _NAME_RE.match(name or ""):
        raise ValueError(f"invalid IPH_NAME {name!r}: must match [A-Za-z0-9_-]{{1,64}}")
    return name


def _runtime_stem(name):
    _check(name)
    return "iph" if IPH_RUNTIME_DIR else f"iph-{name}"


def _tmp_stem(name):
    _check(name)
    return "iph" if IPH_TMP_DIR else f"iph-{name}"


def log_path(name):    return _TMP / f"{_tmp_stem(name)}.log"
def pid_path(name):    return _RUNTIME / f"{_runtime_stem(name)}.pid"
def _sock_path(name):  return _RUNTIME / f"{_runtime_stem(name)}.sock"


def sock_addr(name):
    return str(_sock_path(name))


def spawn_kwargs():
    # Detach the daemon from this terminal so closing the parent shell doesn't kill it.
    return {"start_new_session": True}


def connect(name, timeout=1.0):
    """Blocking client. Returns (sock, token); token is always None on POSIX."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(str(_sock_path(name)))
    return s, None


def request(c, token, req):
    """One-shot send + recv + parse on an open socket. Caller closes the socket."""
    if token:
        req = {**req, "token": token}
    c.sendall((json.dumps(req) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = c.recv(1 << 16)
        if not chunk:
            break
        data += chunk
    return json.loads(data or b"{}")


def ping(name, timeout=1.0):
    """True iff a live daemon answers our ping. A stale .sock or unrelated
    listener won't reply with the right shape — never trust a bare connect."""
    try:
        c, token = connect(name, timeout=timeout)
    except (FileNotFoundError, ConnectionRefusedError, TimeoutError, socket.timeout, OSError):
        return False
    try:
        resp = request(c, token, {"meta": "ping"})
        return isinstance(resp, dict) and resp.get("pong") is True
    except (OSError, ValueError, AttributeError):
        return False
    finally:
        try: c.close()
        except OSError: pass


def identify(name, timeout=1.0):
    """Return the live daemon's PID, or None if unreachable."""
    try:
        c, token = connect(name, timeout=timeout)
    except (FileNotFoundError, ConnectionRefusedError, TimeoutError, socket.timeout, OSError):
        return None
    try:
        resp = request(c, token, {"meta": "ping"})
        if not isinstance(resp, dict) or resp.get("pong") is not True:
            return None
        pid = resp.get("pid")
        # Reject bool (isinstance(True, int) is True), 0, negatives, and absurd values.
        return pid if type(pid) is int and 0 < pid < (1 << 31) else None
    except (OSError, ValueError, AttributeError):
        return None
    finally:
        try: c.close()
        except OSError: pass


async def serve(name, handler):
    """Run the AF_UNIX server until cancelled."""
    path = str(_sock_path(name))
    if os.path.exists(path):
        os.unlink(path)
    # umask 0o077 makes bind() create the socket as 0600 — no TOCTOU window before chmod.
    old_umask = os.umask(0o077)
    try:
        server = await asyncio.start_unix_server(handler, path=path)
    finally:
        os.umask(old_umask)
    async with server:
        await asyncio.Event().wait()


def expected_token():
    """Always None on POSIX — AF_UNIX + chmod 600 is the boundary."""
    return None


def cleanup_endpoint(name):
    p = _sock_path(name)
    try: p.unlink()
    except FileNotFoundError: pass
