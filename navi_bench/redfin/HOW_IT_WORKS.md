# How the Redfin URL Match Script Works

## Technical Deep Dive into the URL Verification Algorithm

### Comprehensive Implementation Documentation

---

## 1. Overview

The Redfin URL Match script is a sophisticated URL verification system that determines whether an AI agent has navigated to the correct Redfin search page. It uses a multi-stage normalization pipeline to handle the vast variety of URL formats that represent equivalent searches.

### 1.1 Core Philosophy

**"Parse → Normalize → Compare"**

Instead of string matching (which would fail on order variations), the script:
1. **Parses** each URL into structured components
2. **Normalizes** each component to a canonical form
3. **Compares** the normalized structures using dictionary equality

This approach ensures that semantically equivalent URLs are recognized as matches, regardless of superficial differences in format, order, or style.

---

## 2. Architecture

### 2.1 High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           URL MATCHING PIPELINE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────┐                      ┌───────────────┐                   │
│  │   Agent URL   │                      │  Ground Truth │                   │
│  │               │                      │      URL      │                   │
│  └───────┬───────┘                      └───────┬───────┘                   │
│          │                                      │                           │
│          ▼                                      ▼                           │
│  ┌───────────────────────────────────────────────────────────────────┐     │
│  │                    _parse_redfin_url()                            │     │
│  │  ┌─────────────────────────────────────────────────────────────┐  │     │
│  │  │ 1. Lowercase & strip whitespace                             │  │     │
│  │  │ 2. URL decode                                               │  │     │
│  │  │ 3. Remove protocol & www                                    │  │     │
│  │  │ 4. Detect rental status                                     │  │     │
│  │  │ 5. Extract location (city or neighborhood)                  │  │     │
│  │  │ 6. Parse filter segment                                     │  │     │
│  │  │ 7. Normalize parameter names (40+ aliases)                  │  │     │
│  │  │ 8. Normalize parameter values (price, sqft, time)           │  │     │
│  │  │ 9. Handle multi-value filters (sort, dedupe, tuple)         │  │     │
│  │  │ 10. Post-process: beds/baths expansion                      │  │     │
│  │  │ 11. Post-process: stories consolidation                     │  │     │
│  │  └─────────────────────────────────────────────────────────────┘  │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│          │                                      │                           │
│          ▼                                      ▼                           │
│  ┌───────────────┐                      ┌───────────────┐                   │
│  │   Normalized  │                      │   Normalized  │                   │
│  │     Dict      │                      │     Dict      │                   │
│  └───────┬───────┘                      └───────┬───────┘                   │
│          │                                      │                           │
│          └──────────────────┬───────────────────┘                           │
│                             │                                               │
│                             ▼                                               │
│                    ┌────────────────┐                                       │
│                    │    COMPARE     │                                       │
│                    │                │                                       │
│                    │ location_type? │                                       │
│                    │ location?      │                                       │
│                    │ state?         │                                       │
│                    │ is_rental?     │                                       │
│                    │ filters == ?   │                                       │
│                    └────────┬───────┘                                       │
│                             │                                               │
│                    ┌────────┴────────┐                                      │
│                    │                 │                                      │
│                    ▼                 ▼                                      │
│              ┌──────────┐     ┌──────────┐                                  │
│              │  MATCH   │     │ NO MATCH │                                  │
│              │ Score=1.0│     │ Score=0.0│                                  │
│              └──────────┘     └──────────┘                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Structures

#### Input URL
```
https://www.redfin.com/city/1387/WA/Bellevue/filter/max-price=2m,min-beds=3,property-type=house
```

#### Parsed Output Structure
```python
{
    "location_type": "city",           # or "neighborhood"
    "location": "bellevue",            # city name or city/neighborhood
    "state": "wa",                     # state code
    "is_rental": False,                # True for rental listings
    "filters": {
        "max-price": "2000000",        # Normalized from 2m
        "min-beds": "3",
        "property-type": "house"
    }
}
```

---

## 3. Parsing Pipeline

### 3.1 Step 1: Initial Cleanup

**Purpose**: Standardize URL format for consistent parsing.

```python
# Input
url = "  HTTPS://WWW.REDFIN.COM/city/1387/WA/Bellevue  "

# Processing
url = url.lower().strip()
# Result: "https://www.redfin.com/city/1387/wa/bellevue"

url = unquote(url)  # URL decode %20 → space, etc.

url = url.replace("http://", "").replace("https://", "").replace("www.", "")
# Result: "redfin.com/city/1387/wa/bellevue"
```

**What this handles**:
- Case variations (HTTP, Http, http)
- Protocol variations (http://, https://)
- www prefix (with or without)
- Leading/trailing whitespace
- URL-encoded characters

---

### 3.2 Step 2: Rental Detection

**Purpose**: Identify if URL is for rental listings.

```python
path = parsed.path  # e.g., "/city/1387/WA/Bellevue/apartments-for-rent/filter/..."

if '/rentals' in path or '/apartments-for-rent' in path:
    result["is_rental"] = True
else:
    result["is_rental"] = False
```

**Why this matters**:
- Rental and for-sale searches are fundamentally different
- Same filters on a rental vs sale URL = different searches
- Must be an exact match on rental status

---

### 3.3 Step 3: Location Extraction

**Purpose**: Extract city/neighborhood name, ignoring numeric IDs.

#### City URLs
```python
# Pattern: /city/1387/WA/Bellevue
city_match = re.search(r'/city/\d+/([^/]+)/([^/]+)', path)

if city_match:
    result["location_type"] = "city"
    result["state"] = unquote(city_match.group(1))   # "wa"
    result["location"] = unquote(city_match.group(2)) # "bellevue"
```

#### Neighborhood URLs
```python
# Pattern: /neighborhood/219261/NY/New-York/Long-Island
neighborhood_match = re.search(r'/neighborhood/\d+/([^/]+)/([^/]+)/([^/]+)', path)

if neighborhood_match:
    result["location_type"] = "neighborhood"
    result["state"] = unquote(neighborhood_match.group(1))      # "ny"
    city = unquote(neighborhood_match.group(2))                  # "new-york"
    neighborhood = unquote(neighborhood_match.group(3))          # "long-island"
    result["location"] = f"{city}/{neighborhood}"                # "new-york/long-island"
```

**Key insight**: The numeric ID (1387, 219261) is IGNORED because:
- Same city can have different IDs
- Only the city/neighborhood name is semantically meaningful

---

### 3.4 Step 4: Filter Parsing

**Purpose**: Extract and normalize search filters.

#### Pre-processing
```python
# Handle commas in prices: 2,000,000 → 2000000
filter_segment = re.sub(r'(\d),(\d)', r'\1\2', filter_segment)
```

#### Main parsing loop
```python
filters = filter_segment.split(",")

for f in filters:
    f = f.strip()
    
    # Skip empty
    if not f:
        continue
    
    # Skip ignored parameters (viewport, sort, utm_*, etc.)
    if self._is_ignored(f):
        continue
    
    if "=" in f:
        key, value = f.split("=", 1)
        
        # Normalize parameter name (40+ aliases)
        key = self._normalize_param_name(key)
        
        # Handle multi-value filters (e.g., property-type=house+condo)
        if "+" in value:
            value_parts = value.split("+")
            normalized_parts = [self._normalize_param_value(key, v) for v in value_parts]
            normalized_parts = list(set(normalized_parts))  # Deduplicate
            result["filters"][key] = tuple(sorted(normalized_parts))  # Sorted tuple
        else:
            value = self._normalize_param_value(key, value)
            result["filters"][key] = value
    else:
        # Boolean flag (e.g., is-fixer, has-view)
        normalized_flag = self._normalize_param_name(f)
        result["filters"][normalized_flag] = "true"
```

---

## 4. Normalization Details

### 4.1 Parameter Name Normalization

**Purpose**: Map aliases to canonical forms.

```python
def _normalize_param_name(self, param: str) -> str:
    param = param.strip().lower()
    
    aliases = {
        # Time on market
        "max-days-on-market": "time-on-market",
        "days-on-market": "time-on-market",
        
        # Stories
        "min-stories": "num-stories-min",
        "max-stories": "num-stories-max",
        "num-stories": "num-stories-min",
        
        # Waterfront
        "has-waterfront": "water-front",
        "waterfront": "water-front",
        
        # Pool
        "has-pool": "pool-type",
        "pool": "pool-type",
        
        # ... 35+ more aliases
    }
    
    return aliases.get(param, param)  # Return alias or original
```

**Example transformations**:
| Input | Output |
|-------|--------|
| `max-days-on-market` | `time-on-market` |
| `has-waterfront` | `water-front` |
| `has-pool` | `pool-type` |
| `allows-dogs` | `dogs-allowed` |

---

### 4.2 Value Normalization

**Purpose**: Normalize values to comparable formats.

#### Prices
```python
if "price" in param and "sqft" not in param:
    value = value.replace(",", "")  # Remove commas
    
    if value.endswith("m"):
        num = float(value[:-1])
        return str(int(num * 1000000))  # 2m → 2000000
    
    elif value.endswith("k"):
        num = float(value[:-1])
        return str(int(num * 1000))  # 500k → 500000
    
    return value
```

| Input | Output |
|-------|--------|
| `2m` | `2000000` |
| `1.5m` | `1500000` |
| `500k` | `500000` |
| `2,000,000` | `2000000` |

#### Square Footage
```python
if "sqft" in param or "lot-size" in param:
    value = value.replace("-sqft", "").replace("sqft", "")
    
    if value.endswith("k"):
        num = float(value[:-1])
        return str(int(num * 1000))  # 1.5k → 1500
```

| Input | Output |
|-------|--------|
| `1500` | `1500` |
| `1.5k` | `1500` |
| `3k` | `3000` |
| `1500-sqft` | `1500` |

#### Time Values
```python
if "time" in param or "market" in param or "days" in param:
    time_map = {
        "1wk": "7days",
        "2wk": "14days",
        "1mo": "30days",
        "3mo": "90days",
        "6mo": "180days",
        "1yr": "365days",
    }
    return time_map.get(value, value)
```

| Input | Output |
|-------|--------|
| `1wk` | `7days` |
| `2wk` | `14days` |
| `1mo` | `30days` |
| `3mo` | `90days` |

---

### 4.3 Multi-Value Filter Handling

**Purpose**: Enable order-independent comparison of multi-value filters.

```python
# Input: property-type=house+condo+townhouse
value_parts = value.split("+")  # ["house", "condo", "townhouse"]

# Normalize each part
normalized_parts = [self._normalize_param_value(key, v) for v in value_parts]

# Deduplicate (house+house+condo → [house, condo])
normalized_parts = list(set(normalized_parts))

# Sort and convert to tuple for consistent comparison
result["filters"][key] = tuple(sorted(normalized_parts))
# ("condo", "house", "townhouse")
```

**Why tuples?**
- Lists aren't hashable (can't be dict keys)
- Sorted tuples enable order-independent comparison
- Immutable for safety

---

## 5. Post-Processing

### 5.1 Beds/Baths Expansion

**Purpose**: Expand shorthand `beds=3` to explicit `min-beds=3,max-beds=3`.

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

| Input | Output |
|-------|--------|
| `beds=3` | `min-beds=3, max-beds=3` |
| `baths=2` | `min-baths=2, max-baths=2` |

---

### 5.2 Stories Consolidation

**Purpose**: Handle different representations of exact story counts.

```python
min_stories = filters.get("num-stories-min")
max_stories = filters.get("num-stories-max")

if min_stories is not None and max_stories is not None:
    if min_stories == max_stories:
        # Same value → consolidate to single key
        filters.pop("num-stories-min")
        filters.pop("num-stories-max")
        filters["stories"] = min_stories
        
elif max_stories is not None and min_stories is None:
    # Only max specified → treat as exact
    filters.pop("num-stories-max")
    filters["stories"] = max_stories
    
elif min_stories is not None and max_stories is None:
    # Only min specified → keep as min-stories
    filters.pop("num-stories-min")
    filters["min-stories"] = min_stories
```

| Input | Output |
|-------|--------|
| `min-stories=2, max-stories=2` | `stories=2` |
| `max-stories=1` | `stories=1` |
| `min-stories=2` | `min-stories=2` |
| `min-stories=1, max-stories=3` | `num-stories-min=1, num-stories-max=3` |

---

## 6. Comparison Logic

### 6.1 URL Matching

```python
def _urls_match(self, agent_url: str, gt_url: str) -> bool:
    agent_parts = self._parse_redfin_url(agent_url)
    gt_parts = self._parse_redfin_url(gt_url)
    
    # 1. Location type must match (city vs neighborhood)
    if agent_parts["location_type"] != gt_parts["location_type"]:
        logger.debug(f"Location type mismatch")
        return False
    
    # 2. Location name must match
    if agent_parts["location"] != gt_parts["location"]:
        logger.debug(f"Location mismatch")
        return False
    
    # 3. State must match
    if agent_parts["state"] != gt_parts["state"]:
        logger.debug(f"State mismatch")
        return False
    
    # 4. Rental status must match
    if agent_parts["is_rental"] != gt_parts["is_rental"]:
        logger.debug(f"Rental type mismatch")
        return False
    
    # 5. Filters must match (order-independent via dict ==)
    if agent_parts["filters"] != gt_parts["filters"]:
        logger.debug(f"Filter mismatch")
        # Log detailed diff for debugging
        self._log_filter_diff(agent_parts["filters"], gt_parts["filters"])
        return False
    
    return True
```

### 6.2 Why Dictionary Comparison Works

```python
# These are equal (order independent):
{"a": "1", "b": "2"} == {"b": "2", "a": "1"}  # True

# These are not equal (different values):
{"a": "1", "b": "2"} == {"a": "1", "b": "3"}  # False

# Multi-value filters use sorted tuples:
{"property-type": ("condo", "house")} == {"property-type": ("condo", "house")}  # True
```

---

## 7. Complete Example Walkthrough

### Input URL
```
HTTP://REDFIN.COM/city/112/wa/bellevue/filter/
viewport=47.6:-122.2,property-type=house+condo,max-days-on-market=1wk,
max-price=2m,min-beds=3,min-stories=1,max-stories=1,sort=hi-price?utm_source=agent
```

### Step-by-Step Processing

#### Step 1: Cleanup
```
url = "http://redfin.com/city/112/wa/bellevue/filter/viewport=47.6:-122.2,..."
       (lowercased, decoded, protocol removed)
```

#### Step 2: Rental Detection
```
"/apartments-for-rent" not in path → is_rental = False
```

#### Step 3: Location Extraction
```
city_match = /city/(\d+)/([^/]+)/([^/]+)/ → groups: "112", "wa", "bellevue"
location_type = "city"
state = "wa"
location = "bellevue"
```

#### Step 4: Filter Parsing
```
filter_segment = "viewport=47.6:-122.2,property-type=house+condo,max-days-on-market=1wk,max-price=2m,min-beds=3,min-stories=1,max-stories=1,sort=hi-price"

For each filter:
- viewport=47.6... → IGNORED (in IGNORED_PARAMS)
- property-type=house+condo → multi-value, sorted tuple
- max-days-on-market=1wk → alias to time-on-market, value to 7days
- max-price=2m → value to 2000000
- min-beds=3 → unchanged
- min-stories=1 → alias to num-stories-min
- max-stories=1 → alias to num-stories-max
- sort=hi-price → IGNORED

utm_source in query → IGNORED
```

#### Step 5: Post-Processing
```
num-stories-min=1, num-stories-max=1 → both equal → consolidate to stories=1
```

#### Final Result
```python
{
    "location_type": "city",
    "location": "bellevue",
    "state": "wa",
    "is_rental": False,
    "filters": {
        "property-type": ("condo", "house"),  # Sorted tuple
        "time-on-market": "7days",             # Alias + time normalized
        "max-price": "2000000",                # 2m → 2000000
        "min-beds": "3",
        "stories": "1"                         # Consolidated
    }
}
```

---

## 8. Performance Characteristics

| Metric | Value |
|--------|-------|
| Single URL parse | ~1ms |
| URL comparison | ~2ms |
| Full 64-test suite | ~5 seconds |
| Memory footprint | Minimal (no caching) |

### Design Trade-offs

1. **Simplicity over speed**: Dictionary comparison is O(n) but code is simple and maintainable
2. **Normalization over heuristics**: Explicit transformations instead of fuzzy matching
3. **Strict matching**: Requires exact filter match (no partial credit)
4. **Stateless**: Each URL parsed independently (no persistent state)

---

## 9. Debugging

### Logging Output

When a mismatch occurs, the script logs detailed information:

```
2026-01-03 10:43:33.239 | DEBUG | Filter mismatch:
2026-01-03 10:43:33.239 | DEBUG |   Agent: {'min-beds': '4', 'max-beds': '4'}
2026-01-03 10:43:33.239 | DEBUG |   GT:    {'min-beds': '3', 'max-beds': '3'}
2026-01-03 10:43:33.239 | DEBUG |   Wrong values: {'min-beds', 'max-beds'}
```

### Diff Categories

| Category | Description |
|----------|-------------|
| Missing filters | Filters in GT but not in agent URL |
| Extra filters | Filters in agent URL but not in GT |
| Wrong values | Same filter key, different value |

---

## 10. Extensibility

### Adding New Parameter Aliases

```python
# In _normalize_param_name():
aliases = {
    # ... existing aliases ...
    "new-alias": "canonical-name",
}
```

### Adding New Value Normalizations

```python
# In _normalize_param_value():
if "new-param" in param:
    # Custom normalization logic
    return normalized_value
```

### Adding New Ignored Parameters

```python
IGNORED_PARAMS = {
    # ... existing ...
    "new-ui-param",
}
```

---

**Last Updated**: 2026-01-03  
**Implementation Version**: 2.0
