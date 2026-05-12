---
name: iphone
description: Direct iPhone control via Appium/XCUITest. Use when the user wants to automate, inspect, or interact with a real iPhone tethered via USB.
---

# iphone-harness

Direct iPhone control via Appium. The iOS analogue of [browser-harness](https://github.com/browser-use/browser-harness) by Browser Use — same doctrine, same skill system, translated from CDP/Chrome to XCUITest/iPhone.

For task-specific edits, use `agent-workspace/agent_helpers.py`. For setup/connection issues, run `iphone-harness --doctor`.

Domain skills (per-app playbooks under `agent-workspace/domain-skills/<bundleId>/`) are off by default. Set `IPH_DOMAIN_SKILLS=1` to enable. When enabled, after launching an app call `domain_skills(bundleId)` to get the matching `.md` filenames — read every one before inventing an approach.

## Usage

```bash
iphone-harness -c '
appium("mobile: launchApp", bundleId="com.apple.MobileSMS")
wait_for_app("com.apple.MobileSMS")
print(active_app())
'
```

- Invoke as `iphone-harness` — it's on $PATH. Helpers pre-imported. Daemon auto-starts.
- Daemon owns one Appium session for IPH_NAME (default `default`). Use distinct IPH_NAME values for multiple phones.

## Tool call shape

```bash
iphone-harness -c '
# any python. helpers pre-imported. daemon auto-starts.
'
```

`run.py` calls `ensure_daemon()` before `exec` — never start/stop manually unless you want to.

## What actually works

- **Tree first, screenshots second.** iOS exposes a rich accessibility tree via `ui_tree()` — use it for action targeting (`find(label='Cancel')`). Use `screenshot()` to verify visual state.
- **Coordinate taps default.** `tap_at_xy(x, y)` goes through SpringBoard, alerts, modals — no foreground-app scoping issue. Pair it with element centers from `find()`: `tap(find(label='Send'))`.
- **App lifecycle goes through `appium(...)`.** No dedicated wrappers — just call XCUITest directly:
  - `appium("mobile: launchApp", bundleId="com.apple.MobileSMS")` — cold-launch
  - `appium("mobile: activateApp", bundleId="...")` — resume without resetting state
  - `appium("mobile: terminateApp", bundleId="...")` — force-quit
  - `appium("mobile: queryAppState", bundleId="...")` — `0`=not installed, `1`=not running, `4`=foreground
  - `appium("mobile: pressButton", name="home")` — Home button (or `volumeUp`/`volumeDown`)
  - `appium("mobile: lock")` / `unlock()` — sleep / wake (`unlock()` is a real helper because it has a multi-step recipe)
  - `appium("mobile: isLocked")` — bool
- **System alerts:** `alert()` reads the buttons; `alert_accept()` / `alert_dismiss()` dispatch the default action. For in-app alerts, treat them as regular UI tree nodes.
- **Verification:** `screenshot()` after every meaningful action. UI trees can lie about visibility during animations.
- **Raw escape:** `appium("mobile: anything", **params)` — anything XCUITest supports, no helper required.

## Interaction skills

If you struggle with a generic mechanic, look in `interaction-skills/`. They cover reusable iOS UI mechanics:
- `home-bar-tap-zone.md` — taps in the bottom ~80px get eaten by the home gesture
- `alerts.md` — system vs. in-app alerts; how to dismiss
- `picker-wheels.md` — date/time/value pickers; use `pick_wheel`, never raw swipes
- `scroll-into-tappable-zone.md` — auto-scroll an element above the home-bar zone before tapping
- `ocr-fallback.md` — when the accessibility tree fails (Camera, web views, custom-drawn UIs)
- `wait-for-animations.md` — let iOS settle before reading the tree

## Design constraints

- Tree-first interaction; screenshots for verification only.
- Connect to a manually-started Appium server. Don't try to launch Appium ourselves.
- `appium(...)` is the public escape hatch — **prefer raw XCUITest scripts over typed wrappers**. Helpers exist only when there's a real recipe inside (multi-step, framework workaround, format conversion). One-line wrappers around `appium('mobile: …')` are NOT added to helpers.py.
- `run.py` stays tiny. No argparse, no subcommands.
- Core helpers stay short. Task-specific helpers go in `agent-workspace/agent_helpers.py`.
- No retries framework, session manager, daemon supervisor, config system, or logging framework.

## Gotchas

- **Home-bar tap zone (bottom ~80px):** taps there are eaten by the iOS home gesture. Scroll the target up first with `tap_safe(el, refind=...)` or use `long_press` (which is NOT eaten by the gesture).
- **Status bar (top ~50px):** taps near `12:59` time / battery icons can trigger system overlays (e.g. clock to top, ringer overlay).
- **Screen locked:** `tap_at_xy()` fails silently when the screen is locked. Always `unlock()` first or check `appium('mobile: isLocked')`.
- **Stale Appium session:** sessions die after `IPH_NEW_COMMAND_TIMEOUT` seconds of inactivity. The daemon auto-reconnects on the next call, but if you see a sudden 5-second pause, that's why.
- **First-launch dialogs:** apps can show onboarding / "What's New" sheets that aren't in the accessibility tree. If `find(label=...)` returns None for an obvious button, screenshot first.
- **System alerts vs. in-app alerts:** `alert()` only sees system-level (SpringBoard) alerts. In-app modals appear as `XCUIElementTypeAlert` in `ui_tree()` — use `find(type='XCUIElementTypeButton', label='Cancel')`.
- **Long messages:** `type_text(MSG)` paces character-by-character (slow + flaky on Unicode). For text > ~80 chars or anything with em-dash / curly quotes / emoji, use `set_value("name == 'fieldName'", MSG)` instead — atomic and Unicode-safe.
- **Picker wheels:** never `send_keys` or raw swipes — use `pick_wheel(predicate, target_substring, direction=...)`.
- **Emoji keyboard taps:** the layout shifts after each pick (frequently-used promotion). Use `click(predicate)` not `tap(coords)` — atomic find+click avoids the layout race.
- **FaceID / passcode prompts:** STOP. Surface to the user. Never auto-dismiss.

## Domain skills (opt-in)

Only applies when `IPH_DOMAIN_SKILLS=1`. Otherwise `agent-workspace/domain-skills/` is dormant.

When enabled, after launching an app call `domain_skills(bundle_id)` to list matching skill files:

```python
appium("mobile: launchApp", bundleId="com.apple.MobileSMS")
wait_for_app("com.apple.MobileSMS")
for f in domain_skills("com.apple.MobileSMS"):
    print(f)  # ['send-text.md', 'tapback-reaction.md']
# Read those .md files before inventing an approach.
```

When you learn anything non-obvious — a stable accessibility id, a quirky alert sequence, a hidden gesture, an app-specific timing — open a PR adding to `agent-workspace/domain-skills/<bundleId>/`. Capture durable shape (predicate names, sequence of actions); avoid pixel coordinates (break on layout/orientation) and secrets.
