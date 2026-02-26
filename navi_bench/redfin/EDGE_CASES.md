# Redfin URL Match - Edge Cases Documentation

## Comprehensive Test Coverage for URL Verification

### 64 Edge Cases Across 16 Categories

**Test Suite Status**: ✅ 64/64 tests passing (100%)

---

## Overview

This document provides detailed documentation of all edge cases covered by the Redfin URL Match verifier. Each test case is designed to verify a specific normalization or comparison behavior, ensuring the verifier handles all real-world URL variations correctly.

---

## Category 1: Filter Order Independence (4 tests)

### Purpose
Verifies that filter order doesn't affect matching. The URL comparison uses dictionary equality, which is inherently order-independent.

### Why This Matters
Redfin's UI may generate filters in different orders depending on user interaction sequence. An AI agent may apply filters in a different order than the ground truth, but the search should still be considered equivalent.

### Test Cases

| Test ID | Description | Input Order | Expected | Result |
|---------|-------------|-------------|----------|--------|
| 1.1 | Exact match | Same as GT | Match | ✅ PASS |
| 1.2 | Completely reversed | `z,y,x,w...` vs `a,b,c,d...` | Match | ✅ PASS |
| 1.3 | Random order | Random shuffle | Match | ✅ PASS |
| 1.4 | Alphabetical order | Sorted A-Z | Match | ✅ PASS |

### Implementation Detail
```python
# Filters stored as dict, compared with ==
agent_filters = {"a": "1", "b": "2"}
gt_filters = {"b": "2", "a": "1"}
agent_filters == gt_filters  # True - order independent
```

---

## Category 2: City ID Variations (3 tests)

### Purpose
Verifies that city IDs in the URL path are ignored - only city names matter.

### Why This Matters
Redfin uses numeric city IDs in their URLs (e.g., `/city/1387/WA/Bellevue`), but the same city can have different IDs in different contexts. An AI agent navigating to Bellevue should match regardless of which ID appears in the URL.

### Test Cases

| Test ID | Description | City ID | City Name | Expected | Result |
|---------|-------------|---------|-----------|----------|--------|
| 2.1 | Different ID (112) | 112 | Bellevue | Match | ✅ PASS |
| 2.2 | Different ID (9999) | 9999 | Bellevue | Match | ✅ PASS |
| 2.3 | Wrong city name | 1387 | Seattle | No Match | ✅ PASS |

### Implementation Detail
```python
# Extract city from path, ignore ID
city_match = re.search(r'/city/\d+/([^/]+)/([^/]+)', path)
#                              ^^^^ ID ignored
state = city_match.group(1)  # "wa"
city = city_match.group(2)   # "bellevue" - this is what matters
```

---

## Category 3: Price Abbreviations (5 tests)

### Purpose
Verifies that all price formats normalize to the same value.

### Why This Matters
Redfin supports multiple price formats:
- Full numbers: `2000000`
- Millions: `2m`, `1.5m`
- Thousands: `2000k`, `500k`
- With commas: `2,000,000`

An AI agent might use any of these formats, so they should all be treated equivalently.

### Test Cases

| Test ID | Description | Input | Normalized | Expected | Result |
|---------|-------------|-------|------------|----------|--------|
| 3.1 | Millions (2m) | `max-price=2m` | `2000000` | Match | ✅ PASS |
| 3.2 | Thousands (2000k) | `max-price=2000k` | `2000000` | Match | ✅ PASS |
| 3.3 | With commas | `max-price=2,000,000` | `2000000` | Match | ✅ PASS |
| 3.4 | Wrong price (1.5m) | `max-price=1.5m` | `1500000` | No Match | ✅ PASS |
| 3.5 | Wrong price (3m) | `max-price=3m` | `3000000` | No Match | ✅ PASS |

### Implementation Detail
```python
def _normalize_param_value(self, param: str, value: str) -> str:
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

### Normalization Table

| Input Format | Example | Normalized Output |
|--------------|---------|-------------------|
| Plain number | `2000000` | `2000000` |
| Millions | `2m` | `2000000` |
| Decimal millions | `1.5m` | `1500000` |
| Thousands | `500k` | `500000` |
| Thousands (large) | `2000k` | `2000000` |
| With commas | `2,000,000` | `2000000` |

---

## Category 4: Parameter Name Variations (4 tests)

### Purpose
Verifies that parameter aliases are normalized to canonical forms.

### Why This Matters
Redfin uses different parameter names for the same filter in different contexts. The verifier maps 40+ aliases to canonical forms to ensure equivalent searches match.

### Test Cases

| Test ID | Description | Input | Canonical | Result |
|---------|-------------|-------|-----------|--------|
| 4.1 | time-on-market alias | `time-on-market=1wk` | `time-on-market=7days` | ✅ PASS |
| 4.2 | days-on-market alias | `days-on-market=1wk` | `time-on-market=7days` | ✅ PASS |
| 4.3 | waterfront alias | `has-waterfront` | `water-front` | ✅ PASS |
| 4.4 | pool alias | `has-pool=either` | `pool-type=either` | ✅ PASS |

### Complete Alias Mapping

| Category | Input Aliases | Canonical Form |
|----------|---------------|----------------|
| Time on Market | `max-days-on-market`, `days-on-market` | `time-on-market` |
| Stories (min) | `min-stories` | `num-stories-min` |
| Stories (max) | `max-stories` | `num-stories-max` |
| Stories (exact) | `num-stories` | `num-stories-min` |
| Waterfront | `has-waterfront`, `waterfront`, `has-water-front` | `water-front` |
| View | `view` | `has-view` |
| Pool | `has-pool`, `pool` | `pool-type` |
| Garage | `garage` | `has-garage` |
| Elevator | `elevator` | `has-elevator` |
| Parking | `parking` | `has-parking` |
| Washer/Dryer | `has-washer-dryer`, `washer-dryer-hookup` | `washer-dryer` |
| Fireplace | `has-fireplace` | `fireplace` |
| Basement | `has-basement`, `basement` | `basement-type` |
| Pets | `allows-pets`, `pet-friendly` | `pets-allowed` |
| Dogs | `allows-dogs`, `dog-friendly` | `dogs-allowed` |
| Cats | `allows-cats`, `cat-friendly` | `cats-allowed` |
| Furnished | `furnished` | `is-furnished` |
| Fixer | `fixer-upper`, `fixer` | `is-fixer` |
| Green Home | `green`, `green-home` | `is-green` |
| Guest House | `has-guest-house` | `guest-house` |
| Primary Bedroom | `primary-bedroom-on-main`, `master-on-main` | `primary-bed-on-main` |
| Dishwasher | `dishwasher` | `has-dishwasher` |
| ATT Fiber | `att-fiber` | `has-att-fiber` |
| Deals | `special-deal`, `deal` | `has-deal` |

---

## Category 5: Case Sensitivity (4 tests)

### Purpose
Verifies that URL matching is case-insensitive.

### Why This Matters
URLs can appear in any case due to browser behavior, copy-paste, or manual entry. The verifier lowercases all URLs before parsing.

### Test Cases

| Test ID | Description | Input Case | Result |
|---------|-------------|------------|--------|
| 5.1 | All UPPERCASE | `HTTPS://WWW.REDFIN.COM/...` | ✅ PASS |
| 5.2 | Mixed Case | `https://www.Redfin.com/City/1387/Wa/Bellevue/...` | ✅ PASS |
| 5.3 | All lowercase | `https://www.redfin.com/city/1387/wa/bellevue/...` | ✅ PASS |
| 5.4 | Random case | `HtTpS://wWw.ReDfIn.CoM/cItY/1387/wA/...` | ✅ PASS |

### Implementation Detail
```python
url = url.lower().strip()  # First step in normalization
```

---

## Category 6: Protocol and Domain (3 tests)

### Purpose
Verifies that protocol (http/https) and www prefix variations are handled.

### Why This Matters
URLs can be provided with or without protocol, with or without www. All variations should match.

### Test Cases

| Test ID | Description | Input | Result |
|---------|-------------|-------|--------|
| 6.1 | HTTP protocol | `http://www.redfin.com/...` | ✅ PASS |
| 6.2 | Without www | `https://redfin.com/...` | ✅ PASS |
| 6.3 | No protocol, no www | `redfin.com/city/1387/...` | ✅ PASS |

### Implementation Detail
```python
url = url.replace("http://", "").replace("https://", "").replace("www.", "")
```

---

## Category 7: Ignored Parameters (5 tests)

### Purpose
Verifies that UI-only and tracking parameters are ignored during comparison.

### Why This Matters
Redfin URLs often contain parameters that don't affect search results:
- `viewport` - Map view coordinates
- `sort` - Display order (not search criteria)
- `no-outline` - Map rendering preference
- UTM parameters - Marketing tracking

These should not cause a mismatch.

### Test Cases

| Test ID | Description | Parameter | Result |
|---------|-------------|-----------|--------|
| 7.1 | Viewport coords | `viewport=47.6:-122.2:47.5:-122.1` | ✅ PASS (ignored) |
| 7.2 | No-outline flag | `no-outline` | ✅ PASS (ignored) |
| 7.3 | Sort order | `sort=hi-price` | ✅ PASS (ignored) |
| 7.4 | UTM parameters | `?utm_source=agent&utm_medium=test&v=10` | ✅ PASS (ignored) |
| 7.5 | Multiple ignored | All combined | ✅ PASS (all ignored) |

### Full List of Ignored Parameters

| Parameter | Reason |
|-----------|--------|
| `viewport` | Map view coordinates - UI state |
| `no-outline` | Map rendering - visual preference |
| `redirect` | Internal routing |
| `map_zoom` | Map zoom level - UI state |
| `zoomLevel` | Alternative zoom parameter |
| `v` | Version/A/B testing |
| `utm_source` | Marketing tracking |
| `utm_medium` | Marketing tracking |
| `utm_content` | Marketing tracking |
| `utm_campaign` | Marketing tracking |
| `android_merchant_id` | Mobile app tracking |
| `myapp_param` | Custom app tracking |
| `referrer` | Referral tracking |
| `sort` | Display order (not search criteria) |

---

## Category 8: Rental vs For Sale (4 tests)

### Purpose
Verifies that rental listings are distinguished from for-sale listings.

### Why This Matters
Redfin has separate URL patterns for rentals:
- `/apartments-for-rent/filter/...`
- `/rentals/filter/...`

A rental search should NOT match a for-sale search, even if all other filters are identical.

### Test Cases

| Test ID | Description | URL Type | Result |
|---------|-------------|----------|--------|
| 8.1 | Rental exact match | `/apartments-for-rent/` | ✅ PASS |
| 8.2 | Rental different city ID | Different ID | ✅ PASS |
| 8.3 | Rental vs sale mismatch | Rental GT, sale agent | ✅ FAIL (correct) |
| 8.4 | /rentals path format | `/rentals/` | ✅ PASS |

### Implementation Detail
```python
if '/rentals' in path or '/apartments-for-rent' in path:
    result["is_rental"] = True

# Comparison
if agent_parts["is_rental"] != gt_parts["is_rental"]:
    return False  # Mismatch!
```

---

## Category 9: Neighborhood URLs (3 tests)

### Purpose
Verifies that neighborhood URLs are parsed and compared correctly.

### Why This Matters
Redfin supports neighborhood-level searches with URLs like:
```
/neighborhood/219261/NY/New-York/Long-Island/filter/...
```

These have a different structure from city URLs and should not match city searches.

### Test Cases

| Test ID | Description | Scenario | Result |
|---------|-------------|----------|--------|
| 9.1 | Neighborhood exact match | Same neighborhood | ✅ PASS |
| 9.2 | Neighborhood different ID | ID 111111 vs 219261 | ✅ PASS |
| 9.3 | Neighborhood vs city mismatch | Neighborhood GT, city agent | ✅ FAIL (correct) |

### Implementation Detail
```python
# Neighborhood pattern
neighborhood_match = re.search(r'/neighborhood/\d+/([^/]+)/([^/]+)/([^/]+)', path)

if neighborhood_match:
    result["location_type"] = "neighborhood"
    result["state"] = neighborhood_match.group(1)
    city = neighborhood_match.group(2)
    neighborhood = neighborhood_match.group(3)
    result["location"] = f"{city}/{neighborhood}"  # Combined
```

---

## Category 10: Square Footage (4 tests)

### Purpose
Verifies that square footage values are normalized correctly.

### Why This Matters
Redfin supports multiple sqft formats:
- Plain numbers: `1500`
- Thousands: `1.5k`, `3k`
- With suffix: `1500-sqft`
- Combined: `1.5k-sqft`

### Test Cases

| Test ID | Description | Input | Normalized | Result |
|---------|-------------|-------|------------|--------|
| 10.1 | Plain number | `min-sqft=1500,max-sqft=3000` | `1500`, `3000` | ✅ PASS |
| 10.2 | K abbreviation | `max-sqft=3k` | `3000` | ✅ PASS |
| 10.3 | -sqft suffix | `min-sqft=1500-sqft` | `1500` | ✅ PASS |
| 10.4 | Wrong sqft value | Different value | | ✅ FAIL (correct) |

### Implementation Detail
```python
if "sqft" in param or "lot-size" in param:
    value = value.replace("-sqft", "").replace("sqft", "")
    
    if value.endswith("k"):
        num = float(value[:-1])
        return str(int(num * 1000))  # 1.5k → 1500
```

---

## Category 11: Stories Consolidation (5 tests)

### Purpose
Verifies that story-related filters are consolidated correctly.

### Why This Matters
When searching for exact story counts, Redfin may use:
- `min-stories=2,max-stories=2` (explicit range)
- `max-stories=2` alone (implied exact)

These should be treated equivalently.

### Test Cases

| Test ID | Description | Input | Consolidated | Result |
|---------|-------------|-------|--------------|--------|
| 11.1 | min=max consolidation | `min-stories=2,max-stories=2` | `stories=2` | ✅ PASS |
| 11.2 | Only max-stories | `max-stories=1` | `stories=1` | ✅ PASS |
| 11.3 | num-stories alias | `num-stories=1` | varies | ✅ PASS |
| 11.4 | Different range | `min=1,max=3` vs `min=2,max=2` | | ✅ FAIL (correct) |
| 11.5 | Range vs exact | `min=1,max=2` vs `min=2,max=2` | | ✅ FAIL (correct) |

### Consolidation Rules

| Scenario | Input | Consolidated Output |
|----------|-------|---------------------|
| min == max | `min-stories=2,max-stories=2` | `{"stories": "2"}` |
| max only | `max-stories=1` | `{"stories": "1"}` |
| min only | `min-stories=2` | `{"min-stories": "2"}` |
| Different min/max | `min-stories=1,max-stories=3` | `{"num-stories-min": "1", "num-stories-max": "3"}` |

---

## Category 12: Multi-Value Filters (5 tests)

### Purpose
Verifies that multi-value filters are compared correctly with order independence.

### Why This Matters
Redfin allows selecting multiple property types:
```
property-type=house+condo+townhouse
```

The order shouldn't matter: `house+condo` should equal `condo+house`.

### Test Cases

| Test ID | Description | Agent Input | GT | Result |
|---------|-------------|-------------|-----|--------|
| 12.1 | Exact match | `house+condo` | `house+condo` | ✅ PASS |
| 12.2 | Reversed order | `condo+house` | `house+condo` | ✅ PASS |
| 12.3 | Subset (missing) | `house` | `house+condo` | ✅ FAIL (correct) |
| 12.4 | Superset (extra) | `house+condo+townhouse` | `house+condo` | ✅ FAIL (correct) |
| 12.5 | Three values | `townhouse+house+condo` | `house+condo+townhouse` | ✅ PASS |

### Implementation Detail
```python
if "+" in value:
    value_parts = value.split("+")
    normalized_parts = [self._normalize_param_value(key, v) for v in value_parts]
    normalized_parts = list(set(normalized_parts))  # Deduplicate
    result["filters"][key] = tuple(sorted(normalized_parts))  # Sorted tuple
```

---

## Category 13: Beds/Baths Consolidation (4 tests)

### Purpose
Verifies that `beds` and `baths` shorthand filters are expanded correctly.

### Why This Matters
Redfin allows:
- `beds=3` (shorthand for exact 3 beds)
- `min-beds=3,max-beds=3` (explicit range)

These should match each other.

### Test Cases

| Test ID | Description | Input | Expanded | Result |
|---------|-------------|-------|----------|--------|
| 13.1 | beds shorthand | `beds=3` | `min-beds=3,max-beds=3` | ✅ PASS |
| 13.2 | baths shorthand | `baths=2` | `min-baths=2,max-baths=2` | ✅ PASS |
| 13.3 | Fractional baths | `min-baths=1.5` | `1.5` | ✅ PASS |
| 13.4 | Different beds | `beds=4` vs `min-beds=3,max-beds=3` | | ✅ FAIL (correct) |

### Implementation Detail
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

---

## Category 14: Include Filters (3 tests)

### Purpose
Verifies that `include` filters are compared correctly.

### Why This Matters
Redfin's `include` filter adds additional listing types to search results:
- `include=sold-3mo` - Include recently sold
- `include=construction` - Include new construction

These are meaningful search criteria that should be matched exactly.

### Test Cases

| Test ID | Description | Scenario | Result |
|---------|-------------|----------|--------|
| 14.1 | Exact include match | `include=sold-3mo` | ✅ PASS |
| 14.2 | Different include value | `sold-1yr` vs `sold-3mo` | ✅ FAIL (correct) |
| 14.3 | Missing include | No include vs `include=sold-3mo` | ✅ FAIL (correct) |

### Supported Include Values

| Value | Description |
|-------|-------------|
| `sold-1mo` | Sold in last month |
| `sold-3mo` | Sold in last 3 months |
| `sold-6mo` | Sold in last 6 months |
| `sold-1yr` | Sold in last year |
| `sold-2yr` | Sold in last 2 years |
| `sold-3yr` | Sold in last 3 years |
| `sold-5yr` | Sold in last 5 years |
| `construction` | New construction |

---

## Category 15: Time on Market (4 tests)

### Purpose
Verifies that time values are normalized correctly.

### Why This Matters
Redfin uses different time formats:
- Weeks: `1wk`, `2wk`
- Months: `1mo`, `3mo`
- Days: `7days`, `30days`

These should be normalized to a common format for comparison.

### Test Cases

| Test ID | Description | Input | Normalized | Result |
|---------|-------------|-------|------------|--------|
| 15.1 | 1wk = 7days | `time-on-market=1wk` | `7days` | ✅ PASS |
| 15.2 | 1mo = 30days | `time-on-market=1mo` | `30days` | ✅ PASS |
| 15.3 | max-days alias | `max-days-on-market=1wk` | `time-on-market=7days` | ✅ PASS |
| 15.4 | Wrong time | `1mo` vs `1wk` | | ✅ FAIL (correct) |

### Time Normalization Table

| Input | Normalized Output |
|-------|-------------------|
| `1wk` | `7days` |
| `2wk` | `14days` |
| `3wk` | `21days` |
| `4wk` | `28days` |
| `1mo` | `30days` |
| `2mo` | `60days` |
| `3mo` | `90days` |
| `6mo` | `180days` |
| `1yr` | `365days` |

---

## Category 16: Boundary Cases (4 tests)

### Purpose
Verifies handling of edge boundary conditions.

### Why This Matters
The verifier should handle malformed or minimal input gracefully:
- Empty URLs
- URLs without filters
- Whitespace
- Trailing slashes

### Test Cases

| Test ID | Description | Input | Result |
|---------|-------------|-------|--------|
| 16.1 | Empty URL | `""` | ✅ FAIL (correct) |
| 16.2 | Base path only | `/city/1387/WA/Bellevue` (no filters) | ✅ FAIL (correct) |
| 16.3 | Whitespace | `  https://...  ` | ✅ PASS (trimmed) |
| 16.4 | Trailing slash | `https://.../filter/.../` | ✅ PASS (stripped) |

### Implementation Detail
```python
url = url.lower().strip()  # Handle whitespace
path = parsed.path.rstrip("/")  # Handle trailing slashes

if not url:
    logger.debug("Empty URL provided")
    return  # No match possible
```

---

## Summary Table

| Category | Tests | Description | Pass Rate |
|----------|-------|-------------|-----------|
| 1. Filter Order | 4 | Order-independent comparison | 100% |
| 2. City ID | 3 | ID ignored, name matched | 100% |
| 3. Price | 5 | 2m, 2000k, commas | 100% |
| 4. Param Aliases | 4 | 40+ alias normalizations | 100% |
| 5. Case | 4 | Case-insensitive | 100% |
| 6. Protocol | 3 | http/https, www | 100% |
| 7. Ignored | 5 | viewport, sort, utm | 100% |
| 8. Rental | 4 | apartments-for-rent, rentals | 100% |
| 9. Neighborhood | 3 | /neighborhood/ vs /city/ | 100% |
| 10. Sqft | 4 | k suffix, -sqft | 100% |
| 11. Stories | 5 | min=max consolidation | 100% |
| 12. Multi-Value | 5 | house+condo order | 100% |
| 13. Beds/Baths | 4 | beds=3 expansion | 100% |
| 14. Include | 3 | sold-3mo, construction | 100% |
| 15. Time | 4 | 1wk=7days conversion | 100% |
| 16. Boundary | 4 | Empty, whitespace | 100% |
| **TOTAL** | **64** | | **100%** ✅ |

---

## Running the Tests

```bash
cd /path/to/redfin
python3 navi_bench/redfin/redfin_url_match.py
```

Expected output: All 64 tests passing with 100% success rate.

---

**Last Updated**: 2026-01-03  
**Test Suite Version**: 2.0
