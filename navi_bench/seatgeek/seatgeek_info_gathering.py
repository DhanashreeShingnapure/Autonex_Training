import functools
import itertools
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from loguru import logger
from playwright.async_api import Page
from pydantic import BaseModel
from typing_extensions import TypedDict

from navi_bench.base import BaseMetric, BaseTaskConfig, UserMetadata, get_import_path
from navi_bench.dates import initialize_user_metadata

class SingleCandidateQuery(TypedDict, total=False):
    """ Single candidate query """
    event_name: str | None
    eventType: str | None
    date: str | None
    time: str | None
    venue: str | None
    city: str | None
    quantityMin: int | None
    highPrice: float | None
    lowPrice: float | None
    section: str | None
    row: str | None
    dealScore: int | None

class MultiCandidateQuery(TypedDict, total=False):
    """ Multi candidate query """
    event_names: list[str] | None
    eventTypes: list[str] | None
    dates: list[str] | None
    times: list[str] | None
    venues: list[str] | None
    cities: list[str] | None
    quantityMin: int | None
    highPrice: float | None
    lowPrice: float | None
    sections: list[str] | None
    rows: list[str] | None
    dealScore: int | None

class InputDict(TypedDict, total=False):
    """Input for update method."""
    page: Page

class InfoDict(TypedDict, total=False):
    """Scraped event information from JavaScript"""
    url: str
    source: str
    eventName: str
    eventType: str
    
    date: str
    time: str
    venue: str
    city: str
    
    section: str
    row: str
    
    pricePerTicket: float
    currency: str
    dealScore: int
    
    availabilityStatus: str
    info: str
    
    pageType: str
    category: str

class FinalResult(BaseModel):
    """Final verification result."""
    score: float
    n_queries: int
    n_covered: int
    queries: list[list[MultiCandidateQuery]]
    is_query_covered: list[bool]

class SeatGeekInfoGathering(BaseMetric):
    """Gather event ticket information from seatgeek to evaluate query coverage."""
    def __init__(self, queries: list[list[MultiCandidateQuery]]) -> None:
        super().__init__()
        self.queries = queries
        self._all_infos: list[list[InfoDict]] = []
        self._is_query_covered: list[bool] = [False] * len(queries)
        self._unavailable_evidences: list[list[list[InfoDict]]] = [
            [[] for _ in alternative_conditions] for alternative_conditions in queries
        ]
        self._navigation_stack: list[dict] = [] 
        self._tracked_pages: set = set()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(queries={self.queries})"

    @functools.cached_property
    def js_script(self) -> str:
        """Load the JavaScript scraper."""
        with open(Path(__file__).parent / "seatgeek_info_gathering.js", "r") as f:
            return f.read()

    async def reset(self) -> None:
        self._all_infos = []
        self._is_query_covered = [False] * len(self.queries)
        self._unavailable_evidences = [[[] for _ in alternative_conditions] for alternative_conditions in self.queries]
        self._navigation_stack = []
        self._tracked_pages = set()
    
    def attach_to_context(self, context) -> None:
        """Attach automatic navigation tracking to a browser context."""
        import asyncio
        
        async def track_page(page) -> None:
            page_id = id(page)
            if page_id in self._tracked_pages:
                return
            self._tracked_pages.add(page_id)
            
            async def on_frame_navigated(frame):
                if frame != page.main_frame:
                    return
                try:
                    logger.info(f"[NAV] TM: {page.url[:80]}...")
                    await self.update(page=page)
                except Exception as e:
                    logger.warning(f"Update failed: {e}")
            
            page.on("framenavigated", lambda f: asyncio.create_task(on_frame_navigated(f)))
            logger.info(f"Tracking attached to TM page: {page.url[:60]}...")
        
        for page in context.pages:
            import asyncio
            asyncio.create_task(track_page(page))
        
        context.on("page", lambda p: asyncio.create_task(track_page(p)))

    async def update(self, **kwargs) -> None:
        """Update with new page information, accommodating Ticketmaster's DOM."""
        inputs: InputDict = kwargs
        page = inputs["page"]
        url = page.url
        
        infos: list[InfoDict] = await page.evaluate(self.js_script)
        
        # =====================================================================
        # DEBUG: SCRAPING STAGE BREAKDOWN
        # =====================================================================
        logger.info("▼▼▼ SCRAPING STAGE BREAKDOWN ▼▼▼")

        if not infos:
            logger.warning("No data scraped at all from this page!")
        else:  
            sources = {}
            for info in infos:
                src = info.get("source", "unknown_source")
                if src not in sources:
                    sources[src] = []
                sources[src].append(info)
                
            for src, items in sources.items():
                logger.info(f"  [{src.upper()}] -> Found {len(items)} items")
                for i, item in enumerate(items[:3]):
                    name = str(item.get("eventName", "Unknown")).title()[:35]
                    price = item.get("price", "N/A")
                    date = item.get("date", "N/A")
                    section = item.get("section", "N/A")
                    row = item.get("row", "N/A")
                    logger.info(f"      {i+1}. {name} | Date: {date} | Price: ${price} | Sec: {section}, Row: {row}")
                
                if len(items) > 3:
                    logger.info(f"      ... and {len(items) - 3} more items from {src}.")
        logger.info("▲▲▲==========================▲▲▲")
        # =====================================================================

        # 4. Filter and Stack logic
        page_type = infos[0].get("pageType", "unknown") if infos else "unknown"

        logger.info(f"Ticketmaster Gathering -> Type: {page_type} | Infos: {len(infos)}")
        self._all_infos.append(infos)
        
        base_url = url.split("?")[0]
        existing_idx = next((i for i, e in enumerate(self._navigation_stack) 
                           if e["base_url"] == base_url and e["page_type"] == page_type), None)
        
        page_entry = {
            "url": url,
            "base_url": base_url,
            "page_type": page_type,
            "infos": infos,
        }
        
        if existing_idx is not None:
            self._navigation_stack[existing_idx] = page_entry
        else:
            self._navigation_stack.append(page_entry)

    async def compute(self) -> FinalResult:
        """Compute final coverage score by walking backwards through navigation stack."""
        event_listing_found = False
        fallback_infos: list[InfoDict] = []
        
        # Walk backwards
        for page_visit in reversed(self._navigation_stack):
            page_type = page_visit["page_type"]
            page_infos = page_visit["infos"]
                
            if page_type == "event_listing" and not event_listing_found:
                event_listing_found = True
                for i, alternative_conditions in enumerate(self.queries):
                    if self._is_query_covered[i]:
                        continue
                    for info in page_infos:
                        if self._check_alternative_conditions(i, alternative_conditions, info):
                            self._is_query_covered[i] = True
                            break
                break
            
            elif page_type in ["event_category", "search_results"]:
                fallback_infos.extend(page_infos)
        
        # Fallback for sold-out/discovery
        if not event_listing_found and fallback_infos:
            for i, alternative_conditions in enumerate(self.queries):
                if self._is_query_covered[i]:
                    continue
                for info in fallback_infos:
                    if self._check_alternative_conditions(i, alternative_conditions, info):
                        self._is_query_covered[i] = True
                        break
        
        # Handle exhaustion
        for i, alternative_conditions in enumerate(self.queries):
            if self._is_query_covered[i]:
                continue
            for j, alternative_condition in enumerate(alternative_conditions):
                if not self._is_exhausted(alternative_condition, self._unavailable_evidences[i][j]):
                    break
            else:
                self._is_query_covered[i] = True

        n_queries = len(self.queries)
        n_covered = sum(self._is_query_covered)
        return FinalResult(
            score=n_covered / max(n_queries, 1),
            n_queries=n_queries,
            n_covered=n_covered,
            queries=self.queries,
            is_query_covered=self._is_query_covered,
        )

    def _check_alternative_conditions(
        self, i: int, alternative_conditions: list[MultiCandidateQuery], info: InfoDict
    ) -> bool:
        for j, alternative_condition in enumerate(alternative_conditions):
            evidences = self._unavailable_evidences[i][j]
            if self._check_multi_candidate_query(alternative_condition, info, evidences):
                return True
        return False

    @classmethod
    def _check_multi_candidate_query(
        cls, query: MultiCandidateQuery, info: InfoDict, evidences: list[InfoDict]
    ) -> bool:
        
        # Text based matches
        if q_names := query.get("event_names"):
            if not any(q.lower() in info.get("eventName", "").lower() for q in q_names):
                return False

        if q_venues := query.get("venues"):
            if not any(q.lower() in info.get("venue", "").lower() for q in q_venues):
                return False

        if q_cities := query.get("cities"):
            city = (info.get("city") or "").lower()
            if not city or not any(c.lower() in city for c in q_cities):
                return False

        # Numeric and Filter constraints
        if quantityMin := query.get("quantityMin"):
            if info.get("ticketCount", 0) < quantityMin:
                return False

        return True

    @classmethod
    def _check_single_candidate_query(cls, query: SingleCandidateQuery, info: InfoDict) -> bool:
        if (q_name := query.get("event_name")) and info.get("eventName", "").lower() != q_name.lower():
            return False
        if (q_date := query.get("date")) and info.get("date") != q_date:
            return False
        return True

    @classmethod
    def _is_exhausted(cls, query: MultiCandidateQuery, evidences: list[InfoDict]) -> bool:
        q_names = query.get("event_names") or [None]
        q_dates = query.get("dates") or [None]

        for q_name, q_date in itertools.product(q_names, q_dates):
            if not any(cls._check_single_candidate_query({"event_name": q_name, "date": q_date}, info) for info in evidences):
                return False
        return True

def generate_task_config_deterministic_seatgeek(
    mode: Literal["any", "all"],
    task: str,
    queries: list[list[MultiCandidateQuery]],
    location: str,
    timezone: str,
    timestamp: int | None = None,
    url: str = "https://www.seatgeek.com",
) -> BaseTaskConfig:
    user_metadata = initialize_user_metadata(timezone, location, timestamp)
    eval_config = {
        "_target_": get_import_path(SeatGeekInfoGathering),
        "queries": queries
    }
    return BaseTaskConfig(url=url, task=task, user_metadata=user_metadata, eval_config=eval_config)