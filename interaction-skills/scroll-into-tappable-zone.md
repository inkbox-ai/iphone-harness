# Scroll into tappable zone

Companion to `home-bar-tap-zone.md`. The home gesture zone (~bottom 80px) eats taps; this is the procedure for getting an off-screen-low element into a tappable position.

## When you need this

Settings rows that scroll. List items in long Mail / Messages / contact pickers. Anything where `find()` returns an element with `el["y"] + el["h"] > screen_h - 80`.

## The recipe (`tap_safe` does this)

```python
def find_db(): return find(name="com.apple.settings.displayAndBrightness")

tap_safe(find_db(), refind=find_db)
```

`tap_safe` re-`find`s the element after each scroll — coordinates shift as the screen moves. **Don't** pass a stale element reference.

## The manual recipe (when tap_safe doesn't fit)

```python
sz = window_size()
danger = sz["height"] - 80

while True:
    el = find(name="com.apple.settings.displayAndBrightness")
    if el is None:
        raise RuntimeError("element disappeared")
    if el["y"] + el["h"] <= danger:
        tap(el)
        break
    # Scroll content up by ~150 points
    midx = sz["width"] // 2
    swipe(midx, sz["height"] - 100, midx, sz["height"] - 250, duration=0.3)
    wait(0.6)
```

## Why a small swipe and not `scroll(direction='down')`

`mobile: scroll` sometimes overshoots — it'll fly past your target on a long list. A controlled `swipe` of ~150 pixels keeps the target in view and reachable on the next iteration.

## Why `wait(0.6)` between swipes

iOS scroll views have a momentum / bounce animation that lasts ~500ms after the swipe ends. Reading the tree before settle returns stale coordinates.

## Verify by re-reading, not by remembering

After each scroll, the element's `y` will be smaller (it moved up). After each tap, the entire screen may have changed (you navigated). Don't keep an element reference from before either action.

## Last-ditch fallback

If even after `max_scrolls`, the element is still in the danger zone (e.g. the screen physically can't scroll any further), `tap_safe` taps near the **top** of the element instead of its center:

```python
safe_y = min(el["cy"], el["y"] + 20)
tap_at_xy(el["cx"], safe_y)
```

This works for elements taller than ~60 px because the element's top is usually clear of the gesture zone even if its center isn't. Doesn't help for small icons.
