"""Appium WebDriver session holder + IPC relay (AF_UNIX, one daemon per IPH_NAME).

This is the iPhone analogue of browser-harness's daemon. Same shape:
  - long-lived process
  - owns one Appium Remote() session to the device via WDA
  - exposes a JSON-line RPC over AF_UNIX
  - auto-recovers from stale sessions (Appium kills idle sessions after ~60s)

Helpers (helpers.py) are stateless functions that marshal each call into JSON
and send it here. The daemon does the actual driver call and returns the result.
"""
import asyncio
import functools
import json
import os
import sys
import time
from pathlib import Path

from . import _ipc as ipc


def _load_env():
    repo_root = Path(__file__).resolve().parents[2]
    workspace = Path(os.environ.get("IPH_AGENT_WORKSPACE", repo_root / "agent-workspace")).expanduser()
    for p in (repo_root / ".env", workspace / ".env"):
        if not p.exists():
            continue
        _load_env_file(p)


def _load_env_file(p):
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

NAME = os.environ.get("IPH_NAME", "default")
SOCK = ipc.sock_addr(NAME)
LOG = str(ipc.log_path(NAME))
PID = str(ipc.pid_path(NAME))

APPIUM_URL = os.environ.get("IPH_APPIUM_URL", "http://127.0.0.1:4723")
UDID = os.environ.get("IPH_UDID")
PLATFORM_VERSION = os.environ.get("IPH_PLATFORM_VERSION")
DEVICE_NAME = os.environ.get("IPH_DEVICE_NAME", "iPhone")
XCODE_ORG_ID = os.environ.get("IPH_XCODE_ORG_ID")
XCODE_SIGNING_ID = os.environ.get("IPH_XCODE_SIGNING_ID", "Apple Development")
WDA_BUNDLE_ID = os.environ.get("IPH_WDA_BUNDLE_ID")
# Idle session timeout (seconds). Appium's default is 60s; bump it so quiet
# stretches between agent calls don't kill the session under us.
NEW_COMMAND_TIMEOUT = int(os.environ.get("IPH_NEW_COMMAND_TIMEOUT", "600"))


def log(msg):
    open(LOG, "a").write(f"{time.strftime('%H:%M:%S')} {msg}\n")


def _build_options():
    """XCUITestOptions for the current device. Lazy import — appium is only needed in the daemon process."""
    from appium.options.ios import XCUITestOptions
    if not UDID:
        raise RuntimeError(
            "IPH_UDID not set. Plug in the iPhone and either:\n"
            "  - export IPH_UDID=<udid>  (find via `idevice_id -l` or `xcrun xctrace list devices`)\n"
            "  - put IPH_UDID=<udid> in <iphone-harness>/.env or <agent-workspace>/.env"
        )
    o = XCUITestOptions()
    o.platform_name = "iOS"
    o.device_name = DEVICE_NAME
    o.udid = UDID
    if PLATFORM_VERSION:
        o.platform_version = PLATFORM_VERSION
    if XCODE_ORG_ID:
        o.xcode_org_id = XCODE_ORG_ID
        o.xcode_signing_id = XCODE_SIGNING_ID
    if WDA_BUNDLE_ID:
        o.updated_wda_bundle_id = WDA_BUNDLE_ID
    o.set_capability("appium:allowProvisioningDeviceRegistration", True)
    o.set_capability("appium:newCommandTimeout", NEW_COMMAND_TIMEOUT)
    # Don't auto-launch any app. The agent decides what to foreground; otherwise
    # connecting attaches to whatever's already on screen (SpringBoard, etc.).
    o.set_capability("appium:autoLaunch", False)
    return o


class Daemon:
    def __init__(self):
        self.driver = None
        self.stop = None  # asyncio.Event, set inside start()
        # Pool a single thread for blocking driver calls so Appium's HTTP
        # client doesn't fight asyncio's event loop. One driver, one worker.
        self._loop = None

    async def _drive(self, fn):
        """Run a blocking driver callable in the default executor."""
        return await self._loop.run_in_executor(None, fn)

    async def _connect(self):
        """(Re)create the WebDriver session. Retries once on transient Appium errors."""
        from appium import webdriver
        opts = _build_options()
        log(f"connecting to Appium at {APPIUM_URL} (udid={UDID})")
        def _make():
            return webdriver.Remote(APPIUM_URL, options=opts)
        try:
            self.driver = await self._drive(_make)
        except Exception as e:
            raise RuntimeError(
                f"Appium session create failed: {e}\n"
                f"Checks:\n"
                f"  - Is Appium running on {APPIUM_URL}?  (start with: appium --base-path /)\n"
                f"  - Is the iPhone plugged in and unlocked?  (check: idevice_id -l)\n"
                f"  - Is WebDriverAgent trusted on the device?  (Settings → General → VPN & Device Management)\n"
            )
        log(f"session ok ({self.driver.session_id})")

    async def _ensure_session(self):
        """If the driver is alive, no-op. Else (re)create."""
        if self.driver is None:
            await self._connect()
            return
        # Cheap liveness probe: ask for session_id. If the session was killed
        # by Appium's idle timeout or a WDA crash, this raises.
        try:
            await self._drive(lambda: self.driver.session_id)
            # session_id is just an attribute; do one harmless real call to be sure.
            await self._drive(lambda: self.driver.execute_script("mobile: activeAppInfo", {}))
        except Exception as e:
            log(f"stale session, reconnecting: {e}")
            try:
                await self._drive(self.driver.quit)
            except Exception:
                pass
            self.driver = None
            await self._connect()

    async def start(self):
        self.stop = asyncio.Event()
        self._loop = asyncio.get_running_loop()
        await self._connect()

    # ---- request handlers ----

    async def handle(self, req):
        meta = req.get("meta")
        if meta == "ping":          return {"pong": True, "pid": os.getpid()}
        if meta == "shutdown":      self.stop.set(); return {"ok": True}
        if meta == "session":       return {"session_id": self.driver.session_id if self.driver else None}

        method = req.get("method")
        if not method:
            return {"error": "missing method"}

        try:
            await self._ensure_session()
        except Exception as e:
            return {"error": str(e)}

        # Each method is a small dispatch. Helpers send {method: "...", params: {...}}.
        params = req.get("params") or {}
        try:
            handler = _DISPATCH.get(method)
            if handler is None:
                return {"error": f"unknown method: {method}"}
            result = await handler(self, params)
            return {"result": result}
        except Exception as e:
            return {"error": f"{method}: {e}"}


# ---- method dispatch -------------------------------------------------------

async def _m_appium(d, params):
    """Raw Appium escape hatch. params: {script, args}.
    `script` is e.g. 'mobile: tap', 'mobile: launchApp', any execute-script the
    XCUITest driver supports. Mirrors browser-harness's cdp() public escape."""
    script = params["script"]
    args = params.get("args", {})
    return await d._drive(lambda: d.driver.execute_script(script, args))


async def _m_screenshot(d, params):
    """Save a PNG screenshot to `path` (or a default tmp path). Returns path."""
    path = params.get("path") or str(ipc._TMP / "iph-shot.png")
    png = await d._drive(d.driver.get_screenshot_as_png)
    with open(path, "wb") as f:
        f.write(png)
    return {"path": path, "bytes": len(png)}


async def _m_page_source(d, params):
    """Raw XML UI tree from WebDriverAgent. Helpers parse it client-side."""
    return await d._drive(lambda: d.driver.page_source)


async def _m_window_size(d, params):
    sz = await d._drive(d.driver.get_window_size)
    return {"width": sz["width"], "height": sz["height"]}


async def _m_click_element(d, params):
    """Find an element by NSPredicate and call WebElement.click() — the real
    WebDriver click, which dispatches a proper UI gesture (handles iOS apps
    that ignore synthetic `mobile: tap` events).

    params: {predicate: str, index: int = 0}
    """
    from appium.webdriver.common.appiumby import AppiumBy
    pred = params["predicate"]
    index = params.get("index", 0)
    def _do():
        elements = d.driver.find_elements(AppiumBy.IOS_PREDICATE, pred)
        if not elements:
            raise RuntimeError(f"no element matched predicate: {pred!r}")
        elements[index].click()
        return {"matched": len(elements)}
    return await d._drive(_do)


async def _m_send_keys(d, params):
    """Find an element by `predicate` (iOS NSPredicate) and send `keys` to it.

    Used for picker wheels (which accept their target value as a string),
    text fields where setting `.value` is more reliable than tap+type, and any
    other element XCUITest can locate but our coordinate-based helpers can't drive.

    params: {predicate: str, keys: str, index: int = 0}
    """
    from appium.webdriver.common.appiumby import AppiumBy
    pred = params["predicate"]
    keys = params["keys"]
    index = params.get("index", 0)
    def _do():
        elements = d.driver.find_elements(AppiumBy.IOS_PREDICATE, pred)
        if not elements:
            raise RuntimeError(f"no element matched predicate: {pred!r}")
        el = elements[index]
        el.send_keys(keys)
        return {"sent": keys, "matched": len(elements)}
    return await d._drive(_do)


async def _m_pick_wheel(d, params):
    """Drive a picker wheel iteratively until its value matches `target` substring.

    XCUITest's `mobile: selectPickerWheelValue` nudges the wheel one row at a
    time in the requested direction until the value contains `target` (or the
    safety limit is hit). Reliable for date/time pickers.

    params: {predicate: str, target: str, index: int = 0,
             direction: 'next'|'previous' = 'next',
             offset: float = 0.15, max_attempts: int = 30}
    """
    from appium.webdriver.common.appiumby import AppiumBy
    pred = params["predicate"]
    target = str(params["target"])
    index = params.get("index", 0)
    direction = params.get("direction", "next")
    offset = float(params.get("offset", 0.15))
    max_attempts = int(params.get("max_attempts", 30))
    def _do():
        elements = d.driver.find_elements(AppiumBy.IOS_PREDICATE, pred)
        if not elements:
            raise RuntimeError(f"no picker matched: {pred!r}")
        el = elements[index]
        for i in range(max_attempts):
            cur = el.get_attribute("value") or ""
            if target in cur:
                return {"value": cur, "attempts": i}
            d.driver.execute_script("mobile: selectPickerWheelValue", {
                "elementId": el.id, "order": direction, "offset": offset,
            })
        cur = el.get_attribute("value") or ""
        return {"value": cur, "attempts": max_attempts, "matched": target in cur}
    return await d._drive(_do)


async def _m_set_value(d, params):
    """Atomic value replace via XCUITest. Falls back across Selenium versions.

    params: {predicate: str, value: str, index: int = 0}
    """
    from appium.webdriver.common.appiumby import AppiumBy
    pred = params["predicate"]
    value = params["value"]
    index = params.get("index", 0)
    def _do():
        elements = d.driver.find_elements(AppiumBy.IOS_PREDICATE, pred)
        if not elements:
            raise RuntimeError(f"no element matched predicate: {pred!r}")
        el = elements[index]
        # Selenium 4.x removed Element.set_value(); use the `mobile: setValue`
        # execute-script with the element's UUID instead.
        try:
            d.driver.execute_script("mobile: setValue", {"elementId": el.id, "text": value})
        except Exception:
            # Last fallback: clear + send_keys.
            try:
                el.clear()
            except Exception:
                pass
            el.send_keys(value)
        return {"set": value, "matched": len(elements)}
    return await d._drive(_do)


_DISPATCH = {
    # Generic XCUITest escape hatch — covers everything `mobile: ...` exposes.
    "appium":         _m_appium,
    # Perception (need raw bytes / parsed XML, not just JSON).
    "screenshot":     _m_screenshot,
    "page_source":    _m_page_source,
    "window_size":    _m_window_size,
    # Element-level operations that need a real WebElement (can't be done via execute-script).
    "click_element":  _m_click_element,
    "send_keys":      _m_send_keys,
    "set_value":      _m_set_value,
    "pick_wheel":     _m_pick_wheel,
}


# ---- server loop -----------------------------------------------------------

async def serve(d):
    async def handler(reader, writer):
        try:
            line = await reader.readline()
            if not line:
                return
            resp = await d.handle(json.loads(line))
            writer.write((json.dumps(resp, default=str) + "\n").encode())
            await writer.drain()
        except Exception as e:
            log(f"conn: {e}")
            try:
                writer.write((json.dumps({"error": str(e)}) + "\n").encode())
                await writer.drain()
            except Exception:
                pass
        finally:
            writer.close()

    serve_task = asyncio.create_task(ipc.serve(NAME, handler))
    stop_task = asyncio.create_task(d.stop.wait())
    await asyncio.sleep(0.05)
    log(f"listening on {ipc.sock_addr(NAME)} (name={NAME})")
    try:
        await asyncio.wait({serve_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
        if serve_task.done():
            await serve_task
    finally:
        for t in (serve_task, stop_task):
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        ipc.cleanup_endpoint(NAME)


async def main():
    d = Daemon()
    await d.start()
    await serve(d)


def already_running():
    return ipc.ping(NAME, timeout=1.0)


if __name__ == "__main__":
    if already_running():
        print(f"daemon already running on {SOCK}", file=sys.stderr)
        sys.exit(0)
    open(LOG, "w").close()
    open(PID, "w").write(str(os.getpid()))
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log(f"fatal: {e}")
        sys.exit(1)
    finally:
        try: os.unlink(PID)
        except FileNotFoundError: pass
