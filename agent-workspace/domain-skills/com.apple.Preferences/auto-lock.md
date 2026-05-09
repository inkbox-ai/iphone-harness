# Settings — Display & Brightness → Auto-Lock

Bundle id: `com.apple.Preferences`. Field-tested on iOS 18.3.2.

## Path

Settings root → "Display & Brightness" → "Auto-Lock" → pick a duration

## Find the rows

The Display & Brightness row in the Settings root list has the canonical accessibility name:

```python
find(name="com.apple.settings.displayAndBrightness")
```

It's typically near the bottom of the Settings root list — often **inside the home-bar gesture zone** (`y > 816`). Use `tap_safe(..., refind=...)` to scroll it into a tappable region first:

```python
def find_db(): return find(name="com.apple.settings.displayAndBrightness")
tap_safe(find_db(), refind=find_db)
```

The Auto-Lock row on the D&B page uses a plain text label:

```python
def find_al(): return find(label="Auto-Lock")
tap_safe(find_al(), refind=find_al)
```

## Auto-Lock options

The options page shows seven cells, **labels in lowercase**:

```
30 seconds
1 minute
2 minutes
3 minutes
4 minutes
5 minutes
Never
```

Tap one with `find(label="5 minutes")` (note: **lowercase `m`**). Don't use `"5 Minutes"` — that returns None.

```python
tap(find(label="5 minutes", type="XCUIElementTypeCell"))
```

## Detect which option is currently selected

Settings option pages show selection via a **separate `XCUIElementTypeButton` named `checkmark`**, NOT via the cell's `value`. Find the checkmark, then match its `y` to a cell's row:

```python
checkmark = find(name="checkmark")
for el in ui_tree(visible_only=True):
    if el["type"] == "XCUIElementTypeCell" and abs(el["y"] - (checkmark["y"] - 25)) < 30:
        print("currently selected:", el["label"])
        break
```

The `-25` offset is because the checkmark is vertically centered in its cell while the cell's `y` is the top edge — adjust if iOS changes the cell padding.

## Low Power Mode caveat

When Low Power Mode is enabled (Settings → Battery → Low Power Mode), iOS **forces Auto-Lock to 30 seconds** and **hides all other options on this page**. If `find(label="5 minutes")` returns None and you only see "30 seconds" + "Never", check Low Power Mode first.

## Traps

- **Labels are lowercase** in this page only. Most other iOS Settings pages use Title Case. Don't memoize the casing convention; check the tree.
- **The cell's `value` field is empty** for all options — it's not how selection is communicated. Use the checkmark approach above.
- **Settings often opens to the last-visited page**, not the root. If you `appium("mobile: launchApp", bundleId="com.apple.Preferences")` and find yourself already on D&B or Auto-Lock options, don't re-navigate; just check `find(label="5 minutes")` first.
- **Display & Brightness lives in the home-bar zone** on this device. Always wrap with `tap_safe`.
