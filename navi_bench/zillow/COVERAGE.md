# Zillow Filter Coverage Documentation

## Overview

This document catalogs all filters available on Zillow with **actual JSON examples** as they appear in the `searchQueryState` URL parameter.

---

## IMPORTANT: Value Format Rules

Zillow uses **TWO different JSON formats** depending on the filter type:

### Format 1: Boolean Filters (On/Off toggles)
```json
{
  "filterState": {
    "hasPool": {"value": true},
    "isHouse": {"value": true},
    "singleStory": {"value": true}
  }
}
```

### Format 2: Range Filters (Min/Max numbers)
```json
{
  "filterState": {
    "price": {"min": 300000, "max": 500000},
    "beds": {"min": 3},
    "sqft": {"min": 1500, "max": 3000}
  }
}
```

> **Range filters use `{"min": X}` directly, NOT `{"min": {"value": X}}`**

---

## 1. SEARCH MODE & LOCATION

### Search Type
**Location**: URL path (not in searchQueryState)

| Type | URL Path |
|------|----------|
| For Sale | `/homes/for_sale/` |
| For Rent | `/homes/for_rent/` |
| Recently Sold | `/homes/recently_sold/` |

### Location & Region
```json
{
  "usersSearchTerm": "Los Angeles CA",
  "regionSelection": [
    {"regionId": 12447, "regionType": 6}
  ]
}
```

| Region Type | Meaning |
|-------------|---------|
| 6 | City |
| 7 | ZIP Code |
| 8 | Neighborhood |

---

## 2. PRICE

### Example: Price Range $300,000 - $500,000
```json
{
  "filterState": {
    "price": {"min": 300000, "max": 500000}
  }
}
```

### Example: Minimum Price Only
```json
{
  "filterState": {
    "price": {"min": 500000}
  }
}
```

### Example: Maximum Price Only
```json
{
  "filterState": {
    "price": {"max": 1000000}
  }
}
```

### Monthly Payment Filter
```json
{
  "filterState": {
    "monthlyPayment": {"min": 2000, "max": 4000}
  }
}
```

---

## 3. BEDS & BATHS

### Example: 3+ Bedrooms
```json
{
  "filterState": {
    "beds": {"min": 3}
  }
}
```

### Example: Exactly 4 Bedrooms
```json
{
  "filterState": {
    "beds": {"min": 4, "max": 4}
  }
}
```

### Example: 2+ Bathrooms
```json
{
  "filterState": {
    "baths": {"min": 2}
  }
}
```

### Example: 3+ Beds AND 2+ Baths
```json
{
  "filterState": {
    "beds": {"min": 3},
    "baths": {"min": 2}
  }
}
```

---

## 4. HOME/PROPERTY TYPE

Zillow uses **two different encoding systems** for property types depending on context:

> **IMPORTANT**: The verifier normalizes both forms to the same canonical keys (e.g., `ishouse`, `istownhouse`), so ground truth and agent URLs will match regardless of encoding style.

### Encoding 1: Positive (Ground Truth Style)

Explicitly states which types are selected:

```json
{
  "filterState": {
    "isHouse": {"value": true}
  }
}
```

### Encoding 2: Negative (Live Browser Style)

The **real Zillow website** uses negative encoding: it sets all NON-selected types to `false`. For example, selecting **Houses only** in the UI produces:

```json
{
  "filterState": {
    "tow": {"value": false},
    "mf":  {"value": false},
    "land":{"value": false},
    "con": {"value": false},
    "apa": {"value": false},
    "apco":{"value": false},
    "manu":{"value": false}
  }
}
```

**How it works**: All 7 property types exist. When all non-House types are false, only Houses remain selected.

### Negative Encoding Examples

| UI Selection | Keys Set to `false` | Inferred Result |
|-------------|---------------------|------------------|
| Houses only | tow, mf, land, con, apa, apco, manu | `ishouse: true` |
| Houses + Townhomes | mf, land, con, apa, apco, manu | `ishouse: true, istownhouse: true` |
| Condos only | sf, tow, mf, land, apa, apco, manu | `iscondo: true` |
| Manufactured only | sf, tow, mf, land, con, apa, apco | `ismanufactured: true` |
| All types (default) | *(no property filters in URL)* | *(no property type filters)* |

### Example: Multiple Property Types (Positive)
```json
{
  "filterState": {
    "isHouse": {"value": true},
    "isTownhouse": {"value": true},
    "isCondo": {"value": true}
  }
}
```

### Abbreviated Keys Reference

| Property Type | Full Key (Canonical) | Abbreviated Key | Notes |
|---------------|---------------------|-----------------|-------|
| Houses | `isHouse` | `sf` | Single-family |
| Townhomes | `isTownhouse` | `tow` | |
| Multi-family | `isMultiFamily` | `mf` | |
| Condos/Co-ops | `isCondo` | `con` | |
| Apartments | `isApartment` | `apa`, `apco` | `apco` = Apartment Community |
| Lots/Land | `isLotLand` | `land` | |
| Manufactured | `isManufactured` | `manu` | |

---

## 5. LISTING TYPE & STATUS

### Example: New Construction Only
```json
{
  "filterState": {
    "isNewConstruction": {"value": true}
  }
}
```

### Example: Foreclosures
```json
{
  "filterState": {
    "isForeclosure": {"value": true}
  }
}
```

### All Listing Status Keys

| Filter | JSON Key |
|--------|----------|
| By Agent | `isForSaleByAgent` |
| By Owner (FSBO) | `isForSaleByOwner` |
| New Construction | `isNewConstruction` |
| Foreclosures | `isForeclosure` |
| Pre-Foreclosures | `isPreForeclosure` |
| Auctions | `isAuction` |
| Coming Soon | `isComingSoon` |
| Pending/Under Contract | `isPendingListings` |
| Accepting Backup Offers | `isAcceptingBackupOffers` |

> All use the format: `{"keyName": {"value": true}}`

---

## 6. SIZE & DIMENSIONS

### Example: 1500-3000 Square Feet
```json
{
  "filterState": {
    "sqft": {"min": 1500, "max": 3000}
  }
}
```

### Example: Lot Size Range
```json
{
  "filterState": {
    "lotSize": {"min": 5000, "max": 20000}
  }
}
```

---

## 7. YEAR BUILT

### Example: Built After 2000
```json
{
  "filterState": {
    "built": {"min": 2000}
  }
}
```

### Example: Built Between 1990-2010
```json
{
  "filterState": {
    "built": {"min": 1990, "max": 2010}
  }
}
```

---

## 8. PARKING

### Example: 2+ Parking Spots
```json
{
  "filterState": {
    "parking": {"min": 2}
  }
}
```

### Example: Must Have Garage
```json
{
  "filterState": {
    "hasGarage": {"value": true}
  }
}
```

---

## 9. BUILDING FEATURES

### Example: Single Story with A/C
```json
{
  "filterState": {
    "singleStory": {"value": true},
    "hasCooling": {"value": true}
  }
}
```

### Example: Has Fireplace
```json
{
  "filterState": {
    "hasFireplace": {"value": true}
  }
}
```

### All Building Feature Keys

| Filter | JSON Key |
|--------|----------|
| Single Story Only | `singleStory` |
| Has Basement | `hasBasement` |
| Must Have A/C | `hasCooling` |
| Hardwood Floors | `hasHardwoodFloors` |
| Fireplace | `hasFireplace` |
| Accessible/Disabled Access | `isAccessible` |

> All use the format: `{"keyName": {"value": true}}`

---

## 10. EXTERIOR FEATURES & VIEWS

### Example: Must Have Pool
```json
{
  "filterState": {
    "hasPool": {"value": true}
  }
}
```

### Example: Pool (Abbreviated Key)
```json
{
  "filterState": {
    "pool": {"value": true}
  }
}
```

### Example: Pool + Mountain View
```json
{
  "filterState": {
    "hasPool": {"value": true},
    "hasMountainView": {"value": true}
  }
}
```

### All Exterior/View Keys

| Filter | JSON Key |
|--------|----------|
| Must Have Pool | `hasPool` or `pool` |
| Waterfront | `isWaterfront` |
| Has View | `hasView` |
| City View | `hasCityView` |
| Mountain View | `hasMountainView` |
| Water View | `hasWaterView` |
| Park View | `hasParkView` |

---

## 11. HOA & FINANCIALS

### Example: Max HOA $500/month
```json
{
  "filterState": {
    "hoa": {"max": 500}
  }
}
```

### Example: No HOA
```json
{
  "filterState": {
    "noHoa": {"value": true}
  }
}
```

---

## 12. 55+ COMMUNITIES

### Example: Only Show 55+ Communities
```json
{
  "filterState": {
    "seniorHousing": {"value": "only"}
  }
}
```

| Option | Value |
|--------|-------|
| Include | `"include"` |
| Exclude | `"exclude"` |
| Only | `"only"` |

---

## 13. TOURS & MEDIA

### Example: Must Have 3D Tour
```json
{
  "filterState": {
    "has3DTour": {"value": true}
  }
}
```

| Filter | JSON Key | Abbreviated Key |
|--------|----------|--|
| Open House | `isOpenHouse` | |
| 3D Tour | `has3DTour` | `h3dt` |
| Showcase | `isShowcase` | |
| Instant Tour Available | `instantTourAvailable` | `ita` |

---

## 14. DAYS ON ZILLOW

### Example: Listed in Last 7 Days
```json
{
  "filterState": {
    "doz": {"value": "7"}
  }
}
```

| Days | Value |
|------|-------|
| 1 day | `"1"` |
| 7 days | `"7"` |
| 14 days | `"14"` |
| 30 days | `"30"` |
| 90 days | `"90"` |
| 6 months | `"6m"` |
| 12 months | `"12m"` |

---

## 15. KEYWORDS

### Example: Search for "granite counters"
```json
{
  "filterState": {
    "keywords": "granite counters"
  }
}
```

---

## 16. RENTAL-SPECIFIC FILTERS

### Example: Dogs Allowed
```json
{
  "filterState": {
    "dogsAllowed": {"value": true}
  }
}
```

### Example: In-Unit Laundry + Furnished
```json
{
  "filterState": {
    "laundryInUnit": {"value": true},
    "isFurnished": {"value": true}
  }
}
```

### Pet Policy Keys
| Filter | JSON Key |
|--------|----------|
| Large Dogs Allowed | `largeDogsAllowed` |
| Small Dogs Allowed | `smallDogsAllowed` |
| Cats Allowed | `catsAllowed` |
| Dogs Allowed (any) | `dogsAllowed` |
| No Pets | `noPets` |

### Laundry Keys
| Filter | JSON Key |
|--------|----------|
| In-Unit Laundry | `laundryInUnit` |
| Laundry in Building | `laundryInBuilding` |
| Washer/Dryer Hookups | `laundryHookup` |

### Other Rental Keys
| Filter | JSON Key |
|--------|----------|
| Furnished | `isFurnished` |
| Income Restricted | `isIncomeRestricted` |
| Utilities Included | `utilitiesIncluded` |
| Short Term Lease | `shortTermLease` |
| Accepts Zillow Applications | `app` |
| Outdoor Space | `os` |
| Controlled Access | `ca` |
| High-Speed Internet | `hsia` |
| Elevator | `eaa` |
| Apartment Community | `fmfb` |

### Move-in Date
```json
{
  "filterState": {
    "rad": {"value": "2026-03-01"}
  }
}
```
> Move-in date uses format `YYYY-MM-DD`

---

## 17. SOLD PROPERTIES

### Example: Sold in Last 30 Days
```json
{
  "filterState": {
    "soldInLast": {"value": "30d"}
  }
}
```

| Time Period | Value |
|-------------|-------|
| 1 day | `"1d"` |
| 7 days | `"7d"` |
| 30 days | `"30d"` |
| 90 days | `"90d"` |
| 6 months | `"6m"` |
| 12 months | `"12m"` |

---

## 18. SORT OPTIONS

> **Note**: The `sort` filter inside `filterState` is **auto-set** by Zillow and is ignored by the verifier. Only `sortSelection` at the top level represents intentional sorting.

### Example: Sort by Newest
```json
{
  "sortSelection": {"value": "days"}
}
```

| Sort Option | Value |
|-------------|-------|
| Homes for You | `globalrelevanceex` |
| Newest | `days` |
| Price (Low to High) | `pricea` |
| Price (High to Low) | `priced` |
| Bedrooms | `beds` |
| Bathrooms | `baths` |
| Square Feet | `size` |
| Lot Size | `lot` |

---

## 19. AUTO-COMPUTED / IGNORED FILTERS

These are automatically added by Zillow and **ignored by the verifier** during comparison:

| Filter | JSON Key | Reason |
|--------|----------|--------|
| Sort (in filterState) | `sort` | Auto-set default, not user intent |
| Monthly Payment | `mp` | Auto-computed from price |
| Pagination | `pagination` | Page number |
| Map Bounds | `mapBounds` | Viewport coordinates |
| Map Visible | `isMapVisible` | UI toggle |
| List Visible | `isListVisible` | UI toggle |
| Map Zoom | `mapZoom` | Zoom level |
| Custom Region ID | `customRegionId` | Internal region mapping |

---

## Complete Example URL

**Task**: Find houses in Los Angeles with 3+ beds, 2+ baths, $500k-$1M, with pool

```json
{
  "usersSearchTerm": "Los Angeles CA",
  "regionSelection": [{"regionId": 12447, "regionType": 6}],
  "filterState": {
    "price": {"min": 500000, "max": 1000000},
    "beds": {"min": 3},
    "baths": {"min": 2},
    "isHouse": {"value": true},
    "hasPool": {"value": true}
  },
  "sortSelection": {"value": "days"}
}
```

**Full URL**:
```
https://www.zillow.com/homes/for_sale/Los-Angeles,-CA_rb/?searchQueryState=%7B%22filterState%22%3A%7B%22price%22%3A%7B%22min%22%3A500000%2C%22max%22%3A1000000%7D%2C%22beds%22%3A%7B%22min%22%3A3%7D%2C%22baths%22%3A%7B%22min%22%3A2%7D%2C%22isHouse%22%3A%7B%22value%22%3Atrue%7D%2C%22hasPool%22%3A%7B%22value%22%3Atrue%7D%7D%7D
```

---

## Coverage Summary

| Category | Filters |
|----------|---------|
| Search Mode & Location | 5 |
| Price | 4 |
| Beds & Baths | 3 |
| Home/Property Type | 9 (+ negative encoding for all combos) |
| Listing Type & Status | 9 |
| Size & Dimensions | 4 |
| Year Built | 2 |
| Parking | 2 |
| Building Features | 6 |
| Exterior Features & Views | 8 |
| HOA & Financials | 2 |
| 55+ Communities | 3 |
| Tours & Media | 4 |
| Days on Zillow | 1 |
| Keywords | 1 |
| Rental-Specific | 25 |
| Sold Properties | 3 |
| Sort Options | 9 |
| Auto-Computed/Ignored | 8 |
| **TOTAL** | **108** |

---

## Quick Reference: Value Format Rules

| Filter Type | Format | Example |
|-------------|--------|---------|
| Boolean (on/off) | `{"key": {"value": true}}` | `{"hasPool": {"value": true}}` |
| Range (min/max) | `{"key": {"min": X, "max": Y}}` | `{"price": {"min": 300000}}` |
| String value | `{"key": {"value": "string"}}` | `{"doz": {"value": "30"}}` |
| Direct string | `{"key": "string"}` | `{"keywords": "pool"}` |
| Negative boolean | `{"key": {"value": false}}` | `{"tow": {"value": false}}` |

---

**Last Updated:** 2026-02-11
**Version:** 2.0.0 (added negative encoding, auto-computed filters)
**Test Suite:** 111/111 tests passing
