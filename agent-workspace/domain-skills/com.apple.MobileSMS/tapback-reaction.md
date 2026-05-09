# Messages — Tapback (react to a message)

Bundle id: `com.apple.MobileSMS`. Field-tested on iOS 18.3.2.

## The Tapback wheel has only 6 fixed reactions

iOS exposes these as immediate Tapback options when you long-press a bubble:

| Image name | Reaction |
|---|---|
| `heart_099` | ❤️ |
| `thumbsup_073` | 👍 |
| `thumbsdown_069` | 👎 |
| `haha-ENG_099` | 😆 |
| `exclamation_099` | ‼️ |
| `question_080` | ❓ |

**Anything else (🔥, 🎉, 🥳, etc.) requires the "Add custom emoji reaction" path.**

## Standard reaction (one of the 6)

```python
# Find the message bubble (a Cell whose label contains the message text)
msg = next(el for el in ui_tree(visible_only=True)
           if el["type"] == "XCUIElementTypeCell" and "your message text" in el["label"])

# Long-press to bring up the wheel
long_press(msg["cx"], msg["cy"], duration=0.8)
wait(1.5)

# Tap the reaction by image name
tap(find(name="heart_099", type="XCUIElementTypeImage"))
```

## Custom emoji reaction (e.g. 🔥)

```python
# Long-press to bring up the wheel
long_press(msg["cx"], msg["cy"], duration=0.8)
wait(1.5)

# Tap "Add custom emoji reaction" (opens the system emoji keyboard)
tap(find(label="Add custom emoji reaction", type="XCUIElementTypeButton"))
wait(2.0)

# CRITICAL: use click() with a predicate, not tap() with coords. The emoji
# keyboard re-lays out the moment you select an emoji once (frequently-used
# row promotion), so coordinates read from the tree go stale instantly.
click("type == 'XCUIElementTypeKey' AND name == '🔥'")
wait(2.0)
```

## Verify

The cell's label updates immediately:

```python
target = next(el for el in ui_tree(visible_only=True)
              if el["type"] == "XCUIElementTypeCell" and "your message text" in el["label"])
assert "You reacted with 🔥" in target["label"], f"expected 🔥 reaction, got: {target['label']!r}"
```

## Replace an existing reaction

If you already reacted with the wrong emoji (easy to do — see traps below), repeat the **exact same flow**: long-press → custom emoji → tap the new emoji. iOS replaces the previous reaction; it doesn't stack.

To **remove** a reaction without replacing: long-press → custom emoji → search for the *currently-active* emoji and tap it again (toggles off). Or tap the existing reaction badge directly on the bubble.

## Traps

- **🔥 / 🎉 / 🥳 are NOT in the standard wheel.** Don't try `find(name="🔥", type="XCUIElementTypeImage")` against the wheel — only the 6 fixed images exist there. Use the custom-emoji path.
- **Coordinate taps on the emoji keyboard are unreliable.** As soon as you pick one emoji it gets promoted into the "Frequently Used" row, shifting every other emoji's position. **Always use `click(predicate)`** — it find-and-clicks atomically inside one Appium call, avoiding the layout race.
- **The custom emoji picker is the system emoji keyboard.** It has a search field (`Search Emoji` placeholder) at the top — useful when the emoji isn't in the visible page (e.g. animals, food).
- **`long_press` works in the home-bar gesture zone.** Unlike `tap`, the long-press gesture doesn't get eaten by the home-swipe; iOS treats them as distinct. Messages near the bottom of the screen don't need scrolling-up before reacting.
- **iMessage-only.** Tapback / reactions don't exist on plain SMS (green-bubble) threads. If `long_press` produces only a context menu (Copy/Reply/etc.) with no reaction wheel above, you're on SMS — fall back to typing an emoji as a regular message.
- **Group chats** show reactions per-person (`<contact name> reacted with X`) — your own reaction in the cell label reads `You reacted with X` as in 1:1 chats.
