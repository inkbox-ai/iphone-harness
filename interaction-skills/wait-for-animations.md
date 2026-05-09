# Wait for animations

iOS animates almost every transition: tab switches, navigation pushes, alerts appearing/dismissing, keyboard show/hide. During an animation, the UI tree returned by `page_source()` is **partially correct**: elements may exist but report wrong coordinates, or be marked `visible="false"` even though they're 90% on screen.

## Symptom

You tap a button, immediately call `find(label="…")` for the next screen, and get None — but a screenshot taken at the same instant clearly shows the element.

## Fix — poll instead of sleep

Don't `wait(1.5)` (you're guessing) and don't `wait(0.1)` (you're racing). Use `wait_for_element`:

```python
tap(find(label="Compose"))
msg_field = wait_for_element(name="messageBodyField", timeout=5.0)
tap(msg_field)
```

`wait_for_element` polls every 0.3s up to the timeout. The animation typically completes in 300-500ms; this lands within one poll of the actual settle.

## Fix — wait for a stable hash of the tree

If the element you want has a generic name shared with the previous screen, poll for the *previous* screen's distinctive element to *disappear*:

```python
prev_marker = find(label="Conversations")  # the title from the list view
tap(some_conversation)
wait_for(lambda: find(label="Conversations") is None, timeout=5.0)
# now the new screen is settled
```

## When to fall back to a fixed sleep

For physics-based animations (rubber-band scroll, bounce, spring) that don't have a clean "done" marker. ~600ms covers most of these:

```python
swipe(...)
wait(0.6)
```

Avoid stacking these — three `wait(0.6)`s in a sequence means you're probably missing a signal.
