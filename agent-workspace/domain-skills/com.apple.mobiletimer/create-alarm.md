# Clock — Create an alarm

Bundle id: `com.apple.mobiletimer` (the Clock app, not Calendar). Field-tested on iOS 18.3.2.

## Open the right tab

Clock has four tabs at the bottom: World Clock, Alarms, Stopwatch, Timers. Each is a `XCUIElementTypeButton`. The currently-selected tab has `value="1"`.

```python
appium("mobile: activateApp", bundleId="com.apple.mobiletimer")
wait(0.6)
alarms_tab = find(name="Alarms", type="XCUIElementTypeButton")
if alarms_tab and alarms_tab["value"] != "1":
    tap(alarms_tab); wait(0.3)
```

## Open the Add Alarm sheet

The "+" button in the navigation bar has `name="Add"` (not "+"):

```python
tap(find(name="Add"))
wait(0.8)
assert find(name="Add Alarm") is not None, "Add Alarm sheet didn't appear"
```

If the sheet is already open from a previous run, cancel it first:

```python
if find(name="Add Alarm") is not None:
    c = find(label="Cancel")
    if c: tap(c); wait(0.4)
```

## Set the time

Two `XCUIElementTypePickerWheel`s, sorted left→right: hour, minute. Hour is 24-hour format (`"06 o'clock"`, `"14 o'clock"`).

```python
pick_wheel("type == 'XCUIElementTypePickerWheel'", "6 o", index=0, direction="previous")
pick_wheel("type == 'XCUIElementTypePickerWheel'", "30 min", index=1, direction="previous")
```

Pick `direction` to minimize attempts (e.g. 14→6 is shorter via `previous`). See `interaction-skills/picker-wheels.md` for the full picker-wheel playbook.

Verify before saving:

```python
wheels = sorted([el for el in ui_tree() if el["type"] == "XCUIElementTypePickerWheel"], key=lambda e: e["cx"])
assert wheels[0]["value"].startswith("06") and wheels[1]["value"].startswith("30"), \
    f"wheels not at 06:30 — got {wheels[0]['value']} / {wheels[1]['value']}"
```

## Set the label (recommended)

The default label is `"Alarm"`, stored as the textfield's `value` (not its `name`). Without a custom label, you can't reliably distinguish multiple alarms with the same time.

```python
set_value("type == 'XCUIElementTypeTextField'", "Morning")
wait(0.3)
```

`set_value` uses XCUITest's atomic `mobile: setValue` (Selenium 4 removed `WebElement.set_value()`). Don't try `tap(field) → type_text(...)` — clearing the existing "Alarm" placeholder is fiddly.

## Save

```python
tap(find(label="Save", type="XCUIElementTypeButton"))
wait(1.5)
```

The new alarm is **enabled by default** (its toggle switch is ON).

## Verify

The alarm list cell labels are formatted `"HH:MM, Label"`:

```python
hits = [el for el in ui_tree(visible_only=True)
        if el["type"] == "XCUIElementTypeCell" and "06:30, Morning" in (el["label"] or "")]
assert hits, "alarm not in list"
```

## Traps

- **Multiple wheels are sorted left-to-right.** `index=0` is hour (leftmost), `index=1` is minute. If iOS layout ever changes (e.g. localization adds AM/PM as a third wheel), audit assumptions.
- **24-hour format is system-wide, not per-app.** If the user has 12-hour time set in Settings → General → Date & Time, the picker wheels show `"6 AM"` / `"6 PM"` instead of `"06 o'clock"`. Match prefix and check for AM/PM in `value` to disambiguate.
- **The hour wheel labels are zero-padded** (`"06 o'clock"`, not `"6 o'clock"`). Match against the un-padded prefix (`"6 o"`) and let pick_wheel's substring search handle it.
- **Edit mode (top-left "Edit" button) shows delete buttons** but the picker wheel API is the same — don't conflate Edit mode with Add Alarm.
- **Repeat / Sound / Snooze rows** are also in the Add Alarm sheet. Default to "Never" / "Radar" / On respectively. Don't tap them unless the user wants to change them.

## What this skill does NOT cover

- Editing an existing alarm (Edit mode → tap the alarm cell — different flow)
- Deleting alarms
- Setting Repeat (which days)
- Changing the alarm sound
- Snooze toggle

Open follow-up skill files for those when needed.
