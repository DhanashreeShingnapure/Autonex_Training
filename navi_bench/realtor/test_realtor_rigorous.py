"""
RIGOROUS Realtor.com URL Verifier Test Suite
=============================================
Comprehensive tests across 25+ categories with extreme multi-filter
combinations. All URL patterns browser-verified against live Realtor.com.

This is a CLIENT-FACING verification — zero tolerance for failures.
"""
import csv
import json
import sys
import os
import traceback

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from navi_bench.realtor.realtor_url_match import RealtorUrlMatch

# ============================================================================
# HELPERS
# ============================================================================
R = "https://www.realtor.com/realestateandhomes-search"
A = "https://www.realtor.com/apartments"

def run_test(name, passed, details=""):
    status = "PASS" if passed else "FAIL"
    icon = "  " if passed else ">>"
    print(f"  {icon}[{status}] {name}")
    if not passed and details:
        print(f"          {details}")
    return passed

def match_test(name, gt_url, agent_url, expected=True):
    """Test if agent_url matches gt_url (or doesn't, if expected=False)."""
    v = RealtorUrlMatch(gt_url=gt_url)
    match, details = v._urls_match(agent_url, gt_url)
    detail = ""
    if match != expected:
        mismatches = details.get("mismatches", [])
        extra = details.get("extra_filters", [])
        detail = f"mismatches={mismatches}, extra={extra}"
    return run_test(name, match == expected, detail)


# ============================================================================
# TEST 1: CSV GROUND TRUTH SELF-MATCH
# ============================================================================
def test_csv_self_match():
    """Every CSV ground truth URL must match itself."""
    print("\n" + "=" * 70)
    print("TEST 1: CSV Ground Truth Self-Match")
    print("=" * 70)

    csv_path = os.path.join(os.path.dirname(__file__), "realtor_benchmark_tasks.csv")
    results = []
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tid = row["task_id"]
            cfg = json.loads(row["task_generation_config_json"])
            gt = cfg["ground_truth_url"]
            try:
                v = RealtorUrlMatch(gt_url=gt)
                ok, det = v._urls_match(gt, gt)
                detail = ""
                if not ok:
                    detail = f"Mismatches: {det.get('mismatches', [])}"
                results.append(run_test(f"[{tid}] self-match", ok, detail))
            except Exception as e:
                results.append(run_test(f"[{tid}] ERROR", False, str(e)))
    return results


# ============================================================================
# TEST 2: SEARCH TYPE DETECTION
# ============================================================================
def test_search_types():
    print("\n" + "=" * 70)
    print("TEST 2: Search Type Detection")
    print("=" * 70)
    r = []
    r.append(match_test("For sale search", f"{R}/San-Francisco_CA", f"{R}/San-Francisco_CA"))
    r.append(match_test("Rental search", f"{A}/San-Francisco_CA", f"{A}/San-Francisco_CA"))
    r.append(match_test("Sold homes search",
        "https://www.realtor.com/sold-homes/San-Francisco_CA",
        "https://www.realtor.com/sold-homes/San-Francisco_CA"))
    r.append(match_test("Open houses search",
        "https://www.realtor.com/open-houses/San-Francisco_CA",
        "https://www.realtor.com/open-houses/San-Francisco_CA"))
    r.append(match_test("Sale vs Rent NO MATCH", f"{R}/San-Francisco_CA", f"{A}/San-Francisco_CA", False))
    r.append(match_test("Sale vs Sold NO MATCH", f"{R}/San-Francisco_CA",
        "https://www.realtor.com/sold-homes/San-Francisco_CA", False))
    r.append(match_test("Rent vs Sold NO MATCH", f"{A}/San-Francisco_CA",
        "https://www.realtor.com/sold-homes/San-Francisco_CA", False))
    r.append(match_test("Sold vs Open houses NO MATCH",
        "https://www.realtor.com/sold-homes/San-Francisco_CA",
        "https://www.realtor.com/open-houses/San-Francisco_CA", False))
    return r


# ============================================================================
# TEST 3: LOCATION PARSING
# ============================================================================
def test_locations():
    print("\n" + "=" * 70)
    print("TEST 3: Location Parsing")
    print("=" * 70)
    r = []
    r.append(match_test("City/State", f"{R}/San-Francisco_CA", f"{R}/San-Francisco_CA"))
    r.append(match_test("Zip code", f"{R}/90210", f"{R}/90210"))
    r.append(match_test("Multi-word city", f"{R}/New-York_NY", f"{R}/New-York_NY"))
    r.append(match_test("Case insensitive", f"{R}/San-Francisco_CA", f"{R}/san-francisco_ca"))
    r.append(match_test("Wrong city NO MATCH", f"{R}/San-Francisco_CA", f"{R}/Los-Angeles_CA", False))
    r.append(match_test("Wrong zip NO MATCH", f"{R}/90210", f"{R}/10001", False))
    r.append(match_test("Wrong state NO MATCH", f"{R}/Portland_OR/beds-3", f"{R}/Portland_ME/beds-3", False))
    return r


# ============================================================================
# TEST 4: BASIC FILTERS (beds, baths, price)
# ============================================================================
def test_basic_filters():
    print("\n" + "=" * 70)
    print("TEST 4: Basic Filters (Beds, Baths, Price)")
    print("=" * 70)
    r = []
    r.append(match_test("3+ beds", f"{R}/SF_CA/beds-3", f"{R}/SF_CA/beds-3"))
    r.append(match_test("Beds range 3-4", f"{R}/SF_CA/beds-3-4", f"{R}/SF_CA/beds-3-4"))
    r.append(match_test("Wrong beds NO", f"{R}/SF_CA/beds-3", f"{R}/SF_CA/beds-4", False))
    r.append(match_test("Missing beds NO", f"{R}/SF_CA/beds-3", f"{R}/SF_CA", False))
    r.append(match_test("2+ baths", f"{R}/SF_CA/baths-2", f"{R}/SF_CA/baths-2"))
    r.append(match_test("Wrong baths NO", f"{R}/SF_CA/baths-2", f"{R}/SF_CA/baths-3", False))
    r.append(match_test("Price range", f"{R}/SF_CA/price-500000-1000000", f"{R}/SF_CA/price-500000-1000000"))
    r.append(match_test("Price na-min", f"{R}/SF_CA/price-na-500000", f"{R}/SF_CA/price-na-500000"))
    r.append(match_test("Price min-na", f"{R}/SF_CA/price-500000-na", f"{R}/SF_CA/price-500000-na"))
    r.append(match_test("Price 500k abbreviation", f"{R}/SF_CA/price-500000-1000000", f"{R}/SF_CA/price-500k-1m"))
    r.append(match_test("Price 2m abbreviation", f"{R}/SF_CA/price-na-2000000", f"{R}/SF_CA/price-na-2m"))
    r.append(match_test("Wrong price NO", f"{R}/SF_CA/price-500000-1000000", f"{R}/SF_CA/price-500000-2000000", False))
    return r


# ============================================================================
# TEST 5: PROPERTY TYPES + ALIASES
# ============================================================================
def test_property_types():
    print("\n" + "=" * 70)
    print("TEST 5: Property Types + Aliases")
    print("=" * 70)
    r = []
    r.append(match_test("Single family", f"{R}/SF_CA/type-single-family-home", f"{R}/SF_CA/type-single-family-home"))
    r.append(match_test("Condo", f"{R}/SF_CA/type-condo", f"{R}/SF_CA/type-condo"))
    r.append(match_test("Townhome", f"{R}/SF_CA/type-townhome", f"{R}/SF_CA/type-townhome"))
    r.append(match_test("Multi-family", f"{R}/SF_CA/type-multi-family-home", f"{R}/SF_CA/type-multi-family-home"))
    r.append(match_test("Land", f"{R}/SF_CA/type-land", f"{R}/SF_CA/type-land"))
    r.append(match_test("Farm", f"{R}/SF_CA/type-farm", f"{R}/SF_CA/type-farm"))
    r.append(match_test("Co-op", f"{R}/SF_CA/type-co-op", f"{R}/SF_CA/type-co-op"))
    r.append(match_test("Mobile home", f"{R}/SF_CA/type-mobile-home", f"{R}/SF_CA/type-mobile-home"))
    # Aliases
    r.append(match_test("Alias: house -> single-family-home", f"{R}/SF_CA/type-single-family-home", f"{R}/SF_CA/type-house"))
    r.append(match_test("Alias: townhouse -> townhome", f"{R}/SF_CA/type-townhome", f"{R}/SF_CA/type-townhouse"))
    r.append(match_test("Alias: ranch -> farm", f"{R}/SF_CA/type-farm", f"{R}/SF_CA/type-ranch"))
    r.append(match_test("Alias: manufactured -> mobile-home", f"{R}/SF_CA/type-mobile-home", f"{R}/SF_CA/type-manufactured"))
    r.append(match_test("Alias: cooperative -> co-op", f"{R}/SF_CA/type-co-op", f"{R}/SF_CA/type-cooperative"))
    r.append(match_test("Wrong type NO", f"{R}/SF_CA/type-condo", f"{R}/SF_CA/type-single-family-home", False))
    # Multi-type
    r.append(match_test("Multi-type condo+townhome", f"{R}/SF_CA/type-condo/type-townhome", f"{R}/SF_CA/type-condo/type-townhome"))
    r.append(match_test("Multi-type reversed order", f"{R}/SF_CA/type-condo/type-townhome", f"{R}/SF_CA/type-townhome/type-condo"))
    r.append(match_test("Multi-type with alias", f"{R}/SF_CA/type-single-family-home/type-condo", f"{R}/SF_CA/type-house/type-condo"))
    return r


# ============================================================================
# TEST 6: SHOW FLAGS
# ============================================================================
def test_show_flags():
    print("\n" + "=" * 70)
    print("TEST 6: Show Flags")
    print("=" * 70)
    r = []
    r.append(match_test("Show open house", f"{R}/SF_CA/show-open-house", f"{R}/SF_CA/show-open-house"))
    r.append(match_test("Show new construction", f"{R}/SF_CA/show-new-construction", f"{R}/SF_CA/show-new-construction"))
    r.append(match_test("Show price reduced", f"{R}/SF_CA/show-price-reduced", f"{R}/SF_CA/show-price-reduced"))
    r.append(match_test("Show foreclosure", f"{R}/SF_CA/show-foreclosure", f"{R}/SF_CA/show-foreclosure"))
    r.append(match_test("Show pending", f"{R}/SF_CA/show-pending", f"{R}/SF_CA/show-pending"))
    r.append(match_test("Show contingent", f"{R}/SF_CA/show-contingent", f"{R}/SF_CA/show-contingent"))
    r.append(match_test("Show 55-plus", f"{R}/SF_CA/show-55-plus", f"{R}/SF_CA/show-55-plus"))
    r.append(match_test("Show 3d-tours", f"{R}/SF_CA/show-3d-tours", f"{R}/SF_CA/show-3d-tours"))
    r.append(match_test("Show virtual-tours", f"{R}/SF_CA/show-virtual-tours", f"{R}/SF_CA/show-virtual-tours"))
    r.append(match_test("Missing show flag NO", f"{R}/SF_CA/show-open-house", f"{R}/SF_CA", False))
    r.append(match_test("Wrong show flag NO", f"{R}/SF_CA/show-open-house", f"{R}/SF_CA/show-foreclosure", False))
    return r


# ============================================================================
# TEST 7: ADVANCED FILTERS (sqft, lot, age, DOM, HOA, radius)
# ============================================================================
def test_advanced_filters():
    print("\n" + "=" * 70)
    print("TEST 7: Advanced Filters (sqft, lot, age, DOM, HOA, radius)")
    print("=" * 70)
    r = []
    r.append(match_test("Sqft range", f"{R}/SF_CA/sqft-2000-3000", f"{R}/SF_CA/sqft-2000-3000"))
    r.append(match_test("Sqft min only", f"{R}/SF_CA/sqft-2000", f"{R}/SF_CA/sqft-2000"))
    r.append(match_test("Wrong sqft NO", f"{R}/SF_CA/sqft-2000-3000", f"{R}/SF_CA/sqft-1000-2000", False))
    r.append(match_test("Lot size", f"{R}/SF_CA/lot-sqft-5000-10000", f"{R}/SF_CA/lot-sqft-5000-10000"))
    r.append(match_test("Wrong lot NO", f"{R}/SF_CA/lot-sqft-5000-10000", f"{R}/SF_CA/lot-sqft-1000-5000", False))
    r.append(match_test("Home age", f"{R}/SF_CA/age-0-10", f"{R}/SF_CA/age-0-10"))
    r.append(match_test("Year built", f"{R}/SF_CA/year-built-2000-2024", f"{R}/SF_CA/year-built-2000-2024"))
    r.append(match_test("Stories", f"{R}/SF_CA/stories-1", f"{R}/SF_CA/stories-1"))
    r.append(match_test("Garage", f"{R}/SF_CA/garage-2", f"{R}/SF_CA/garage-2"))
    r.append(match_test("HOA filter", f"{R}/SF_CA/hoa-na-500", f"{R}/SF_CA/hoa-na-500"))
    r.append(match_test("DOM 7 days", f"{R}/SF_CA/dom-7", f"{R}/SF_CA/dom-7"))
    r.append(match_test("Radius 25mi", f"{R}/SF_CA/radius-25", f"{R}/SF_CA/radius-25"))
    r.append(match_test("Sold within 30", f"{R}/SF_CA/show-recently-sold/sold-within-30",
                         f"{R}/SF_CA/show-recently-sold/sold-within-30"))
    return r


# ============================================================================
# TEST 8: FILTER ORDER INDEPENDENCE
# ============================================================================
def test_filter_order():
    print("\n" + "=" * 70)
    print("TEST 8: Filter Order Independence")
    print("=" * 70)
    r = []
    r.append(match_test("beds/price swapped",
        f"{R}/SF_CA/beds-3/price-500000-1000000",
        f"{R}/SF_CA/price-500000-1000000/beds-3"))
    r.append(match_test("4 filters reversed",
        f"{R}/SF_CA/beds-3/baths-2/price-500000-1000000/type-single-family-home",
        f"{R}/SF_CA/type-single-family-home/price-500000-1000000/baths-2/beds-3"))
    r.append(match_test("5 filters scrambled",
        f"{R}/SF_CA/beds-3/baths-2/price-na-500000/type-condo/show-open-house",
        f"{R}/SF_CA/show-open-house/type-condo/baths-2/beds-3/price-na-500000"))
    r.append(match_test("6 filters scrambled",
        f"{R}/SF_CA/beds-4/baths-3/price-500000-1000000/type-single-family-home/sqft-2000-3000/show-new-construction",
        f"{R}/SF_CA/show-new-construction/sqft-2000-3000/type-single-family-home/baths-3/price-500000-1000000/beds-4"))
    r.append(match_test("7 filters scrambled",
        f"{R}/SF_CA/beds-4/baths-3/price-500000-1000000/type-single-family-home/sqft-2000-3000/show-new-construction/hoa-na-500",
        f"{R}/SF_CA/hoa-na-500/show-new-construction/sqft-2000-3000/baths-3/type-single-family-home/price-500000-1000000/beds-4"))
    return r


# ============================================================================
# TEST 9: CASE SENSITIVITY + PROTOCOL VARIATIONS
# ============================================================================
def test_case_and_protocol():
    print("\n" + "=" * 70)
    print("TEST 9: Case Sensitivity + Protocol Variations")
    print("=" * 70)
    r = []
    r.append(match_test("ALL UPPERCASE", f"{R}/San-Francisco_CA/beds-3",
        "HTTPS://WWW.REALTOR.COM/REALESTATEANDHOMES-SEARCH/SAN-FRANCISCO_CA/BEDS-3"))
    r.append(match_test("Mixed case", f"{R}/San-Francisco_CA/beds-3",
        "https://www.Realtor.com/RealEstateAndHomes-Search/San-Francisco_CA/Beds-3"))
    r.append(match_test("HTTP vs HTTPS", f"{R}/San-Francisco_CA",
        "http://www.realtor.com/realestateandhomes-search/San-Francisco_CA"))
    r.append(match_test("Without www", f"{R}/San-Francisco_CA",
        "https://realtor.com/realestateandhomes-search/San-Francisco_CA"))
    return r


# ============================================================================
# TEST 10: SORT & PAGINATION IGNORED
# ============================================================================
def test_sort_pagination():
    print("\n" + "=" * 70)
    print("TEST 10: Sort & Pagination Ignored")
    print("=" * 70)
    r = []
    r.append(match_test("Sort ignored", f"{R}/SF_CA/beds-3", f"{R}/SF_CA/beds-3/sby-2"))
    r.append(match_test("Pagination ignored", f"{R}/SF_CA/beds-3", f"{R}/SF_CA/beds-3/pg-5"))
    r.append(match_test("Both ignored", f"{R}/SF_CA/beds-3", f"{R}/SF_CA/beds-3/sby-6/pg-3"))
    r.append(match_test("Sort+pagination with complex filters",
        f"{R}/SF_CA/beds-3/baths-2/price-na-1000000/type-condo",
        f"{R}/SF_CA/beds-3/baths-2/price-na-1000000/type-condo/sby-1/pg-10"))
    return r


# ============================================================================
# TEST 11: RECENTLY SOLD + OPEN HOUSE EQUIVALENCE
# ============================================================================
def test_equivalences():
    print("\n" + "=" * 70)
    print("TEST 11: Recently Sold + Open House Equivalence")
    print("=" * 70)
    r = []
    r.append(match_test("sold-homes -> show-recently-sold",
        "https://www.realtor.com/sold-homes/San-Francisco_CA",
        f"{R}/San-Francisco_CA/show-recently-sold"))
    r.append(match_test("show-recently-sold -> sold-homes",
        f"{R}/San-Francisco_CA/show-recently-sold",
        "https://www.realtor.com/sold-homes/San-Francisco_CA"))
    r.append(match_test("open-houses -> show-open-house",
        "https://www.realtor.com/open-houses/San-Francisco_CA",
        f"{R}/San-Francisco_CA/show-open-house"))
    r.append(match_test("show-open-house -> open-houses",
        f"{R}/San-Francisco_CA/show-open-house",
        "https://www.realtor.com/open-houses/San-Francisco_CA"))
    r.append(match_test("open-houses + extra filters (agent has beds)",
        "https://www.realtor.com/open-houses/San-Francisco_CA",
        f"{R}/San-Francisco_CA/show-open-house/beds-3"))
    return r


# ============================================================================
# TEST 12: RENTAL PATH ALIASES
# ============================================================================
def test_rental_aliases():
    print("\n" + "=" * 70)
    print("TEST 12: Rental Path Aliases")
    print("=" * 70)
    r = []
    r.append(match_test("rentals alias", f"{A}/SF_CA", "https://www.realtor.com/rentals/SF_CA"))
    r.append(match_test("houses-for-rent alias", f"{A}/SF_CA", "https://www.realtor.com/houses-for-rent/SF_CA"))
    r.append(match_test("apartments-for-rent alias", f"{A}/SF_CA", "https://www.realtor.com/apartments-for-rent/SF_CA"))
    return r


# ============================================================================
# TEST 13: EXTRA FILTERS ALLOWED
# ============================================================================
def test_extra_filters():
    print("\n" + "=" * 70)
    print("TEST 13: Extra Filters Allowed (Agent has MORE filters than GT)")
    print("=" * 70)
    r = []
    r.append(match_test("Agent has extra beds", f"{R}/SF_CA/price-500000-1000000",
        f"{R}/SF_CA/price-500000-1000000/beds-3"))
    r.append(match_test("Agent has extra show flag", f"{R}/SF_CA/beds-3",
        f"{R}/SF_CA/beds-3/show-open-house"))
    r.append(match_test("Agent has extra type", f"{R}/SF_CA/beds-3/price-na-1000000",
        f"{R}/SF_CA/beds-3/price-na-1000000/type-condo"))
    r.append(match_test("Agent has extra sqft", f"{R}/SF_CA/beds-3/price-na-1000000/type-condo",
        f"{R}/SF_CA/beds-3/price-na-1000000/type-condo/sqft-1000-2000"))
    r.append(match_test("Agent has extra sort+pg", f"{R}/SF_CA/beds-3",
        f"{R}/SF_CA/beds-3/sby-6/pg-2"))
    return r


# ============================================================================
# TEST 14: RENTAL SPECIFIC FILTERS (pets, amenities)
# ============================================================================
def test_rental_filters():
    print("\n" + "=" * 70)
    print("TEST 14: Rental Specific Filters (Pets, Amenities)")
    print("=" * 70)
    r = []
    r.append(match_test("Dog-friendly", f"{A}/SF_CA/dog-friendly", f"{A}/SF_CA/dog-friendly"))
    r.append(match_test("Cat-friendly", f"{A}/SF_CA/cat-friendly", f"{A}/SF_CA/cat-friendly"))
    r.append(match_test("Both pets", f"{A}/SF_CA/dog-friendly/cat-friendly",
        f"{A}/SF_CA/dog-friendly/cat-friendly"))
    r.append(match_test("Both pets reversed order", f"{A}/SF_CA/dog-friendly/cat-friendly",
        f"{A}/SF_CA/cat-friendly/dog-friendly"))
    r.append(match_test("In-unit laundry", f"{A}/SF_CA/with_inunitlaundry",
        f"{A}/SF_CA/with_inunitlaundry"))
    r.append(match_test("Pool (features-cs)", f"{A}/SF_CA/features-cs", f"{A}/SF_CA/features-cs"))
    r.append(match_test("Gym (features-gy)", f"{A}/SF_CA/features-gy", f"{A}/SF_CA/features-gy"))
    r.append(match_test("Wrong pet NO", f"{A}/SF_CA/dog-friendly", f"{A}/SF_CA/cat-friendly", False))
    r.append(match_test("Missing pet NO", f"{A}/SF_CA/dog-friendly", f"{A}/SF_CA", False))
    return r


# ============================================================================
# TEST 15: QUERY PARAMETERS IGNORED (map view, layers, schools, etc.)
# ============================================================================
def test_query_params_ignored():
    print("\n" + "=" * 70)
    print("TEST 15: Query Parameters Ignored (Map View, Layers, Schools)")
    print("=" * 70)
    gt = f"{R}/San-Francisco_CA/beds-3/price-na-1000000"
    r = []
    r.append(match_test("Map view param",
        gt, gt + "?view=map&pos=37.89,-122.55,37.73,-122.26,11.88"))
    r.append(match_test("Map + Flood layer",
        gt, gt + "?view=map&layer=Flood&pos=37.8,-122.5,37.7,-122.2,12"))
    r.append(match_test("Map + Schools",
        gt, gt + "?view=map&schools_pin=true&schools_options=school-elementary"))
    r.append(match_test("Map + Amenities",
        gt, gt + "?view=map&amenities_pin=true&neighborhood_pin=true"))
    r.append(match_test("All query params at once",
        gt, gt + "?view=map&layer=Estimate&pos=37.8,-122.5,37.7,-122.2,12&schools_pin=true&amenities_pin=true"))
    return r


# ============================================================================
# TEST 16: EXTREME MULTI-FILTER COMBOS (5-7 filters) — POSITIVE
# ============================================================================
def test_extreme_positive():
    print("\n" + "=" * 70)
    print("TEST 16: EXTREME Multi-Filter Combos (5-7 filters) - Positive")
    print("=" * 70)
    r = []

    # 5 filters
    r.append(match_test("5F: beds+baths+price+type+show",
        f"{R}/Dallas_TX/beds-4/baths-3/price-500000-1000000/type-single-family-home/show-new-construction",
        f"{R}/Dallas_TX/beds-4/baths-3/price-500000-1000000/type-single-family-home/show-new-construction"))

    # 5 filters scrambled
    r.append(match_test("5F scrambled: show+type+price+baths+beds",
        f"{R}/Dallas_TX/beds-4/baths-3/price-500000-1000000/type-single-family-home/show-new-construction",
        f"{R}/Dallas_TX/show-new-construction/type-single-family-home/price-500000-1000000/baths-3/beds-4"))

    # 6 filters
    r.append(match_test("6F: beds+baths+price+type+sqft+show",
        f"{R}/Seattle_WA/beds-3/baths-2/price-na-900000/type-single-family-home/sqft-2000-3000/show-open-house",
        f"{R}/Seattle_WA/beds-3/baths-2/price-na-900000/type-single-family-home/sqft-2000-3000/show-open-house"))

    # 6 filters with HOA
    r.append(match_test("6F: type+hoa+beds+baths+price+dom",
        f"{R}/San-Francisco_CA/type-condo/hoa-na-500/beds-2/baths-1/price-na-1200000/dom-14",
        f"{R}/San-Francisco_CA/type-condo/hoa-na-500/beds-2/baths-1/price-na-1200000/dom-14"))

    # 6 filters with lot
    r.append(match_test("6F: show+type+beds+baths+price+lot",
        f"{R}/Phoenix_AZ/show-foreclosure/type-single-family-home/beds-3/baths-2/price-na-400000/lot-sqft-5000-na",
        f"{R}/Phoenix_AZ/show-foreclosure/type-single-family-home/beds-3/baths-2/price-na-400000/lot-sqft-5000-na"))

    # 7 filters
    r.append(match_test("7F: show+type+beds+baths+price+sqft+hoa",
        f"{R}/Miami_FL/show-new-construction/type-condo/beds-2/baths-2/price-na-800000/sqft-1000-2000/hoa-na-600",
        f"{R}/Miami_FL/show-new-construction/type-condo/beds-2/baths-2/price-na-800000/sqft-1000-2000/hoa-na-600"))

    # 7 filters with age
    r.append(match_test("7F: type+age+beds+baths+price+sqft+dom",
        f"{R}/Denver_CO/type-single-family-home/age-0-5/beds-4/baths-3/price-500000-900000/sqft-2500-na/dom-7",
        f"{R}/Denver_CO/type-single-family-home/age-0-5/beds-4/baths-3/price-500000-900000/sqft-2500-na/dom-7"))

    # 7 filters all scrambled
    r.append(match_test("7F fully scrambled order",
        f"{R}/Denver_CO/type-single-family-home/age-0-5/beds-4/baths-3/price-500000-900000/sqft-2500-na/dom-7",
        f"{R}/Denver_CO/dom-7/sqft-2500-na/price-500000-900000/baths-3/beds-4/age-0-5/type-single-family-home"))

    # 6 filters with price abbreviations
    r.append(match_test("6F with price abbreviations (500k, 1m)",
        f"{R}/Los-Angeles_CA/beds-3/baths-2/price-500000-1000000/type-single-family-home/sqft-1500-na/show-price-reduced",
        f"{R}/Los-Angeles_CA/beds-3/baths-2/price-500k-1m/type-house/sqft-1500-na/show-price-reduced"))

    # 6 filters with type alias
    r.append(match_test("6F with type alias (house -> single-family-home)",
        f"{R}/Austin_TX/type-single-family-home/beds-3/baths-2/price-na-600000/sqft-1500-3000/dom-3",
        f"{R}/Austin_TX/type-house/beds-3/baths-2/price-na-600000/sqft-1500-3000/dom-3"))

    return r


# ============================================================================
# TEST 17: EXTREME MULTI-FILTER COMBOS — NEGATIVE (must NOT match)
# ============================================================================
def test_extreme_negative():
    print("\n" + "=" * 70)
    print("TEST 17: EXTREME Multi-Filter Combos - Negative (must NOT match)")
    print("=" * 70)
    r = []

    # Same 6 filters but ONE price value is wrong
    r.append(match_test("6F price mismatch",
        f"{R}/Seattle_WA/beds-3/baths-2/price-na-900000/type-single-family-home/sqft-2000-3000/show-open-house",
        f"{R}/Seattle_WA/beds-3/baths-2/price-na-800000/type-single-family-home/sqft-2000-3000/show-open-house",
        False))

    # Same 6 filters but type is different
    r.append(match_test("6F type mismatch",
        f"{R}/Seattle_WA/beds-3/baths-2/price-na-900000/type-single-family-home/sqft-2000-3000/show-open-house",
        f"{R}/Seattle_WA/beds-3/baths-2/price-na-900000/type-condo/sqft-2000-3000/show-open-house",
        False))

    # Same 6 filters but show flag is different
    r.append(match_test("6F show flag mismatch",
        f"{R}/Seattle_WA/beds-3/baths-2/price-na-900000/type-single-family-home/sqft-2000-3000/show-open-house",
        f"{R}/Seattle_WA/beds-3/baths-2/price-na-900000/type-single-family-home/sqft-2000-3000/show-foreclosure",
        False))

    # Same 7 filters but beds is wrong
    r.append(match_test("7F beds mismatch",
        f"{R}/Denver_CO/type-single-family-home/age-0-5/beds-4/baths-3/price-500000-900000/sqft-2500-na/dom-7",
        f"{R}/Denver_CO/type-single-family-home/age-0-5/beds-3/baths-3/price-500000-900000/sqft-2500-na/dom-7",
        False))

    # Same 7 filters but location is wrong
    r.append(match_test("7F location mismatch",
        f"{R}/Denver_CO/type-single-family-home/age-0-5/beds-4/baths-3/price-500000-900000/sqft-2500-na/dom-7",
        f"{R}/Austin_TX/type-single-family-home/age-0-5/beds-4/baths-3/price-500000-900000/sqft-2500-na/dom-7",
        False))

    # Same 7 filters but search type is wrong (sale vs rent)
    r.append(match_test("7F search type mismatch (sale vs rent)",
        f"{R}/Denver_CO/beds-4/baths-3/price-500000-900000/type-single-family-home/sqft-2500-na",
        f"{A}/Denver_CO/beds-4/baths-3/price-500000-900000",
        False))

    # Agent missing one GT filter from 6
    r.append(match_test("6F agent missing sqft filter",
        f"{R}/Seattle_WA/beds-3/baths-2/price-na-900000/type-single-family-home/sqft-2000-3000/show-open-house",
        f"{R}/Seattle_WA/beds-3/baths-2/price-na-900000/type-single-family-home/show-open-house",
        False))

    # Agent missing two GT filters
    r.append(match_test("6F agent missing sqft+show",
        f"{R}/Seattle_WA/beds-3/baths-2/price-na-900000/type-single-family-home/sqft-2000-3000/show-open-house",
        f"{R}/Seattle_WA/beds-3/baths-2/price-na-900000/type-single-family-home",
        False))

    return r


# ============================================================================
# TEST 18: EXTREME RENTAL COMBOS
# ============================================================================
def test_extreme_rental():
    print("\n" + "=" * 70)
    print("TEST 18: EXTREME Rental Multi-Filter Combos")
    print("=" * 70)
    r = []

    # 5 rental filters
    r.append(match_test("5F rental: dog+beds+baths+laundry+price",
        f"{A}/San-Francisco_CA/dog-friendly/beds-2/baths-1/with_inunitlaundry/price-na-4000",
        f"{A}/San-Francisco_CA/dog-friendly/beds-2/baths-1/with_inunitlaundry/price-na-4000"))

    # 5 rental scrambled
    r.append(match_test("5F rental scrambled",
        f"{A}/San-Francisco_CA/dog-friendly/beds-2/baths-1/with_inunitlaundry/price-na-4000",
        f"{A}/San-Francisco_CA/price-na-4000/with_inunitlaundry/baths-1/beds-2/dog-friendly"))

    # 6 rental filters
    r.append(match_test("6F rental: cat+pool+beds+baths+price range",
        f"{A}/Los-Angeles_CA/cat-friendly/features-cs/beds-2/baths-2/price-2000-4000",
        f"{A}/Los-Angeles_CA/cat-friendly/features-cs/beds-2/baths-2/price-2000-4000"))

    # 7 rental filters
    r.append(match_test("7F rental: dog+cat+laundry+beds+baths+price",
        f"{A}/New-York_NY/dog-friendly/cat-friendly/with_inunitlaundry/beds-2/baths-2/price-na-5000",
        f"{A}/New-York_NY/dog-friendly/cat-friendly/with_inunitlaundry/beds-2/baths-2/price-na-5000"))

    # 7 rental fully scrambled
    r.append(match_test("7F rental fully scrambled",
        f"{A}/New-York_NY/dog-friendly/cat-friendly/with_inunitlaundry/beds-2/baths-2/price-na-5000",
        f"{A}/New-York_NY/price-na-5000/baths-2/beds-2/with_inunitlaundry/cat-friendly/dog-friendly"))

    # Rental negative: wrong pet
    r.append(match_test("Rental: dog vs cat NO",
        f"{A}/SF_CA/dog-friendly/beds-2/price-na-3000",
        f"{A}/SF_CA/cat-friendly/beds-2/price-na-3000", False))

    # Rental negative: missing laundry
    r.append(match_test("Rental: missing laundry NO",
        f"{A}/SF_CA/dog-friendly/with_inunitlaundry/beds-2/price-na-3000",
        f"{A}/SF_CA/dog-friendly/beds-2/price-na-3000", False))

    return r


# ============================================================================
# TEST 19: EXTREME RECENTLY SOLD COMBOS
# ============================================================================
def test_extreme_sold():
    print("\n" + "=" * 70)
    print("TEST 19: EXTREME Recently Sold Multi-Filter Combos")
    print("=" * 70)
    r = []

    # 6 filters sold
    r.append(match_test("6F sold: recently-sold+within-90+beds+baths+price+type",
        f"{R}/Chicago_IL/show-recently-sold/sold-within-90/beds-3/baths-2/price-200000-500000/type-single-family-home",
        f"{R}/Chicago_IL/show-recently-sold/sold-within-90/beds-3/baths-2/price-200000-500000/type-single-family-home"))

    # 6 filters sold scrambled
    r.append(match_test("6F sold scrambled",
        f"{R}/Chicago_IL/show-recently-sold/sold-within-90/beds-3/baths-2/price-200000-500000/type-single-family-home",
        f"{R}/Chicago_IL/type-single-family-home/price-200000-500000/baths-2/beds-3/sold-within-90/show-recently-sold"))

    # Sold equivalence with filters
    r.append(match_test("sold-homes path + beds matches show-recently-sold + beds",
        "https://www.realtor.com/sold-homes/San-Francisco_CA",
        f"{R}/San-Francisco_CA/show-recently-sold/beds-3"))

    # Sold with price abbreviations
    r.append(match_test("5F sold with price abbreviation",
        f"{R}/Austin_TX/show-recently-sold/type-single-family-home/beds-4/baths-3/price-300000-700000",
        f"{R}/Austin_TX/show-recently-sold/type-house/beds-4/baths-3/price-300k-700k"))

    # Sold wrong timeframe
    r.append(match_test("Sold wrong timeframe NO",
        f"{R}/SF_CA/show-recently-sold/sold-within-30",
        f"{R}/SF_CA/show-recently-sold/sold-within-90", False))

    return r


# ============================================================================
# TEST 20: EXTREME ZIP CODE + COMPLEX FILTERS
# ============================================================================
def test_extreme_zip():
    print("\n" + "=" * 70)
    print("TEST 20: EXTREME ZIP Code + Complex Filters")
    print("=" * 70)
    r = []

    r.append(match_test("ZIP + 4 filters",
        f"{R}/90210/beds-3/baths-2/price-na-5000000/type-single-family-home",
        f"{R}/90210/beds-3/baths-2/price-na-5000000/type-single-family-home"))

    r.append(match_test("ZIP + 4 filters scrambled",
        f"{R}/90210/beds-3/baths-2/price-na-5000000/type-single-family-home",
        f"{R}/90210/type-single-family-home/price-na-5000000/baths-2/beds-3"))

    r.append(match_test("ZIP + 4 filters + alias",
        f"{R}/90210/beds-3/baths-2/price-na-5000000/type-single-family-home",
        f"{R}/90210/beds-3/baths-2/price-na-5m/type-house"))

    r.append(match_test("Rental ZIP + 3 filters",
        f"{A}/60601/beds-2/baths-1/price-na-3000",
        f"{A}/60601/beds-2/baths-1/price-na-3000"))

    r.append(match_test("ZIP mismatch NO",
        f"{R}/90210/beds-3/baths-2/price-na-5000000",
        f"{R}/90211/beds-3/baths-2/price-na-5000000", False))

    return r


# ============================================================================
# TEST 21: EXTREME EDGE CASES
# ============================================================================
def test_extreme_edge_cases():
    print("\n" + "=" * 70)
    print("TEST 21: EXTREME Edge Cases")
    print("=" * 70)
    r = []

    # Price abbreviation in complex: 500k-1m with 6 filters
    r.append(match_test("Price abbrev in 6F complex",
        f"{R}/Dallas_TX/beds-4/baths-3/price-500000-1000000/type-single-family-home/sqft-2500-4000",
        f"{R}/Dallas_TX/beds-4/baths-3/price-500k-1m/type-house/sqft-2500-4000"))

    # Multiple type aliases in complex
    r.append(match_test("Multi-type aliases: house+townhouse in 4F",
        f"{R}/SF_CA/type-single-family-home/type-townhome/beds-3/price-na-1000000",
        f"{R}/SF_CA/type-house/type-townhouse/beds-3/price-na-1m"))

    # URL with trailing slash
    r.append(match_test("Trailing slash ignored",
        f"{R}/San-Francisco_CA/beds-3",
        f"{R}/San-Francisco_CA/beds-3/"))

    # Map query params with complex filters
    r.append(match_test("Map params + 6F complex",
        f"{R}/Seattle_WA/beds-3/baths-2/price-na-900000/type-single-family-home/sqft-2000-3000/show-open-house",
        f"{R}/Seattle_WA/beds-3/baths-2/price-na-900000/type-single-family-home/sqft-2000-3000/show-open-house?view=map&pos=47.6,-122.4,47.5,-122.2,12&layer=Flood"))

    # Case insensitive with 6 filters
    r.append(match_test("Case insensitive 6F",
        f"{R}/San-Francisco_CA/beds-3/baths-2/price-na-1000000/type-condo/sqft-1000-2000/show-open-house",
        "HTTPS://WWW.REALTOR.COM/REALESTATEANDHOMES-SEARCH/SAN-FRANCISCO_CA/BEDS-3/BATHS-2/PRICE-NA-1000000/TYPE-CONDO/SQFT-1000-2000/SHOW-OPEN-HOUSE"))

    # Agent has extra filter on top of 6F GT
    r.append(match_test("Agent extra filter on 6F GT",
        f"{R}/Seattle_WA/beds-3/baths-2/price-na-900000/type-single-family-home/sqft-2000-3000/show-open-house",
        f"{R}/Seattle_WA/beds-3/baths-2/price-na-900000/type-single-family-home/sqft-2000-3000/show-open-house/dom-7"))

    # All abbreviations at once: price + type alias + scrambled + case
    r.append(match_test("Kitchen sink: price_abbrev + alias + scrambled + case",
        f"{R}/Los-Angeles_CA/show-price-reduced/type-single-family-home/beds-3/baths-2/price-800000-2000000/sqft-1500-na",
        "HTTPS://REALTOR.COM/REALESTATEANDHOMES-SEARCH/LOS-ANGELES_CA/SQFT-1500-NA/PRICE-800K-2M/BATHS-2/BEDS-3/TYPE-HOUSE/SHOW-PRICE-REDUCED"))

    return r


# ============================================================================
# TEST 22: EXTREME 8-FILTER STRESS TESTS
# ============================================================================
def test_8_filter_stress():
    print("\n" + "=" * 70)
    print("TEST 22: EXTREME 8-Filter Stress Tests")
    print("=" * 70)
    r = []

    # 8 filters: type + show + beds + baths + price + sqft + hoa + dom
    r.append(match_test("8F: type+show+beds+baths+price+sqft+hoa+dom",
        f"{R}/Miami_FL/type-condo/show-new-construction/beds-2/baths-2/price-na-800000/sqft-1000-2000/hoa-na-500/dom-7",
        f"{R}/Miami_FL/type-condo/show-new-construction/beds-2/baths-2/price-na-800000/sqft-1000-2000/hoa-na-500/dom-7"))

    # 8 filters fully scrambled
    r.append(match_test("8F fully scrambled",
        f"{R}/Miami_FL/type-condo/show-new-construction/beds-2/baths-2/price-na-800000/sqft-1000-2000/hoa-na-500/dom-7",
        f"{R}/Miami_FL/dom-7/hoa-na-500/sqft-1000-2000/price-na-800000/baths-2/beds-2/show-new-construction/type-condo"))

    # 8 filters with aliases + abbreviations
    r.append(match_test("8F with aliases + abbreviations",
        f"{R}/Dallas_TX/type-single-family-home/show-price-reduced/beds-4/baths-3/price-500000-1000000/sqft-2500-4000/lot-sqft-5000-na/age-0-10",
        f"{R}/Dallas_TX/type-house/show-price-reduced/beds-4/baths-3/price-500k-1m/sqft-2500-4000/lot-sqft-5000-na/age-0-10"))

    # 8 filters with one wrong = NO match
    r.append(match_test("8F with one wrong baths NO",
        f"{R}/Dallas_TX/type-single-family-home/show-price-reduced/beds-4/baths-3/price-500000-1000000/sqft-2500-4000/lot-sqft-5000-na/age-0-10",
        f"{R}/Dallas_TX/type-single-family-home/show-price-reduced/beds-4/baths-2/price-500000-1000000/sqft-2500-4000/lot-sqft-5000-na/age-0-10",
        False))

    # 8F rental: dog+cat+laundry+pool+beds+baths+price
    r.append(match_test("8F rental: dog+cat+laundry+pool+beds+baths+price scrambled",
        f"{A}/New-York_NY/dog-friendly/cat-friendly/with_inunitlaundry/features-cs/beds-2/baths-2/price-na-5000",
        f"{A}/New-York_NY/price-na-5000/baths-2/beds-2/features-cs/with_inunitlaundry/cat-friendly/dog-friendly"))

    return r


# ============================================================================
# TEST 23: CROSS-SEARCH-TYPE COMPREHENSIVE NEGATIVE
# ============================================================================
def test_cross_search_type_negatives():
    print("\n" + "=" * 70)
    print("TEST 23: Cross-Search-Type Comprehensive Negatives")
    print("=" * 70)
    r = []

    base_filters = "/beds-3/baths-2/price-na-1000000/type-single-family-home"

    # Same filters, different search types
    r.append(match_test("Sale vs Rent with identical filters NO",
        f"{R}/SF_CA{base_filters}", f"{A}/SF_CA{base_filters}", False))
    r.append(match_test("Sale vs Sold with identical filters NO",
        f"{R}/SF_CA{base_filters}",
        "https://www.realtor.com/sold-homes/SF_CA" + base_filters, False))
    r.append(match_test("Rent vs Sold with identical filters NO",
        f"{A}/SF_CA/beds-3/baths-2/price-na-3000",
        f"{R}/SF_CA/show-recently-sold/beds-3/baths-2/price-na-3000", False))

    return r


# ============================================================================
# TEST 24: REGRESSION — show-recently-sold false positive (Bug #1 from review)
# ============================================================================
def test_show_recently_sold_regression():
    print("\n" + "=" * 70)
    print("TEST 24: REGRESSION - show-recently-sold False Positive Fix")
    print("=" * 70)
    r = []

    # CRITICAL: GT has show-recently-sold as a filter, agent does NOT → must NOT match
    r.append(match_test("BUG1 regression: GT has show-recently-sold, agent missing it",
        f"{R}/SF_CA/show-recently-sold",
        f"{R}/SF_CA", False))

    # Same but with extra filters
    r.append(match_test("BUG1 regression: GT has show-recently-sold+beds, agent missing sold flag",
        f"{R}/SF_CA/show-recently-sold/beds-3/price-na-500000",
        f"{R}/SF_CA/beds-3/price-na-500000", False))

    # Equivalence should still work: sold-homes ↔ show-recently-sold
    r.append(match_test("Equivalence still works: sold-homes → show-recently-sold",
        "https://www.realtor.com/sold-homes/SF_CA",
        f"{R}/SF_CA/show-recently-sold"))

    # And the reverse
    r.append(match_test("Equivalence still works: show-recently-sold → sold-homes",
        f"{R}/SF_CA/show-recently-sold",
        "https://www.realtor.com/sold-homes/SF_CA"))

    # show-recently-sold on both sides (same search_type=sale) should match
    r.append(match_test("Both have show-recently-sold → should match",
        f"{R}/SF_CA/show-recently-sold/beds-3",
        f"{R}/SF_CA/show-recently-sold/beds-3"))

    # show-open-house same regression check
    r.append(match_test("GT has show-open-house, agent missing it → NO",
        f"{R}/SF_CA/show-open-house",
        f"{R}/SF_CA", False))

    return r


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("RIGOROUS REALTOR.COM VERIFIER TEST SUITE")
    print("Zero tolerance for failures - client delivery verification")
    print("=" * 70)

    all_results = []

    try:
        all_results += test_csv_self_match()
        all_results += test_search_types()
        all_results += test_locations()
        all_results += test_basic_filters()
        all_results += test_property_types()
        all_results += test_show_flags()
        all_results += test_advanced_filters()
        all_results += test_filter_order()
        all_results += test_sort_pagination()
        all_results += test_equivalences()
        all_results += test_rental_aliases()
        all_results += test_extra_filters()
        all_results += test_rental_filters()
        all_results += test_query_params_ignored()
        all_results += test_case_and_protocol()
        all_results += test_extreme_positive()
        all_results += test_extreme_negative()
        all_results += test_extreme_rental()
        all_results += test_extreme_sold()
        all_results += test_extreme_zip()
        all_results += test_extreme_edge_cases()
        all_results += test_8_filter_stress()
        all_results += test_cross_search_type_negatives()
        all_results += test_show_recently_sold_regression()
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        traceback.print_exc()

    # Final summary
    print("\n" + "=" * 70)
    passed = sum(all_results)
    total = len(all_results)
    failed = total - passed

    if total == 0:
        print("ERROR: No tests were executed!")
        sys.exit(1)

    pct = 100 * passed / total
    print(f"FINAL RESULTS: {passed}/{total} tests passed ({pct:.1f}%)")
    if failed > 0:
        print(f"FAILURES: {failed} tests FAILED")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED - READY FOR CLIENT")
    print("=" * 70)
