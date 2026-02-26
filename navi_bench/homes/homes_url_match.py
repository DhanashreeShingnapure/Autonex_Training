"""
Homes.com URL Match Verifier (Universal Edition)

Handles both Path-Based Slugs AND Query Parameters.
Now correctly parses Property Types (condos, townhomes) and Transaction Types (rent/sale).
"""

import re
from typing import Any, Dict, Optional, Tuple, List, Union
from urllib.parse import parse_qs, urlparse
from pydantic import BaseModel
from datetime import datetime
from zoneinfo import ZoneInfo
from navi_bench.base import BaseMetric, BaseTaskConfig, UserMetadata, get_import_path



class HomesVerifierResult(BaseModel):
    score: float
    match: bool
    agent_url: str
    ground_truth_url: str
    details: dict


class HomesUrlMatch(BaseMetric):
    """
    Universal Homes.com Verifier.
    """

    def __init__(
        self,
        gt_urls: Union[str, List[str], List[List[str]]],
        *,
        strict_location: bool = True,
        strict_filters: bool = True
    ):
        # 1. Handle single string (e.g., "http...")
        if isinstance(gt_urls, str):
            self.gt_urls = [gt_urls]
            
        # 2. Handle List of Lists (The navi_bench pipeline format)
        elif len(gt_urls) > 0 and isinstance(gt_urls[0], list):
            self.gt_urls = [url for sublist in gt_urls for url in sublist]
            
        # 3. Handle flat 1D list (Your test script format)
        else:
            self.gt_urls = gt_urls
            
        self.strict_location = strict_location
        self.strict_filters = strict_filters
        self._agent_url: Optional[str] = None
    
    async def reset(self) -> None:
        """
        Clears the internal state for the next evaluation run.
        Prevents stale agent URLs from leaking across tasks.
        """
        self._agent_url = None

    async def update(self, *, url: Optional[str] = None, **kwargs) -> None:
        if url:
            self._agent_url = url
            

    async def compute(self) -> HomesVerifierResult:
        if not self._agent_url:
            return HomesVerifierResult(
                score=0.0, match=False, agent_url="", 
                ground_truth_url=self.gt_urls[0], 
                details={"error": "No agent URL provided"}
            )
        
        # Check against ALL provided GT URLs
        best_details = {}
        for gt_url in self.gt_urls:
            match, details = self._urls_match(self._agent_url, gt_url)
            if match:
                return HomesVerifierResult(
                    score=1.0, match=True, agent_url=self._agent_url,
                    ground_truth_url=gt_url, details=details
                )
            best_details = details

        return HomesVerifierResult(
            score=0.0, match=False, agent_url=self._agent_url,
            ground_truth_url=self.gt_urls[0], details=best_details
        )

    def _parse_homes_url(self, url: str) -> Dict[str, Any]:
        """
        Parses filters from URL path AND query parameters.
        """
        result = {
            "location": None,
            "filters": {
                "keywords": []  # List to hold amenities/styles found in path
            }
        }

        if not url:
            return result

        parsed = urlparse(url)
        path_segments = [s for s in parsed.path.split("/") if s]
        
        # --- 1. PATH SEGMENT PARSING ---
        for segment in path_segments:
            segment_lower = segment.lower()
            
            # A. Check for Combined Transaction/Property Type (e.g., 'condos-for-sale')
            txn_match = re.match(r"^(.*?)-(for-sale|for-rent|sold)$", segment_lower)
            
            # --- FIX 1: Explicitly handle standalone transaction types ---
            if segment_lower in {"for-sale", "for-rent", "sold"}:
                result["filters"]["transaction_type"] = segment_lower
                continue

            # Handle Combined (e.g. condos-for-sale)
            # We exclude standalone matches here to avoid 'for-sale' matching group 1='for', group 2='sale' logic errors
            elif txn_match:
                # Ensure it's not just the standalone word (handled above)
                if txn_match.group(1): 
                    result["filters"]["property_type_slug"] = txn_match.group(1) 
                    result["filters"]["transaction_type"] = txn_match.group(2)
                continue
            
            # --- FIX 1: Catch 'new-construction', 'foreclosures' etc. ---
            if segment_lower in {"new-homes", "new-construction", "foreclosures", "open-house"}:
                result["filters"]["listing_category"] = segment_lower
                continue

           # B. Check for Metric Slugs (Price, Bed, Bath, STUDIO)
            is_metric = False
            
            if segment_lower == "studio":
                result["filters"]["beds_min"] = 0
                result["filters"]["beds_max"] = 0
                is_metric = True
            
            # Price: p-500k, p-1m-5m
            if segment_lower.startswith("p-"):
                val = segment_lower[2:].replace("k", "000").replace("m", "000000").replace("+", "")
                if "-" in val:
                    try:
                        min_p, max_p = val.split("-")
                        result["filters"]["price_min"] = self._clean_num(min_p)
                        result["filters"]["price_max"] = self._clean_num(max_p)
                    except: pass
                else:
                    result["filters"]["price_min"] = self._clean_num(val)
                is_metric = True

            # Bedrooms: 3-bed, 3-bedroom, 3-to-5-bedroom
            elif re.search(r"(studio|\d+)(?:-to-(\d+))?-bed", segment_lower):
                bed_match = re.search(r"(studio|\d+)(?:-to-(\d+))?-bed", segment_lower)
                
                # Group 1 is either 'studio' or the minimum number
                min_val = bed_match.group(1)
                result["filters"]["beds_min"] = 0 if min_val == "studio" else int(min_val)
                
                # Group 2 is the max value (if a range is present)
                if bed_match.group(2):
                    result["filters"]["beds_max"] = int(bed_match.group(2))
                    
                is_metric = True

            # Bathrooms: 2-bath, 2-ba
            bath_match = re.search(r"(\d+(?:\.\d+)?)-ba", segment_lower)
            if bath_match:
                result["filters"]["baths_min"] = float(bath_match.group(1))
                is_metric = True
                
            if is_metric:
                continue

            # C. Location & Keyword Heuristic
            if not re.match(r"^\d+$", segment_lower):
                # If Location is NOT set, this is the Location
                if not result["location"]: 
                    result["location"] = segment_lower.replace("-", " ")
                
                # --- FIX: If Location IS set, this is a Filter Keyword ---
                else:
                    # Check for architectural styles (e.g. 'ranch-style-homes')
                    style_match = re.match(r"^(.*?)-style-homes$", segment_lower)
                    if style_match:
                        result["filters"]["architectural_style"] = style_match.group(1)
                    else:
                        # Otherwise, treat as a generic keyword (e.g. 'fireplace', 'pool')
                        result["filters"]["keywords"].append(segment_lower)

        # --- 2. QUERY PARAM EXTRACTION (Overrides Path) ---
        qs = parse_qs(parsed.query)
        
        # Mapping of URL Param -> Internal Filter Key
        numeric_map = {
            "price-min": "price_min", "price-max": "price_max",
            "beds-min": "beds_min",   "beds-max": "beds_max",
            "bed-min": "beds_min",    "bed-max": "beds_max",
            "baths-min": "baths_min", "bath-min": "baths_min",
            "baths-max": "baths_max", "bath-max": "baths_max",
            "sfmin": "sqft_min",      "sfmax": "sqft_max",
            "yb-min": "year_built_min", "yb-max": "year_built_max",
            "gsr-min": "School_Rating_min", "gsr-max": "School_Rating_max",
            "st-min": "stories_min",
            "parking": "parking_spots",
            "ls-min": "lot_size_min",
            "pp-min": "price_per_sqft_min", "pp-max": "price_per_sqft_max",
            "property_type": "property_type_id", # Query params use IDs (e.g. 4, 16)
            "listing_type": "listing_type_id"
        }

        for url_key, filter_key in numeric_map.items():
            if url_key in qs:
                # We store these as strings or numbers depending on cleaning
                # For IDs (property_type), we keep them as is (comma separated strings)
                if "type" in url_key:
                     result["filters"][filter_key] = qs[url_key][0]
                else:
                     result["filters"][filter_key] = self._clean_num(qs[url_key][0])

        # Amenities and Sort Keys
        exact_matches = ["am", "sk", "bb"]
        for key in exact_matches:
            if key in qs:
                result["filters"][key] = qs[key][0]

        return result

    def _clean_num(self, val: str) -> int:
        """
        Robustly cleans numbers strings like '$500,000+', '3000sf', '3+'.
        """
        try:
            # Keep only digits and dots
            clean = re.sub(r"[^\d.]", "", str(val))
            return int(float(clean))
        except:
            return 0

    def _urls_match(self, agent_url: str, gt_url: str) -> Tuple[bool, Dict]:
        agent_parts = self._parse_homes_url(agent_url)
        gt_parts = self._parse_homes_url(gt_url)
        
        details = {
            "agent_parsed": agent_parts,
            "gt_parsed": gt_parts,
            "mismatches": []
        }

        # Check Location
        if self.strict_location and gt_parts["location"]:
            a_loc = agent_parts["location"] or ""
            g_loc = gt_parts["location"] or ""
            # Looser check: pass if one is a substring of the other
            if g_loc not in a_loc and a_loc not in g_loc:
                details["mismatches"].append({
                    "field": "location",
                    "agent": a_loc,
                    "expected": g_loc
                })
                return False, details

        # Check Filters
        if self.strict_filters:
            for key, expected_val in gt_parts["filters"].items():
                agent_val = agent_parts["filters"].get(key)
                
                # 1. Handle Keywords List (Order-Independent)
                if key == "keywords":
                    if not expected_val: 
                        continue
                    agent_set = set(agent_val or [])
                    expected_set = set(expected_val)
                    if not expected_set.issubset(agent_set):
                        details["mismatches"].append({
                            "field": "keywords",
                            "agent": agent_val,
                            "expected": expected_val
                        })
                        return False, details
                    continue

                # 2. Handle Comma-Separated ID Strings (Order-Independent)
                # Apply this to amenities, property types, and listing types
                if key in {"am", "property_type_id", "listing_type_id"} and isinstance(expected_val, str):
                    expected_set = set(expected_val.split(","))
                    # Ensure agent_val is a string before splitting, handle None gracefully
                    agent_set = set(str(agent_val).split(",")) if agent_val else set()
                    
                    # Using exact set match (ignores order). 
                    # Change to expected_set.issubset(agent_set) if you want to allow extra agent filters.
                    if expected_set != agent_set:
                        details["mismatches"].append({
                            "field": key,
                            "agent": agent_val,
                            "expected": expected_val
                        })
                        return False, details
                    continue

                # 3. Default Strict Equality for all other values (Numbers, simple strings)
                if agent_val != expected_val:
                    details["mismatches"].append({
                        "field": key,
                        "agent": agent_val,
                        "expected": expected_val
                    })
                    return False, details

        return True, details
    
def generate_task_config(
    url: str,
    task: str,
    location: str,
    timezone: str,
    gt_urls: list[list[str]],
) -> BaseTaskConfig:
    tz_info = ZoneInfo(timezone)
    timestamp = int(datetime.now(tz_info).timestamp())
    user_metadata = UserMetadata(location=location, timezone=timezone, timestamp=timestamp)

    eval_target = get_import_path(HomesUrlMatch)
    eval_config = {"_target_": eval_target, "gt_urls": gt_urls}

    return BaseTaskConfig(url=url, task=task, user_metadata=user_metadata, eval_config=eval_config)