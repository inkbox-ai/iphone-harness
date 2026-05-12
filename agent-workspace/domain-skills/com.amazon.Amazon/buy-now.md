# Amazon — Buy Now (one-step reorder)

Bundle id: `com.amazon.Amazon`. Field-tested on iOS 18.3.2.

End-to-end **autonomous purchase**. Skips the cart, uses Amazon's Buy Now flow. Assumes the user is already signed in to Amazon with a default payment method and at least one saved address.

⚠️ **This skill spends money.** Doctrine: **always pause for explicit user confirmation immediately before tapping the final "Place your order" button.** Never auto-pay.

## Flow

```python
appium("mobile: launchApp", bundleId="com.amazon.Amazon")
wait_for_app("com.amazon.Amazon")
wait(3.0)

# 1. Find the product — fastest path is the top search field, which auto-suggests
#    past searches first.
sf = find(type="XCUIElementTypeSearchField")
tap(sf); wait(0.6)

# Optional: if the user has bought it before, an autocomplete suggestion
# matching their query usually appears. Tap that to short-circuit the search.
suggestion = find(label="<exact past-search-text>", type="XCUIElementTypeButton")
if suggestion:
    tap(suggestion); wait(4.0)
else:
    set_value("type == 'XCUIElementTypeSearchField'", "<query>")
    wait(0.5)
    # Submit via the keyboard search key
    go = next((e for e in ui_tree()
               if e["type"] in ("XCUIElementTypeButton","XCUIElementTypeKey")
               and e.get("label","").lower() in ("search","go","return")
               and e["y"] > 600), None)
    tap(go); wait(4.0)

# 2. Pick the right product card on the search-results page.
#    Skip any element whose label starts with 'Sponsored Ad' — those are paid
#    placements, not what the user wanted.
#    Prefer cards with a 'Purchased N times' badge — they match the user's
#    real history.
product_link = next(
    (el for el in ui_tree()
     if el["type"] == "XCUIElementTypeLink"
     and "<product distinguishing phrase>" in el.get("label","")
     and "Sponsored" not in el.get("label","")),
    None,
)
tap(product_link); wait(5.0)

# 3. On the product detail page, scroll until 'Buy Now' is visible.
def find_buy_now(): return find(label="Buy Now", type="XCUIElementTypeButton")
buy = find_buy_now()
while buy is None:
    scroll_by(dy=-400, velocity=800); wait(1.0)
    buy = find_buy_now()
tap(buy); wait(5.0)

# 4. Single-tap checkout screen appears. Verify it BEFORE the user confirms.
#    Read the totals, the Ship-to address, and the payment method from
#    the visible elements:
addr   = next((el for el in ui_tree() if "Ship to" in el.get("label","")), None)
pay    = next((el for el in ui_tree() if "Pay with" in el.get("label","")), None)
total  = next((el for el in ui_tree() if "Total" in el.get("label","")), None)
# Show these to the user. Confirm address, payment, and total are what they expect.

# 5. ⚠ AGENT MUST STOP HERE FOR EXPLICIT USER CONFIRMATION.
#    Do not auto-tap 'Place your order'. Wait for the user to say yes.

# 6. On user confirmation only:
tap(find(label="Place your order", type="XCUIElementTypeButton"))
wait(6.0)

# 7. Verify success.
ok = wait_for(
    lambda: any("Order placed" in el.get("label","") for el in ui_tree()),
    timeout=15.0,
)
if not ok:
    raise RuntimeError("'Order placed' confirmation did not appear — order status unknown")
```

## Variant disambiguation

When a search returns multiple variants of the same product, use the **"Purchased N times"** badge as the signal for "the one I like." Amazon shows it above the price for items the user has bought before:

```python
# Highest purchase-count variant wins
candidates = []
for el in ui_tree():
    if el["type"] == "XCUIElementTypeLink" and el.get("label","").startswith("<brand prefix>"):
        # Look for sibling 'Purchased N times' StaticText near same y
        nearby = [s for s in ui_tree()
                  if s["type"] == "XCUIElementTypeStaticText"
                  and abs(s["y"] - el["y"]) < 50
                  and "Purchased" in s.get("label","")]
        count = 0
        if nearby:
            import re
            m = re.search(r"Purchased (\d+) time", nearby[0]["label"])
            count = int(m.group(1)) if m else 1
        candidates.append((count, el))
candidates.sort(key=lambda c: -c[0])
best = candidates[0][1] if candidates else None
```

If a variant has no "Purchased N times" badge, it's a first-time buy — ask the user before proceeding.

## Buy Now vs Add to Cart

| Path | When to use |
|---|---|
| **Buy Now** | Single-item reorder of a known product. Skips cart, goes straight to single-tap checkout. Faster, fewer pages to navigate. |
| **Add to Cart → Checkout** | Multi-item orders, gift-message workflows, or anything that needs cart review. More steps, more confirmations. |

The user typically specifies which they want. Default to Buy Now if they say "order it" or "reorder X" with no qualifier — it's the lowest-step path.

## Selectors

| Label / Name | Type | What |
|---|---|---|
| `Search or ask a question` (search field placeholder) | SearchField | Top-of-screen search. Tap → autocomplete dropdown shows past searches first. |
| `Add to cart` | Button | Cart-based path (skip for Buy Now flow) |
| `Buy Now` | Button | Single-tap checkout entry |
| `Place your order` | Button | The real payment commit — pause here for user confirmation |
| `Your Amazon` | Button (bottom tab bar) | Personal area: orders, returns, lists |
| `Orders` | Link | Full order history with search |

## Traps

- **Sponsored Ad placements are everywhere.** When searching, the first product card is *very often* a paid ad for the same or a competing product. Check the label prefix — `"Sponsored Ad - …"` means skip it. Tap the next, organically-ranked match.
- **"Purchased N times" badge is the signal**, not the product position. Sponsored ads may even sit above the user's actual previous purchase.
- **The Buy Now button has a `Subscribe & Save` neighbor.** Don't confuse them. Buy Now is the orange/yellow button; Subscribe & Save sets up a recurring order — never tap accidentally.
- **Multiple delivery-speed tiles** appear on the checkout screen ("Tomorrow FREE Two-Day" vs "Today $2.99 Same-Day"). The currently-selected one has a colored border. Don't auto-change unless the user requested it.
- **The Ship-to address gets truncated** in the checkout UI (`"322 DORCHESTE..."`). The full address IS used — the truncation is visual only. Confirm via the order-placed screen, which shows the full address.
- **Multiple Place-your-order buttons can exist on the page** if there's a "Get $X back" promo at the top. The real button is at the bottom — find by `y` if needed.
- **The 5-day countdown timer** (`"Order within 8 hrs 26 min"`) under delivery date is informational. It doesn't affect the order — just the delivery window.

## Mandatory pre-purchase verification

Before tapping `Place your order`, the agent MUST confirm with the user:

1. **The product** (full name + variant + pack size)
2. **The total** (including tax and shipping)
3. **The shipping address** (especially if the user asked to change it from the default)
4. **The payment method** (last 4 digits of the card)

Read these out, wait for explicit confirmation, then tap. **Never assume.**

## What this skill does NOT cover

- Adding a new shipping address mid-checkout (different flow, complex form)
- Switching payment methods mid-checkout
- Applying a gift card / promo code at checkout
- Multi-item orders (use the cart flow)
- Subscribe & Save flows
- Returns and refunds
- Amazon Fresh / Whole Foods grocery orders (different bundle id, different UI)

Open follow-up skill files when tackling those.
