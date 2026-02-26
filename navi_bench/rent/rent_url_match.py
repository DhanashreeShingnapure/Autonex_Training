"""
Rent.com URL Match Verifier

Parses Rent.com's unique underscore-separated path slugs.
Correctly extracts state, city, property types, beds, baths, prices, and amenities.
"""

import re
from typing import Any, Dict, Optional, Tuple, List, Union
from urllib.parse import parse_qs, urlparse
from pydantic import BaseModel
from datetime import datetime
from zoneinfo import ZoneInfo
from navi_bench.base import BaseMetric, BaseTaskConfig, UserMetadata, get_import_path


class RentVerifierResult(BaseModel):
    score: float
    match: bool
    agent_url: str
    ground_truth_url: str
    details: dict


class RentUrlMatch(BaseMetric):
    """
    Universal Rent.com Verifier.
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

    async def compute(self) -> RentVerifierResult:
        if not self._agent_url:
            return RentVerifierResult(
                score=0.0, match=False, agent_url="", 
                ground_truth_url=self.gt_urls[0], 
                details={"error": "No agent URL provided"}
            )
        
        best_details = {}
        for gt_url in self.gt_urls:
            match, details = self._urls_match(self._agent_url, gt_url)
            if match:
                return RentVerifierResult(
                    score=1.0, match=True, agent_url=self._agent_url,
                    ground_truth_url=gt_url, details=details
                )
            best_details = details

        return RentVerifierResult(
            score=0.0, match=False, agent_url=self._agent_url,
            ground_truth_url=self.gt_urls[0], details=best_details
        )

    def _parse_rent_url(self, url: str) -> Dict[str, Any]:
        """
        Parses filters and locations from a Rent.com URL.
        """
        # We use sets temporarily to avoid duplicates
        property_types = set()
        beds = set()
        baths = set()
        amenities = set()
        
        result = {
            "location": None,
            "filters": {}
        }

        if not url:
            return result

        parsed = urlparse(url)
        path_segments = [s for s in parsed.path.split("/") if s]
        
        if not path_segments:
            return result

        # --- 1. STATE & CITY PARSING ---
        # Format usually is: /state/city[-property_type]/filter1_filter2
        state = ""
        city_raw = ""
        filters_str = ""

        if len(path_segments) == 1:
            state = path_segments[0]
        elif len(path_segments) == 2:
            state = path_segments[0]
            city_raw = path_segments[1]
        elif len(path_segments) >= 3:
            state = path_segments[0]
            city_raw = path_segments[1]
            filters_str = path_segments[2] # The underscore string

        # Clean city and check for attached property types (e.g. 'denver-houses')
        if city_raw:
            city_lower = city_raw.lower()
            txn_match = re.match(r"^(.*?)-(apartments|houses|townhouses|condos)$", city_lower)
            if txn_match:
                city_clean = txn_match.group(1).replace("-", " ")
                property_types.add(txn_match.group(2))
                result["location"] = f"{state.replace('-', ' ').lower()} {city_clean}"
            else:
                result["location"] = f"{state.replace('-', ' ').lower()} {city_lower.replace('-', ' ')}"
        elif state:
             result["location"] = state.replace('-', ' ').lower()

        # --- 2. UNDERSCORE FILTER PARSING ---
        if filters_str:
            chunks = filters_str.lower().split("_")
            for chunk in chunks:
                if chunk in {"apartments", "townhouses", "condos", "houses"}:
                    property_types.add(chunk)
                elif chunk.startswith("max-price-"):
                    result["filters"]["price_max"] = self._clean_num(chunk.split("-")[-1])
                elif chunk.startswith("min-price-"):
                    result["filters"]["price_min"] = self._clean_num(chunk.split("-")[-1])
                elif chunk.startswith("sqft-min-"):
                    result["filters"]["sqft_min"] = self._clean_num(chunk.split("-")[-1])
                elif chunk == "studio":
                    beds.add(0)
                elif re.match(r"(\d+)-bedroom", chunk):
                    beds.add(int(re.match(r"(\d+)-bedroom", chunk).group(1)))
                elif re.match(r"(\d+)-bathroom", chunk):
                    baths.add(int(re.match(r"(\d+)-bathroom", chunk).group(1)))
                elif chunk.startswith("sort-"):
                    result["filters"]["sort"] = chunk
                else:
                    # Treat anything else as an amenity or keyword (e.g., 'air-conditioning')
                    amenities.add(chunk)

        # --- 3. QUERY PARAM EXTRACTION ---
        qs = parse_qs(parsed.query)
        
        numeric_map = {
            "min_price": "price_min", "max_price": "price_max",
        }
        for url_key, filter_key in numeric_map.items():
            if url_key in qs:
                result["filters"][filter_key] = self._clean_num(qs[url_key][0])

        if "property-type" in qs:
            for pt in qs["property-type"][0].split(","):
                property_types.add(pt.strip().lower())

        # Save sets as sorted lists so they are JSON serializable
        if property_types: result["filters"]["property_types"] = sorted(list(property_types))
        if beds: result["filters"]["beds"] = sorted(list(beds))
        if baths: result["filters"]["baths"] = sorted(list(baths))
        if amenities: result["filters"]["amenities"] = sorted(list(amenities))

        return result

    def _clean_num(self, val: str) -> int:
        try:
            clean = re.sub(r"[^\d.]", "", str(val))
            return int(float(clean))
        except:
            return 0

    def _urls_match(self, agent_url: str, gt_url: str) -> Tuple[bool, Dict]:
        agent_parts = self._parse_rent_url(agent_url)
        gt_parts = self._parse_rent_url(gt_url)
        
        details = {
            "agent_parsed": agent_parts,
            "gt_parsed": gt_parts,
            "mismatches": []
        }

        # Check Location
        if self.strict_location and gt_parts["location"]:
            a_loc = agent_parts["location"] or ""
            g_loc = gt_parts["location"] or ""
            # Substring matching for safety
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
                
                # Sets/Lists Comparison (Subset logic: Agent must contain everything GT asked for)
                if isinstance(expected_val, list):
                    if not expected_val:
                        continue
                    expected_set = set(expected_val)
                    agent_set = set(agent_val) if agent_val else set()
                    
                    if not expected_set.issubset(agent_set):
                        details["mismatches"].append({
                            "field": key,
                            "agent": sorted(list(agent_set)),
                            "expected": sorted(list(expected_set))
                        })
                        return False, details
                    continue

                # Scalar Comparison (Prices, Sorts, etc)
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

    eval_target = get_import_path(RentUrlMatch)
    eval_config = {"_target_": eval_target, "gt_urls": gt_urls}

    return BaseTaskConfig(url=url, task=task, user_metadata=user_metadata, eval_config=eval_config)