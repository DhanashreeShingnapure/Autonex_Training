# Zillow Verifier: Research Journey

## How We Built & Debugged the Zillow URL Match Verifier

*A narrative account of the research, implementation, and debugging process for the Zillow verifier module in NaviBench.*

---

## Phase 1: Initial Exploration — Understanding Zillow's URL Structure

### Opening the Browser

The first step was straightforward: open Chrome and navigate to [zillow.com/homes/for_sale/](https://www.zillow.com/homes/for_sale/). The immediate observation was that Zillow's URL structure is fundamentally different from other real estate sites like Redfin.

**Key Discovery:** Unlike Redfin (which encodes filters in the URL path like `/min-price=500000/`), Zillow packs **ALL** search state into a single URL parameter called `searchQueryState`. This parameter contains URL-encoded JSON.

```
https://www.zillow.com/homes/for_sale/?searchQueryState=%7B%22filterState%22%3A%7B...%7D%7D
```

When decoded:
```json
{
  "pagination": {},
  "mapBounds": { "west": -118.86, "east": -117.95, "south": 33.69, "north": 34.34 },
  "regionSelection": [{ "regionId": 12447, "regionType": 6 }],
  "isMapVisible": true,
  "filterState": {
    "price": { "min": 500000, "max": 1000000 },
    "beds": { "min": 3 }
  },
  "isListVisible": true
}
```

**First insight**: The `filterState` object is the core — it contains every user-selected filter. Everything else (`pagination`, `mapBounds`, `isMapVisible`, etc.) is UI state that should be ignored during verification.

### Identifying Filter Formats

By clicking through different filters on the Zillow UI and watching the URL change, we identified two primary JSON formats:

1. **Boolean filters** use `{"key": {"value": true}}` — e.g., `{"isHouse": {"value": true}}`
2. **Range filters** use `{"key": {"min": X, "max": Y}}` — e.g., `{"price": {"min": 300000}}`

This was a crucial distinction because range filters do NOT use the `{"value": ...}` wrapper.

---

## Phase 2: Deep Filter Audit — Cataloging All 100+ Filters

### Systematic Browser Exploration

We opened every filter panel on Zillow and documented what appeared in the URL:

1. **Home Type dropdown** — Clicked each checkbox (Houses, Townhomes, Multi-family, Condos, Lots/Land, Apartments, Manufactured) and noted the keys
2. **Price panel** — Entered min/max values and observed `price: {min: X, max: Y}`
3. **Beds & Baths** — Selected different bed/bath counts
4. **More Filters (expanded panel)** — This was the goldmine:
   - Square footage, lot size, year built
   - Parking spots, garage requirement
   - Pool, waterfront, views (city, mountain, water, park)
   - HOA limits, 55+ communities
   - Building features (single story, basement, A/C, hardwood floors, fireplace)
   - Listing status (by agent, by owner, foreclosure, auction, new construction, coming soon)
   - Tours & media (open house, 3D tour, showcase)
   - Days on Zillow
   - Keywords

5. **Rental-specific filters** — Switched to "For Rent" mode and discovered a whole additional set:
   - Pet policies (large dogs, small dogs, cats, no pets)
   - Laundry (in-unit, in-building, hookups)
   - Amenities (furnished, utilities included, short-term lease)
   - Abbreviated keys unique to rentals (`app`, `os`, `ca`, `hsia`, `eaa`, `fmfb`, `rad`)

6. **Sort options** — Found at the top-level `sortSelection` object, separate from `filterState`
7. **Sold properties** — Discovered `soldInLast` filter with date codes (`7d`, `30d`, `90d`, `6m`, `12m`)

### The Abbreviation Discovery

During the audit, we noticed Zillow uses **two different key formats** for the same filter. For example, "Houses" appears as:

- `isHouse` (full key, found in some ground truth URLs)
- `sf` (abbreviated key, found in some live browser URLs)

We compiled the complete abbreviation table:

| Abbreviated | Full (Canonical) |
|------------|-----------------|
| `sf` | `isHouse` |
| `tow` | `isTownhouse` |
| `mf` | `isMultiFamily` |
| `con` | `isCondo` |
| `apa` | `isApartment` |
| `apco` | `isApartment` (community alias) |
| `land` | `isLotLand` |
| `manu` | `isManufactured` |

This ended up being documented in [COVERAGE.md](./COVERAGE.md) with JSON examples for every single filter.

---

## Phase 3: Building the Verifier

### Core Architecture

Based on the research, we designed a 4-step pipeline:

1. **Parse** the URL → extract `searchQueryState` JSON
2. **Normalize** keys (lowercase) and values (expand ranges, unwrap booleans)
3. **Compare** normalized dictionaries
4. **Score** — missing/wrong filters = fail, extra filters = allowed

### Test Suite

Built a comprehensive test suite covering all 18 filter categories with 111 individual test cases. This runs directly from the module:

```bash
python -m navi_bench.zillow.zillow_url_match
```

---

## Phase 4: Setting Up the Human Demo

### The Bot Detection Problem

When we first tried running the demo with Playwright (the standard browser automation tool), Zillow's bot detection immediately blocked us. The page would load with a CAPTCHA or a "press and hold" challenge.

**Root cause**: Playwright's Chromium carries detectable automation fingerprints that Zillow's security system flags.

### CDP Mode Solution

The fix was to use **Chrome DevTools Protocol (CDP)** mode:

1. Launch a **real Chrome browser** (not Playwright's bundled Chromium) with `--remote-debugging-port=9222`
2. Connect Playwright to it via CDP: `playwright.chromium.connect_over_cdp("http://localhost:9222")`
3. This gives us the full real browser environment — no automation flags

We modified `demo.py` to:
- Auto-detect Chrome's installation path on Windows
- Launch Chrome with CDP enabled
- Connect Playwright over CDP
- Navigate to Zillow without triggering bot detection

### Integrating with NaviBench Framework

The verifier needed to integrate with NaviBench's evaluator framework:
- Added `BaseMetric` inheritance to `ZillowUrlMatch`
- Implemented `reset()` method
- Created `generate_task_config()` function
- Exported it from `navi_bench/zillow/__init__.py`

---

## Phase 5: The Negative Encoding Bug — The Hardest Problem

### The Symptom

After getting CDP mode working and the demo running, we executed the test task:

> *"Find houses for sale in Los Angeles, CA with at least 3 bedrooms priced under $800,000"*

We navigated to Zillow, searched for Los Angeles, set 3+ beds, max $800K price, and selected **Houses only** from the Home Type filter. Everything looked correct in the browser.

**But the score came back 0.0** — the verifier said `ishouse` was missing.

### The Investigation

We decoded the URL from the agent's browser:

```json
{
  "filterState": {
    "sort": {"value": "globalrelevanceex"},
    "beds": {"min": 3},
    "price": {"max": 800000},
    "mp": {"max": 4000},
    "tow": {"value": false},
    "mf": {"value": false},
    "land": {"value": false},
    "con": {"value": false},
    "apa": {"value": false},
    "apco": {"value": false},
    "manu": {"value": false}
  }
}
```

And compared it with the ground truth:

```json
{
  "filterState": {
    "beds": {"min": 3},
    "price": {"max": 800000},
    "isHouse": {"value": true}
  }
}
```

### The Root Cause

**Zillow uses negative encoding for property types in the live browser.**

When you select "Houses" in the Home Type dropdown:
- The **UI** shows only "Houses" checked
- The **URL** sets all OTHER types to `false`
- The URL does NOT contain `isHouse: true`

But our ground truth uses **positive encoding** (`isHouse: true`).

The normalizer was dropping all `false` values (treating them as default state), so the agent URL parsed to `{}` for property types, while the ground truth parsed to `{ishouse: True}`.

### The Fix — Negative Encoding Inference

We added property type inference logic to `_normalize_filter_state()`:

1. Track which abbreviated property type keys are set to `false`
2. Map them to canonical types using `ABBREV_TO_CANONICAL`
3. Compute: `selected_types = ALL_PROPERTY_TYPES - disabled_types`
4. Set the selected types to `True` in the normalized output

This handles **every combination**:

| Browser URL pattern | Inferred result |
|----|---|
| All others false | `ishouse: True` |
| All except tow/sf false | `ishouse: True, istownhouse: True` |
| All except con false | `iscondo: True` |
| No property filters | All types selected (default) |

### Additional Fixes

Two more auto-computed filters were causing noise:

- `sort: globalrelevanceex` — Zillow's default sort, auto-added, not user intent
- `mp: {max: 4000}` — Monthly payment auto-calculated from the price filter

Both were added to `IGNORED_PARAMS` so they don't appear as "extra" filters in the comparison output.

---

## Phase 6: Verification

After all fixes, we re-ran the demo:

```
ZILLOW DEMO TASK
Task: Find houses for sale in Los Angeles, CA with at least 3 bedrooms priced under $800,000

Result: Score = 1.0 ✅
```

And the comprehensive test suite:

```
TEST SUMMARY: 111/111 tests passed (100.0%)
```

---

## Key Learnings

### 1. Always test with real browser URLs
Ground truth URLs and live browser URLs can use completely different encoding patterns. You must test with actual browser-produced URLs, not just synthetic ones.

### 2. Zillow's dual encoding system
The most subtle finding was that Zillow uses positive encoding in some contexts and negative encoding in others. The same logical state ("Houses only") can be represented two completely different ways:
- Positive: `{"isHouse": {"value": true}}`
- Negative: `{"tow": false, "mf": false, "land": false, "con": false, "apa": false, "apco": false, "manu": false}`

### 3. Auto-computed fields are noise
Zillow adds computed fields like monthly payment and default sort that aren't part of user intent. These must be excluded from comparison.

### 4. Bot detection requires real browsers
Playwright's bundled Chromium gets immediately flagged by Zillow. CDP mode with a real Chrome instance is the only reliable approach.

---

## File Reference

| File | Purpose |
|------|---------|
| [zillow_url_match.py](./zillow_url_match.py) | Core verifier — parsing, normalization, comparison, 111 tests |
| [COVERAGE.md](./COVERAGE.md) | Complete filter catalog with JSON examples for all 108 filters |
| [HOW_IT_WORKS.md](./HOW_IT_WORKS.md) | Technical deep dive on the parsing pipeline |
| [demo.py](../../demo.py) | Human demo runner with CDP mode |

---

**Author:** NaviBench Team
**Date:** 2026-02-11
**Version:** 1.0.0
