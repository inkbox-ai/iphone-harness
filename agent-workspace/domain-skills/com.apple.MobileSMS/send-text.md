# Messages — send a text to an existing conversation

Bundle id: `com.apple.MobileSMS`. Field-tested on iOS 18.3.2.

## Open the right conversation

The Messages list view shows conversations as `XCUIElementTypeCell`s whose `label` begins with the contact display name OR the raw phone number (depending on whether the number is in Contacts).

```python
appium("mobile: launchApp", bundleId="com.apple.MobileSMS")
wait_for_app("com.apple.MobileSMS")

PHONE = "+1 (XXX) XXX-XXXX"  # the recipient — pass in or read from caller

# Match by `label BEGINSWITH` — the label includes preview text after the number.
convo = wait_for_element(timeout=5.0)  # any element to confirm the list rendered
# Find the conversation cell whose label starts with the phone or contact name
candidates = [el for el in ui_tree() if el["label"].startswith(PHONE)]
if not candidates:
    raise RuntimeError(f"no conversation starts with {PHONE!r}")
tap(candidates[0])
```

The exact `label` format on a freshly received iMessage is:
`"+1 (XXX) XXX-XXXX. <preview text>. <date/time>."`

So `startswith(PHONE)` is the durable predicate. Don't match against the full label — preview text changes every time.

## Type and send

The compose field has a stable accessibility id: `messageBodyField`. The send button is conditional — only visible once the field has at least one character.

For **short messages** (< ~80 chars, ASCII-only):

```python
field = wait_for_element(name="messageBodyField", timeout=5.0)
tap(field)
type_text("hello from iphone-harness")
wait(0.3)  # let the Send button enable
```

For **long messages** (> ~80 chars) OR anything with non-ASCII (em-dash, curly quotes, emoji): **use `set_value`, not `type_text`.** Per-character `mobile: keys` is slow on iMessage's text view (~5+ seconds for 250 chars on a real device) and can time out the IPC client mid-message, leaving the text truncated. `set_value` is atomic and Unicode-safe:

```python
field = wait_for_element(name="messageBodyField", timeout=5.0)
tap(field); wait(0.3)
set_value("name == 'messageBodyField'", "Long message with em-dash — and emoji 🎉 …")
wait(0.5)  # let the Send button enable
```

Field's placeholder is `"iMessage"` (or `"Text Message"` for SMS). After `set_value`, re-read the field's `value` to confirm the message landed verbatim — the placeholder vanishes once content is present.

Then send (button matchers, in priority):

```python
# The send button can be matched two ways depending on iOS minor version:
#   - name == 'sendButton'
#   - label == 'Send' (older builds)
send = find(type="XCUIElementTypeButton", name="sendButton") \
    or find(type="XCUIElementTypeButton", label="Send")
tap(send)
```

## Verify

After the tap, the message bubble appears in the conversation. Verify by scrolling to bottom (Messages auto-scrolls, but verify) and checking the last bubble:

```python
wait(1.0)
sent = [el for el in ui_tree() if el["type"] == "XCUIElementTypeStaticText" and el["value"] == "hello from iphone-harness"]
assert sent, "message did not appear in the conversation"
```

## Traps

- **Conversation row vs. group row:** group iMessage threads have multiple participants in the label, often comma-separated. `startswith(PHONE)` won't match a group thread that *includes* PHONE — it might appear as `"Alice, +1 (XXX)…, Bob"`. Use `PHONE in el["label"]` if you want group threads.
- **Search bar:** Messages has a search bar at the top. Tapping it doesn't navigate — it puts focus in the search field. If you accidentally tap there, press the home button to back out.
- **Predictive bar interference:** the QuickType predictive bar can swallow the tap on Send if your tap coordinates land on a suggestion. The `find(type='XCUIElementTypeButton', name='sendButton')` selector is safe; raw `tap_at_xy(...)` derived from a screenshot is not.
- **iMessage vs. SMS color:** iMessage bubbles are blue, SMS green. Both work the same way for sending; this only matters when reading.
- **First message after a long quiet period:** Messages sometimes shows a "delivered" indicator on the previous bubble before the new one appears. Don't assume the latest bubble is yours — check by `value` not by position.

## What does NOT work yet

- Tapback / reactions: not covered here.
- Replying inline (thread reply): not covered here.
- Sending an image attachment: not covered here.

Open follow-up skill files for those when needed.
