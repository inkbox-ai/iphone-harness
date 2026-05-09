# OCR fallback

When the accessibility tree doesn't reach the content, fall back to Apple Vision OCR via `ocr()`.

Cases where the tree fails you:
- Camera viewfinder / Photos thumbnails (image content)
- Web views (Safari, in-app SFSafariViewController) — text is there, but it's behind WKWebView and often not exposed
- Custom-drawn UIs (game-like menus, charts, canvas-based apps)
- "What's New" splash screens that hide their text behind static images
- Firmware-level dialogs and the lock screen
- Apps that explicitly hide accessibility (some banking, some ID/wallet)

## The OCR call

```python
lines, (px_w, px_h) = ocr()  # auto-screenshots first
# lines: [{"text": "Cancel", "confidence": 0.99, "box": [x, y, w, h]}, ...]   # PIXEL coords
```

Pixel coords come back in *physical* pixels. A 2× device (e.g. iPhone 11/XR-class) produces a screenshot whose width and height are 2× the values `window_size()` returns; a 3× Pro device produces 3× — so `ocr()` boxes can be 2× or 3× the values you'd pass to `tap_at_xy()`. Always derive the scale at runtime; never assume:

```python
sz = window_size()
sx, sy = sz["width"] / px_w, sz["height"] / px_h
for line in lines:
    x, y, w, h = line["box"]
    cx_pt = (x + w/2) * sx
    cy_pt = (y + h/2) * sy
    print(line["text"], "→", cx_pt, cy_pt)
```

Or use the convenience: `find_text("Cancel")` returns the matching line dict already augmented with `cx_pt`, `cy_pt`:

```python
m = find_text("Cancel")
if m: tap_at_xy(m["cx_pt"], m["cy_pt"])
```

## Annotated screenshot for LLM grounding

```python
path, lines = annotated_screenshot()  # red boxes + numeric labels around each OCR line
print(path)  # e.g. /tmp/iph-shot.annotated.png
```

Pass this PNG + the `lines` list to a vision-capable LLM. The numbers in the image map to indices in `lines` — the model can say "tap box 7" and you do `lines[7]`.

This is the iPhone-native version of the "indexed elements" pattern from web automation. Use it when:
- you can't trust the accessibility tree
- you want to give the LLM a unified visual + spatial reference
- you're building a screen-reasoning loop (look → think → tap)

`annotated_screenshot(run_ocr=False)` annotates UI-tree elements instead of OCR lines — useful when the tree is rich but you want to point an LLM at specific nodes.

## Caveats

- **OCR is slower than the tree.** ~300-800ms per screen. Don't run it in tight loops.
- **Confidence < 0.5 is unreliable.** Filter early.
- **Vision misreads small text** at scale 1×. If a critical button is tiny, screenshot a region and OCR that.
- **Languages:** pass `languages=("en-US","fr-FR",...)` for multilingual UIs. Default is English only.
