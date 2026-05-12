"""iPhone control via Appium/XCUITest.

Core helpers live here. Agent-editable helpers live in
IPH_AGENT_WORKSPACE/agent_helpers.py.

Design parallels browser-harness/helpers.py:
  - thin marshalling functions; all real work happens in the daemon
  - coordinate-first interaction (`tap_at_xy`); UI-tree-aware helpers (`find`) for stable labels
  - one public escape hatch: `appium('mobile: ...', **params)` — anything XCUITest supports
"""
import importlib.util
import json
import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from . import _ipc as ipc

CORE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CORE_DIR.parent.parent
AGENT_WORKSPACE = Path(os.environ.get("IPH_AGENT_WORKSPACE", REPO_ROOT / "agent-workspace")).expanduser()


def _load_env():
    for p in (REPO_ROOT / ".env", AGENT_WORKSPACE / ".env"):
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

NAME = os.environ.get("IPH_NAME", "default")


def _send(req, timeout=120.0):
    c, token = ipc.connect(NAME, timeout=timeout)
    try:
        c.settimeout(timeout)  # also extend the recv timeout
        r = ipc.request(c, token, req)
    finally:
        c.close()
    if isinstance(r, dict) and "error" in r:
        raise RuntimeError(r["error"])
    return r


# ---- escape hatch ----------------------------------------------------------

def appium(script, **args):
    """Raw Appium execute-script. Anything XCUITest supports.

    Examples:
        appium('mobile: tap', x=200, y=400)
        appium('mobile: launchApp', bundleId='com.apple.MobileSMS')
        appium('mobile: scroll', direction='down')
        appium('mobile: alert', action='accept')
        appium('mobile: getPasteboard')
    """
    return _send({"method": "appium", "params": {"script": script, "args": args}})["result"]


# ---- perception ------------------------------------------------------------

ASSISTIVE_TOUCH_X = 390
ASSISTIVE_TOUCH_Y = 180


def native_screenshot():
    """Trigger the iPhone's *native* screenshot (the kind that saves to Photos)
    by tapping the AssistiveTouch floating dot configured for Single-Tap=Screenshot.

    This is what you want for any workflow that needs an image *on the iPhone*
    (Instagram post, Messages attachment, etc.) — `screenshot()` saves to the
    Mac's filesystem, but Apple blocks every programmatic path for getting a
    file INTO the device Photos library. The only reliable autonomous path is:

      1. Display the target content on screen
      2. Tap the AssistiveTouch dot — iOS captures the screen, saves to Photos

    Prerequisites (one-time setup):
      - Settings → Accessibility → Touch → AssistiveTouch → On
      - Settings → Accessibility → Touch → AssistiveTouch → Single-Tap → Screenshot
      - Dot positioned at default top-right (about x=390, y=180)

    Use `set_assistive_touch(on=True)` to do this setup programmatically on
    a fresh device, or `set_assistive_touch(on=False)` to clean up after.

    iOS hides the dot from the screenshot it produces, so the saved photo is
    clean — no dot artifact. The dot itself remains visible on screen between
    captures.

    Override `ASSISTIVE_TOUCH_X` / `ASSISTIVE_TOUCH_Y` if you've moved the dot.
    """
    tap_at_xy(ASSISTIVE_TOUCH_X, ASSISTIVE_TOUCH_Y)
    wait(1.0)  # iOS screenshot animation + write-to-Photos delay


def set_assistive_touch(on=True):
    """Enable or disable AssistiveTouch. When enabling, also binds Single-Tap
    to Screenshot so `native_screenshot()` works.

        set_assistive_touch(True)   # turn on + bind to Screenshot
        set_assistive_touch(False)  # turn off (cleanup after task / re-test)

    Idempotent — checks the toggle's current state and only acts when needed.
    Drives Settings → Accessibility → Touch → AssistiveTouch. When `on=True`,
    additionally opens the Single-Tap picker and selects "Screenshot" if not
    already chosen.

    The disable path is useful for end-to-end testing: turn off → reset →
    turn back on to verify the whole setup flow works on a fresh-looking
    device.

    Returns True when the desired state is confirmed; raises RuntimeError if
    any navigation step fails.
    """
    # Terminate first → cold launch lands on Settings root reliably.
    # (Without this, Settings resumes whatever inner page was last open and
    # the back-out loop can dead-end on nav bars that don't have a Settings
    # back button.)
    appium("mobile: terminateApp", bundleId="com.apple.Preferences")
    wait(0.8)
    appium("mobile: launchApp", bundleId="com.apple.Preferences")
    wait(2.5)

    # Settings root → Accessibility (may need a small scroll-up to find it)
    def find_acc():
        return find(label="Accessibility", type="XCUIElementTypeCell") or \
               find(label="Accessibility", type="XCUIElementTypeButton")
    acc = find_acc()
    if acc is None:
        # Scroll up just in case
        scroll_by(dy=300, velocity=400); wait(0.8)
        acc = find_acc()
    if acc is None:
        raise RuntimeError("Couldn't find Accessibility in Settings.")
    tap(acc); wait(2.0)

    # Accessibility → Touch (it lives under PHYSICAL AND MOTOR; usually low on the page)
    def find_touch():
        return find(label="Touch", type="XCUIElementTypeCell")
    touch = find_touch()
    if touch is None:
        scroll_by(dy=-400, velocity=400); wait(0.8)
        touch = find_touch()
    if touch is None:
        raise RuntimeError("Couldn't find Touch row under Accessibility.")
    tap_safe(touch, refind=find_touch); wait(2.0)

    # Touch → AssistiveTouch
    at_row = find(label="AssistiveTouch", type="XCUIElementTypeCell")
    if at_row is None:
        raise RuntimeError("Couldn't find AssistiveTouch row.")
    tap(at_row); wait(2.0)

    # Read the toggle's current state
    sw = find(label="AssistiveTouch", type="XCUIElementTypeSwitch")
    if sw is None:
        raise RuntimeError("Couldn't find AssistiveTouch toggle switch.")
    currently_on = sw.get("value") == "1"
    want_on = bool(on)

    # If we want it OFF and it's currently ON → flip the toggle and return.
    if not want_on:
        if currently_on:
            tap(sw); wait(1.5)
        return True

    # We want it ON. Ensure the toggle is on.
    if not currently_on:
        tap(sw); wait(1.5)

    # Then ensure Single-Tap is bound to Screenshot.
    # If the row's secondary text already says "Screenshot", skip the picker.
    st_row = find(label="Single-Tap", type="XCUIElementTypeCell")
    if st_row is None:
        raise RuntimeError("Couldn't find Single-Tap row under AssistiveTouch.")
    # The row's label includes the currently-selected action when collapsed
    # (e.g. label='Single-Tap, Screenshot'); but Apple's iOS 18 shows the action
    # as a sibling element. Always open the picker and confirm.
    tap(st_row); wait(2.0)

    # Slow-scroll until "Screenshot" is visible (Settings list, alphabetical)
    ss = find(label="Screenshot")
    for _ in range(8):
        if ss: break
        scroll_by(dy=-300, velocity=400); wait(0.8)
        ss = find(label="Screenshot")
    if ss is None:
        raise RuntimeError(
            "Couldn't find 'Screenshot' action in Single-Tap picker — iOS may have "
            "renamed it or removed it on this version."
        )
    tap(ss); wait(1.5)
    return True


def screenshot(path=None):
    """Save a PNG screenshot of the current screen. Returns the path.

    iOS screenshots come back at the device's *physical* pixel resolution; the
    UI tree's coordinates are in *logical points*. Don't use raw screenshot
    pixels for tap coordinates — call `window_size()` and divide.
    """
    r = _send({"method": "screenshot", "params": {"path": path} if path else {}})["result"]
    return r["path"]


def ocr(image_path=None, languages=("en-US",)):
    """Apple Vision OCR on a PNG. macOS-only — uses the system Vision framework
    via PyObjC; no network, no API keys.

    If `image_path` is None, takes a fresh screenshot first. Returns
    `(lines, (width, height))` where each line is:
        {'text': str, 'confidence': float, 'box': [x, y, w, h]}   # pixel coords, top-left origin

    Use this when the accessibility tree doesn't reach the content you need —
    Camera, web views, image-based UIs, custom-drawn views. Pixel boxes are in
    *physical* pixels; divide by devicePixelRatio (= screenshot_w / window_size().w)
    before passing to tap_at_xy().
    """
    if image_path is None:
        image_path = screenshot()
    try:
        import Vision
        from Foundation import NSURL
    except ImportError as e:
        raise RuntimeError(
            "ocr() needs PyObjC (macOS only). Install: pip install pyobjc-framework-Vision"
        ) from e

    url = NSURL.fileURLWithPath_(image_path)
    src = Vision.CIImage.imageWithContentsOfURL_(url)
    if src is None:
        raise RuntimeError(f"could not load image: {image_path}")

    extent = src.extent()
    w_px, h_px = float(extent.size.width), float(extent.size.height)

    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)
    if languages:
        request.setRecognitionLanguages_(list(languages))

    handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(src, None)
    ok, err = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError(f"Vision request failed: {err}")

    out = []
    for obs in request.results() or []:
        cands = obs.topCandidates_(1)
        if not cands:
            continue
        cand = cands[0]
        bb = obs.boundingBox()
        # Vision boxes are normalized, origin bottom-left. Flip to top-left pixel coords.
        x = bb.origin.x * w_px
        wi = bb.size.width * w_px
        hi = bb.size.height * h_px
        y = (1.0 - bb.origin.y - bb.size.height) * h_px
        out.append({
            "text": str(cand.string()),
            "confidence": round(float(cand.confidence()), 3),
            "box": [round(x, 1), round(y, 1), round(wi, 1), round(hi, 1)],
        })
    return out, (int(w_px), int(h_px))


def find_text(query, languages=("en-US",), case_sensitive=False):
    """Run OCR and return the first line whose text matches `query`.
    `query` is a substring (or callable taking the line text). Returns the line
    dict (with `box` in pixel coords) plus a `cx_pt, cy_pt` pair already
    converted to logical points so you can `tap_at_xy(line['cx_pt'], line['cy_pt'])`.
    Returns None if no match.
    """
    lines, (w_px, h_px) = ocr(languages=languages)
    sz = window_size()
    sx = sz["width"] / w_px
    sy = sz["height"] / h_px
    if callable(query):
        match = query
    elif case_sensitive:
        match = lambda t: query in t
    else:
        q = query.lower()
        match = lambda t: q in t.lower()
    for line in lines:
        if match(line["text"]):
            x, y, w, h = line["box"]
            line = dict(line)
            line["cx_pt"] = round((x + w / 2) * sx, 1)
            line["cy_pt"] = round((y + h / 2) * sy, 1)
            return line
    return None


def annotated_screenshot(path=None, run_ocr=True):
    """Save a screenshot with red boxes + numeric labels around either OCR'd text
    lines (run_ocr=True, default) or every visible UI-tree element (run_ocr=False).

    Returns (annotated_path, lines_or_elements). Use this when you want to point
    an LLM at the visual structure of the screen — it's the "indexed elements"
    pattern from the browser-harness world but iPhone-native.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        raise RuntimeError("annotated_screenshot() needs Pillow. Install: pip install pillow") from e

    base = screenshot(path)
    if run_ocr:
        items, (w_px, h_px) = ocr(base)
        boxes = [(it["box"], it.get("text", "")) for it in items]
        result = items
    else:
        sz = window_size()
        sx = Image.open(base).size[0] / sz["width"]
        sy = Image.open(base).size[1] / sz["height"]
        items = ui_tree(visible_only=True)
        boxes = [
            ([el["x"] * sx, el["y"] * sy, el["w"] * sx, el["h"] * sy], el.get("label") or el.get("name") or el["type"])
            for el in items
        ]
        result = items

    img = Image.open(base).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()

    for i, (box, _label) in enumerate(boxes):
        x, y, w, h = box
        x0, y0, x1, y1 = x, y, x + w, y + h
        draw.rectangle([x0, y0, x1, y1], outline=(255, 60, 60, 255), width=2)
        s = str(i)
        tb = draw.textbbox((0, 0), s, font=font)
        lw, lh = tb[2] - tb[0], tb[3] - tb[1]
        pad = 3
        bg = [x0, max(0, y0 - lh - pad * 2), x0 + lw + pad * 2, y0]
        draw.rectangle(bg, fill=(255, 60, 60, 220))
        draw.text((x0 + pad, bg[1] + pad), s, fill=(255, 255, 255, 255), font=font)

    annotated = (path or base).replace(".png", ".annotated.png") if (path or base).endswith(".png") else (path or base) + ".annotated.png"
    img.save(annotated)
    return annotated, result


def window_size():
    """Logical-point screen size: {'width': W, 'height': H}.

    These are the units `tap_at_xy(x, y)` expects. Multiply by devicePixelRatio
    to get physical pixels (iPhone 11+: 3x for Pro models, 2x for non-Pro).
    """
    return _send({"method": "window_size", "params": {}})["result"]


def page_source():
    """Raw XML UI tree from WebDriverAgent. Use ui_tree() for parsed dicts."""
    return _send({"method": "page_source", "params": {}})["result"]


def ui_tree(visible_only=False):
    """Flat list of UI elements from the current screen.

    Each element is a dict:
        {type, name, label, value, x, y, w, h, cx, cy, accessible, visible, traits}

    `cx, cy` are the geometric center — pass directly to tap_at_xy().
    Set visible_only=True to skip off-screen / hidden nodes (most use cases want this).
    """
    xml = page_source()
    root = ET.fromstring(xml)
    out = []
    for el in root.iter():
        a = el.attrib
        if "x" not in a or "width" not in a:
            continue
        try:
            x, y = int(a["x"]), int(a["y"])
            w, h = int(a["width"]), int(a["height"])
        except (TypeError, ValueError):
            continue
        if w <= 0 or h <= 0:
            continue
        is_visible = a.get("visible") == "true"
        if visible_only and not is_visible:
            continue
        out.append({
            "type": a.get("type", el.tag),
            "name": a.get("name") or "",
            "label": a.get("label") or "",
            "value": a.get("value") or "",
            "x": x, "y": y, "w": w, "h": h,
            "cx": x + w // 2, "cy": y + h // 2,
            "accessible": a.get("accessible") == "true",
            "visible": is_visible,
            "traits": a.get("traits") or "",
        })
    return out


def find(label=None, name=None, type=None, value=None, visible_only=True):
    """Return the first UI element matching the given criteria, or None.

    All criteria are AND'd. String fields match by exact equality. Pass startswith=
    or contains= via match_first() for fuzzy matching.

        find(label='Cancel')
        find(type='XCUIElementTypeButton', name='sendButton')
    """
    for el in ui_tree(visible_only=visible_only):
        if label is not None and el["label"] != label: continue
        if name  is not None and el["name"]  != name:  continue
        if type  is not None and el["type"]  != type:  continue
        if value is not None and el["value"] != value: continue
        return el
    return None


def find_all(label=None, name=None, type=None, value=None, visible_only=True):
    """Return all matching UI elements."""
    out = []
    for el in ui_tree(visible_only=visible_only):
        if label is not None and el["label"] != label: continue
        if name  is not None and el["name"]  != name:  continue
        if type  is not None and el["type"]  != type:  continue
        if value is not None and el["value"] != value: continue
        out.append(el)
    return out


def active_app():
    """{bundleId, name, pid, ...} for the foreground app.

    Equivalent to `appium('mobile: activeAppInfo')`. Kept as a named helper
    because `wait_for_app` calls it internally and agents poll it constantly.
    """
    return appium("mobile: activeAppInfo")


def domain_skills(bundle_id):
    """List skill .md filenames for this bundle id, when IPH_DOMAIN_SKILLS=1.

    Call this after `appium('mobile: launchApp', bundleId=...)` to surface
    per-app playbooks the agent should read before driving the app.
    """
    if os.environ.get("IPH_DOMAIN_SKILLS") != "1":
        return []
    d = AGENT_WORKSPACE / "domain-skills" / bundle_id
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.rglob("*.md"))[:10]


# ---- input -----------------------------------------------------------------

def tap_at_xy(x, y):
    """Single tap at logical-point (x, y). Goes through SpringBoard, alerts, modals."""
    appium("mobile: tap", x=x, y=y)


def tap(el):
    """Tap an element returned by find()/ui_tree(). Uses its center."""
    if el is None:
        raise RuntimeError("tap(): element is None")
    tap_at_xy(el["cx"], el["cy"])


HOME_BAR_PX = 80  # bottom region iOS reserves for the home gesture; taps here are eaten


def tap_safe(el, refind=None, max_scrolls=4):
    """Tap an element, scrolling it up first if it's in the home-bar gesture zone.

    iOS reserves the bottom ~80 logical points for the home-indicator swipe.
    Taps in that zone don't reach the app — they trigger the system gesture.
    This helper checks the element's bottom edge against the danger zone, and
    if too low, scrolls the screen up and re-finds the element until it's
    tappable (or `max_scrolls` is exhausted).

    Pass `refind` as a zero-arg callable that re-locates the element after a
    scroll (since coordinates change). Example:
        tap_safe(find(name='auto-lock'), refind=lambda: find(name='auto-lock'))

    If `refind` is None, scrolling once won't help (we'd be tapping stale
    coordinates), so we just tap-as-is.
    """
    if el is None:
        raise RuntimeError("tap_safe(): element is None")
    sz = window_size()
    danger_y = sz["height"] - HOME_BAR_PX
    cur = el
    for _ in range(max_scrolls):
        if cur["y"] + cur["h"] <= danger_y:
            tap_at_xy(cur["cx"], cur["cy"])
            return cur
        if refind is None:
            break
        # Scroll screen up so the element migrates higher.
        midx = sz["width"] // 2
        swipe(midx, sz["height"] - 100, midx, sz["height"] - 250, duration=0.3)
        wait(0.6)
        cur = refind()
        if cur is None:
            raise RuntimeError("tap_safe: refind() returned None after scrolling")
    # Last resort: tap higher up inside the element instead of its center.
    safe_y = min(cur["cy"], cur["y"] + 20)
    tap_at_xy(cur["cx"], safe_y)
    return cur


def double_tap(x, y):
    appium("mobile: doubleTap", x=x, y=y)


def long_press(x, y, duration=1.0):
    """Touch-and-hold at (x, y) for `duration` seconds."""
    appium("mobile: touchAndHold", x=x, y=y, duration=duration)


def swipe(x1, y1, x2, y2, duration=0.4):
    """Swipe from (x1, y1) to (x2, y2)."""
    appium("mobile: dragFromToForDuration", duration=duration,
           fromX=x1, fromY=y1, toX=x2, toY=y2)


def scroll(direction="down", x=None, y=None):
    """Scroll the current scroll view. `direction` ∈ {up, down, left, right}.
    Pass x, y to scroll within a specific element if needed (XCUITest infers if omitted).

    Note: `mobile: scroll` doesn't work in some apps' custom scroll views
    (X/Twitter, Instagram) because they don't expose a standard XCUIElementTypeScrollView.
    For those, use `scroll_by(dy=...)` instead — it's gesture-based.
    """
    args = {"direction": direction}
    if x is not None and y is not None:
        sz = window_size()
        # XCUITest's mobile:scroll wants velocity-style parameters in some
        # versions; the simplest cross-version recipe is dragFromToForDuration.
        midx = sz["width"] // 2
        if direction == "down":
            swipe(midx, sz["height"] * 3 // 4, midx, sz["height"] // 4)
        elif direction == "up":
            swipe(midx, sz["height"] // 4, midx, sz["height"] * 3 // 4)
        elif direction == "left":
            swipe(sz["width"] * 3 // 4, sz["height"] // 2, sz["width"] // 4, sz["height"] // 2)
        elif direction == "right":
            swipe(sz["width"] // 4, sz["height"] // 2, sz["width"] * 3 // 4, sz["height"] // 2)
        return
    appium("mobile: scroll", **args)


def scroll_by(dy=-400, x=None, y=None, velocity=1200):
    """Scroll the current view by `dy` pixels using a high-velocity flick gesture.

    `dy` < 0  → scroll DOWN (reveal content below — finger drags up)
    `dy` > 0  → scroll UP   (reveal content above — finger drags down)

    Uses XCUITest's `mobile: dragFromToWithVelocity` with a fast velocity (default
    1200pt/sec). The high velocity is critical: iOS classifies a touch as a tap
    only at low velocities; a fast flick is unambiguously a scroll, so it does
    NOT trigger taps on whatever cells are under the start point.

    This is the right primitive for **custom-scrollview apps** (X/Twitter,
    Instagram, TikTok) where `mobile: scroll` returns "no scrollable target" and
    a normal `swipe()` accidentally taps cells before iOS recognizes the drag.

        scroll_by(dy=-400)                # scroll down ~400pt
        scroll_by(dy=300)                 # scroll up ~300pt
        scroll_by(dy=-600, velocity=1500) # bigger jump on a stubborn view

    Returns True (always — call `screenshot()` before/after if you need to
    verify the scroll actually moved content).
    """
    sz = window_size()
    if x is None: x = sz["width"] // 2
    if y is None: y = sz["height"] - 150  # start near bottom for natural feel
    target_y = max(50, min(sz["height"] - 50, y + dy))
    appium(
        "mobile: dragFromToWithVelocity",
        fromX=x, fromY=y,
        toX=x,   toY=target_y,
        pressDuration=0.0,   # immediate flick — no press-recognized-as-tap-or-long-press
        holdDuration=0.0,
        velocity=velocity,
    )
    wait(1.2)  # let momentum scroll settle
    return True


def type_text(text):
    """Type into the currently-focused text input. Uses XCUITest's `mobile: keys`.

    Caveats inherited from Appium/XCUITest:
      - Multi-line / paragraph text can be slow; consider `set_value` for long bodies.
      - Some apps swallow individual key events on the first character — call this
        only after confirming a text field is focused (visible keyboard).
    """
    appium("mobile: keys", keys=list(text))


def click(predicate, index=0):
    """Real WebDriver click (vs. synthetic `mobile: tap`). Use when an app's
    button visibly highlights but its handler doesn't fire — many third-party
    iOS apps (YouTube, Instagram, TikTok) install custom gesture recognizers
    that swallow `mobile: tap`.

        click("type == 'XCUIElementTypeButton' AND label BEGINSWITH 'like'")
    """
    return _send({"method": "click_element", "params": {"predicate": predicate, "index": index}})["result"]


def send_keys(predicate, keys, index=0):
    """Find an element by iOS NSPredicate and send keys to it.

    Use for picker wheels (which accept target row as a string), and any
    element where `tap + type_text` doesn't work.

        send_keys("type == 'XCUIElementTypePickerWheel'", "6", index=0)   # left wheel
        send_keys("type == 'XCUIElementTypePickerWheel'", "30", index=1)  # right wheel
    """
    return _send({"method": "send_keys", "params": {"predicate": predicate, "keys": keys, "index": index}})["result"]


def set_value(predicate, value, index=0):
    """Atomic value replace via XCUITest's set_value. Faster than send_keys for long text.

        set_value("type == 'XCUIElementTypeTextField' AND name == 'subject'", "My subject")
    """
    return _send({"method": "set_value", "params": {"predicate": predicate, "value": value, "index": index}})["result"]


def pick_wheel(predicate, target, index=0, direction="next", offset=0.15, max_attempts=30):
    """Spin a picker wheel until its value contains `target` (substring match).

    Uses XCUITest's `mobile: selectPickerWheelValue` — far more reliable than
    raw swipes because it advances one row at a time and stops on match.

        # Set the alarm hour wheel to 6
        pick_wheel("type == 'XCUIElementTypePickerWheel'", "6 o", index=0)
        # Set minutes to 30
        pick_wheel("type == 'XCUIElementTypePickerWheel'", "30 min", index=1)

    `direction` is 'next' (downward / increasing) or 'previous' (upward / decreasing).
    Picker wheel labels often contain unit text (e.g. "6 o'clock", "30 minutes") —
    use a short distinctive prefix to avoid ambiguity with other rows.
    """
    return _send({"method": "pick_wheel", "params": {
        "predicate": predicate, "target": target, "index": index,
        "direction": direction, "offset": offset, "max_attempts": max_attempts,
    }})["result"]


# ---- device-level ----------------------------------------------------------

def unlock():
    """Wake the screen and dismiss the lock screen via swipe-up.

    On FaceID/no-passcode devices this lands you on the home screen.
    On passcode devices it lands you on the passcode pad — the agent
    cannot type into the secure pad; surface to the user.

    Two-step pattern (XCUITest's `mobile: unlock` only wakes on some devices):
      1. mobile: unlock          (turn the screen on)
      2. swipe up from bottom    (dismiss the lock screen on FaceID phones)
    """
    appium("mobile: unlock")
    if not appium("mobile: isLocked"):
        return
    sz = window_size()
    # Swipe from just above the home bar up to roughly 1/3 from the top.
    swipe(sz["width"] // 2, sz["height"] - 10, sz["width"] // 2, sz["height"] // 3, duration=0.4)
    wait(1.0)


# ---- waits -----------------------------------------------------------------

def wait(seconds=1.0):
    time.sleep(seconds)


def wait_for(predicate, timeout=10.0, poll=0.3):
    """Poll predicate() until it returns truthy or timeout. Returns the value."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        v = predicate()
        if v:
            return v
        time.sleep(poll)
    return None


def wait_for_element(label=None, name=None, type=None, value=None, timeout=10.0):
    """Wait until find(...) returns non-None, or timeout. Returns the element or None."""
    return wait_for(lambda: find(label=label, name=name, type=type, value=value), timeout=timeout)


def wait_for_app(bundle_id, timeout=10.0):
    """Wait until the foreground app's bundleId == bundle_id, or timeout."""
    return wait_for(lambda: active_app().get("bundleId") == bundle_id, timeout=timeout)


# ---- alerts ----------------------------------------------------------------

def alert():
    """Read the currently-shown system alert, or None.
    Returns: {'buttons': [...], 'label': '...'} or None.

    For in-app alerts (XCUIElementTypeAlert in the tree), use find/ui_tree instead.
    """
    try:
        return appium("mobile: alert", action="getButtons")
    except Exception:
        return None


def alert_accept():
    """Tap the default Accept button (Allow, OK, Yes) on a system alert."""
    appium("mobile: alert", action="accept")


def alert_dismiss():
    """Tap the default Dismiss button (Cancel, Don't Allow, No) on a system alert."""
    appium("mobile: alert", action="dismiss")


# ---- control center --------------------------------------------------------

def open_control_center():
    """Pull down Control Center from the top-right corner. Verifies it opened.

    Detection: when CC is open, the foreground app is `com.apple.springboard`
    AND a button labeled 'Add Controls' is present in the tree (CC's edit-mode
    affordance, visible in normal mode too on iOS 18+).

    Raises RuntimeError if CC didn't open after the swipe.
    """
    sz = window_size()
    swipe(sz["width"] - 20, 0, sz["width"] - 20, sz["height"] // 2, duration=0.3)
    wait(0.8)
    if not _control_center_is_open():
        # one retry — sometimes the first swipe is too short to register
        swipe(sz["width"] - 20, 0, sz["width"] - 20, sz["height"] // 2, duration=0.4)
        wait(1.0)
        if not _control_center_is_open():
            raise RuntimeError("Control Center did not open. Foreground app: " + active_app().get("bundleId", "?"))


def close_control_center():
    """Dismiss Control Center by pressing Home."""
    appium("mobile: pressButton", name="home")
    wait(0.4)


def _control_center_is_open():
    if active_app().get("bundleId") != "com.apple.springboard":
        return False
    return find(label="Add Controls", type="XCUIElementTypeButton") is not None


def ensure_cc_tile(tile_label):
    """Make sure Control Center has a tile with the given label, installing
    it if missing. Returns the tile element (for follow-up taps).

    Tile labels match the Add Controls picker exactly: 'Screen Recording',
    'Flashlight', 'Calculator', 'Timer', 'Camera', 'Magnifier', 'Notes',
    'Voice Memos', 'Low Power Mode', etc.

    Recipe:
      1. Open CC if not already open
      2. If the tile already exists, return it
      3. Else: tap 'Add Controls' → tap 'Add a Control' → tap the named option → exit edit
      4. Re-find the tile and return it
    """
    if not _control_center_is_open():
        open_control_center()

    existing = find(label=tile_label, type="XCUIElementTypeButton")
    if existing:
        return existing

    # Enter edit mode
    add_controls = find(label="Add Controls", type="XCUIElementTypeButton")
    if add_controls is None:
        raise RuntimeError("'Add Controls' button not found — Control Center may not be open")
    tap(add_controls)
    wait(0.8)

    # Tap "Add a Control" — typically at bottom, often in the home-bar zone
    def find_add_a_control():
        return find(label="Add a Control", type="XCUIElementTypeButton")
    add_btn = find_add_a_control()
    if add_btn is None:
        raise RuntimeError("'Add a Control' button not visible after entering edit mode")
    tap_safe(add_btn, refind=find_add_a_control)
    wait(1.5)

    # Pick the requested tile from the picker
    tile_option = find(label=tile_label, type="XCUIElementTypeIcon") or \
                  find(label=tile_label, type="XCUIElementTypeButton")
    if tile_option is None:
        raise RuntimeError(
            f"Tile {tile_label!r} not found in Add Controls picker. "
            f"Try opening it manually (open_control_center → Add Controls → Add a Control) "
            f"and check the exact label."
        )
    tap(tile_option)
    wait(1.0)

    # Exit edit mode by tapping a neutral spot
    sz = window_size()
    tap_at_xy(sz["width"] // 2, sz["height"] // 3)
    wait(0.8)

    # Re-find the tile in normal CC view
    tile = find(label=tile_label, type="XCUIElementTypeButton") or \
           find(label=tile_label, type="XCUIElementTypeIcon")
    if tile is None:
        raise RuntimeError(f"Tile {tile_label!r} was added but is not visible in CC after exiting edit mode")
    return tile


# ---- text injection / credentials ------------------------------------------

def paste_text(text, predicate=None, index=0):
    """Inject text into a focused (or specified) text field via XCUITest's
    atomic set_value path. Faster, Unicode-safe, and works on secure fields
    where `type_text` is too slow / per-char and where `mobile: setPasteboard`
    is unavailable on real devices.

    If `predicate` is None, defaults to the first focused or first text-input
    field on screen — useful when iOS just popped an Apple ID password sheet
    or a Safari URL bar and the keyboard is up.

    For long messages or anything with non-ASCII characters (em-dash, curly
    quotes, emoji), prefer this over `type_text(...)`.
    """
    if predicate is None:
        # Default: any focused TextField/SecureTextField, or the first one visible.
        predicate = (
            "(type == 'XCUIElementTypeTextField' OR "
            "type == 'XCUIElementTypeSecureTextField') AND "
            "(value != NULL OR hasKeyboardFocus == 1)"
        )
    set_value(predicate, text, index=index)


# ---- screen recording ------------------------------------------------------

def start_screen_recording():
    """Start a screen recording. Installs the CC tile if missing.

    Returns when iOS's 3-second countdown is complete and recording is live.
    The recording captures everything on the device's screen and saves to
    Photos when stopped.
    """
    open_control_center()
    tile = ensure_cc_tile("Screen Recording")
    # Tap the tile (the BUTTON variant — there's also an XCUIElementTypeIcon
    # at the same position; tapping the button is what toggles recording).
    btn = find(label="Screen Recording", type="XCUIElementTypeButton")
    if btn is None:
        # ensure_cc_tile may have returned the icon variant; click via predicate
        click("type == 'XCUIElementTypeButton' AND label == 'Screen Recording'")
    else:
        tap(btn)
    close_control_center()
    # iOS shows a 3-second countdown before the recording actually starts.
    wait(4.0)


def stop_screen_recording():
    """Stop an in-progress screen recording. Tap the red dot in the status bar
    and confirm. The video is saved to Photos.

    Raises RuntimeError if no recording is in progress (no Stop alert appeared).
    """
    # The status-bar red recording indicator is at the top-left, around (40, 25).
    tap_at_xy(40, 25)
    wait(1.5)
    # Confirm the alert
    stop_btn = find(label="Stop", type="XCUIElementTypeButton")
    if stop_btn is None:
        # Maybe nothing was recording, or the alert path differs
        raise RuntimeError("Stop confirmation not visible — was a recording actually in progress?")
    tap(stop_btn)
    wait(1.5)


# ---- agent-helpers hot-load ------------------------------------------------

def _load_agent_helpers():
    """Load IPH_AGENT_WORKSPACE/agent_helpers.py into our globals so user-`-c`
    scripts see the helpers without an import. Mirrors browser-harness."""
    p = AGENT_WORKSPACE / "agent_helpers.py"
    if not p.exists():
        return
    spec = importlib.util.spec_from_file_location("iphone_harness_agent_helpers", p)
    if not spec or not spec.loader:
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for k, v in vars(module).items():
        if k.startswith("_"):
            continue
        globals()[k] = v


_load_agent_helpers()
