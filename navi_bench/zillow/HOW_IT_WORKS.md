# How the Zillow URL Match Verifier Works

## Technical Deep Dive

---

## 1. Overview

The Zillow URL Match verifier validates AI agent navigation by parsing Zillow's `searchQueryState` URL parameter. Unlike Redfin (which uses path-based filters) or StubHub (which requires DOM scraping), Zillow encodes ALL filter state in a single URL-encoded JSON object.

### 1.1 Core Philosophy

**"Decode → Normalize → Compare"**

1. **Decode** the `searchQueryState` JSON from the URL
2. **Normalize** filter values to comparable formats
3. **Compare** normalized structures using dictionary equality

---

## 2. URL Structure

### 2.1 Zillow URL Anatomy

```
https://www.zillow.com/homes/for_sale/Los-Angeles,-CA_rb/?searchQueryState=%7B%22filterState%22%3A%7B...%7D%7D
│                      │            │                  │                     │
│                      │            │                  │                     └─ URL-encoded JSON
│                      │            │                  └─ Query parameter name
│                      │            └─ Location suffix (_rb = region boundary)
│                      └─ Search type (for_sale, for_rent, recently_sold)
└─ Base domain
```

### 2.2 Decoded searchQueryState

```json
{
  "pagination": {},
  "mapBounds": {
    "west": -118.6682,
    "east": -118.1553,
    "south": 33.7036,
    "north": 34.3373
  },
  "regionSelection": [
    {
      "regionId": 12447,
      "regionType": 6
    }
  ],
  "isMapVisible": true,
  "filterState": {
    "price": {"min": 500000, "max": 1000000},
    "beds": {"min": 3},
    "baths": {"min": 2},
    "isHouse": {"value": true}
  },
  "isListVisible": true,
  "sortSelection": {"value": "globalrelevanceex"}
}
```

---

## 3. Parsing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ZILLOW URL PARSING PIPELINE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ INPUT: https://zillow.com/homes/for_sale/?searchQueryState=...      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STEP 1: Extract Search Type from Path                               │   │
│  │   - /homes/for_sale/ → "for_sale"                                   │   │
│  │   - /homes/for_rent/ → "for_rent"                                   │   │
│  │   - /homes/recently_sold/ → "recently_sold"                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STEP 2: Extract Location from Path                                  │   │
│  │   - /Los-Angeles,-CA_rb/ → "los angeles ca"                         │   │
│  │   - Normalize dashes, underscores, commas                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STEP 3: Parse searchQueryState                                      │   │
│  │   1. Extract from query params                                      │   │
│  │   2. URL decode: %7B → {                                            │   │
│  │   3. JSON parse to dict                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STEP 4: Normalize filterState                                       │   │
│  │   - Convert keys to lowercase                                       │   │
│  │   - Handle {value: true} → true                                     │   │
│  │   - Expand {min: X, max: Y} → key_min, key_max                      │   │
│  │   - Skip false/null values (default state)                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ OUTPUT: Normalized Dictionary                                       │   │
│  │   {                                                                 │   │
│  │     "search_type": "for_sale",                                      │   │
│  │     "location": "los angeles ca",                                   │   │
│  │     "filters": {                                                    │   │
│  │       "price_min": 500000,                                          │   │
│  │       "price_max": 1000000,                                         │   │
│  │       "beds_min": 3,                                                │   │
│  │       "ishouse": true                                               │   │
│  │     }                                                               │   │
│  │   }                                                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Filter Normalization

### 4.1 Value Format Handling

Zillow uses several filter value formats:

```python
# Format 1: Boolean with value wrapper
{"isHouse": {"value": true}}
-> {"ishouse": True}

# Format 2: Range filter
{"price": {"min": 500000, "max": 1000000}}
-> {"price_min": 500000, "price_max": 1000000}

# Format 3: Exact value
{"beds": {"exact": 3}}
-> {"beds_exact": 3}

# Format 4: Simple boolean
{"hasPool": true}
-> {"haspool": True}
```

### 4.2 Key Normalization

All keys are normalized to lowercase:

```python
"isHouse" -> "ishouse"
"hasMountainView" -> "hasmountainview"
"filterState" -> "filterstate"
```

### 4.3 Property Type Normalization

Property types have special handling due to Zillow's dual encoding:

**Abbreviated key mapping** (abbreviated -> canonical):
```python
"sf"   -> "ishouse"         # Single-family
"tow"  -> "istownhouse"     # Townhomes
"mf"   -> "ismultifamily"   # Multi-family
"con"  -> "iscondo"         # Condos/Co-ops
"land" -> "islotland"       # Lots/Land
"apa"  -> "isapartment"     # Apartments
"apco" -> "isapartment"     # Apartment Community (alias)
"manu" -> "ismanufactured"  # Manufactured
```

**Negative encoding inference**: When the live Zillow browser sets types to false, the verifier infers the selected types:
```python
# Browser URL: tow:false, mf:false, land:false, con:false, apa:false, apco:false, manu:false
# All non-house types disabled -> infer: ishouse: True

# Browser URL: mf:false, land:false, con:false, apa:false, apco:false, manu:false
# All except house and townhouse disabled -> infer: ishouse: True, istownhouse: True
```

### 4.4 Ignored Parameters

These UI-state and auto-computed parameters are ignored during comparison:

- `pagination` - Page number
- `mapBounds` - Map viewport coordinates
- `isMapVisible` - Map toggle state
- `isListVisible` - List toggle state
- `mapZoom` - Zoom level
- `customRegionId` - Internal region mapping
- `sort` - Auto-set default sort (inside filterState)
- `mp` - Auto-computed monthly payment from price

---

## 5. Comparison Logic

### 5.1 Matching Algorithm

```python
def _urls_match(self, agent_url: str, gt_url: str) -> bool:
    agent = self._parse_zillow_url(agent_url)
    gt = self._parse_zillow_url(gt_url)
    
    # 1. Search type must match
    if agent["search_type"] != gt["search_type"]:
        return False
    
    # 2. Location must match (if strict mode)
    if self.strict_location and gt["location"]:
        if not location_matches(agent["location"], gt["location"]):
            return False
    
    # 3. All ground truth filters must be present
    for key, value in gt["filters"].items():
        if agent["filters"].get(key) != value:
            return False  # Missing or wrong value
    
    # Extra filters in agent URL are ALLOWED
    return True
```

### 5.2 Matching Rules

| Scenario | Result |
|----------|--------|
| Agent URL has all required filters | ✅ PASS |
| Agent URL missing a required filter | ❌ FAIL |
| Agent URL has wrong filter value | ❌ FAIL |
| Agent URL has extra filters | ✅ PASS (allowed) |
| Search type mismatch | ❌ FAIL |
| Location mismatch (strict mode) | ❌ FAIL |

---

## 6. Example Walkthrough

### Input URLs

**Ground Truth:**
```
https://www.zillow.com/homes/for_sale/?searchQueryState={"filterState":{"price":{"min":500000},"beds":{"min":3}}}
```

**Agent URL:**
```
https://www.zillow.com/homes/for_sale/Los-Angeles,-CA_rb/?searchQueryState={"filterState":{"price":{"min":500000},"beds":{"min":3},"isHouse":{"value":true}}}
```

### Parsed Results

**Ground Truth Parsed:**
```python
{
    "search_type": "for_sale",
    "location": "",
    "filters": {
        "price_min": 500000,
        "beds_min": 3
    }
}
```

**Agent Parsed:**
```python
{
    "search_type": "for_sale",
    "location": "los angeles ca",
    "filters": {
        "price_min": 500000,
        "beds_min": 3,
        "ishouse": True  # Extra filter
    }
}
```

### Comparison

1. ✅ Search type: `for_sale` == `for_sale`
2. ✅ Location: GT is empty, so no check needed
3. ✅ `price_min`: 500000 == 500000
4. ✅ `beds_min`: 3 == 3
5. ℹ️ `ishouse`: Extra filter (allowed)

**Result: PASS (Score: 1.0)**

---

## 7. Performance

| Metric | Value |
|--------|-------|
| Single URL parse | ~1ms |
| URL comparison | ~1ms |
| 30+ test suite | <100ms |
| Memory footprint | Minimal |

---

## 8. Extending the Verifier

### Adding New Filters

```python
# In _normalize_filter_state():
if key == "newFilterName":
    normalized["newfilter"] = self._normalize_value(value)
```

### Adding Ignored Parameters

```python
IGNORED_PARAMS = {
    "pagination",
    "mapBounds",
    "newIgnoredParam",  # Add here
}
```

---

**Last Updated:** 2026-02-11
**Version:** 2.0.0 (added property type normalization, negative encoding, auto-computed filters)
