# Instagram — Post a photo

Bundle id: `com.burbn.instagram`. Field-tested on iOS 18.3.2.

End-to-end autonomous photo post: pick from Photos → caption → Share. Assumes the image is already in the iPhone Photos library (use `native_screenshot()` from `interaction-skills/native-screenshot.md` if you need to get it there first).

Companion to `navigation.md` (general IG selectors) — this doc covers only the post-creation flow.

## Full flow

```python
appium("mobile: launchApp", bundleId="com.burbn.instagram")
wait_for_app("com.burbn.instagram")
wait(2.0)

# 1. Open creation menu
tap(find(name="create", type="XCUIElementTypeButton"))
wait(2.5)

# 2. If first-time use of Photos in this IG install, dismiss permission priming
priming = find(name="ig-photo-library-priming-continue-button")
if priming:
    tap(priming); wait(2.5)
    # iOS-native PHPicker permission sheet — prefer Limit Access (privacy-safe)
    limit = find(label="Limit Access…")  # NOTE: curly ellipsis, not three dots
    if limit:
        tap(limit); wait(2.5)
        # Now in the photo picker grid

# 3. Pick the photo
# The picker grid items are NOT well-exposed via accessibility name. Tap by
# coordinate — newest photos are at top-left. On a 414×896 device the first
# tile sits at roughly (62, 280).
tap_at_xy(62, 280)
wait(1.5)
# The picker's Done button persists in the top-right — tap it to commit selection
tap(find(label="Done", type="XCUIElementTypeButton"))
wait(3.0)

# 4. Composer page (preview + POST/STORY/REEL selector)
tap(find(label="Next", type="XCUIElementTypeButton")); wait(3.5)

# 5. Filter/edit page — skip
tap(find(label="Next", type="XCUIElementTypeButton")); wait(3.5)

# 6. Final composer — caption + Share
field = find(name="caption-cell-text-view", type="XCUIElementTypeTextView")
tap(field); wait(1.0)
type_text("Hello world")
wait(0.6)
# Tapping OK exits the caption sub-screen and returns to the main composer
tap(find(label="OK", type="XCUIElementTypeButton"))
wait(2.0)

# 7. Post
tap(find(label="Share", type="XCUIElementTypeButton"))
wait(6.0)  # Instagram needs time to upload + process
```

## Verification

Look for the post-success banner: `"Done posting. Want to send it directly to friends?"` — present in the tree as a `StaticText`. Also: the foreground bundle id stays `com.burbn.instagram` and the user's handle appears in a fresh feed cell beneath the banner.

```python
# Wait up to 10s for the success banner
hit = wait_for(
    lambda: any("Done posting" in (el.get("label","")) for el in ui_tree()),
    timeout=10.0,
)
if not hit:
    raise RuntimeError("post-success banner not seen — upload may have failed")
```

## Selectors used (stable)

| `name` | Type | What |
|---|---|---|
| `create` | Button | Top-left + in main feed → opens creation menu |
| `ig-photo-library-priming-continue-button` | Button | Continue past IG's permission priming page |
| `caption-cell-text-view` | TextView | The caption input field on the final composer screen |
| `creation-post`, `creation-reel`, `creation-story`, `creation-story-highlight`, `creation-fundraiser` | Cell | Creation-menu rows — for posts always use `creation-post` (or just the auto-flow via `create`) |

Plus label-matched buttons: `Next`, `OK`, `Share`, `Done`, `Cancel`, `Limit Access…`, `Allow Full Access`, `Don't Allow`.

## Traps

- **Curly-ellipsis in "Limit Access…"** — Apple's native PHPicker prompt uses U+2026 `…`, not three ASCII dots. `find(label="Limit Access...")` returns None. Always match the curly form.
- **Picker grid cells are not name-addressable.** The iOS PHPicker doesn't expose each photo's date/identifier in a way our `find()` can match. Coordinate-tap by row/column is the only reliable path. Newest is at top-left `(62, 280)` on 414×896 devices; subsequent rows are ~120px tall, columns are ~125px wide.
- **First-launch interstitials** — see `navigation.md` for the full list (ATT prompt, ad personalization, Instagram map). They may appear *between* steps if you took a long pause; check after every wait.
- **The "Add AI Label" toggle** at the bottom of the composer — leave it off for unmodified photos. Toggle it on if your image was AI-generated; IG will flag it for viewers. The selector is a `XCUIElementTypeSwitch` near the bottom of the composer.
- **Two "Next" buttons in sequence** — the composer flow has THREE screens after picking the photo: (1) crop/select-mode picker, (2) filter/edit, (3) caption+share. Tap Next on the first two; the third's primary action is Share.
- **Share button can be temporarily disabled** while the photo is processing — wait ~1s after entering the final composer before tapping it.
- **Post upload takes 3-6s.** `wait(6.0)` after Share is a reasonable default; longer for videos.

## What this skill does NOT cover

- Multi-photo carousel posts (selecting >1 photo in the picker)
- Story / Reel composition (different flow, different actions)
- Tagging people / adding location (need separate sub-flows for each)
- Cross-posting to Facebook (separate toggle on the final composer)
- AI Label (handled briefly above; deeper config is a separate skill)
- Editing or deleting an existing post

Add follow-up skill files for those when needed.
