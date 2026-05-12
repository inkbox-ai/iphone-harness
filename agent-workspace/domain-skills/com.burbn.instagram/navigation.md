# Instagram — Navigation & core selectors

Bundle id: `com.burbn.instagram`. Field-tested 2026-05-11.

Instagram exposes a **clean, stable accessibility id namespace**. Almost every action is reachable by `find(name="...")`. Prefer name-based selectors over coordinates here — Instagram's layout shifts often, but the ids don't.

## Bottom tab bar (y=813)

Five tabs, each a button with a stable name. All are always present at the bottom of the main feed (auto-hides on inner views like profile detail; see "back-out gotcha" below).

| `name` | What it opens |
|---|---|
| `mainfeed-tab` | Main feed (Home) |
| `reels-tab` | Reels feed |
| `direct-inbox-tab` | DMs. Label includes badge: `'Direct messages , N unread messages'` — parse the N |
| `explore-tab` | Explore / Search |
| `profile-tab` | Your own profile |

## Top bar (main feed)

| `name` | What it does |
|---|---|
| `create` | Opens Create-post creation menu (same as `profile-add-button` on profile) |
| `main-feed-logo` | Tap to scroll feed to top |
| `activity` | Opens Notifications (the "activity" feed) |

## First-launch / interstitial dismissals (recurring traps)

Instagram pops several modals on cold launches and at random intervals. Detect and dismiss each one:

| Modal | Dismiss with |
|---|---|
| "You have a say in your experience" (ad personalization) | `tap(find(label="Continue", type="XCUIElementTypeButton"))` |
| iOS App Tracking Transparency prompt | `tap(find(label="Ask App Not to Track"))` |
| "Allow Instagram to access your photos and videos" | `tap(find(name="ig-photo-library-priming-continue-button"))` — leads to iOS photo picker; only Allow if user has explicitly authorized |
| "Introducing the Instagram map" | `tap(find(name="Not now"))` |
| Other "X" / dismiss buttons | look for `find(name="Dismiss")` or `find(label="Not now")` |

Use this as your launch boilerplate:

```python
appium("mobile: launchApp", bundleId="com.burbn.instagram")
wait(3.5)
# Drain any first-launch interstitials
for _ in range(5):
    cont = find(label="Continue")
    if cont and find(label="Ask App Not to Track"):
        # The iOS-native tracking sheet — pick the privacy-safe option
        tap(find(label="Ask App Not to Track"))
        wait(1.5); continue
    not_now = find(label="Not now") or find(name="Not now")
    if not_now:
        tap(not_now); wait(1.5); continue
    cont = find(label="Continue", type="XCUIElementTypeButton")
    if cont and not find(name="mainfeed-tab"):
        tap(cont); wait(1.5); continue
    break
```

## Search (Explore tab)

```python
tap(find(name="explore-tab"))
wait(2.5)
sf = find(name="search-text-input", type="XCUIElementTypeSearchField")
tap(sf); wait(0.4)
set_value("name == 'search-text-input'", "openai")
wait(1.5)
```

Result cells follow this pattern:
- `search-collection-view-cell-<username>` — for account suggestions (e.g. `search-collection-view-cell-openai`)
- `search-collection-view-cell-<numeric-id>` — for search-term suggestions / topics
- Each cell contains child `StaticText` with: handle, "verified account" marker, follower count (`'5.2M followers'`)

**Trap: tapping the cell itself opens a search-results filter view, NOT the profile.** To navigate to a user's actual profile, tap the **`StaticText` whose name matches the username**:

```python
tap(find(name="openai", type="XCUIElementTypeStaticText"))
wait(3.5)
# Now on the real profile
```

## Profile page (yours or others')

Stable header selectors (work on any profile):

| `name` | What |
|---|---|
| `user-detail-header-media-button` | Posts count — child StaticText holds the number (`'1,748'`) |
| `user-detail-header-followers` | Followers count |
| `user-detail-header-following-button` | Following count |
| `user-detail-header-follow-button` | Follow/Unfollow toggle (label changes: `'Follow openai'` ↔ `'Following'`) |
| `profile-action-bar-button` | **3 instances per profile** — distinguish by `label`: `'Edit profile'` / `'Share profile'` (own profile) or `'Message'` (others) |
| `profile-more-button` | Settings & activity (own profile only; top-right) |
| `profile-more-bar-button` | More options (others' profiles) |
| `profile-add-button` | Create menu (own profile; top-left) |
| `user-switch-title-button` | Username in nav bar (your username) — tap for account switcher |
| `media-thumbnail-cell` | Each grid item. Label = `'Photo by <user>'` / `'Video by <user>'` / `'N photos or videos from <user>'` (carousel) |

Grid filter tabs (below the action bar):
- `ig_icon_photo_grid_tall_filled_24` — posts grid
- `ig_icon_reels_pano_prism_outline_24` — reels
- `ig_icon_reshare_outline_24` — reposts (own profile)
- `ig_icon_tag_up_outline_24` — tagged

## Feed-post action bar (any post in feed)

When a post is on screen, its action row has every selector you need:

| `name` | What |
|---|---|
| `like-button` | Tap to like/unlike |
| `like-count-button` | Static — label format: `'<N> likes'` |
| `comment-button` | Opens comments |
| `comment-count-button` | Label: `'<N> comments'` |
| `repost-button` | Repost |
| `repost-count-button` | Label: `'Repost number is <N>'` |
| `send-button` | DM this post |
| `reshare-count-button` | Label: `'<N> shares'` |
| `save-button` | Save to your collection |
| `feed-item-header-user-button` | Tap to open the author's profile. Label = username |
| `follow-button` | Follow/Unfollow the author. Label = `'Follow <user>'` |
| `more_options` | Three-dots menu (Report, Mute, Hide, etc.) |

Read like-count from a post:

```python
btn = find(name="like-count-button")
import re
m = re.match(r"(\d[\d,]*)\s+likes", btn.get("label",""))
likes = int(m.group(1).replace(",","")) if m else 0
```

## Edit profile

`tap(find(name="profile-action-bar-button", label="Edit profile"))` (it's an exact-match find).

Form fields, all stable names:

| `name` | What |
|---|---|
| `profile-full-name` | TextField |
| `profile-user-name` | TextField (handle — changing this has side effects, ask user) |
| `profile-pronouns` | TextField |
| `profile-links` | TextField |
| `profile-gender` | TextField |
| `change-profile-photo-button` | Avatar |
| `Edit profile picture` | (also a button) |
| `business-conversion-switch-to-profe` | Switch to professional account (don't tap without asking) |

For Bio, the StaticText `name="Bio"` is the label; the actual editable field appears when you tap below it (need to drill in).

## Notifications ("activity")

```python
tap(find(name="activity"))   # top-right of main feed
wait(2.5)
```

Each item is a `XCUIElementTypeCell` with `name="activity-story-item"`. The label contains the full notification text + relative timestamp (`'4 days ago'`, `'7 minutes ago'`).

Top of the page may have a `Follow requests` cell — tap to manage pending follow requests.

## Direct Messages (DM inbox)

```python
tap(find(name="direct-inbox-tab"))
wait(2.5)
```

Each conversation = `direct_recipient_core_view` button. Label format: `'<user>. Profile picture, <user>, Tap to chat'`.
- `direct-message-button` — New chat (top-right of inbox)
- `search-text-input` — search conversations (same name as Explore's search field, but a different element — scoped by foreground screen)
- `ig-direct-inbox-action-button` — multi-purpose: "Requests" tab, "See all" buttons

## Creation menu (Post / Reel / Story / Highlight / Fundraiser)

Open via either `profile-add-button` (profile tab) or `create` (main feed top bar).

Cells:
- `creation-reel` — Reel
- `creation-post` — Post (photo/video)
- `creation-story` — Story (24h)
- `creation-story-highlight` — Highlights (curated stories)
- `creation-fundraiser` — Fundraiser

Tapping any of these triggers the iOS **"Allow Instagram to access your photos and videos"** prompt on first use. The continue button is `ig-photo-library-priming-continue-button`. Following that prompt accept leads to the iOS PHPicker — granting Instagram access to user photos is sensitive; **only proceed with explicit user authorization.**

## The back-out trap

Once you tap into an inner profile or post, **the bottom tab bar disappears** (Instagram hides it on detail views). `find(name="profile-tab")` returns None until you navigate out.

Three ways to back out:

1. **iOS left-edge back swipe**: `swipe(5, sz["height"]//2, sz["width"]//2, sz["height"]//2, duration=0.3)`. Most reliable for profile detail views.
2. **Navbar BackButton**: `find(name="BackButton")` — only present on some inner views.
3. **Terminate + relaunch**: `appium("mobile: terminateApp", bundleId="com.burbn.instagram"); wait(1.5); appium("mobile: launchApp", bundleId="com.burbn.instagram")`. Last resort, but always works to reset to main feed.

## Scrolling

Use `scroll_by(dy=-700, velocity=1200)` for the feed and any list view. **Do NOT use bare `swipe()` on a feed** — the swipe start lands on a post cell and drills into the detail view first.

Instagram doesn't auto-load feed on a slow scroll; medium-fast flicks (`velocity=1200-1500`) work best.

## What I haven't tested

- Posting an actual photo (requires Photos permission, didn't grant)
- Sending a DM (requires choosing a real recipient + writing real text)
- Live video creation
- Story creation with stickers/text/music
- Comment composition (the comment field selector — probably `comment-text-input` by analogy with `search-text-input`)
- Reels swipe-up/swipe-down navigation
- Account switcher (`user-switch-title-button` tap)
- Settings menu (via `profile-more-button`)

Add follow-up skill files when you tackle those.
