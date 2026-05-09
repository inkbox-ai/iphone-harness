# Home-bar tap zone

iOS reserves the bottom ~80 logical points of the screen for the home indicator gesture. **Taps in that zone get eaten by the system** — they swipe-up the foreground app instead of activating whatever element is there.

## Symptom

You read the UI tree, find a button whose center `cy` is within ~80 points of the bottom edge, call `tap_at_xy(...)`, and either nothing happens or the App Switcher opens.

## Diagnosis

```python
sz = window_size()  # e.g. {'width': 414, 'height': 896} on iPhone 11/XR
home_bar_top = sz["height"] - 80
print("home bar zone:", home_bar_top, "..", sz["height"])
```

If the target's `cy` is inside that zone, the tap will fail.

## Fix — pick the higher point of a tall element

`tap()` uses an element's geometric center. If the element is tall enough that its top is well clear of the home bar, tap higher up:

```python
el = find(label="Send")
y = min(el["cy"], el["y"] + 20)   # 20 px down from the element's top
tap_at_xy(el["cx"], y)
```

## Fix — scroll the target up first

If the element is small AND lives in the home-bar zone, scroll the surrounding view up by ~100 px before tapping:

```python
sz = window_size()
swipe(sz["width"] // 2, sz["height"] - 100, sz["width"] // 2, sz["height"] - 200)
wait(0.3)
tap(find(label="Send"))
```

## Don't bother

Most stock apps put their bottom toolbar above the home bar already (their bottom edge is `screen_height - 34` not `screen_height - 0`). The tree's `y + h` for a real button is usually safe. The trap is custom-drawn UIs that ignore safe-area insets.
