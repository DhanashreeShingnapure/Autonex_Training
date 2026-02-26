# Redfin URL Match Script

## Advanced URL Verification System with Intelligent Normalization

### Comprehensive Technical Documentation

**NaviBench Framework**

---

## 1. Executive Summary

The Redfin URL Match script is a production-grade URL verification metric for the NaviBench framework. It employs an advanced normalization strategy that intelligently handles Redfin's complex URL structure, including multi-value filters, price abbreviations, parameter aliases, city ID variations, rental detection, neighborhood URLs, and more.

### 1.1 Purpose

This script evaluates whether an AI agent has successfully navigated to the correct Redfin real estate search page by comparing the agent's final URL against predefined ground truth URLs. It is designed to handle the full complexity of Redfin's URL structure where search filters are embedded in the URL path.

### 1.2 Design Philosophy

The script follows a **"Parse → Normalize → Compare"** approach:

1. **Parse**: Extract location type, city/neighborhood, state, rental status, and filters from URL path
2. **Normalize**: Apply intelligent transformations (aliases, abbreviations, multi-values, consolidation)
3. **Compare**: Use dictionary equality for order-independent matching

This ensures:
- ✅ Deterministic and predictable behavior
- ✅ Robust handling of URL variations
- ✅ Easy debugging and maintenance

### 1.3 Core Capabilities

| Feature | Description | Status |
|---------|-------------|--------|
| Path-based Filters | Handles Redfin's `/filter/...` URL segments | ✅ |
| Location Types | Supports both city and neighborhood URLs | ✅ |
| Rental Detection | Distinguishes `/apartments-for-rent` and `/rentals` | ✅ |
| Multi-value Filters | `property-type=house+condo` with order independence | ✅ |
| Price Abbreviations | `2m → 2000000`, `2000k → 2000000`, `2,000,000 → 2000000` | ✅ |
| Sqft Abbreviations | `1.5k → 1500`, `1500-sqft → 1500` | ✅ |
| Parameter Aliases | 40+ aliases for common Redfin parameters | ✅ |
| Stories Consolidation | `min=max` → single "stories" key | ✅ |
| Beds/Baths Expansion | `beds=3` → `min-beds=3,max-beds=3` | ✅ |
| Time Normalization | `1wk → 7days`, `1mo → 30days` | ✅ |
| City ID Flexibility | Matches by name, ignores numeric ID | ✅ |
| Comma Handling | Removes commas from prices before parsing | ✅ |
| Ignored UI Params | viewport, sort, no-outline, UTM tracking | ✅ |
| Case Insensitivity | Lowercase normalization | ✅ |
| Include Filters | `include=sold-3mo`, `include=construction` | ✅ |
| Boolean Flags | `is-fixer`, `has-view`, `air-conditioning` | ✅ |
| Move-in Date | Date format normalization | ✅ |
| Multiple GT URLs | Supports multiple acceptable answers | ✅ |

---

## 2. Architecture Overview

### 2.1 Component Structure

| Component | Type | Purpose |
|-----------|------|---------|
| `InputDict` | TypedDict | Input specification containing URL string |
| `FinalResult` | Pydantic Model | Output model with score (0.0 or 1.0) |
| `RedfinUrlMatch` | BaseMetric | Main evaluation metric class |
| `generate_task_config` | Function | Factory for creating task configurations |

### 2.2 Dependencies

| Library | Purpose |
|---------|---------|
| `re` | Regular expressions for URL parsing |
| `urllib.parse` | URL parsing: `urlparse`, `unquote` |
| `beartype` | Runtime type checking with `@beartype` decorator |
| `loguru` | Structured logging for debugging and monitoring |
| `pydantic` | Data validation for FinalResult model |
| `navi_bench.base` | BaseMetric, BaseTaskConfig, get_import_path |
| `navi_bench.dates` | initialize_user_metadata for task context |

### 2.3 Data Flow Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA FLOW PIPELINE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Agent navigates to Redfin and applies search filters                    │
│                              ↓                                              │
│  2. update() receives current browser URL                                   │
│                              ↓                                              │
│  3. _parse_redfin_url() extracts:                                          │
│     • location_type (city vs neighborhood)                                  │
│     • location (city name or city/neighborhood)                             │
│     • state                                                                 │
│     • is_rental                                                             │
│     • filters (dictionary)                                                  │
│                              ↓                                              │
│  4. _normalize_param_name() maps 40+ parameter aliases                      │
│                              ↓                                              │
│  5. _normalize_param_value() handles:                                       │
│     • Price abbreviations (2m, 500k)                                        │
│     • Sqft abbreviations (1.5k, -sqft)                                      │
│     • Time values (1wk → 7days)                                             │
│     • Date formats (move-in-date)                                           │
│                              ↓                                              │
│  6. POST-PROCESSING:                                                        │
│     • beds/baths consolidation                                              │
│     • stories consolidation                                                 │
│                              ↓                                              │
│  7. Multi-value filters sorted into tuples for comparison                   │
│                              ↓                                              │
│  8. _parse_redfin_url() processes each ground truth URL                     │
│                              ↓                                              │
│  9. Dictionary comparison: agent_filters == gt_filters                      │
│                              ↓                                              │
│  10. Match found → _found_match = True; else continue checking              │
│                              ↓                                              │
│  11. compute() returns FinalResult with score (1.0 or 0.0)                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. RedfinUrlMatch Class

The main evaluation metric implementing the BaseMetric interface for NaviBench integration.

### 3.1 Class Constants

#### 3.1.1 IGNORED_PARAMS

Parameters that are stripped during normalization because they don't affect search results:

| Parameter | Reason for Ignoring |
|-----------|---------------------|
| `viewport` | Map view coordinates - UI state, not search criteria |
| `no-outline` | Map rendering option - visual preference only |
| `redirect` | Internal routing parameter |
| `map_zoom` | Map zoom level - UI state |
| `zoomLevel` | Alternative zoom parameter |
| `v` | Version parameter - A/B testing or feature flags |
| `utm_source` | Marketing tracking - traffic source identification |
| `utm_medium` | Marketing tracking - medium type (email, cpc, etc.) |
| `utm_content` | Marketing tracking - content variation identifier |
| `utm_campaign` | Marketing tracking - campaign identifier |
| `android_merchant_id` | Mobile app tracking - Android specific |
| `myapp_param` | Custom app parameter - internal tracking |
| `referrer` | Referral tracking - source page identification |
| `sort` | Sort order doesn't affect search filters, only display order |

### 3.2 Parameter Aliases (40+)

The script normalizes parameter names to canonical forms. This handles Redfin's parameter name variations:

| Category | Input Aliases | Canonical Form |
|----------|---------------|----------------|
| **Time on Market** | `max-days-on-market`, `days-on-market` | `time-on-market` |
| **Stories** | `min-stories` | `num-stories-min` |
| **Stories** | `max-stories` | `num-stories-max` |
| **Stories** | `num-stories` | `num-stories-min` |
| **Waterfront** | `has-waterfront`, `waterfront`, `has-water-front` | `water-front` |
| **View** | `view` | `has-view` |
| **Pool** | `has-pool`, `pool` | `pool-type` |
| **Garage** | `garage` | `has-garage` |
| **Elevator** | `elevator` | `has-elevator` |
| **Parking** | `parking` | `has-parking` |
| **Washer/Dryer** | `has-washer-dryer`, `washer-dryer-hookup` | `washer-dryer` |
| **Fireplace** | `has-fireplace` | `fireplace` |
| **Basement** | `has-basement`, `basement` | `basement-type` |
| **Pets** | `allows-pets`, `pet-friendly` | `pets-allowed` |
| **Dogs** | `allows-dogs`, `dog-friendly` | `dogs-allowed` |
| **Cats** | `allows-cats`, `cat-friendly` | `cats-allowed` |
| **Furnished** | `furnished` | `is-furnished` |
| **Fixer** | `fixer-upper`, `fixer` | `is-fixer` |
| **Green Home** | `green`, `green-home` | `is-green` |
| **Guest House** | `has-guest-house` | `guest-house` |
| **Primary Bedroom** | `primary-bedroom-on-main`, `master-on-main` | `primary-bed-on-main` |
| **Dishwasher** | `dishwasher` | `has-dishwasher` |
| **ATT Fiber** | `att-fiber` | `has-att-fiber` |
| **Deals** | `special-deal`, `deal` | `has-deal` |

### 3.3 Instance Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `gt_urls` | `list[str]` | List of acceptable ground truth URLs |
| `_found_match` | `bool` | Internal flag indicating if match was found |

### 3.4 Methods

#### 3.4.1 `__init__(gt_url: str | list[str])`

Constructor that initializes the metric with ground truth URL(s).

- Accepts single string or list of strings
- Normalizes single URL to list for uniform processing
- Initializes `_found_match` to `False`

```python
# Single URL
evaluator = RedfinUrlMatch(
    gt_url="https://www.redfin.com/city/1387/WA/Bellevue/filter/min-beds=3"
)

# Multiple acceptable URLs
evaluator = RedfinUrlMatch(
    gt_url=[
        "https://www.redfin.com/city/1387/WA/Bellevue/filter/min-beds=3",
        "https://www.redfin.com/city/112/WA/Bellevue/filter/min-beds=3"
    ]
)
```

#### 3.4.2 `async reset()`

Resets the metric state for a new evaluation run.

- Sets `_found_match` back to `False`

#### 3.4.3 `async update(**kwargs)`

Main evaluation method called with current browser state.

- Extracts URL from kwargs
- Parses and normalizes it
- Iterates through all ground truth URLs comparing parsed components
- Sets `_found_match = True` on first match
- Logs match/no-match results

#### 3.4.4 `async compute() → FinalResult`

Returns the final evaluation result.

- Score is `1.0` if any match was found
- Score is `0.0` otherwise

#### 3.4.5 `_urls_match(agent_url: str, gt_url: str) → bool`

Compares two URLs by parsing and comparing their components.

1. Parses both URLs into structured components
2. Compares location type (city vs neighborhood)
3. Compares location name (case-insensitive)
4. Compares state code
5. Compares rental status
6. Compares filter dictionaries (order-independent)
7. Returns `True` only if all components match

#### 3.4.6 `_parse_redfin_url(url: str) → dict`

The core parsing algorithm that extracts structured data from Redfin URLs.

**Returns:**
```python
{
    "location_type": str,  # "city" or "neighborhood"
    "location": str,       # e.g., "bellevue" or "new-york/long-island"
    "state": str,          # e.g., "wa"
    "is_rental": bool,     # True if /rentals/ or /apartments-for-rent/
    "filters": dict        # e.g., {"max-price": "2000000", "min-beds": "3"}
}
```

#### 3.4.7 `_normalize_param_name(param: str) → str`

Maps parameter name aliases to canonical forms. See section 3.2 for the complete alias table.

#### 3.4.8 `_normalize_param_value(param: str, value: str) → str`

Normalizes parameter values. Handles:

| Type | Input Examples | Normalized Output |
|------|----------------|-------------------|
| Price (millions) | `2m`, `1.5m` | `2000000`, `1500000` |
| Price (thousands) | `500k`, `2000k` | `500000`, `2000000` |
| Price (commas) | `2,000,000` | `2000000` |
| Sqft (k suffix) | `1.5k`, `3k` | `1500`, `3000` |
| Sqft (-sqft suffix) | `1500-sqft` | `1500` |
| Time (weeks) | `1wk`, `2wk` | `7days`, `14days` |
| Time (months) | `1mo`, `3mo` | `30days`, `90days` |
| Time (year) | `1yr` | `365days` |
| Date | `1/15/2026` | `1/15/2026` (normalized) |

---

## 4. Advanced Normalization Algorithm

The `_parse_redfin_url()` method transforms any valid Redfin URL into a structured dictionary, enabling intelligent comparison.

### 4.1 Step-by-Step Process

#### Step 1: Initial Cleanup

```python
url = url.lower().strip()
url = unquote(url)  # URL decode
url = url.replace("http://", "").replace("https://", "").replace("www.", "")
```

**Before:** `HTTPS://WWW.REDFIN.COM/city/1387/WA/Bellevue`  
**After:** `redfin.com/city/1387/wa/bellevue`

#### Step 2: Parse URL Structure

```python
parsed = urlparse("http://" + url)
path = parsed.path.rstrip("/")
```

#### Step 3: Detect Rental Listings

```python
if '/rentals' in path or '/apartments-for-rent' in path:
    result["is_rental"] = True
```

#### Step 4: Extract Location

**City URLs:**
```python
# Pattern: /city/1387/WA/Bellevue
city_match = re.search(r'/city/\d+/([^/]+)/([^/]+)', path)
result["location_type"] = "city"
result["state"] = city_match.group(1)   # "wa"
result["location"] = city_match.group(2) # "bellevue"
```

**Neighborhood URLs:**
```python
# Pattern: /neighborhood/219261/NY/New-York/Long-Island
neighborhood_match = re.search(r'/neighborhood/\d+/([^/]+)/([^/]+)/([^/]+)', path)
result["location_type"] = "neighborhood"
result["state"] = neighborhood_match.group(1)  # "ny"
city = neighborhood_match.group(2)             # "new-york"
neighborhood = neighborhood_match.group(3)     # "long-island"
result["location"] = f"{city}/{neighborhood}"  # "new-york/long-island"
```

**Key Feature:** City/Neighborhood IDs (1387, 219261) are IGNORED - only names matter!

#### Step 5: Pre-process Filter Segment

```python
# Remove commas from prices: 2,000,000 → 2000000
filter_segment = re.sub(r'(\d),(\d)', r'\1\2', filter_segment)
```

#### Step 6: Parse Individual Filters

```python
filters = filter_segment.split(",")
for f in filters:
    # Skip ignored parameters
    if f.startswith("viewport") or f.startswith("sort"):
        continue
    
    if "=" in f:
        key, value = f.split("=", 1)
        
        # Normalize parameter name
        key = _normalize_param_name(key)
        
        # Handle multi-value filters (e.g., property-type=house+condo)
        if "+" in value:
            value_parts = value.split("+")
            normalized_parts = [_normalize_param_value(key, v) for v in value_parts]
            # Deduplicate and sort for consistent comparison
            normalized_parts = list(set(normalized_parts))
            result["filters"][key] = tuple(sorted(normalized_parts))
        else:
            value = _normalize_param_value(key, value)
            result["filters"][key] = value
    else:
        # Boolean flag (e.g., is-fixer, has-view)
        normalized_flag = _normalize_param_name(f)
        result["filters"][normalized_flag] = "true"
```

#### Step 7: Post-Processing - Beds/Baths Consolidation

```python
if "beds" in filters:
    beds_val = filters.pop("beds")
    filters["min-beds"] = beds_val
    filters["max-beds"] = beds_val

if "baths" in filters:
    baths_val = filters.pop("baths")
    filters["min-baths"] = baths_val
    filters["max-baths"] = baths_val
```

#### Step 8: Post-Processing - Stories Consolidation

```python
min_stories = filters.get("num-stories-min")
max_stories = filters.get("num-stories-max")

if min_stories is not None and max_stories is not None:
    if min_stories == max_stories:
        # Same value - consolidate to single key
        filters.pop("num-stories-min")
        filters.pop("num-stories-max")
        filters["stories"] = min_stories
elif max_stories is not None and min_stories is None:
    # Only max specified - treat as exact
    filters.pop("num-stories-max")
    filters["stories"] = max_stories
elif min_stories is not None and max_stories is None:
    # Only min specified - keep as min-stories
    filters.pop("num-stories-min")
    filters["min-stories"] = min_stories
```

#### Step 9: Compare Dictionaries

```python
# Order-independent comparison via dict equality
if agent_parts["filters"] == gt_parts["filters"]:
    return True
```

---

## 5. Normalization Examples

### Example 1: Basic Normalization

**Input:**
```
https://www.redfin.com/city/1387/WA/Bellevue/filter/min-beds=3,max-price=2000000
```

**Output:**
```python
{
    "location_type": "city",
    "location": "bellevue",
    "state": "wa",
    "is_rental": False,
    "filters": {
        "min-beds": "3",
        "max-price": "2000000"
    }
}
```

### Example 2: Price Abbreviations

**Input:**
```
https://www.redfin.com/city/1387/WA/Bellevue/filter/max-price=2m,min-beds=3
```

**Output:**
```python
{
    "location_type": "city",
    "location": "bellevue",
    "state": "wa",
    "is_rental": False,
    "filters": {
        "max-price": "2000000",  # 2m → 2000000
        "min-beds": "3"
    }
}
```

### Example 3: Multi-Value Filters

**Input:**
```
https://www.redfin.com/city/1387/WA/Bellevue/filter/property-type=house+condo
```

**Output:**
```python
{
    "location_type": "city",
    "location": "bellevue",
    "state": "wa",
    "is_rental": False,
    "filters": {
        "property-type": ("condo", "house")  # Sorted tuple for comparison
    }
}
```

### Example 4: Parameter Aliases

**Input:**
```
https://www.redfin.com/city/1387/WA/Bellevue/filter/max-days-on-market=1wk
```

**Output:**
```python
{
    "location_type": "city",
    "location": "bellevue",
    "state": "wa",
    "is_rental": False,
    "filters": {
        "time-on-market": "7days"  # Alias normalized + time value normalized
    }
}
```

### Example 5: Neighborhood URL

**Input:**
```
https://www.redfin.com/neighborhood/219261/NY/New-York/Long-Island/filter/min-price=1m
```

**Output:**
```python
{
    "location_type": "neighborhood",
    "location": "new-york/long-island",
    "state": "ny",
    "is_rental": False,
    "filters": {
        "min-price": "1000000"
    }
}
```

### Example 6: Rental URL

**Input:**
```
https://www.redfin.com/city/16163/WA/Seattle/apartments-for-rent/filter/min-beds=2,max-price=3500
```

**Output:**
```python
{
    "location_type": "city",
    "location": "seattle",
    "state": "wa",
    "is_rental": True,  # Detected from URL path
    "filters": {
        "min-beds": "2",
        "max-price": "3500"
    }
}
```

### Example 7: Complete Complex Example

**Input:**
```
HTTP://REDFIN.COM/city/112/wa/bellevue/filter/
viewport=47.6:-122.2,property-type=house+condo,max-days-on-market=1wk,
max-price=2m,min-beds=3,min-stories=1,max-stories=1,sort=hi-price?utm_source=agent
```

**Output:**
```python
{
    "location_type": "city",
    "location": "bellevue",
    "state": "wa",
    "is_rental": False,
    "filters": {
        "property-type": ("condo", "house"),  # Multi-value, sorted
        "time-on-market": "7days",            # Alias + time normalized
        "max-price": "2000000",               # 2m → 2000000
        "min-beds": "3",
        "stories": "1"                        # min=max consolidated
    }
    # viewport IGNORED (UI param)
    # sort IGNORED (doesn't affect search)
    # utm_source IGNORED (tracking param)
}
```

---

## 6. Supported Redfin Filters

The normalization approach handles any Redfin filter generically. Below is a reference of common Redfin filters:

### 6.1 Price & Financial Filters

| Filter | Format | Example | Normalized |
|--------|--------|---------|------------|
| `min-price` | `min-price={value}` | `min-price=500k` | `500000` |
| `max-price` | `max-price={value}` | `max-price=2m` | `2000000` |
| `max-hoa` | `max-hoa={value}` | `max-hoa=500` | `500` |
| `min-price-per-sqft` | `min-price-per-sqft={value}` | `min-price-per-sqft=200` | `200` |
| `max-price-per-sqft` | `max-price-per-sqft={value}` | `max-price-per-sqft=500` | `500` |

### 6.2 Room Filters

| Filter | Format | Example | Notes |
|--------|--------|---------|-------|
| `min-beds` | `min-beds={value}` | `min-beds=3` | |
| `max-beds` | `max-beds={value}` | `max-beds=4` | |
| `beds` | `beds={value}` | `beds=3` | Expands to min+max |
| `min-baths` | `min-baths={value}` | `min-baths=2` | |
| `max-baths` | `max-baths={value}` | `max-baths=3` | |
| `baths` | `baths={value}` | `baths=2` | Expands to min+max |

### 6.3 Size & Structure Filters

| Filter | Format | Example | Normalized |
|--------|--------|---------|------------|
| `min-sqft` | `min-sqft={value}` | `min-sqft=1.5k` | `1500` |
| `max-sqft` | `max-sqft={value}` | `max-sqft=3000-sqft` | `3000` |
| `min-stories` | `min-stories={value}` | `min-stories=1` | `num-stories-min` |
| `max-stories` | `max-stories={value}` | `max-stories=2` | `num-stories-max` |
| `min-lot-size` | `min-lot-size={value}` | `min-lot-size=0.5` | `0.5` |
| `max-lot-size` | `max-lot-size={value}` | `max-lot-size=2` | `2` |

### 6.4 Property Type Filter

| Value | Description |
|-------|-------------|
| `house` | Single-family homes |
| `condo` | Condominiums |
| `townhouse` | Townhouses |
| `multi-family` | Multi-family properties |
| `land` | Vacant land |
| `manufactured` | Manufactured homes |
| `house+condo` | Multiple types (multi-value) |
| `house+condo+townhouse` | Three types (multi-value) |

### 6.5 Time & Age Filters

| Filter | Format | Example | Normalized |
|--------|--------|---------|------------|
| `min-year-built` | `min-year-built={value}` | `min-year-built=1980` | `1980` |
| `max-year-built` | `max-year-built={value}` | `max-year-built=2020` | `2020` |
| `time-on-market` | `time-on-market={value}` | `time-on-market=1wk` | `7days` |
| `max-days-on-market` | `max-days-on-market={value}` | `max-days-on-market=1wk` | `7days` (aliased) |

### 6.6 Amenity Filters (Boolean)

| Filter | Aliases | Description |
|--------|---------|-------------|
| `water-front` | `has-waterfront`, `waterfront` | Waterfront property |
| `has-view` | `view` | Property with view |
| `pool-type` | `has-pool`, `pool` | Has pool |
| `has-garage` | `garage` | Has garage |
| `has-elevator` | `elevator` | Has elevator |
| `has-parking` | `parking` | Has parking |
| `fireplace` | `has-fireplace` | Has fireplace |
| `basement-type` | `has-basement`, `basement` | Has basement |
| `washer-dryer` | `has-washer-dryer`, `washer-dryer-hookup` | In-unit washer/dryer |
| `air-conditioning` | | Has A/C |
| `is-fixer` | `fixer-upper`, `fixer` | Fixer-upper |
| `is-green` | `green`, `green-home` | Green/eco-friendly home |
| `guest-house` | `has-guest-house` | Has guest house |
| `primary-bed-on-main` | `primary-bedroom-on-main`, `master-on-main` | Primary bedroom on main floor |
| `has-dishwasher` | `dishwasher` | Has dishwasher |
| `has-att-fiber` | `att-fiber` | ATT Fiber available |
| `has-deal` | `special-deal`, `deal` | Has special deal |

### 6.7 Rental-Specific Filters

| Filter | Aliases | Description |
|--------|---------|-------------|
| `dogs-allowed` | `allows-dogs`, `dog-friendly` | Allows dogs |
| `cats-allowed` | `allows-cats`, `cat-friendly` | Allows cats |
| `pets-allowed` | `allows-pets`, `pet-friendly` | Allows pets |
| `is-furnished` | `furnished` | Furnished rental |
| `move-in-date` | | Available move-in date |

### 6.8 Include Filters

| Value | Description |
|-------|-------------|
| `sold-1mo` | Include sold in last month |
| `sold-3mo` | Include sold in last 3 months |
| `sold-6mo` | Include sold in last 6 months |
| `sold-1yr` | Include sold in last year |
| `sold-2yr` | Include sold in last 2 years |
| `sold-3yr` | Include sold in last 3 years |
| `sold-5yr` | Include sold in last 5 years |
| `construction` | Include new construction |

### 6.9 Location Types

| Type | URL Pattern | Example |
|------|-------------|---------|
| City | `/city/{id}/{state}/{name}/` | `/city/1387/WA/Bellevue/` |
| Neighborhood | `/neighborhood/{id}/{state}/{city}/{name}/` | `/neighborhood/219261/NY/New-York/Long-Island/` |
| City Rentals | `/city/{id}/{state}/{name}/apartments-for-rent/` | `/city/16163/WA/Seattle/apartments-for-rent/` |
| City Rentals Alt | `/city/{id}/{state}/{name}/rentals/` | `/city/1387/WA/Bellevue/rentals/` |

---

## 7. Task Configuration

### 7.1 generate_task_config Function

| Parameter | Type | Description |
|-----------|------|-------------|
| `task` | `str` | Natural language task description for the agent |
| `gt_url` | `list[str]` | List of acceptable ground truth URLs |
| `location` | `str` | User's location context |
| `timezone` | `str` | User's timezone (IANA format) |
| `timestamp` | `int \| None` | Optional Unix timestamp for task |
| `url` | `str` | Starting URL (default: redfin.com) |

### 7.2 Example Usage

```python
from navi_bench.redfin.redfin_url_match import RedfinUrlMatch, generate_task_config

# Generate task configuration
task_config = generate_task_config(
    task="Find 3-4 bedroom houses in Bellevue under $2M built after 1980",
    gt_url=[
        "https://www.redfin.com/city/1387/WA/Bellevue/filter/min-beds=3,max-beds=4,max-price=2m,min-year-built=1980,property-type=house"
    ],
    location="Seattle, WA",
    timezone="America/Los_Angeles"
)

# Create evaluator
evaluator = RedfinUrlMatch(gt_url=task_config.eval_config["gt_url"])

# During agent execution
await evaluator.reset()
await evaluator.update(url=agent_current_url)

# Get final result
result = await evaluator.compute()
print(f"Score: {result.score}")  # 1.0 = match, 0.0 = no match
```

---

## 8. Running the Test Suite

### 8.1 Command

```bash
cd /path/to/redfin
python3 navi_bench/redfin/redfin_url_match.py
```

### 8.2 Expected Output

```
================================================================================
REDFIN URL VERIFIER - COMPREHENSIVE EDGE CASE TEST SUITE
================================================================================
Testing 60+ edge cases across 16 categories
================================================================================

CATEGORY 1: FILTER ORDER INDEPENDENCE (4 tests)
================================================================================
✅ Test 1.1: Exact match
✅ Test 1.2: Completely reversed order
✅ Test 1.3: Random order
✅ Test 1.4: Alphabetical order

CATEGORY 2: CITY ID VARIATIONS (3 tests)
================================================================================
✅ Test 2.1: City ID 112 (vs 1387)
✅ Test 2.2: City ID 9999 (any ID works for same city)
✅ Test 2.3: Wrong city correctly rejected

... (all 16 categories) ...

================================================================================
FINAL RESULTS
================================================================================
Total Tests: 64
Passed: 64
Failed: 0
Success Rate: 100.0%
================================================================================

🎉 ALL TESTS PASSED! Verifier is production-ready.
================================================================================
```

---

## 9. Documentation Files

| Document | Description |
|----------|-------------|
| [README.md](./README.md) | This file - comprehensive documentation |
| [EDGE_CASES.md](./EDGE_CASES.md) | All 64 edge cases across 16 categories |
| [HOW_IT_WORKS.md](./HOW_IT_WORKS.md) | Technical algorithm explanation |

---

## 10. Summary & Statistics

| Metric | Value |
|--------|-------|
| Total Lines of Code | 1400+ |
| Test Cases | 64 |
| Test Categories | 16 |
| Test Success Rate | 100% |
| Ignored Parameters | 14 |
| Parameter Aliases | 40+ |
| Price Formats Supported | 4 (plain, m, k, commas) |
| Sqft Formats Supported | 4 (plain, k, -sqft, k-sqft) |
| Time Formats Supported | 8 (1wk, 2wk, 1mo, 2mo, 3mo, 6mo, 1yr, days) |

### 10.1 Key Features Summary

| Feature | Status |
|---------|--------|
| Advanced normalization with multi-value filters | ✅ |
| Price and sqft abbreviations | ✅ |
| City/Neighborhood ID flexibility | ✅ |
| Rental vs sale detection | ✅ |
| 40+ parameter aliases | ✅ |
| Stories consolidation | ✅ |
| Beds/baths expansion | ✅ |
| Time value normalization | ✅ |
| Include filter support | ✅ |
| Order-independent comparison | ✅ |
| Comma handling in prices | ✅ |
| Deterministic behavior | ✅ |
| Easy to debug with logging | ✅ |
| Handles unknown filters generically | ✅ |
| Multiple ground truth URLs | ✅ |
| Type-safe with beartype | ✅ |
| Async-compatible for NaviBench | ✅ |
| Production-ready (100% test pass) | ✅ |

---

## 11. Changelog

### Version 2.0 (2026-01-03)

**New Features:**
- Added neighborhood URL support (`/neighborhood/...`)
- Added rental detection (`/apartments-for-rent`, `/rentals`)
- Added square footage normalization (k, -sqft suffix)
- Added 40+ parameter aliases (up from 3)
- Added stories consolidation (min=max → single key)
- Added beds/baths expansion (beds=3 → min+max)
- Added time value normalization (1wk → 7days)
- Added include filter support (sold-3mo, construction)
- Added move-in-date normalization
- Added sort parameter to ignored list

**Test Suite:**
- Expanded from 50 to 64 tests
- Expanded from 13 to 16 categories
- Added: Rental, Neighborhood, Sqft, Stories, Beds/Baths, Include, Time categories

### Version 1.0 (2025-12-19)

- Initial release with 50 tests across 13 categories
- Basic price abbreviation support
- City ID flexibility
- Multi-value filter support

---

## 12. Conclusion

This Redfin URL Match verifier represents a production-grade implementation with:

- ✅ **1400+ lines** of well-documented code
- ✅ **64 comprehensive tests** covering all edge cases
- ✅ **100% test success rate**
- ✅ **Advanced features** (multi-value, aliases, abbreviations, consolidation)
- ✅ **Robust error handling** and validation
- ✅ **Complete NaviBench integration**

The verifier is ready for production use in evaluating AI agents' ability to navigate Redfin's real estate search interface.

---

**Document Version**: 2.0  
**Last Updated**: 2026-01-03  
**Test Suite Status**: ✅ 64/64 tests passing (100%)
