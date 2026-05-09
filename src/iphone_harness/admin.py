"""Daemon lifecycle, doctor, --reload. Mirrors browser-harness/admin.py shape but smaller.

The agent-facing functions are:
  - ensure_daemon()      idempotent — spawns the daemon if not running
  - restart_daemon()     stops the running daemon (next call respawns)
  - run_doctor()         diagnostic: Appium up, device paired, WDA trusted, daemon healthy
"""
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

from . import _ipc as ipc

NAME = os.environ.get("IPH_NAME", "default")
APPIUM_URL = os.environ.get("IPH_APPIUM_URL", "http://127.0.0.1:4723")


def _version():
    try:
        from importlib.metadata import version
        return version("iphone-harness")
    except Exception:
        return None


def daemon_alive(name=None):
    return ipc.ping(name or NAME, timeout=1.0)


def ensure_daemon(wait=30.0, name=None, env=None):
    """Spawn the daemon if no live one is reachable. Idempotent."""
    name = name or NAME
    if daemon_alive(name):
        # Live ping is enough — but verify the Appium-side handshake too. A
        # daemon whose webdriver session died still answers meta:* but errors
        # on real method calls. Probe with `mobile: activeAppInfo` (cheap, real call).
        try:
            s, token = ipc.connect(name, timeout=3.0)
            resp = ipc.request(s, token, {
                "method": "appium",
                "params": {"script": "mobile: activeAppInfo", "args": {}},
            })
            if isinstance(resp, dict) and "result" in resp:
                return
        except Exception:
            pass
        restart_daemon(name)

    e = {**os.environ, **({"IPH_NAME": name} if name else {}), **(env or {})}
    p = subprocess.Popen(
        [sys.executable, "-m", "iphone_harness.daemon"],
        env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        **ipc.spawn_kwargs(),
    )
    deadline = time.time() + wait
    while time.time() < deadline:
        if daemon_alive(name):
            return
        if p.poll() is not None:
            break
        time.sleep(0.2)
    msg = _log_tail(name) or "(no log output)"
    raise RuntimeError(
        f"iphone-harness daemon didn't come up — last log lines:\n{msg}\n"
        f"Run `iphone-harness --doctor` to diagnose."
    )


def _log_tail(name=None, n=30):
    p = ipc.log_path(name or NAME)
    try:
        return "\n".join(p.read_text().splitlines()[-n:])
    except FileNotFoundError:
        return ""


def restart_daemon(name=None):
    """Best-effort daemon shutdown + cleanup. Verifies identity before signaling."""
    name = name or NAME
    pid_path = str(ipc.pid_path(name))

    daemon_pid = ipc.identify(name, timeout=1.0)

    # Step 1: ask the daemon to shut down via IPC if it's reachable.
    if daemon_alive(name):
        try:
            s, _ = ipc.connect(name, timeout=2.0)
            try:
                ipc.request(s, None, {"meta": "shutdown"})
            finally:
                s.close()
        except Exception:
            pass

    # Step 2: wait briefly for it to exit gracefully.
    deadline = time.time() + 3.0
    while time.time() < deadline:
        if not daemon_alive(name):
            break
        time.sleep(0.1)

    # Step 3: if still alive AND we verified identity, escalate to SIGTERM.
    if daemon_alive(name) and daemon_pid:
        try:
            os.kill(daemon_pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        time.sleep(0.5)

    # Step 4: cleanup pid + sock files.
    try: os.unlink(pid_path)
    except FileNotFoundError: pass
    ipc.cleanup_endpoint(name)


# ---- doctor ----------------------------------------------------------------

def _check_appium():
    try:
        with urllib.request.urlopen(f"{APPIUM_URL}/status", timeout=2.0) as r:
            data = r.read().decode()
            return True, data[:200]
    except urllib.error.URLError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


def _check_device():
    udid = os.environ.get("IPH_UDID")
    if not udid:
        return False, "IPH_UDID not set"
    try:
        out = subprocess.check_output(["idevice_id", "-l"], timeout=5.0).decode().strip().splitlines()
        if udid in out:
            return True, f"paired ({udid})"
        return False, f"udid {udid} not in `idevice_id -l`: {out!r}"
    except FileNotFoundError:
        return False, "`idevice_id` not installed (brew install libimobiledevice)"
    except Exception as e:
        return False, str(e)


def run_doctor():
    """Diagnostic. Prints status of each external dependency. Returns 0 on all-green."""
    print(f"iphone-harness {_version() or '(dev)'}\n")
    rc = 0

    print("[1/4] Appium server")
    ok, info = _check_appium()
    print(f"   {'OK' if ok else 'FAIL'}: {APPIUM_URL}  -- {info}")
    if not ok:
        print("   Fix: start Appium with `appium --base-path /` (port 4723).")
        rc = 1

    print("[2/4] Device pairing")
    ok, info = _check_device()
    print(f"   {'OK' if ok else 'FAIL'}: {info}")
    if not ok:
        print("   Fix: plug in iPhone, unlock, and `Trust This Computer` if prompted.")
        rc = 1

    print("[3/4] Daemon")
    if daemon_alive():
        pid = ipc.identify(NAME) or "?"
        print(f"   OK: alive (pid={pid}, sock={ipc.sock_addr(NAME)})")
    else:
        print(f"   not running (will spawn on first `iphone-harness -c`)")

    print("[4/4] Recent daemon log")
    tail = _log_tail()
    if tail:
        for line in tail.splitlines()[-10:]:
            print(f"   {line}")
    else:
        print("   (no log file yet)")

    return rc
