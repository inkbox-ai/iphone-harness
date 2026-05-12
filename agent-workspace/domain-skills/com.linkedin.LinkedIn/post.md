# LinkedIn — Post

Bundle id: `com.linkedin.LinkedIn`. Field-tested on iOS 18.3.2.

End-to-end autonomous text post (with optional image). Assumes the user is already signed into LinkedIn on the device.

## Flow — text-only post

```python
appium("mobile: launchApp", bundleId="com.linkedin.LinkedIn")
wait_for_app("com.linkedin.LinkedIn")
wait(4.0)   # cold launches need this

# 1. Open composer — Post button is the top-right of the home tab
tap(find(label="Post", type="XCUIElementTypeButton"))
wait(3.5)

# 2. Write the message
MSG = "Hello World!\n\nThis is a multi-line post with a URL: https://example.com"
set_value("type == 'XCUIElementTypeTextView'", MSG)
wait(0.6)

# 3. Submit
tap(find(label="Post", type="XCUIElementTypeButton"))
wait(6.0)   # upload + post-success animation

# 4. Verify
ok = wait_for(
    lambda: any("Post successful" in el.get("label","") for el in ui_tree()),
    timeout=10.0,
)
if not ok:
    raise RuntimeError("post-success screen did not appear")
```

After success, LinkedIn may show a "Share this post on your page" nag — tap **Not now** to dismiss:

```python
not_now = find(label="Not now", type="XCUIElementTypeButton")
if not_now: tap(not_now); wait(2.0)
```

## Selectors (stable)

| `name` / `label` | Type | What |
|---|---|---|
| `Post` *(top-right of home tab)* | Button | Opens composer |
| `Post` *(top-right of composer)* | Button | Submits — disabled until min character count is met |
| `feedComposeGalleryButton` | Button | Image picker entry (composer) |
| `feedComposeMoreButton` | Button | More sharing options (composer) |
| `ComposeWritingAssistantPremiumButton` | Button | "Rewrite with AI" — Premium-only |
| The TextView itself | `XCUIElementTypeTextView` | The post body; placeholder label is `"Share your thoughts..."`. Name is a numeric LinkedIn internal id (not stable across versions). |
| `Anyone ▾` | Button | Audience selector. Tap to switch from Anyone → Connections only → Group, etc. |
| `Cancel` / `X` (top-left of composer) | Button | Discard composer (prompts to save draft) |

For the audience selector, `Anyone` is the default. Don't change it unless the user specifies — accidentally posting to "Connections only" makes the post invisible to most viewers.

## Text content

- **Newlines work** in `set_value()`. `"Line 1\n\nLine 2"` produces an empty line between Line 1 and Line 2, just like the iOS-native paste behavior.
- **URLs** auto-link when the post renders, no special escaping needed.
- **Emoji** work in `set_value()` (it's Unicode-safe). Avoid `type_text()` for emoji — slow per-character and some glyphs fail.
- The minimum character count is **20**. The composer's Post button stays disabled until you hit it. The counter renders as `<current>/20` in the bottom-left while you're under the minimum, then disappears.

## Traps

- **"Rewrite with AI"** sits where one might expect a submit button. The Submit is the top-right `Post` button, not the bottom-left AI button.
- **The TextView's `name` is a numeric LinkedIn ID** like `'13617'`. Don't predicate on it — use `type == 'XCUIElementTypeTextView'` or `label == 'Share your thoughts...'`.
- **Audience selector affects post reach.** Always verify it reads `Anyone` (or whatever the user specified) before posting.
- **The composer auto-saves drafts.** Tapping the top-left `X` to abort triggers a "Save Draft?" alert. Choose `Discard` to throw it away cleanly.

## What this skill does NOT cover

- Posting to a Company Page (rather than the personal profile)
- Carousels / multi-photo posts
- Document attachments (PDFs, slides)
- Polls / events / fundraisers
- Adding hashtags via the @mention helper (just type `#tag` directly in the body — works fine)
- Replying to a post / commenting on a post (different flow, different selectors)
- Scheduling a post (the clock icon next to the Post button)

Open follow-up skill files when tackling those.

---

## Appendix — Attaching an image

The composer's bottom-right `🖼️` button (`feedComposeGalleryButton`) opens an iOS PHPicker. Add an image step between **2. Write the message** and **3. Submit**:

```python
# 2b. Open LinkedIn's image picker
tap(find(name="feedComposeGalleryButton"))
wait(3.0)

# 2c. Handle iOS native Photos permission prompt (first-time only)
limit = find(label="Limit Access…")  # NOTE: curly ellipsis U+2026, not three dots
if limit:
    tap(limit); wait(3.0)
    # iOS PHPicker grid is now visible. Newest photo is top-left at (62, 290)
    # on a 414×896 device. PHPicker cells aren't reliably name-addressable —
    # coordinate-tap is the right tool.
    tap_at_xy(62, 290)
    wait(1.0)
    tap(find(label="Done", type="XCUIElementTypeButton"))
    wait(3.5)

# 2d. LinkedIn's internal picker shows what it can see from the (now-limited)
#     Photos library. Each photo cell has a name like
#     'Photo from May 11, 2026 11:58:42 PM' — find the most recent one.
clawd = next(
    (el for el in ui_tree()
     if el["type"] == "XCUIElementTypeCell"
     and el.get("label","").startswith("Photo from")),
    None,
)
tap(clawd); wait(1.5)
tap(find(label="Add", type="XCUIElementTypeButton"))
wait(3.5)

# 2e. Image-edit preview appears (pencil, ALT, person-tag). Tap Next to
#     return to the composer with the image attached.
tap(find(label="Next", type="XCUIElementTypeButton"))
wait(3.5)
```

After the image is attached, continue with **3. Submit** as in the text-only flow.

### Image-attach traps

- **Two pickers in sequence.** Tapping `feedComposeGalleryButton` opens iOS's PHPicker first (with optional `Limit Access` flow). After that, LinkedIn shows its **own** internal picker with a `Cancel | Recents | Add` chrome. You must tap a photo *and* then `Add` — selecting alone doesn't proceed.
- **`Limit Access…` uses U+2026 curly ellipsis.** `find(label="Limit Access...")` (three ASCII dots) returns None.
- **The image-edit preview has a `Next` button**, not a Done or confirm. Don't tap the pencil/ALT/text icons unless the user specifies — those open editing sub-flows that have to be backed out of separately.
- **PHPicker cells are not name-addressable.** The iOS Photos picker (the system-level one, before LinkedIn's internal picker) doesn't expose each cell with a `name` we can predicate on. Coordinate-tap to `(62, 290)` for the top-left/newest is the reliable approach.
- **The Post button takes ~2-6 seconds** to enable after the image attaches (LinkedIn is uploading in the background). If `tap(Post)` produces no visible effect, wait 2-3 more seconds and re-find — it may have been disabled at tap time.
- **Image edit chrome obscures the image preview** at the top of the composer. Don't worry about this — the image renders correctly in the published post.

### Verification of the attached image

The composer renders the image inline below the text after `Next`. Confirm before posting:

```python
img = find(type="XCUIElementTypeImage")  # may need a more specific predicate if the composer shows multiple
assert img is not None, "image did not attach to composer"
```
