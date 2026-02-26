# How the Realtor.com URL Match Script Works

## Technical Deep Dive into the URL Verification Algorithm

---

## 1. Overview

The Realtor.com URL Match script verifies whether an AI agent has navigated to the correct Realtor.com search page. It uses a **path-segment based parsing** approach where filters, location, and search type are all extracted from URL path segments.

### Core Philosophy

**"Parse → Normalize → Compare"**

Instead of string matching, the script:
1. **Parses** each URL into structured components (search type, location, filters)
2. **Normalizes** each component (lowercase, aliases, abbreviations)
3. **Compares** the normalized structures using dictionary equality

---

## 2. Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      URL MATCHING PIPELINE                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────┐                    ┌───────────────┐                 │
│  │   Agent URL   │                    │  Ground Truth │                 │
│  │               │                    │      URL      │                 │
│  └───────┬───────┘                    └───────┬───────┘                 │
│          │                                    │                         │
│          ▼                                    ▼                         │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │              _parse_realtor_url()                            │       │
│  │  1. Lowercase & strip whitespace                            │       │
│  │  2. URL decode                                               │       │
│  │  3. Parse path ONLY (query string ignored)                  │       │
│  │  4. Detect search type from first path segment              │       │
│  │  5. Extract location (City_ST, ZIP, or Neighborhood)         │       │
│  │  6. Parse remaining segments as filters                     │       │
│  │  7. Normalize property types (20+ aliases)                  │       │
│  │  8. Normalize prices (500k → 500000, 1m → 1000000)         │       │
│  │  9. Expand show flags                                       │       │
│  │  10. Ignore sort/pagination segments                         │       │
│  └─────────────────────────────────────────────────────────────┘       │
│          │                                    │                         │
│          ▼                                    ▼                         │
│  ┌───────────────┐                    ┌───────────────┐                 │
│  │   Normalized  │                    │   Normalized  │                 │
│  │     Dict      │                    │     Dict      │                 │
│  └───────┬───────┘                    └───────┬───────┘                 │
│          │                                    │                         │
│          └────────────────┬───────────────────┘                         │
│                           │                                             │
│                           ▼                                             │
│                  ┌────────────────┐                                     │
│                  │    COMPARE     │                                     │
│                  │                │                                     │
│                  │ search_type?   │                                     │
│                  │ ├─ equivalence │                                     │
│                  │ location?      │                                     │
│                  │ filters == ?   │                                     │
│                  │ ├─ order-free  │                                     │
│                  └────────┬───────┘                                     │
│                           │                                             │
│                  ┌────────┴────────┐                                    │
│                  │                 │                                    │
│                  ▼                 ▼                                    │
│            ┌──────────┐     ┌──────────┐                               │
│            │  MATCH   │     │ NO MATCH │                               │
│            │ Score=1.0│     │ Score=0.0│                               │
│            └──────────┘     └──────────┘                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Structures

#### Input URL
```
https://www.realtor.com/realestateandhomes-search/San-Francisco_CA/beds-3/price-500000-1000000/type-house
```

#### Parsed Output
```python
{
    "search_type": "sale",
    "location": "san-francisco_ca",
    "filters": {
        "beds": "3",
        "price": "500000-1000000",
        "type": "single-family-home"
    }
}
```

---

## 3. Parsing Pipeline

### Step 1: Initial Cleanup

```python
url = url.strip().lower()    # Normalize case
url = unquote(url)           # URL decode %20 etc.
# Add protocol if missing
if not url.startswith(("http://", "https://")):
    url = "https://" + url

parsed = urlparse(url)
path = parsed.path.strip("/")  # Query string is IGNORED entirely
```

> **Important**: The parser uses `parsed.path` only. Query parameters like `?view=map`, `?layer=Flood`, `?schools_pin=true`, and `?amenities_pin=true` are purely visual and are automatically discarded.

### Step 2: Detect Search Type

```python
SEARCH_TYPE_PATHS = {
    "realestateandhomes-search": "sale",
    "apartments": "rent",
    "rentals": "rent",           # alias
    "houses-for-rent": "rent",   # alias
    "sold-homes": "sold",
    "open-houses": "open_houses",
}

first_segment = segments[0]
if first_segment in SEARCH_TYPE_PATHS:
    search_type = SEARCH_TYPE_PATHS[first_segment]
```

### Step 3: Extract Location

```python
# Check if segment looks like a filter (beds-3, type-condo, etc.)
if not _is_filter_segment(segment):
    location = _normalize_location(segment)
    # Result: "san-francisco_ca" or "90210"
```

### Step 4: Parse Filter Segments

Each remaining segment is parsed individually:

```python
# beds-3       → ("beds", "3")
# price-500k   → ("price", "500000")     # abbreviation expanded
# type-house   → ("type", "single-family-home")  # alias resolved
# show-open-house → ("show-open-house", "true")
# sby-2        → ignored (sort)
# pg-3         → ignored (pagination)
```

---

## 4. Normalization Details

### Property Type Aliases (20+)

| Input | Normalized |
|-------|-----------|
| `house`, `houses`, `single-family`, `sfh` | `single-family-home` |
| `townhouse`, `townhouses` | `townhome` |
| `ranch`, `ranches` | `farm` |
| `manufactured`, `mobile` | `mobile-home` |
| `coop`, `cooperative` | `co-op` |
| `condos`, `condominium` | `condo` |

### Price Normalization

```python
# Abbreviations
"500k"    → "500000"
"1m"      → "1000000"
"1.5m"    → "1500000"
"2.5k"    → "2500"

# na values preserved
"na"      → "na"  (unbounded)
```

### Show Flag Aliases

```python
SHOW_FLAG_ALIASES = {
    "show-open-houses": "open-house",
    "show-sold": "recently-sold",
    "show-recently-sold-homes": "recently-sold",
    "show-new-homes": "new-construction",
}
```

---

## 5. Search Type Equivalence

The most complex part of the comparison handles **equivalent search representations**:

### Sold Equivalence

```python
# These are equivalent:
# /sold-homes/City        ↔  /realestateandhomes-search/City/show-recently-sold

# When matched via equivalence, the show-recently-sold flag is
# REMOVED from filter comparison to avoid false mismatches
```

### Open Houses Equivalence

```python
# These are equivalent:
# /open-houses/City       ↔  /realestateandhomes-search/City/show-open-house

# Similarly, show-open-house flag removed from filter comparison
```

### Implementation

```python
if agent_type != gt_type:
    # Check sold equivalence
    agent_is_sold = (agent_type == "sale" 
                     and "show-recently-sold" in agent_filters)
    gt_is_sold = (gt_type == "sale"
                  and "show-recently-sold" in gt_filters)
    sold_match = (agent_type == "sold" and gt_is_sold) 
              or (gt_type == "sold" and agent_is_sold)
    
    # Similar for open houses...
    
    if not (sold_match or open_match):
        return False  # Type mismatch
```

---

## 6. Filter Comparison

### Order-Independent

Filters are stored in a `dict`, so comparison is naturally order-independent:

```python
# These match:
{"beds": "3", "price": "500000-1000000"}
==
{"price": "500000-1000000", "beds": "3"}
```

### Extra Filters Allowed

If the agent URL has MORE filters than the ground truth, this is noted but NOT penalized:

```python
# GT:    beds-3, price-500000-1000000
# Agent: beds-3, price-500000-1000000, type-condo
# Result: MATCH (type-condo is "extra" — noted but OK)
```

### Multi-Value Types

Multiple `type-*` segments are merged:

```python
# /type-condo/type-townhome → {"type": "condo,townhome"}
# /type-townhome/type-condo → {"type": "condo,townhome"}  (sorted)
```

---

## 7. Complete Example Walkthrough

### Input
```
HTTPS://WWW.REALTOR.COM/sold-homes/San-Francisco_CA/beds-3/price-500k-1m/type-house/sby-2
```

### Step-by-Step

1. **Cleanup**: `https://www.realtor.com/sold-homes/san-francisco_ca/beds-3/price-500k-1m/type-house/sby-2`
2. **Search type**: `sold-homes` → `search_type = "sold"`
3. **Location**: `san-francisco_ca` → `location = "san-francisco_ca"`
4. **Filters**:
   - `beds-3` → `{"beds": "3"}`
   - `price-500k-1m` → `{"price": "500000-1000000"}` (abbreviations expanded)
   - `type-house` → `{"type": "single-family-home"}` (alias resolved)
   - `sby-2` → IGNORED (sort)

### Final Parsed Result
```python
{
    "search_type": "sold",
    "location": "san-francisco_ca",
    "filters": {
        "beds": "3",
        "price": "500000-1000000",
        "type": "single-family-home"
    }
}
```

### Comparison with GT
```
GT: https://www.realtor.com/realestateandhomes-search/San-Francisco_CA/show-recently-sold/price-500000-1000000/beds-3/type-single-family-home
```

1. **Search type**: `sold` vs `sale` + `show-recently-sold` → **EQUIVALENT** ✅
2. **Location**: `san-francisco_ca` == `san-francisco_ca` ✅
3. **Filters** (after removing equivalence flag):
   - Agent: `{"beds": "3", "price": "500000-1000000", "type": "single-family-home"}`
   - GT: `{"beds": "3", "price": "500000-1000000", "type": "single-family-home"}`
   - **MATCH** ✅

**Result**: Score = 1.0

---

## 8. Query String Handling

Realtor.com appends query parameters for map interactions. These are **purely visual** and do not affect search results:

```python
# These query params are all IGNORED by the parser:
# ?view=map                                    → Map/list toggle
# ?pos=37.89,-122.55,37.73,-122.26,11.88       → Map viewport
# ?layer=Flood                                 → Map overlay
# ?schools_pin=true                            → School markers
# ?neighborhood_pin=true                       → Neighborhood markers
# ?amenities_pin=true                          → Amenity markers

# The parser uses urlparse(url).path only, so all query params are discarded.
```

---

## 9. Testing

All tests live in a dedicated external file — the verifier module contains zero inline tests.

```bash
python navi_bench/realtor/test_realtor_rigorous.py
```

### Test Suite: 232 tests across 23 categories

- **CSV Self-Match** (74 tests) — every benchmark GT URL matches itself
- **Basic Filters** — beds, baths, price, types, locations, show flags
- **Advanced Filters** — sqft, lot, age, HOA, DOM, radius, sold-within
- **Equivalences** — sold-homes↔show-recently-sold, open-houses↔show-open-house
- **EXTREME Combos** — 5-8 simultaneous filters, scrambled orders, aliases + abbreviations
- **Negative Tests** — wrong values, missing filters, cross-search-type mismatches
- **Edge Cases** — case insensitivity, map query params, trailing slashes, protocol variations

---

## 10. Extensibility

### Adding New Property Type Aliases
```python
PROPERTY_TYPE_ALIASES = {
    # ... existing ...
    "new-alias": "canonical-slug",
}
```

### Adding New Show Flags
```python
SHOW_FLAG_ALIASES = {
    # ... existing ...
    "show-new-flag": "canonical-flag",
}
```

### Adding New Filter Prefixes
```python
# In _is_filter_segment():
filter_prefixes = (
    # ... existing ...
    "new-prefix-",
)

# In _parse_filter_segment():
if seg.startswith("new-prefix-"):
    return "new-filter", seg[len("new-prefix-"):]
```

---

**Last Updated**: 2026-02-26
**Implementation Version**: 3.0 (Tests externalized, query param handling documented)
