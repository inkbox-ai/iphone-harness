# Picker wheels

Wherever iOS shows a vertical scrolling wheel to pick a value (alarms, timers, date pickers, country selectors, settings dropdowns, photo aspect ratios), the element type is `XCUIElementTypePickerWheel` with `traits="Adjustable"`.

## What does NOT work

- `mobile: setPickerValue` — **not implemented** in this XCUITest version. Throws `NotImplementedError`. Don't try it.
- `element.send_keys("6")` on a picker wheel — silent no-op for most wheels. Some accept the visible row label exactly (e.g. minutes wheel sometimes accepts `"30"`) but it's not reliable. Skip it.
- Raw swipe-to-spin (`swipe(cx, cy, cx, cy + N*32, ...)`) — works in theory; in practice, inertia overshoots and you have to verify+correct in a loop. Don't bother — there's a better tool.

## What works

`mobile: selectPickerWheelValue`. Wrapped in our harness as `pick_wheel`:

```python
pick_wheel("type == 'XCUIElementTypePickerWheel'", "6 o",   index=0, direction="previous")
pick_wheel("type == 'XCUIElementTypePickerWheel'", "30 min", index=1, direction="next")
```

It iteratively nudges one row at a time and stops when the wheel's `value` contains the `target` substring. Field-tested: 14→6 in 8 attempts, 36→30 in 6 attempts.

## Match the right value

Picker wheel labels almost always include unit text:

| Wheel type | Example values |
|---|---|
| Hour (24h) | `"00 o'clock"`, `"06 o'clock"`, `"14 o'clock"` |
| Minute | `"00 minutes"`, `"30 minutes"` |
| Date day | `"Tuesday, January 14"` |
| Country | `"United States"`, `"United Kingdom"` |

Use a short distinctive prefix to avoid collisions:
- `"6 o"` matches `"06 o'clock"` but not `"16 o'clock"`. ✅
- `"6"` matches BOTH `"06 o'clock"` and `"16 o'clock"` — first match wins, may not be what you want. ❌
- `"30 min"` is unambiguous. ✅
- `"30"` may match `"30 minutes"` AND `"30 seconds"` (if both wheels are visible). ❌

The apostrophe in `"o'clock"` is the **curly Unicode apostrophe** `’` (U+2019), not ASCII `'`. Don't include it in your match — keep the prefix short and ASCII-safe.

## Multiple wheels on one screen

Add Alarm has two wheels (hour, minute). Date picker has three. Country picker has one. Distinguish by `index=` in the predicate match order:

```python
wheels = sorted([el for el in ui_tree() if el["type"] == "XCUIElementTypePickerWheel"], key=lambda e: e["cx"])
# wheels[0] is leftmost, wheels[N-1] is rightmost
```

The `index` parameter in `pick_wheel` matches the order Appium's `find_elements` returns them, which on iOS is left-to-right by `cx`. If a layout looks ambiguous, screenshot first and confirm visually.

## Direction

`direction="next"` advances the wheel forward (downward / increasing values).
`direction="previous"` goes backward (upward / decreasing values).

Pick the shorter route to your target:
- 14 → 6 hours: 8 backward (`previous`) vs 16 forward — pick `previous`.
- 5 → 50 minutes: 45 forward vs 15 backward — pick `previous`.

If you don't know the current value, just pick one — `pick_wheel` will hit the safety cap (default 30 attempts) and surface a non-matching `value` so you can retry the other way. Cheap to be wrong.

## Offset

`offset=0.15` (default) means each nudge moves the wheel by 15% of its visible height. Higher = bigger jumps but more inertia overshoot risk. Lower = more accurate but slower. Stick with the default unless a specific wheel is misbehaving.

## When pick_wheel times out / hangs

Two failure modes seen:

1. **WDA "socket hang up"** — happens occasionally on long picker spins (~30+ rows). Retry the call; usually goes through.
2. **IPC timeout** — `_send` defaults to a 120s timeout. If a wheel needs >120s of nudging, you've probably picked the wrong direction. Cancel the sheet, re-open, retry the other direction.

## Verify after

Always re-read the wheels' `value` after `pick_wheel` returns. The result dict tells you whether it converged:

```python
r = pick_wheel(..., "6 o", ...)
# r = {"value": "06 o'clock", "attempts": 8}             # success
# r = {"value": "11 o'clock", "attempts": 30, "matched": False}   # gave up
if not r.get("matched", True):
    raise RuntimeError(f"picker didn't reach target; ended at {r['value']}")
```
