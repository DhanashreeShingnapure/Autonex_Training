"""StreetEasy URL Match verifier for property search navigation.

This module provides functionality to verify AI agent navigation on StreetEasy
by comparing the agent's final URL against expected ground truth URLs.

The verifier handles all StreetEasy URL variations including:
- Sale vs Rental vs Sold listings
- Borough and neighborhood-level locations
- Pipe-delimited filter segments (price:500000-|beds:2|type:D1)
- Property type codes (D1=condo, P1=co-op, comma-delimited combos)
- Amenity prefix format (amenities:doorman, amenities:elevator)
- Optional amenity prefix (opt_amenities:X — "Must-have" toggle OFF)
- Range filters with hyphen (price:MIN-MAX, sqft:MIN-MAX)
- Comparison operators (beds>=2, baths>=1.5)
- Pets filter (pets:allowed)
- Status filter (status:sold, status:open)
- Filter order independence
- Case insensitivity
- Domain variations (www/no-www, http/https)
- Sort parameter ignored (query param, not a search filter)

Chrome-Verified Patterns (Feb 2026):
- type:D1 = Condo, type:P1 = Co-op, type:D1,P1 = combo
- amenities:doorman, amenities:elevator, amenities:gym, amenities:laundry
- opt_amenities:parking (Must-have toggle OFF → optional amenity)
- pets:allowed (not pets:cats/pets:large_dogs)
- beds>=2, baths>=1.5 (comparison operators)
- status:sold
- price:500000-700000
- ?sort_by=se_score (default sort, query param)
"""

import re
from typing import TypedDict
from urllib.parse import urlparse, unquote, parse_qs

from beartype import beartype
from loguru import logger
from pydantic import BaseModel

from navi_bench.base import BaseMetric, BaseTaskConfig, get_import_path
from navi_bench.dates import initialize_user_metadata


class InputDict(TypedDict, total=False):
    url: str


class FinalResult(BaseModel):
    score: float


class StreetEasyVerifierResult(BaseModel):
    """Detailed verification result for StreetEasy URL matching."""
    score: float
    match: bool
    agent_url: str = ""
    gt_url: str = ""
    details: dict = {}


# ============================================================================
# CONSTANTS
# ============================================================================

# Valid domains
VALID_DOMAINS = {"streeteasy.com", "www.streeteasy.com"}

# Search type mapping from URL path
SEARCH_TYPES = {
    "for-sale": "sale",
    "for-rent": "rent",
    "sold": "sold",
    "past-sales": "sold",
}

# NYC boroughs (canonical lowercase forms)
BOROUGHS = {
    "manhattan", "brooklyn", "queens", "bronx", "staten-island",
    "nyc", "new-york-city",
}

# Parameters to ignore during comparison (UI-only, don't affect search)
IGNORED_QUERY_PARAMS = {
    "sort_by", "sort", "page", "map_bounds", "polygon",
    "utm_source", "utm_medium", "utm_content", "utm_campaign",
    "referrer", "v", "map_zoom",
}

# Pipe-delimited path filters to ignore (map/viewport artifacts)
# in_rect = map bounding box (lat,lat,lon,lon) from zoom/pan
IGNORED_FILTERS = {"in_rect"}

# Chrome-Verified Property Type Codes
PROPERTY_TYPE_CODES = {
    "D1": "condo",
    "P1": "coop",
    "D2": "condop",
    "D3": "townhouse",
    "D4": "house",
    "D5": "multi_family",
    "D6": "unknown_d6",
    "D7": "unknown_d7",
}

# Reverse mapping: human-readable name → code
PROPERTY_TYPE_NAMES_TO_CODES = {
    "condo": "D1",
    "condos": "D1",
    "condominium": "D1",
    "coop": "P1",
    "coops": "P1",
    "co-op": "P1",
    "co_op": "P1",
    "cooperative": "P1",
    "condop": "D2",
    "condops": "D2",
    "cond-op": "D2",
    "condo-op": "D2",
    "condo_op": "D2",
    "townhouse": "D3",
    "townhouses": "D3",
    "house": "D4",
    "houses": "D4",
    "single_family": "D4",
    "single-family": "D4",
    "multi_family": "D5",
    "multi-family": "D5",
    "multifamily": "D5",
}

# Filter name aliases: map variant names to canonical names
# Note: amenities are prefixed with "amenities:" in real URLs
FILTER_NAME_ALIASES = {
    # Price
    "price": "price",
    "ppsf": "ppsf",
    # Beds
    "beds": "beds",
    "bedrooms": "beds",
    "bed": "beds",
    "bedroom": "beds",
    # Baths
    "baths": "baths",
    "bathrooms": "baths",
    "bath": "baths",
    "bathroom": "baths",
    # Square footage
    "sqft": "sqft",
    "sq_ft": "sqft",
    "square_feet": "sqft",
    # Type (property type with codes)
    "type": "type",
    # Status
    "status": "status",
    # Pets
    "pets": "pets",
    "pet": "pets",
    # Rental-specific (these may NOT use amenities: prefix)
    "no_fee": "no_fee",
    "no-fee": "no_fee",
    "nofee": "no_fee",
    "furnished": "furnished",
    "short_term": "short_term",
    "short-term": "short_term",
    "owner": "owner",
    "by_owner": "owner",
    "guarantors_accepted": "guarantors_accepted",
    # Building features (these appear in "More" panel)
    "prewar": "prewar",
    "pre_war": "prewar",
    "pre-war": "prewar",
    "new_development": "new_development",
    "new_developments": "new_development",
    "new-development": "new_development",
    "new-developments": "new_development",
    "new_dev": "new_development",
    "income_restricted": "income_restricted",
    "income-restricted": "income_restricted",
    "year_built_min": "year_built_min",
    "year_built_max": "year_built_max",
    # Sale-specific
    "sale_type": "sale_type",
    "sale-type": "sale_type",
    # Financial
    "maintenance": "maintenance",
    "taxes": "taxes",
    "common_charges": "common_charges",
    "common-charges": "common_charges",
    # Other
    "days_on_market": "days_on_market",
    "days-on-market": "days_on_market",
    "subway": "subway",
    "transit_lines": "subway",
    "transit": "subway",
    "transit-lines": "subway",
    "transit_line": "subway",
    "school": "school",
    "zip": "zip",
    "keywords": "keywords",
    "open_house": "open_house",
    "virtual_tour": "virtual_tour",
    "3d_tour": "virtual_tour",
    "video_tour": "virtual_tour",
    # Area (neighborhood ID)
    "area": "area",
}

# Amenity name aliases: map variant names to canonical amenity values
# These use the "amenities:" or "opt_amenities:" prefix in real URLs
# amenities: = Must-have toggle ON
# opt_amenities: = Must-have toggle OFF (optional/preferred)
AMENITY_ALIASES = {
    "doorman": "doorman",
    "elevator": "elevator",
    "gym": "gym",
    "fitness": "gym",
    "pool": "pool",
    "swimming_pool": "pool",
    "laundry": "laundry",
    "laundry_in_building": "laundry",
    "laundry-in-building": "laundry",
    "garage": "garage",
    "garage_parking": "garage",
    "parking": "parking",
    "storage": "storage",
    "bike_room": "bike_room",
    "bike-room": "bike_room",
    "roof_deck": "roof_deck",
    "roof-deck": "roof_deck",
    "common_outdoor": "common_outdoor",
    "common_outdoor_space": "common_outdoor",
    "shared_outdoor_space": "common_outdoor",
    "childrens_playroom": "childrens_playroom",
    "live_in_super": "live_in_super",
    "live-in-super": "live_in_super",
    "concierge": "concierge",
    "package_room": "package_room",
    "central_air": "central_air",
    "central-air": "central_air",
    "verizon_fios": "verizon_fios",
    "dishwasher": "dishwasher",
    "in_unit_laundry": "in_unit_laundry",
    "in-unit-laundry": "in_unit_laundry",
    "washer_dryer": "in_unit_laundry",
    "outdoor_space": "outdoor_space",
    "outdoor-space": "outdoor_space",
    "private_outdoor_space": "outdoor_space",
    "private-outdoor-space": "outdoor_space",
    "pied_a_terre": "pied_a_terre",
    "pied-a-terre": "pied_a_terre",
    "terrace": "terrace",
    "balcony": "balcony",
    "garden": "garden",
    "fireplace": "fireplace",
    "home_office": "home_office",
    "home-office": "home_office",
    "eat_in_kitchen": "eat_in_kitchen",
    "eat-in-kitchen": "eat_in_kitchen",
    "walk_in_closet": "walk_in_closet",
    "walk-in-closet": "walk_in_closet",
    "no_fee": "no_fee",
    "no-fee": "no_fee",
    "furnished": "furnished",
}

# Status value aliases
STATUS_ALIASES = {
    "open": "open",
    "active": "open",
    "closed": "closed",
    "sold": "sold",
    "in_contract": "in_contract",
    "in-contract": "in_contract",
    "contract": "in_contract",
    "unavailable": "closed",
}

# Boolean value normalization
BOOLEAN_TRUE_VALUES = {"1", "true", "yes", "on", "allowed", "new development", "pre-war", "pre_war", "prewar"}


# ============================================================================
# VERIFIER CLASS
# ============================================================================

@beartype
class StreetEasyUrlMatch(BaseMetric):
    """
    Comprehensive StreetEasy URL verifier with robust handling of all URL patterns.

    Chrome-Verified (Feb 2026):
    - Property types: type:D1 (condo), type:P1 (co-op), type:D1,P1 (combo)
    - Amenities: amenities:doorman, amenities:elevator, amenities:gym, amenities:laundry
    - Pets: pets:allowed (single toggle)
    - Range: price:500000-700000, sqft:750-1200
    - Comparison: beds>=2, baths>=1.5
    - Status: status:sold, status:open
    - Sort: ?sort_by=se_score (query param, ignored)

    Handles:
    - Search type detection (for-sale, for-rent, sold/past-sales)
    - Borough and neighborhood location parsing
    - Pipe-delimited filter segments (key:value|key:value)
    - Property type code normalization (D1=condo, P1=co-op)
    - Amenities namespace (amenities:X)
    - Range filters (price:500000-1000000, sqft:750-1200)
    - Comparison operators (beds>=2, baths>=1.5)
    - Filter order independence (any order should match)
    - Case insensitivity throughout
    - Domain variations (with/without www, http/https)
    - Sort parameter ignored (query param, not a filter)
    - Price normalization (commas stripped, abbreviations)
    """

    def __init__(self, gt_url: str | list[str]) -> None:
        super().__init__()
        if isinstance(gt_url, str):
            self.gt_urls = [gt_url]
        else:
            self.gt_urls = gt_url
        self._found_match = False
        self._agent_url = ""
        self._matched_gt_url = ""
        self._match_details = {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(gt_urls={self.gt_urls})"

    async def reset(self) -> None:
        """Reset the match state for new evaluation."""
        self._found_match = False
        self._agent_url = ""
        self._matched_gt_url = ""
        self._match_details = {}

    async def update(self, **kwargs) -> None:
        """Update with new URL to check against ground truth."""
        inputs: InputDict = kwargs
        url = inputs.get("url", "")

        if not url:
            logger.debug("Empty URL provided")
            return

        self._agent_url = url

        for gt_url in self.gt_urls:
            match, details = self._urls_match(url, gt_url)
            if match:
                self._found_match = True
                self._matched_gt_url = gt_url
                self._match_details = details
                logger.info(f"Match found: {url[:100]}...")
                return

        logger.info(f"No match found: {url[:100]}...")

    async def compute(self) -> FinalResult:
        """Compute final score (1.0 = match, 0.0 = no match)."""
        score = 1.0 if self._found_match else 0.0
        result = FinalResult(score=score)
        logger.info(f"Final score: {score}")
        return result

    async def compute_detailed(self) -> StreetEasyVerifierResult:
        """Compute detailed result with match info."""
        score = 1.0 if self._found_match else 0.0
        return StreetEasyVerifierResult(
            score=score,
            match=self._found_match,
            agent_url=self._agent_url,
            gt_url=self._matched_gt_url,
            details=self._match_details,
        )

    # ========================================================================
    # URL MATCHING
    # ========================================================================

    def _urls_match(self, agent_url: str, gt_url: str) -> tuple[bool, dict]:
        """
        Check if two StreetEasy URLs represent the same search.
        Returns (match_bool, details_dict).
        """
        details = {"mismatches": [], "extra_filters": []}
        try:
            agent_parts = self._parse_streeteasy_url(agent_url)
            gt_parts = self._parse_streeteasy_url(gt_url)

            # Compare search type (sale vs rent vs sold)
            if agent_parts["search_type"] != gt_parts["search_type"]:
                details["mismatches"].append(
                    f"Search type: '{agent_parts['search_type']}' vs '{gt_parts['search_type']}'"
                )
                return False, details

            # Compare location and neighborhood
            # StreetEasy supports two URL formats for neighborhoods:
            #   1. /for-sale/manhattan/upper-west-side/filters (borough + neighborhood)
            #   2. /for-sale/upper-west-side/filters (neighborhood as location)
            # Both formats should match each other (browser-verified Feb 2026:
            # format 1 actually 404s on the real site, but we accept both in the
            # verifier for backward compatibility with existing GT data).
            agent_loc = agent_parts["location"]
            agent_nbhd = agent_parts["neighborhood"]
            gt_loc = gt_parts["location"]
            gt_nbhd = gt_parts["neighborhood"]

            # Normalize: if one URL has borough+neighborhood and the other has
            # neighborhood-as-location, extract the effective neighborhood
            agent_effective_nbhd = agent_nbhd or agent_loc
            gt_effective_nbhd = gt_nbhd or gt_loc

            # Case 1: Both have same structure (both borough+nbhd or both nbhd-only)
            if agent_loc == gt_loc and agent_nbhd == gt_nbhd:
                pass  # Exact match
            # Case 2: One has borough+neighborhood, other has neighborhood-as-location
            elif agent_nbhd and not gt_nbhd and agent_nbhd == gt_loc:
                pass  # e.g., agent: manhattan/upper-west-side, gt: upper-west-side
            elif gt_nbhd and not agent_nbhd and gt_nbhd == agent_loc:
                pass  # e.g., gt: manhattan/upper-west-side, agent: upper-west-side
            # Case 3: Both have neighborhoods but via different structures
            elif agent_effective_nbhd == gt_effective_nbhd:
                pass  # Same effective neighborhood
            else:
                details["mismatches"].append(
                    f"Location: '{agent_loc}/{agent_nbhd}' vs '{gt_loc}/{gt_nbhd}'"
                )
                return False, details

            # Compare filters (order-independent)
            agent_filters = agent_parts["filters"]
            gt_filters = gt_parts["filters"]

            # Check all GT filters exist in agent
            for key, gt_val in gt_filters.items():
                if key not in agent_filters:
                    details["mismatches"].append(f"Missing filter: {key}={gt_val}")
                    return False, details
                agent_val = agent_filters[key]
                if not self._filter_values_match(key, agent_val, gt_val):
                    details["mismatches"].append(
                        f"Filter value mismatch: {key}: '{agent_val}' vs '{gt_val}'"
                    )
                    return False, details

            # Check for extra filters in agent (note but don't fail)
            extra = set(agent_filters.keys()) - set(gt_filters.keys())
            if extra:
                details["extra_filters"] = list(extra)

            return True, details

        except Exception as e:
            logger.error(f"Error comparing URLs: {e}")
            details["mismatches"].append(f"Parse error: {str(e)}")
            return False, details

    # ========================================================================
    # URL PARSING
    # ========================================================================

    def _parse_streeteasy_url(self, url: str) -> dict:
        """
        Parse a StreetEasy URL into normalized components.

        Returns dict with keys:
            search_type: "sale", "rent", or "sold"
            location: borough name (lowercase)
            neighborhood: neighborhood name (lowercase) or ""
            filters: dict of normalized filter key -> value
        """
        url = url.strip()
        url = unquote(url)

        # Parse URL
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        parsed = urlparse(url)
        path = parsed.path.strip("/")
        path_lower = path.lower()

        result = {
            "search_type": "",
            "location": "",
            "neighborhood": "",
            "filters": {},
        }

        # Split path into segments
        segments = [s for s in path_lower.split("/") if s]

        if not segments:
            return result

        # Extract search type from first segment
        if segments[0] in SEARCH_TYPES:
            result["search_type"] = SEARCH_TYPES[segments[0]]
            segments = segments[1:]
        else:
            result["search_type"] = "sale"

        if not segments:
            return result

        # Extract location (borough) from next segment
        location_segment = segments[0]
        if ":" not in location_segment and ">=" not in location_segment:
            result["location"] = location_segment
            segments = segments[1:]
        else:
            return result

        if not segments:
            return result

        # Check for neighborhood segment (before filters)
        if segments and ":" not in segments[0] and ">=" not in segments[0] and "|" not in segments[0]:
            result["neighborhood"] = segments[0]
            segments = segments[1:]

        if not segments:
            return result

        # Remaining segments contain filters (pipe-delimited)
        filter_str = "/".join(segments)

        # Split on pipe to get individual filters
        raw_filters = filter_str.split("|")

        for raw_filter in raw_filters:
            raw_filter = raw_filter.strip()
            if not raw_filter:
                continue

            key, value = self._parse_single_filter(raw_filter)
            if key:
                # Skip map/viewport filters
                if key.lower().replace("-", "_") in IGNORED_FILTERS:
                    continue
                canonical_key, canonical_value = self._normalize_filter(key, value)

                # Handle multi-value filters (e.g., subway:L|subway:1)
                if canonical_key in result["filters"]:
                    existing = result["filters"][canonical_key]
                    existing_set = set(existing.split(","))
                    new_set = set(canonical_value.split(","))
                    merged = sorted(existing_set | new_set)
                    result["filters"][canonical_key] = ",".join(merged)
                else:
                    result["filters"][canonical_key] = canonical_value

        return result

    def _parse_single_filter(self, raw: str) -> tuple[str, str]:
        """
        Parse a single filter string like 'price:500000-1000000' or 'beds>=2'.
        Returns (key, value).
        """
        # Handle >= operator (beds>=2, baths>=1.5, sqft>=850)
        if ">=" in raw:
            parts = raw.split(">=", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip() + "-"  # Convert to range: beds>=2 → beds:2-
                return key, value

        # Handle standard colon separator (price:500000-1000000)
        if ":" in raw:
            parts = raw.split(":", 1)
            if len(parts) == 2:
                return parts[0].strip(), parts[1].strip()

        return "", ""

    # ========================================================================
    # NORMALIZATION
    # ========================================================================

    def _normalize_filter(self, key: str, value: str) -> tuple[str, str]:
        """
        Normalize a filter key and value to canonical forms.

        Handles:
        - amenities:X → key="amenities", value normalized
        - type:D1,P1 → key="type", value normalized
        - price normalization (commas, abbreviations)
        - status aliases
        - Boolean normalization
        """
        key = key.lower().strip()
        value = value.strip().lower()

        # Handle "amenities:" and "opt_amenities:" prefixes
        # StreetEasy uses two prefixes depending on the "Must-have" toggle:
        #   amenities:X     = Must-have ON (required amenity)
        #   opt_amenities:X = Must-have OFF (optional/preferred amenity)
        # Both are normalized to "amenities" key for matching, since task
        # descriptions say "with parking" not "must-have parking".
        # Supports single (amenities:doorman) and comma-separated
        # (amenities:elevator,doorman) values (browser-verified Feb 2026)
        if key in ("amenities", "opt_amenities"):
            amenities = [a.strip() for a in value.split(",")]
            normalized = []
            for a in amenities:
                canonical = AMENITY_ALIASES.get(a.replace("-", "_"), a)
                normalized.append(canonical)
            return "amenities", ",".join(sorted(normalized))

        # Normalize key using aliases
        key_underscore = key.replace("-", "_")
        canonical_key = FILTER_NAME_ALIASES.get(
            key_underscore, FILTER_NAME_ALIASES.get(key, key)
        )

        # Handle property type codes
        if canonical_key == "type":
            return "type", self._normalize_type_value(value)

        # Handle status
        if canonical_key == "status":
            return "status", STATUS_ALIASES.get(value, value)

        # Handle price/financial ranges
        if canonical_key in ("price", "maintenance", "taxes", "common_charges", "ppsf"):
            return canonical_key, self._normalize_price_value(value)

        # Handle pets
        if canonical_key == "pets":
            return "pets", value  # Keep as-is: "allowed", "cats", etc.

        # Handle sqft (strip commas)
        if canonical_key == "sqft":
            return "sqft", value.replace(",", "")

        # Handle boolean-like filters
        if canonical_key in (
            "no_fee", "furnished", "short_term", "owner", "guarantors_accepted",
            "prewar", "new_development", "income_restricted",
            "virtual_tour", "open_house",
        ):
            if value in BOOLEAN_TRUE_VALUES:
                return canonical_key, "1"
            return canonical_key, value

        # Handle subway lines (keep value as-is)
        if canonical_key == "subway":
            return "subway", value.upper()  # Normalize: l → L

        return canonical_key, value

    def _normalize_type_value(self, value: str) -> str:
        """
        Normalize property type value.
        Handles: D1, P1, D1,P1, or human-readable names.
        Returns comma-separated sorted codes.
        """
        value = value.strip().upper()

        # If already code format (D1, P1, D1,P1)
        parts = [p.strip() for p in value.split(",")]
        normalized = []
        for part in parts:
            if part in PROPERTY_TYPE_CODES:
                normalized.append(part)
            elif part.lower() in PROPERTY_TYPE_NAMES_TO_CODES:
                normalized.append(PROPERTY_TYPE_NAMES_TO_CODES[part.lower()])
            else:
                normalized.append(part)

        return ",".join(sorted(normalized))

    def _normalize_price_value(self, value: str) -> str:
        """
        Normalize price values: strip commas, expand abbreviations.
        e.g., '500k' → '500000', '2m' → '2000000', '1,500,000' → '1500000'
        """
        value = value.replace(",", "").replace("$", "").strip()

        # Handle range format MIN-MAX
        if "-" in value:
            parts = value.split("-", 1)
            left = self._expand_price_abbrev(parts[0]) if parts[0] else ""
            right = self._expand_price_abbrev(parts[1]) if parts[1] else ""
            return f"{left}-{right}"

        return self._expand_price_abbrev(value)

    def _expand_price_abbrev(self, val: str) -> str:
        """Expand price abbreviation: 500k → 500000, 2m → 2000000."""
        val = val.strip()
        if not val:
            return val
        if val.endswith("m"):
            try:
                return str(int(float(val[:-1]) * 1_000_000))
            except ValueError:
                return val
        if val.endswith("k"):
            try:
                return str(int(float(val[:-1]) * 1_000))
            except ValueError:
                return val
        return val

    def _filter_values_match(self, key: str, agent_val: str, gt_val: str) -> bool:
        """
        Compare two filter values, accounting for:
        - Comma-separated multi-values (order independent)
        - Boolean equivalence (1 == true == allowed)
        - Range equivalence
        """
        if agent_val == gt_val:
            return True

        # Multi-value comparison (type:D1,P1 vs type:P1,D1)
        if "," in agent_val or "," in gt_val:
            agent_set = set(agent_val.split(","))
            gt_set = set(gt_val.split(","))
            return agent_set == gt_set

        # Boolean equivalence
        if agent_val in BOOLEAN_TRUE_VALUES and gt_val in BOOLEAN_TRUE_VALUES:
            return True

        return False


# ============================================================================
# TASK CONFIG GENERATION
# ============================================================================

def generate_task_config(
    task: str,
    location: str,
    timezone: str,
    gt_url: list[str] | None = None,
    ground_truth_url: str | None = None,
    timestamp: int | None = None,
    url: str = "https://streeteasy.com",
) -> BaseTaskConfig:
    """Generate task configuration for StreetEasy URL matching.

    Accepts either ``gt_url`` (NaviBench canonical form, list of strings) or
    ``ground_truth_url`` (CSV export form, single string) so that the function
    works both when called by ``instantiate()`` from the benchmark CSV and when
    called directly from code.
    """
    # Resolve gt_url from either parameter
    if gt_url is None and ground_truth_url is not None:
        gt_url = [ground_truth_url]
    elif isinstance(gt_url, str):
        gt_url = [gt_url]
    elif gt_url is None:
        raise ValueError("Either 'gt_url' or 'ground_truth_url' must be provided.")

    user_metadata = initialize_user_metadata(timezone, location, timestamp)
    eval_target = get_import_path(StreetEasyUrlMatch)
    eval_config = {"_target_": eval_target, "gt_url": gt_url}
    return BaseTaskConfig(
        url=url, task=task, user_metadata=user_metadata, eval_config=eval_config
    )


# ============================================================================
# COMPREHENSIVE EDGE CASE TESTS — 75+ Tests Across 20 Categories
# (Updated with Chrome-verified URL patterns)
# ============================================================================

if __name__ == "__main__":
    import asyncio

    print("=" * 80)
    print("STREETEASY URL VERIFIER — COMPREHENSIVE EDGE CASE TEST SUITE")
    print("Chrome-Verified Patterns (Feb 2026)")
    print("=" * 80)

    async def run_comprehensive_tests():
        """Run all edge case tests."""
        total_tests = 0
        passed_tests = 0

        def run_test(name, gt_url, agent_url, expected_match=True):
            nonlocal total_tests, passed_tests
            total_tests += 1
            evaluator = StreetEasyUrlMatch(gt_url=gt_url)
            match, details = evaluator._urls_match(agent_url, gt_url)
            status = "✅" if match == expected_match else "❌"
            if match == expected_match:
                passed_tests += 1
            else:
                extra = ""
                if details.get("mismatches"):
                    extra = f" — {details['mismatches']}"
                print(f"  {status} {name}{extra}")
                return
            print(f"  {status} {name}")

        # ================================================================
        # 1. SEARCH TYPE DETECTION
        # ================================================================
        print("\n📁 1. Search Type Detection")
        print("-" * 40)

        run_test(
            "Sale search type",
            "https://streeteasy.com/for-sale/manhattan",
            "https://streeteasy.com/for-sale/manhattan",
        )
        run_test(
            "Rental search type",
            "https://streeteasy.com/for-rent/brooklyn",
            "https://streeteasy.com/for-rent/brooklyn",
        )
        run_test(
            "Sold search type",
            "https://streeteasy.com/sold/manhattan",
            "https://streeteasy.com/sold/manhattan",
        )
        run_test(
            "Sale vs Rent should NOT match",
            "https://streeteasy.com/for-sale/manhattan",
            "https://streeteasy.com/for-rent/manhattan",
            expected_match=False,
        )
        run_test(
            "Sale vs Sold should NOT match",
            "https://streeteasy.com/for-sale/manhattan",
            "https://streeteasy.com/sold/manhattan",
            expected_match=False,
        )

        # ================================================================
        # 2. LOCATION PARSING
        # ================================================================
        print("\n📍 2. Location Parsing")
        print("-" * 40)

        run_test(
            "Manhattan location",
            "https://streeteasy.com/for-sale/manhattan",
            "https://streeteasy.com/for-sale/manhattan",
        )
        run_test(
            "Brooklyn location",
            "https://streeteasy.com/for-rent/brooklyn",
            "https://streeteasy.com/for-rent/brooklyn",
        )
        run_test(
            "Queens location",
            "https://streeteasy.com/for-sale/queens",
            "https://streeteasy.com/for-sale/queens",
        )
        run_test(
            "Manhattan vs Brooklyn should NOT match",
            "https://streeteasy.com/for-sale/manhattan",
            "https://streeteasy.com/for-sale/brooklyn",
            expected_match=False,
        )
        run_test(
            "Neighborhood location",
            "https://streeteasy.com/for-sale/manhattan/upper-west-side",
            "https://streeteasy.com/for-sale/manhattan/upper-west-side",
        )
        run_test(
            "Staten Island location",
            "https://streeteasy.com/for-sale/staten-island",
            "https://streeteasy.com/for-sale/staten-island",
        )

        # ================================================================
        # 3. PRICE FILTERS
        # ================================================================
        print("\n💰 3. Price Filters")
        print("-" * 40)

        run_test(
            "Price range (Chrome-verified)",
            "https://streeteasy.com/for-sale/manhattan/price:500000-700000",
            "https://streeteasy.com/for-sale/manhattan/price:500000-700000",
        )
        run_test(
            "Min price only",
            "https://streeteasy.com/for-sale/manhattan/price:500000-",
            "https://streeteasy.com/for-sale/manhattan/price:500000-",
        )
        run_test(
            "Max price only",
            "https://streeteasy.com/for-sale/manhattan/price:-1000000",
            "https://streeteasy.com/for-sale/manhattan/price:-1000000",
        )
        run_test(
            "Price with commas vs without",
            "https://streeteasy.com/for-sale/manhattan/price:500000-1000000",
            "https://streeteasy.com/for-sale/manhattan/price:500,000-1,000,000",
        )
        run_test(
            "Price abbreviation k",
            "https://streeteasy.com/for-sale/manhattan/price:500000-1000000",
            "https://streeteasy.com/for-sale/manhattan/price:500k-1000k",
        )
        run_test(
            "Price abbreviation m",
            "https://streeteasy.com/for-sale/manhattan/price:500000-2000000",
            "https://streeteasy.com/for-sale/manhattan/price:500k-2m",
        )
        run_test(
            "Wrong price should NOT match",
            "https://streeteasy.com/for-sale/manhattan/price:500000-1000000",
            "https://streeteasy.com/for-sale/manhattan/price:300000-800000",
            expected_match=False,
        )

        # ================================================================
        # 4. BEDS FILTER (Chrome-Verified)
        # ================================================================
        print("\n🛏️  4. Beds Filter (Chrome-Verified)")
        print("-" * 40)

        run_test(
            "Exact beds",
            "https://streeteasy.com/for-sale/manhattan/beds:2",
            "https://streeteasy.com/for-sale/manhattan/beds:2",
        )
        run_test(
            "Studio (beds:0)",
            "https://streeteasy.com/for-rent/manhattan/beds:0",
            "https://streeteasy.com/for-rent/manhattan/beds:0",
        )
        run_test(
            "Min beds with >= (Chrome-verified)",
            "https://streeteasy.com/for-rent/manhattan/beds>=2",
            "https://streeteasy.com/for-rent/manhattan/beds>=2",
        )
        run_test(
            "Different beds should NOT match",
            "https://streeteasy.com/for-sale/manhattan/beds:2",
            "https://streeteasy.com/for-sale/manhattan/beds:3",
            expected_match=False,
        )

        # ================================================================
        # 5. BATHS FILTER (Chrome-Verified)
        # ================================================================
        print("\n🚿 5. Baths Filter")
        print("-" * 40)

        run_test(
            "Exact baths (Chrome-verified)",
            "https://streeteasy.com/for-sale/manhattan/baths:1",
            "https://streeteasy.com/for-sale/manhattan/baths:1",
        )
        run_test(
            "Min baths with >=",
            "https://streeteasy.com/for-rent/manhattan/baths>=1.5",
            "https://streeteasy.com/for-rent/manhattan/baths>=1.5",
        )
        run_test(
            "Beds + Baths combo (Chrome-verified)",
            "https://streeteasy.com/for-sale/manhattan/beds:2|baths:1",
            "https://streeteasy.com/for-sale/manhattan/beds:2|baths:1",
        )

        # ================================================================
        # 6. PROPERTY TYPE — CODES (Chrome-Verified ✅)
        # ================================================================
        print("\n🏠 6. Property Type — Codes (Chrome-Verified)")
        print("-" * 40)

        run_test(
            "Condo: type:D1 (Chrome-verified)",
            "https://streeteasy.com/for-sale/manhattan/type:D1",
            "https://streeteasy.com/for-sale/manhattan/type:D1",
        )
        run_test(
            "Co-op: type:P1 (Chrome-verified)",
            "https://streeteasy.com/for-sale/manhattan/type:P1",
            "https://streeteasy.com/for-sale/manhattan/type:P1",
        )
        run_test(
            "Combo: type:D1,P1 (Chrome-verified comma-delimited)",
            "https://streeteasy.com/for-sale/manhattan/type:D1,P1",
            "https://streeteasy.com/for-sale/manhattan/type:D1,P1",
        )
        run_test(
            "Combo order independent: D1,P1 vs P1,D1",
            "https://streeteasy.com/for-sale/manhattan/type:D1,P1",
            "https://streeteasy.com/for-sale/manhattan/type:P1,D1",
        )
        run_test(
            "Human-readable condo → D1",
            "https://streeteasy.com/for-sale/manhattan/type:D1",
            "https://streeteasy.com/for-sale/manhattan/type:condo",
        )
        run_test(
            "Human-readable co-op → P1",
            "https://streeteasy.com/for-sale/manhattan/type:P1",
            "https://streeteasy.com/for-sale/manhattan/type:coop",
        )
        run_test(
            "Human-readable condos → D1",
            "https://streeteasy.com/for-sale/manhattan/type:D1",
            "https://streeteasy.com/for-sale/manhattan/type:condos",
        )
        run_test(
            "Wrong type should NOT match",
            "https://streeteasy.com/for-sale/manhattan/type:D1",
            "https://streeteasy.com/for-sale/manhattan/type:P1",
            expected_match=False,
        )

        # ================================================================
        # 7. AMENITIES — amenities: PREFIX (Chrome-Verified ✅)
        # ================================================================
        print("\n✨ 7. Amenities — amenities: prefix (Chrome-Verified)")
        print("-" * 40)

        run_test(
            "Doorman (Chrome-verified: amenities:doorman)",
            "https://streeteasy.com/for-sale/manhattan/amenities:doorman",
            "https://streeteasy.com/for-sale/manhattan/amenities:doorman",
        )
        run_test(
            "Elevator (Chrome-verified: amenities:elevator)",
            "https://streeteasy.com/for-sale/manhattan/amenities:elevator",
            "https://streeteasy.com/for-sale/manhattan/amenities:elevator",
        )
        run_test(
            "Gym (Chrome-verified: amenities:gym)",
            "https://streeteasy.com/for-sale/manhattan/amenities:gym",
            "https://streeteasy.com/for-sale/manhattan/amenities:gym",
        )
        run_test(
            "Laundry (Chrome-verified: amenities:laundry)",
            "https://streeteasy.com/for-sale/manhattan/amenities:laundry",
            "https://streeteasy.com/for-sale/manhattan/amenities:laundry",
        )
        run_test(
            "Doorman + Elevator combo",
            "https://streeteasy.com/for-sale/manhattan/amenities:doorman|amenities:elevator",
            "https://streeteasy.com/for-sale/manhattan/amenities:doorman|amenities:elevator",
        )
        run_test(
            "In-unit laundry",
            "https://streeteasy.com/for-rent/manhattan/amenities:in_unit_laundry",
            "https://streeteasy.com/for-rent/manhattan/amenities:in_unit_laundry",
        )
        run_test(
            "Amenity alias: fitness → gym",
            "https://streeteasy.com/for-sale/manhattan/amenities:gym",
            "https://streeteasy.com/for-sale/manhattan/amenities:fitness",
        )

        # ================================================================
        # 7b. OPT_AMENITIES (Must-have toggle OFF, Chrome-Verified ✅)
        # ================================================================
        print("\n✨ 7b. Optional Amenities — opt_amenities: prefix (Chrome-Verified)")
        print("-" * 40)

        run_test(
            "opt_amenities:parking matches amenities:parking",
            "https://streeteasy.com/for-sale/brooklyn/amenities:parking",
            "https://streeteasy.com/for-sale/brooklyn/opt_amenities:parking",
        )
        run_test(
            "opt_amenities:doorman,gym matches amenities:doorman,gym",
            "https://streeteasy.com/for-sale/manhattan/amenities:doorman,gym",
            "https://streeteasy.com/for-sale/manhattan/opt_amenities:doorman,gym",
        )
        run_test(
            "amenities:parking matches opt_amenities:parking (reverse)",
            "https://streeteasy.com/for-sale/brooklyn/opt_amenities:parking",
            "https://streeteasy.com/for-sale/brooklyn/amenities:parking",
        )
        run_test(
            "opt_amenities with other filters",
            "https://streeteasy.com/for-sale/brooklyn/type:D1|beds:2|amenities:parking",
            "https://streeteasy.com/for-sale/brooklyn/type:D1|beds:2|opt_amenities:parking",
        )
        run_test(
            "opt_amenities does NOT match different amenity",
            "https://streeteasy.com/for-sale/brooklyn/opt_amenities:parking",
            "https://streeteasy.com/for-sale/brooklyn/opt_amenities:gym",
            expected_match=False,
        )

        # ================================================================
        # 8. PETS FILTER (Chrome-Verified ✅)
        # ================================================================
        print("\n🐾 8. Pets Filter (Chrome-Verified)")
        print("-" * 40)

        run_test(
            "Pets allowed (Chrome-verified)",
            "https://streeteasy.com/for-sale/manhattan/pets:allowed",
            "https://streeteasy.com/for-sale/manhattan/pets:allowed",
        )
        run_test(
            "Pets NOT match different value",
            "https://streeteasy.com/for-sale/manhattan/pets:allowed",
            "https://streeteasy.com/for-sale/manhattan/pets:none",
            expected_match=False,
        )

        # ================================================================
        # 9. STATUS FILTER (Chrome-Verified)
        # ================================================================
        print("\n📊 9. Status Filter")
        print("-" * 40)

        run_test(
            "Status open",
            "https://streeteasy.com/for-sale/manhattan/status:open",
            "https://streeteasy.com/for-sale/manhattan/status:open",
        )
        run_test(
            "Status sold (Chrome-verified)",
            "https://streeteasy.com/for-sale/manhattan/status:sold",
            "https://streeteasy.com/for-sale/manhattan/status:sold",
        )
        run_test(
            "Status active = open alias",
            "https://streeteasy.com/for-sale/manhattan/status:open",
            "https://streeteasy.com/for-sale/manhattan/status:active",
        )
        run_test(
            "Status in_contract vs in-contract",
            "https://streeteasy.com/for-sale/manhattan/status:in_contract",
            "https://streeteasy.com/for-sale/manhattan/status:in-contract",
        )

        # ================================================================
        # 10. SQUARE FOOTAGE
        # ================================================================
        print("\n📐 10. Square Footage")
        print("-" * 40)

        run_test(
            "SQFT range",
            "https://streeteasy.com/for-sale/manhattan/sqft:750-1200",
            "https://streeteasy.com/for-sale/manhattan/sqft:750-1200",
        )
        run_test(
            "Min SQFT with >=",
            "https://streeteasy.com/for-sale/manhattan/sqft>=850",
            "https://streeteasy.com/for-sale/manhattan/sqft>=850",
        )

        # ================================================================
        # 11. RENTAL-SPECIFIC
        # ================================================================
        print("\n🏢 11. Rental-Specific Filters")
        print("-" * 40)

        run_test(
            "No fee",
            "https://streeteasy.com/for-rent/manhattan/no_fee:1",
            "https://streeteasy.com/for-rent/manhattan/no_fee:1",
        )
        run_test(
            "No-fee alias (hyphenated)",
            "https://streeteasy.com/for-rent/manhattan/no_fee:1",
            "https://streeteasy.com/for-rent/manhattan/no-fee:1",
        )
        run_test(
            "Furnished",
            "https://streeteasy.com/for-rent/manhattan/furnished:1",
            "https://streeteasy.com/for-rent/manhattan/furnished:1",
        )
        run_test(
            "Boolean true vs 1",
            "https://streeteasy.com/for-rent/manhattan/no_fee:1",
            "https://streeteasy.com/for-rent/manhattan/no_fee:true",
        )

        # ================================================================
        # 12. BUILDING FEATURES
        # ================================================================
        print("\n🏗️  12. Building Features")
        print("-" * 40)

        run_test(
            "Pre-war",
            "https://streeteasy.com/for-sale/manhattan/prewar:1",
            "https://streeteasy.com/for-sale/manhattan/prewar:1",
        )
        run_test(
            "Pre-war alias (pre_war)",
            "https://streeteasy.com/for-sale/manhattan/prewar:1",
            "https://streeteasy.com/for-sale/manhattan/pre_war:1",
        )
        run_test(
            "Pre-war alias (pre-war)",
            "https://streeteasy.com/for-sale/manhattan/prewar:1",
            "https://streeteasy.com/for-sale/manhattan/pre-war:1",
        )
        run_test(
            "New development",
            "https://streeteasy.com/for-sale/manhattan/new_development:1",
            "https://streeteasy.com/for-sale/manhattan/new_development:1",
        )

        # ================================================================
        # 13. SALE-SPECIFIC
        # ================================================================
        print("\n💼 13. Sale-Specific Filters")
        print("-" * 40)

        run_test(
            "Sale type foreclosure",
            "https://streeteasy.com/for-sale/manhattan/sale_type:foreclosure",
            "https://streeteasy.com/for-sale/manhattan/sale_type:foreclosure",
        )

        # ================================================================
        # 14. SUBWAY / TRANSIT
        # ================================================================
        print("\n🚇 14. Subway / Transit")
        print("-" * 40)

        run_test(
            "Subway L line",
            "https://streeteasy.com/for-rent/brooklyn/subway:L",
            "https://streeteasy.com/for-rent/brooklyn/subway:L",
        )
        run_test(
            "Subway case insensitive",
            "https://streeteasy.com/for-rent/brooklyn/subway:L",
            "https://streeteasy.com/for-rent/brooklyn/subway:l",
        )
        run_test(
            "Multiple subway lines",
            "https://streeteasy.com/for-rent/manhattan/subway:1|subway:2|subway:3",
            "https://streeteasy.com/for-rent/manhattan/subway:3|subway:1|subway:2",
        )

        # ================================================================
        # 15. FILTER ORDER INDEPENDENCE
        # ================================================================
        print("\n🔄 15. Filter Order Independence")
        print("-" * 40)

        run_test(
            "Same filters different order (2 filters)",
            "https://streeteasy.com/for-sale/manhattan/price:500000-|beds:2",
            "https://streeteasy.com/for-sale/manhattan/beds:2|price:500000-",
        )
        run_test(
            "Same filters different order (3 filters)",
            "https://streeteasy.com/for-sale/manhattan/price:500000-|beds:2|type:D1",
            "https://streeteasy.com/for-sale/manhattan/type:D1|price:500000-|beds:2",
        )
        run_test(
            "Complex order independence (5 filters)",
            "https://streeteasy.com/for-rent/brooklyn/price:2000-3500|beds:2|no_fee:1|amenities:doorman|amenities:elevator",
            "https://streeteasy.com/for-rent/brooklyn/amenities:elevator|beds:2|amenities:doorman|price:2000-3500|no_fee:1",
        )

        # ================================================================
        # 16. CASE INSENSITIVITY
        # ================================================================
        print("\n🔤 16. Case Insensitivity")
        print("-" * 40)

        run_test(
            "Lowercase vs mixed case location",
            "https://streeteasy.com/for-sale/manhattan",
            "https://streeteasy.com/for-sale/Manhattan",
        )
        run_test(
            "Uppercase filter key",
            "https://streeteasy.com/for-sale/manhattan/beds:2",
            "https://streeteasy.com/for-sale/manhattan/BEDS:2",
        )

        # ================================================================
        # 17. DOMAIN & PROTOCOL VARIATIONS
        # ================================================================
        print("\n🌐 17. Domain & Protocol Variations")
        print("-" * 40)

        run_test(
            "http vs https",
            "https://streeteasy.com/for-sale/manhattan",
            "http://streeteasy.com/for-sale/manhattan",
        )
        run_test(
            "www vs no-www",
            "https://streeteasy.com/for-sale/manhattan",
            "https://www.streeteasy.com/for-sale/manhattan",
        )
        run_test(
            "No protocol",
            "https://streeteasy.com/for-sale/manhattan",
            "streeteasy.com/for-sale/manhattan",
        )

        # ================================================================
        # 18. SORT PARAMETER IGNORED
        # ================================================================
        print("\n📋 18. Sort Parameter (Ignored)")
        print("-" * 40)

        run_test(
            "Sort param ignored (Chrome-verified: ?sort_by=se_score)",
            "https://streeteasy.com/for-sale/manhattan/beds:2",
            "https://streeteasy.com/for-sale/manhattan/beds:2?sort_by=se_score",
        )
        run_test(
            "Different sort params still match",
            "https://streeteasy.com/for-sale/manhattan/beds:2?sort_by=price_asc",
            "https://streeteasy.com/for-sale/manhattan/beds:2?sort_by=price_desc",
        )

        # ================================================================
        # 19. COMPLEX MULTI-FILTER — REAL CHROME URLs
        # ================================================================
        print("\n🎯 19. Complex Multi-Filter (Chrome-Verified URLs)")
        print("-" * 40)

        run_test(
            "Chrome URL #1: type + price + beds (Chrome-verified)",
            "https://streeteasy.com/for-sale/manhattan/type:D1|price:500000-700000|beds:2?sort_by=se_score",
            "https://streeteasy.com/for-sale/manhattan/beds:2|type:D1|price:500000-700000?sort_by=se_score",
        )
        run_test(
            "Chrome URL #2: type + price + beds + pets (Chrome-verified)",
            "https://streeteasy.com/for-sale/manhattan/type:D1|price:500000-700000|beds:2|pets:allowed?sort_by=se_score",
            "https://streeteasy.com/for-sale/manhattan/pets:allowed|beds:2|type:D1|price:500000-700000?sort_by=se_score",
        )
        run_test(
            "Chrome URL #3: all filters (Chrome-verified)",
            "https://streeteasy.com/for-sale/manhattan/type:D1|price:500000-700000|beds:2|amenities:doorman|pets:allowed?sort_by=se_score",
            "https://streeteasy.com/for-sale/manhattan/amenities:doorman|pets:allowed|beds:2|price:500000-700000|type:D1?sort_by=se_score",
        )
        run_test(
            "Missing filter should NOT match",
            "https://streeteasy.com/for-sale/manhattan/type:D1|price:500000-|beds:2",
            "https://streeteasy.com/for-sale/manhattan/price:500000-|beds:2",
            expected_match=False,
        )

        # ================================================================
        # 20. NEIGHBORHOOD + FILTERS
        # ================================================================
        print("\n🏘️  20. Neighborhood + Filters")
        print("-" * 40)

        run_test(
            "Neighborhood with filters",
            "https://streeteasy.com/for-sale/manhattan/upper-west-side/type:D1|price:500000-",
            "https://streeteasy.com/for-sale/manhattan/upper-west-side/type:D1|price:500000-",
        )
        run_test(
            "Neighborhood filter order",
            "https://streeteasy.com/for-sale/manhattan/upper-west-side/type:D1|price:500000-",
            "https://streeteasy.com/for-sale/manhattan/upper-west-side/price:500000-|type:D1",
        )
        run_test(
            "Different neighborhood should NOT match",
            "https://streeteasy.com/for-sale/manhattan/upper-west-side/type:D1",
            "https://streeteasy.com/for-sale/manhattan/upper-east-side/type:D1",
            expected_match=False,
        )

        # ================================================================
        # RESULTS SUMMARY
        # ================================================================
        print("\n" + "=" * 80)
        print(f"RESULTS: {passed_tests}/{total_tests} tests passed")
        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED!")
        else:
            print(f"❌ {total_tests - passed_tests} tests FAILED")
        print("=" * 80)

        return passed_tests == total_tests

    asyncio.run(run_comprehensive_tests())
