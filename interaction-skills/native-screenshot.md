# Native screenshot (save to Photos)

The harness's `screenshot()` writes to the **Mac's filesystem**, not to the iPhone's Photos library. For any workflow that needs the image to be **on the iPhone** (Instagram post, Messages attachment, AirDrop, save to Files, etc.), `screenshot()` is the wrong tool.

This document covers the **one autonomous path that works** for getting an image into the iPhone's Photos library.

## Why this is hard

Apple deliberately blocks every programmatic write path to the Photos library on real iOS devices:

| What you'd try | Why it doesn't work |
|---|---|
| `appium("mobile: addMediaToLibrary", ...)` | `NotImplementedError` on real devices — simulator-only by Apple's design |
| `appium("mobile: pushFile", "@<bundleId>/...", ...)` | Photos library isn't in any app's sandbox; returns `InstallationLookupFailed` |
| `idevicescreenshot` (libimobiledevice) | Captures over USB to the **Mac**, not into Photos |
| HID button-chord (Side + Volume Up) via `mobile: performIoHidEvent` | XCTest can't fire two hardware buttons simultaneously — documented limitation |
| `mobile: setPasteboard` then paste | Simulator-only on real devices |
| AppleScript / `osascript` driving AirDrop on the Mac | macOS sandbox blocks Claude Code from sending keystrokes |

## The solution — AssistiveTouch dot

iOS ships an accessibility feature called **AssistiveTouch**: a small floating button that lives on top of every app. You can configure it so that **a single tap on the dot triggers a native iOS screenshot** — the same one the Side + Volume Up chord produces, identical pipeline, saves to Photos library.

The harness drives the dot like any other UI element, and Apple itself fires the screenshot. iOS even auto-hides the dot from the screenshot it produces, so the saved photo has no dot artifact.

This is the **only autonomous path** for putting an arbitrary on-screen image into Photos.

## One-time setup

Run once per device:

```python
set_assistive_touch(on=True)
```

This drives Settings → Accessibility → Touch → AssistiveTouch → toggle ON and Single-Tap → Screenshot. Idempotent — re-running on a configured device is a no-op.

After this, the floating dot is visible at the default position (top-right, roughly `(390, 180)` on a 414×896 device). The user can drag it elsewhere; update `ASSISTIVE_TOUCH_X` / `ASSISTIVE_TOUCH_Y` in `helpers.py` if you do.

To disable the dot (cleanup, end-to-end re-test, or when the dot is in the way of a UI you're driving):

```python
set_assistive_touch(on=False)
```

The disable path is also what makes this helper proper test infrastructure — turn off → re-enable → verify the whole flow on a "fresh" state. Doctrine-aligned: every helper that changes device state should have a way to put state back.

## Using it

```python
native_screenshot()
```

That's the whole helper — a single tap at the dot's known position, plus a 1-second wait for iOS's capture animation + write-to-Photos to complete. The image appears in Photos → Library → Recents (and in Photos → Albums → Recently Saved) within ~1 second.

Typical workflow:

```python
# 1. Display the content you want to capture
appium("mobile: launchApp", bundleId="com.apple.mobilesafari")
# ... navigate Safari to a page with the Clawd image ...

# 2. Capture to Photos
native_screenshot()

# 3. Use the captured image in another app
appium("mobile: launchApp", bundleId="com.burbn.instagram")
# ... drive Instagram's create-post flow; the photo picker shows the just-captured image at top ...
```

## What gets captured

The native screenshot captures **exactly the current screen** — full screen, including status bar, navigation chrome, and whatever app is foregrounded. iOS auto-hides:
- The AssistiveTouch dot itself
- The carrier signal / battery indicators briefly during the flash animation

It does NOT hide:
- Any other UI iOS is drawing (notifications, in-app banners)
- Status bar (time, Wi-Fi, battery — these are baked into the capture)

If you need to capture only a *region*, crop the saved photo afterward (load via `screenshot()` to get a Mac copy you can edit, or accept the full-screen capture and crop on the consumer side).

## Resolution & quality

Native screenshots are at the device's **physical pixel resolution**:
- 2× device (iPhone 11/XR-class, our test phone): **828×1792**
- 3× device (Pro models): **1242×2688** or similar

iOS saves them as PNG (or HEIC if Settings → Camera → Formats → "High Efficiency" is on). File size typically 200–700 KB.

## Common pitfalls

- **Dot position assumption**: if the dot has been dragged from the default `(390, 180)`, `native_screenshot()` will tap an empty area and silently do nothing. Take a regular `screenshot()` after to verify the capture happened (Photos count should increment).
- **App-modal dialogs**: if a modal dialog is on screen, AssistiveTouch may be partially obscured but still functional. If `native_screenshot()` stops working after a modal appears, screenshot the screen and check the dot is still visible.
- **Stage Manager / Split View**: not tested. The dot moves but should still work.
- **Disable when not needed**: AssistiveTouch is a permanent floating overlay. It's hidden from screenshots and most screen recordings, but it IS visible to the user. Keep it on as long as your harness needs it; disable in Settings → Accessibility → Touch → AssistiveTouch when done.

## Verifying it worked

The cheapest verification is comparing photo counts before/after:

```python
# Capture a "before" screenshot of Photos (the Mac-side kind, just to read state)
appium("mobile: launchApp", bundleId="com.apple.mobileslideshow")
wait(2.0)
# Look for the photo count somewhere in the UI, e.g.:
# 'Photos, 47 Items' on the Library tab
# After native_screenshot, that number should increment by 1.
```

For more rigorous verification, use the iPhone's "Recently Saved" album — it shows only the photos added in the last week and is the most reliable view to confirm a fresh save.

## Why we have to commit to this trick

Apple has been **tightening** Photos-library protection across every iOS release. Each year more programmatic paths get closed (e.g. `mobile: addMediaToLibrary` worked on real devices in earlier XCUITest versions; now it doesn't). **AssistiveTouch is the most durable path** because:

- It's a documented accessibility feature Apple actively maintains
- It's invoked by a normal tap event, which the harness can always send
- It uses Apple's own screenshot pipeline, so output quality + Photos integration are first-class

Unless Apple removes AssistiveTouch's Screenshot action (which would break a real accessibility use case), this trick should keep working across iOS versions.

## Related skills

- `ocr-fallback.md` — for reading the *content* of a screenshot once you have one
- `home-bar-tap-zone.md` — relevant if the dot is positioned near the bottom of the screen
