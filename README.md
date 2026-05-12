<img src="docs/banner.png" alt="iPhone Harness" width="100%" />

# iPhone Harness 📱

Direct iPhone control via Appium/XCUITest. For iPhone tasks where you need **complete freedom**.

A thin, editable harness. The agent perceives the device via UI tree + screenshots, acts via low-level taps and swipes, and writes its own per-app skills as it learns.

> **Inspired by [browser-harness](https://github.com/browser-use/browser-harness) by [Browser Use](https://browser-use.com).** This project is the iOS analogue of their work — same doctrine ("connect an LLM directly to a real device with a thin, editable harness"), same skill system (interaction skills + agent-written domain skills), same "raw protocol over typed wrappers" rule. Go read their [bitter-lesson post](https://browser-use.com/posts/bitter-lesson-agent-harnesses) and the [agents-that-actually-learn post](https://browser-use.com/posts/web-agents-that-actually-learn) — they explain *why* this kind of harness works.

```
  ● agent: wants to send a text
  │
  ● ui_tree() → finds compose field, send button
  │
  ● tap(field) → type_text(...) → tap(send)
  │
  ✓ message sent
```

## Setup

See `install.md` for the full setup. TL;DR:

```bash
brew install libimobiledevice
npm i -g appium && appium driver install xcuitest
pip install -e .   # from this directory
cp .env.example .env  # fill in IPH_UDID, IPH_XCODE_ORG_ID, IPH_WDA_BUNDLE_ID
```

Plug in the iPhone, unlock, trust the computer, and trust the WDA developer profile in **Settings → General → VPN & Device Management**.

## Usage

```bash
# Start Appium in one terminal:
appium --base-path /

# In another terminal:
iphone-harness --doctor                   # diagnose
iphone-harness -c 'print(active_app())'   # smoke test
```

Drive Messages:

```bash
iphone-harness -c '
appium("mobile: launchApp", bundleId="com.apple.MobileSMS")
wait_for_app("com.apple.MobileSMS")
field = wait_for_element(name="messageBodyField", timeout=5.0)
tap(field)
type_text("hello from iphone-harness")
tap(find(type="XCUIElementTypeButton", name="sendButton"))
'
```

## Skills

### Interaction skills (generic iOS UI mechanics)

| File | What |
|---|---|
| [`alerts.md`](interaction-skills/alerts.md) | System vs. in-app alerts; accept/dismiss patterns |
| [`home-bar-tap-zone.md`](interaction-skills/home-bar-tap-zone.md) | Why taps in the bottom ~80px fail, and how to scroll around it |
| [`native-screenshot.md`](interaction-skills/native-screenshot.md) | Saving images to Photos via AssistiveTouch (the only reliable path) |
| [`ocr-fallback.md`](interaction-skills/ocr-fallback.md) | When the accessibility tree fails: Apple Vision OCR via `ocr()` |
| [`picker-wheels.md`](interaction-skills/picker-wheels.md) | Driving date/time/value picker wheels with `pick_wheel` |
| [`scroll-into-tappable-zone.md`](interaction-skills/scroll-into-tappable-zone.md) | `tap_safe` and the auto-scroll-out-of-home-bar pattern |
| [`wait-for-animations.md`](interaction-skills/wait-for-animations.md) | Poll-for-element patterns instead of fixed sleeps |

### Domain skills (per-app playbooks)

| App | Skill | What |
|---|---|---|
| **Amazon** (`com.amazon.Amazon`) | [`buy-now.md`](agent-workspace/domain-skills/com.amazon.Amazon/buy-now.md) | One-step reorder via Buy Now; variant disambiguation by purchase count; required pre-purchase confirmation |
| **Chess.com** (`com.chess.iphone`) | [`play-a-bot.md`](agent-workspace/domain-skills/com.chess.iphone/play-a-bot.md) | Bot selection, move-entry pattern (`tap piece → tap destination`), reading board state and move list from the accessibility tree, end-game UI |
| **Instagram** (`com.burbn.instagram`) | [`navigation.md`](agent-workspace/domain-skills/com.burbn.instagram/navigation.md) | Tab map, search, profile selectors, post action row, edit profile, DM inbox, creation menu, interstitial dismissals |
| **Instagram** | [`post-photo.md`](agent-workspace/domain-skills/com.burbn.instagram/post-photo.md) | Full create-post flow including photo picker permission dance |
| **LinkedIn** (`com.linkedin.LinkedIn`) | [`post.md`](agent-workspace/domain-skills/com.linkedin.LinkedIn/post.md) | Text + image post end-to-end |
| **Messages** (`com.apple.MobileSMS`) | [`send-text.md`](agent-workspace/domain-skills/com.apple.MobileSMS/send-text.md) | Send a text to a phone number or existing conversation |
| **Messages** | [`tapback-reaction.md`](agent-workspace/domain-skills/com.apple.MobileSMS/tapback-reaction.md) | React to a message with a Tapback (incl. custom emoji) |
| **Clock** (`com.apple.mobiletimer`) | [`create-alarm.md`](agent-workspace/domain-skills/com.apple.mobiletimer/create-alarm.md) | Add a new alarm with picker-wheel time entry |
| **Settings** (`com.apple.Preferences`) | [`auto-lock.md`](agent-workspace/domain-skills/com.apple.Preferences/auto-lock.md) | Set Auto-Lock duration |

Domain skill discovery is opt-in: set `IPH_DOMAIN_SKILLS=1` and call `domain_skills(bundle_id)` after launching an app to list matching `.md` files.

## Architecture

~700 lines across:

- `src/iphone_harness/run.py` — `iphone-harness` CLI (tiny)
- `src/iphone_harness/helpers.py` — public action API auto-imported into `-c` scripts
- `src/iphone_harness/daemon.py` — long-lived process owning the Appium WebDriver session
- `src/iphone_harness/admin.py` — daemon lifecycle + doctor
- `src/iphone_harness/_ipc.py` — AF_UNIX JSON-line RPC
- `agent-workspace/agent_helpers.py` — agent-editable helpers
- `agent-workspace/domain-skills/<bundleId>/*.md` — per-app skills (opt-in via `IPH_DOMAIN_SKILLS=1`)
- `interaction-skills/*.md` — reusable iOS UI mechanics

## Public API surface

Pre-imported in every `-c` script. See `helpers.py` for the full list.

```
# Perception
screenshot(path=None)                            → str path on Mac (NOT on iPhone)
window_size()                                    → {'width', 'height'}  (logical points)
ui_tree(visible_only=False)                      → list[dict]
find(label=, name=, type=, value=)               → element or None
find_all(...)                                    → list[element]
active_app()                                     → {'bundleId', ...}
ocr(image_path=None, languages=("en-US",))       → (lines, (px_w, px_h))
find_text(query, ...)                            → line dict with cx_pt/cy_pt or None
annotated_screenshot(path=None, run_ocr=True)    → (annotated_path, items)
page_source()                                    → raw XML

# Native screenshot — captures + saves to iPhone Photos library
# (see interaction-skills/native-screenshot.md for why & how)
native_screenshot()                              # fires iOS native screenshot via AssistiveTouch dot
set_assistive_touch(on=True)                     # toggle AssistiveTouch + bind Single-Tap=Screenshot

# Input
tap_at_xy(x, y)
tap(element)
tap_safe(element, refind=callable)               # auto-scrolls out of home-bar zone
double_tap(x, y)
long_press(x, y, duration=1.0)
swipe(x1, y1, x2, y2, duration=0.4)
scroll(direction='down')                         # standard mobile: scroll (fails in custom scrollviews)
scroll_by(dy=-400, x=None, y=None, velocity=1200) # gesture-based; works in X/Instagram-class apps
type_text(text)
click(predicate, index=0)                        # real WebDriver click (custom-gesture apps)
send_keys(predicate, keys, index=0)              # for picker wheels accepting row strings
set_value(predicate, value, index=0)             # atomic field replace; use for long text
paste_text(text, predicate=None, index=0)        # convenience wrapper around set_value
pick_wheel(predicate, target, direction='next')  # iterative spin until value matches

# Control Center & screen recording
open_control_center()                            # swipe-from-top-right with verify
close_control_center()                           # press home
ensure_cc_tile(label)                            # install a CC tile if not present
start_screen_recording()                         # full flow: open CC, ensure tile, tap, wait 3s
stop_screen_recording()                          # tap red status-bar dot + confirm

# Device
unlock()                                         # multi-step: wake + swipe-up

# Waits
wait(seconds=1.0)
wait_for(predicate, timeout=10.0)
wait_for_element(label=, name=, type=, value=, timeout=10.0)
wait_for_app(bundle_id, timeout=10.0)

# Alerts (system-level only; in-app alerts are normal UI tree nodes)
alert()
alert_accept()
alert_dismiss()

# Skill discovery
domain_skills(bundle_id)                         → list[str] of .md filenames

# Escape hatch — anything XCUITest exposes
appium('mobile: launchApp', bundleId='...')
appium('mobile: activateApp', bundleId='...')
appium('mobile: terminateApp', bundleId='...')
appium('mobile: queryAppState', bundleId='...')
appium('mobile: pressButton', name='home')       # name ∈ {home, volumeup, volumedown}
appium('mobile: lock')
appium('mobile: isLocked')
appium('mobile: activeAppInfo')
appium('mobile: anything', **params)
```

## Contributing

PRs welcome — **fork the repo, use it for real tasks, push your improvements back.** That's the whole flow.

The most valuable contributions are **new skills**:

- **Domain skills** (`agent-workspace/domain-skills/<bundleId>/*.md`) — per-app playbooks for individual iOS apps (Spotify, WhatsApp, Notion, your bank, etc.). Each one captures the durable shape of an app: stable accessibility ids, the sequence of taps to reach a goal, the gotchas that broke you on the first try.
- **Interaction skills** (`interaction-skills/*.md`) — reusable iOS UI mechanics that aren't app-specific (date pickers, share sheets, AirDrop receiver flow, permissions prompts, custom-gesture apps, etc.).
- **Bug fixes** and **harness improvements** are equally welcome.

### Skills are written by the harness, not by you

This is the doctrine borrowed from [browser-harness](https://github.com/browser-use/browser-harness). Don't sit down and try to write a skill from memory. Instead:

1. **Use the harness for a real task on the app.** Drive the agent (Claude Code, your own LLM, whatever) and watch it work.
2. **When the agent figures something non-obvious out** — a stable accessibility id, a hidden gesture, an animation timing, a quirky alert sequence — **the agent files the skill itself**.
3. **You PR the generated `.md` file.** Tweak prose if you like, but the load-bearing parts (selectors, action sequences, traps) should reflect what actually worked in the live device, not what you think *should* work.

Hand-authored skills lie. Agent-generated skills reflect the actual UI tree.

### How to PR

1. Fork this repo.
2. Clone your fork, set up `.env` (see `install.md`).
3. Use the harness for whatever you're trying to automate — let the agent generate skill files as it learns.
4. Open a PR back to this repo with the new `agent-workspace/domain-skills/<bundleId>/*.md` (or `interaction-skills/*.md`).

Small and focused PRs are great — one skill at a time. If you're not sure where to start, browse `agent-workspace/domain-skills/` to see the shape of existing skills.

### What NOT to put in skills

- **Pixel coordinates** — those break on different screen sizes and orientations. Use accessibility predicates (`name`, `label`, `type`) instead.
- **Secrets, credentials, or personal data** — the directory is public. Don't include phone numbers, emails, payment info, or anything tied to your specific account.
- **Task narration** — skills capture the *map* (durable structure of the app), not the *diary* (what you did on Tuesday). "Tap Send" yes; "Then I sent Ray a message" no.

If you're not sure whether something belongs, open an issue and ask.

---

## Credits

This harness is the iOS analogue of [**browser-harness**](https://github.com/browser-use/browser-harness) by [Browser Use](https://browser-use.com). The architecture (CLI → daemon → protocol → device), the skill system (interaction-skills + domain-skills), the doctrine ("raw protocol over typed wrappers", "skills are written by the harness, not by you"), and large parts of the code structure (`_ipc.py`, the `-c` execution model, the agent-workspace pattern) are direct adaptations of their work — translated from Chrome/CDP to iPhone/Appium-XCUITest.

If you find this useful, go give them a ⭐ first. Required reading:
- [The Bitter Lesson of Agent Harnesses](https://browser-use.com/posts/bitter-lesson-agent-harnesses)
- [Web Agents That Actually Learn](https://browser-use.com/posts/web-agents-that-actually-learn)

Released under the MIT License. See [`LICENSE`](LICENSE).
