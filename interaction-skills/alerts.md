# Alerts

There are two distinct things called "alerts" on iOS, and they need different handling.

## System alerts (SpringBoard-presented)

Pop up over any app: permission prompts, "Update Apple ID Settings", "Trust This Computer", iOS update nags. **They're owned by SpringBoard, not by the foreground app**, so you can hit them with the system-level alert API:

```python
buttons = appium("mobile: alert", action="getButtons")
# ['Settings', 'Cancel']

alert_accept()    # taps the default Accept (usually leftmost / OK / Allow / Settings)
alert_dismiss()   # taps the default Dismiss (usually rightmost / Cancel / Don't Allow)
```

`alert()` returns the buttons or None if no alert is present. Use that as a "is there a system alert?" probe between steps.

### Watch out

- The "default action" semantics (`accept` vs. `dismiss`) is decided by Appium's heuristic, not iOS. For high-stakes decisions (Allow Tracking, Delete Account, etc.) **read the buttons explicitly and tap by name** instead of trusting `accept`/`dismiss`:

  ```python
  buttons = appium("mobile: alert", action="getButtons")
  if "Don't Allow" in buttons:
      appium("mobile: alert", action="dismiss", buttonLabel="Don't Allow")
  ```

- Some "alerts" are actually action sheets or modal sheets; they'll show up in `ui_tree()` as `XCUIElementTypeSheet`, not in `alert()`. Try the in-app path below if `alert()` returns None but you can clearly see a modal.

## In-app alerts (XCUIElementTypeAlert in the tree)

Drawn by the foreground app inside its own window. Appear in `page_source()` as `<XCUIElementTypeAlert>` with child buttons. Treat them as regular UI elements:

```python
btn = find(type="XCUIElementTypeButton", label="Cancel")
if btn:
    tap(btn)
```

If multiple alerts are stacked, `find_all` returns them in tree order; the visually-frontmost one is usually the last in the list.

## Detecting the alert *type*

```python
# Heuristic — try system first, fall back to tree.
sys_alert = alert()
if sys_alert:
    print("system alert:", sys_alert)
else:
    in_app = find(type="XCUIElementTypeAlert")
    if in_app:
        print("in-app alert:", in_app["name"])
```

## Re-entrant alerts

Some prompts re-fire immediately if their underlying condition isn't fixed (e.g. the Google password alert reappears on every wake until you actually go to Settings). Tapping Cancel may dismiss it for *this moment* but not solve the cause. If the same alert returns twice in a row, surface to the user.
