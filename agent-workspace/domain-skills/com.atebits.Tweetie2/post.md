# X (Twitter) — Post

Bundle id: **`com.atebits.Tweetie2`** *(legacy id from the Twitter→X rename; the app's internal Apple ID still points to "Tweetie2")*. Field-tested on iOS 18.3.2.

End-to-end autonomous post with optional image attachment. Assumes the user is already signed in.

## Flow — text-only post

```python
appium("mobile: launchApp", bundleId="com.atebits.Tweetie2")
wait_for_app("com.atebits.Tweetie2")
wait(4.0)

# 1. Open composer — the floating action button bottom-right
tap(find(name="FabComposeButton"))
wait(3.0)

# 2. Write the text — TextView's name is the placeholder text including
#    trailing space; predicate by type for robustness.
MSG = "your post text here, URLs auto-link"
set_value("type == 'XCUIElementTypeTextView'", MSG)
wait(0.6)

# 3. If your text contains a URL, X auto-generates a link-preview card
#    BELOW the text. To remove it, see the "Link preview cards" section
#    below.

# 4. Submit
tap(find(label="Post", type="XCUIElementTypeButton"))
wait(5.0)
```

## Selectors

| `name` / `label` | Type | What |
|---|---|---|
| `FabComposeButton` | Button | Floating Action Button (bottom-right of feeds) — opens composer |
| `What's happening? ` *(includes trailing space)* | TextView | Main post text area. Name is the placeholder string; for robustness predicate by type instead: `type == 'XCUIElementTypeTextView'` |
| `Everyone` (or `Verified accounts`, `My Communities`, etc.) | Button | Audience selector — tap to switch reply visibility. Leave alone unless user specifies |
| `Cancel` (top-left of composer) | Button | Abort. Triggers a Save Draft? prompt |
| `Post` (top-right of composer) | Button | Submit. Disabled until text has any content |
| `Everyone can reply` | Button | Reply-controls modal entry — DM-only, only some accounts, etc. |
| Bottom-row icons (image picker, camera, GIF, etc.) | Buttons | All in the tool row above the keyboard, all addressable |

## Link preview cards

When the post text contains a URL, X **auto-generates a link-preview card** below the text. The card appears as an Other/Image element with the link's title, description, and a small thumbnail. To dismiss it (keep the URL as plain text only):

```python
# After typing text containing a URL, wait ~1s for the card to appear
wait(1.0)

# The card has a small dismiss-X in its top-right corner. The button may
# be unlabeled — find it by position: it's the topmost button inside the
# card's y-range (typically y=280-410) at the right edge (x≈360+).
for el in ui_tree(visible_only=True):
    if (el["type"] == "XCUIElementTypeButton"
        and 250 < el["y"] < 420
        and el["x"] > 340):
        tap(el); wait(0.6)
        break
```

Alternative: dismiss the card by simply tapping the visible X at coordinates approximately `(385, 290)` on a 414×896 device. The exact y depends on the card's expanded height (a card with a thumbnail is taller than one without).

If the link card's dismiss button isn't reachable by predicate, fall back to OCR (`find_text("✕")` or `find_text("Close")`) or visual inspection via `screenshot()` + `Read`.

## Attaching an image

The image-picker entry is in the bottom tool row, above the keyboard:

```python
# Look for the image/photo icon — its name varies by X version. Find the
# leftmost button in the tool row (y ≈ 550-600 with keyboard up).
icons = [el for el in ui_tree(visible_only=True)
         if el["type"] == "XCUIElementTypeButton"
         and 540 < el["y"] < 620
         and el["x"] < 80]
tap(icons[0])  # leftmost = photo library
wait(3.0)

# X uses a custom in-app picker (NOT the iOS-native PHPicker). Handle the
# first-time-use Photos-permission flow if presented:
allow = find(label="Allow Access to All Photos") or find(label="Limit Access…")
if allow:
    tap(find(label="Limit Access…"))   # curly-ellipsis U+2026
    wait(3.0)
    # iOS native picker grid — newest at top-left
    tap_at_xy(62, 290)
    wait(1.0)
    tap(find(label="Done", type="XCUIElementTypeButton"))
    wait(3.0)
    # Returns to X's internal picker

# In X's internal picker, the newest photo is the first cell in the grid.
# Tap it, then tap the "Add" or done equivalent.
photo_cells = [el for el in ui_tree(visible_only=True)
               if el["type"] == "XCUIElementTypeCell"
               and "Photo" in el.get("label","")]
if photo_cells:
    tap(photo_cells[0]); wait(1.0)
# X may auto-attach on first tap, or require a confirm button:
add = find(label="Add") or find(label="Done") or find(label="Next")
if add: tap(add); wait(3.0)
```

After attachment, the composer renders the image inline below the text. The Post button stays enabled (or re-enables after upload).

## Verifying success

X doesn't show an explicit "Posted" banner like LinkedIn does — instead it just closes the composer and returns to the feed. Verify by checking the foreground state:

```python
# After tapping Post + waiting:
wait(5.0)
# The composer is gone if 'FabComposeButton' is visible again
if find(name="FabComposeButton"):
    print("posted — composer closed, back on feed")
else:
    raise RuntimeError("composer didn't close — post may have failed or is uploading")
```

For a stronger confirmation, the user's most recent post should now appear at the top of their profile. Navigate via Account Menu → Profile and check the first cell.

## Traps

- **The bundle id is `com.atebits.Tweetie2`, not `com.twitter.twitter` or `com.x.X`.** Atebits is the company Twitter acquired the original Tweetie iOS client from; Apple bundle ids don't rename even when the product does.
- **The TextView's `name` is the placeholder string** including a trailing space: `'What's happening? '`. Don't predicate on it — use `type == 'XCUIElementTypeTextView'`.
- **Link-preview cards auto-expand below the text** for any URL the post contains. If the user doesn't want the card, dismiss it via the card's X button BEFORE tapping Post. After Post, the card is committed and can't be removed (without deleting and reposting).
- **X's photo picker is NOT the iOS-native PHPicker.** It's an internal grid. The PHPicker only appears as an intermediate step the first time Photos permission is granted (or when "Limit Access" is in effect — to pick which additional photos to expose). After that, X works directly with whatever's in its allowed set.
- **`Limit Access…` uses U+2026 curly ellipsis** in the iOS permission sheet. `find(label="Limit Access...")` (three ASCII dots) returns None.
- **The Post button is at the top-right of the composer**, not bottom. Compose-screen bottom is the tool row + keyboard.
- **Bot speech bubbles** (yes, X has these too on certain Premium AI Reply prompts) overlay the composer for ~2 seconds when first opening. Wait them out before predicate-finding buttons.
- **Account Menu** is the side-drawer entry (top-left), NOT a tab bar item. X's bottom tab bar shows feed / search / notifications / messages but not profile — profile is via the Account Menu drawer.
- **Drafts auto-save** when tapping Cancel. The next composer open may resume the saved draft; clear with `set_value("type == 'XCUIElementTypeTextView'", "")` before typing fresh.

## What this skill does NOT cover

- Replying to / quoting an existing post (long-press on a feed post opens the action menu; selectors differ)
- DM composition (different bundle area, different selectors)
- Threads (multi-post chains — there's a `+` button to add subsequent posts to the same thread)
- Polls
- Premium features (Audio, Spaces, longer character limits, Articles, etc.)
- Editing a posted post (Premium-only)
- Following / unfollowing users programmatically (long-press on a profile card)
- Direct-URL navigation via `x://` URL scheme

Open follow-up skill files for those when needed.
