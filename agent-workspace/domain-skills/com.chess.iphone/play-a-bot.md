# Chess.com — Play a Bot

Bundle id: `com.chess.iphone`. Field-tested on iOS 18.3.2.

**App mechanics only** — selectors, navigation, move-entry, end-game UI. This document is silent on chess strategy.

## Why this app is friendly to automate

Chess.com exposes an **exceptionally clean accessibility tree** for the board. Every piece is a `XCUIElementTypeImage` whose label encodes both the piece type AND the square in algebraic notation (e.g. `White Pawne2`, `Black Knightg8`). Empty destination squares for the currently-selected piece are labeled with just the square (e.g. `e4`). The move list at the top of the game screen is fully readable and labels each move in standard algebraic notation.

This means: **no coordinate math is needed**. Pieces and squares are addressable by name.

## Entering the bot game

```python
# Launch
appium("mobile: launchApp", bundleId="com.chess.iphone")
wait_for_app("com.chess.iphone")
wait(4.0)

# Home tab → Play
tap(find(label="Play", type="XCUIElementTypeButton")); wait(3.5)

# Play menu → Play a Bot
tap(find(label="Play a Bot")); wait(3.5)
```

## Bot picker

The bot grid is grouped: **PIRATES** (themed), **ADAPTIVE** (locked behind Diamond membership), **BEGINNER**, plus more sections below. Each bot is a `XCUIElementTypeImage` with a label like `'Polly, Rated 199'` — the rating is parseable.

To pick the lowest-rated bot:

```python
import re
bots = []
for el in ui_tree(visible_only=True):
    if el["type"] != "XCUIElementTypeImage": continue
    lab = el.get("label","")
    m = re.match(r"^(.+?), Rated (\d+)$", lab)
    if m:
        bots.append((int(m.group(2)), m.group(1), el))
bots.sort()
lowest = bots[0]  # → (199, 'Polly', <element>)
tap(lowest[2]); wait(0.6)
tap(find(label="Choose", type="XCUIElementTypeButton")); wait(3.5)
```

Locked bots show a 🔒 icon overlay but they're still in the tree. Don't try to select them — they'll trigger a paywall sheet.

## Game setup screen

After picking a bot, a setup screen appears with three sections:

| Section | Default | Options |
|---|---|---|
| **I PLAY AS** | White (king icon highlighted) | White / Random / Black |
| **MODE** | **Friendly** (Hints & takebacks allowed) | Challenge / Friendly / Assisted / Custom |
| **Big green button** | `Play!` | — |

Friendly mode is what an automation agent wants — it allows takebacks if a move is illegal, and shows hint markers (small green dots on suggested squares) that can be used as visual aids.

```python
tap(find(label="Play!", type="XCUIElementTypeButton"))
wait(5.0)
```

## Move-entry pattern

Two-tap: **tap the piece → tap the destination**.

```python
# Selectors
piece = find(label="White Pawne2", type="XCUIElementTypeImage")
tap(piece); wait(1.0)

# After selecting a piece, every legal destination square becomes a tappable
# XCUIElementTypeImage with label equal to the algebraic-notation square name.
dest = find(label="e4", type="XCUIElementTypeImage")
tap(dest); wait(3.0)   # Bot's reply animates in within ~2-3s
```

### Capturing a piece

For captures, the destination label is the **target piece's name**, not the square name. The square label is only present for empty destinations.

```python
# White knight on c3 captures black pawn on d5
tap(find(label="White Knightc3")); wait(1.0)
tap(find(label="Black Pawnd5"))   # the target piece is the tap target
wait(3.0)
```

### Castling

Tap the king, then tap the destination square (`g1` for kingside, `c1` for queenside as white):

```python
tap(find(label="White Kinge1")); wait(1.0)
tap(find(label="g1"))   # kingside castle
wait(3.0)
```

### Promotion

When a pawn reaches the back rank, a promotion picker appears as a popover with four piece images. Each is labeled with the piece type — tap whichever is wanted. Default to Queen unless specified:

```python
# After moving a pawn to the back rank, the picker auto-appears
tap(find(label="Queen", type="XCUIElementTypeImage"))
wait(2.0)
```

## Reading the position

Every piece on the board is a `XCUIElementTypeImage` with label `"<Color> <Piece><file><rank>"`. This is the cleanest possible API for board state.

```python
def board_state():
    """Return a dict mapping square → piece (e.g. {'e4': 'White Pawn', ...})."""
    state = {}
    for el in ui_tree(visible_only=True):
        if el["type"] != "XCUIElementTypeImage": continue
        lab = el.get("label","")
        if lab.startswith(("White ", "Black ")):
            # Label is like "White Pawne2"; the last 2 chars are the square
            sq = lab[-2:]
            piece = lab[:-2]
            state[sq] = piece
    return state

print(board_state())
# → {'a8': 'Black Rook', 'b8': 'Black Knight', ..., 'e2': 'White Pawn', ...}
```

## Reading the move list

The move list is rendered as a horizontal scrolling bar at the top of the game screen. Each move pair is `<number>. <white> <black>`, with each move as its own `XCUIElementTypeButton` whose label is the algebraic-notation move:

```python
def move_list():
    """Read the move list. Returns a list of (white, black) tuples."""
    seen = set()
    moves = []
    pair_white = None
    for el in ui_tree(visible_only=True):
        if el["type"] != "XCUIElementTypeButton": continue
        lab = el.get("label","")
        if not lab or el["y"] > 200: continue
        # Move labels are short algebraic notation: 1-6 chars, no spaces
        if 1 <= len(lab) <= 7 and lab not in seen and not lab.endswith("."):
            seen.add(lab)
            # Heuristic: this iteration alternates white→black→white...
            if pair_white is None:
                pair_white = lab
            else:
                moves.append((pair_white, lab))
                pair_white = None
    if pair_white:
        moves.append((pair_white, None))
    return moves
```

Captured this state mid-game (move 13 in a Sicilian):
```
[('e4','c5'), ('Nf3','Nc6'), ('d4','cxd4'), ('Nxd4','Nf6'), ('Nc3','e6'),
 ('Be3','g6'), ('Bc4','d5'), ('exd5','exd5'), ('Nxd5','Nxd5'),
 ('Bxd5','Qxd5'), ('O-O','a5'), ('c4','Qd8'), ('Nb5','Qxd1')]
```

## In-game bottom bar

| `name` / `label` | Type | What |
|---|---|---|
| `Options` | Cell | Game menu — change board theme, resign, abort, settings |
| `Resign` | Cell | Resign the game (prompts for confirmation) |
| `Hint` | Cell | Shows a suggested move (Friendly / Assisted mode only) |
| `Undo` | Cell | Take back the last move pair (Friendly / Assisted mode only) |

Note: these are `XCUIElementTypeCell`, not Button. Predicate accordingly.

## Hint markers

In Friendly / Assisted mode, when a piece is selected, **the suggested destination square is also rendered as a discoverable element** with label = the square's algebraic notation (e.g. `e4`). The same `e4` element is also the legal-move target for the currently-selected piece — there's no separate "suggestion" element.

This means a naive "find by square" can succeed for either an empty legal destination OR a hint marker — they're the same element. The label disappears as soon as the move is played.

## End-game flow

When a game ends (resign, checkmate, draw, etc.):

1. A modal appears with `<Bot name> Won by <reason>` / `You Won by <reason>` heading
2. Player avatars + names shown
3. Three action buttons: `Game Review` / `New Bot` / `Rematch`
4. Below: marketing CTA ("Take Your Game to the Next Level" — Diamond upsell)

```python
# Resign flow
tap(find(label="Resign", type="XCUIElementTypeCell")); wait(2.0)
# Confirmation dialog appears
confirm = next((el for el in ui_tree()
                if el.get("label") == "Resign"
                and el["type"] == "XCUIElementTypeButton"
                and el["y"] > 700), None)
tap(confirm); wait(3.0)

# End-game modal now visible
end_text = next((el.get("label","") for el in ui_tree(visible_only=True)
                 if el["type"] == "XCUIElementTypeStaticText"
                 and "Won by" in el.get("label","")), None)
print(end_text)   # → "Polly Won" + separately "by Resignation"

# Dismiss / next action
tap(find(label="New Bot", type="XCUIElementTypeButton")); wait(2.5)
# or tap(find(label="Rematch")), etc.
```

## Traps

- **Friendly-mode green dots are NOT separate elements.** They visually mark legal destinations but in the tree they're just the square labels (`e4`, `f3`, etc.) — the same nodes you'd tap anyway. Don't try to "find a hint marker" and then "tap the square underneath" — there's only one element per square.
- **Capture destinations are addressed by the captured piece's label**, not the square. Tapping `find(label="d5")` when a black pawn is on d5 returns None; use `find(label="Black Pawnd5")` instead.
- **Move-list buttons appear before the move is actually played on the board.** Don't use move-list state as a source of truth for whose turn it is — use piece positions.
- **Bot "talking" speech bubbles overlay the board** but don't block taps. They auto-dismiss after 2-3 seconds. If a tap appears to miss, wait 2s for the bubble to fade and retry.
- **`Resign` is a Cell, not a Button.** `find(label="Resign", type="XCUIElementTypeButton")` returns None and only finds the confirmation-dialog Button. Use the Cell type for the bottom-bar entry, the Button type for the confirmation.
- **The bot's reply takes 1–4 seconds** at low difficulty levels — longer at higher ratings. A `wait(3.0)` after each player move is a safe default; reduce/increase based on bot strength.
- **WDA `page_source` occasionally returns `socket hang up`** mid-game (transient WDA hiccup unrelated to chess.com). Retry the call once before treating it as a real error.
- **Disambiguating two pieces of the same type on the same rank** (e.g. two White Pawns moving up the board) is automatic because the label includes the square. But after Nxd5 / Nxd5 / Bxd5 / Qxd5 sequences where multiple pieces visit d5, only one piece is on d5 at any moment — the label is always unambiguous.

## What this skill does NOT cover

- Online play against humans (different flow, matchmaking, time controls, chat moderation)
- Puzzles, lessons, tournaments — different bundle areas with their own selectors
- Time controls / clock interaction in timed games
- Drawing arrows / highlighting squares (long-press gestures on the board)
- Board theme / piece-set customization (Options menu)
- Setting up custom positions from FEN
- The chess strategy itself (this skill is mechanics-only by design)

For game-strategy decisions, the agent should rely on its own chess knowledge or the in-game hint feature — Chess.com's hint marker in Friendly mode is reliably accurate and addressable by label.
