#!/usr/bin/env python
"""
Redfin Property Search Verification Demo

Human-in-the-loop verification system for Redfin property searches.
This demo tracks navigation via URL matching only (no JavaScript scraping).

Features:
- Real-time URL tracking during navigation
- Stealth browser configuration (anti-detection)
- Filter comparison with detailed diff output
- Multiple search scenarios (city, rental, amenity filters)

Author: NaviBench Team
"""

import asyncio
import sys
from dataclasses import dataclass, field

from playwright.async_api import async_playwright
from loguru import logger

# Import our evaluator
from navi_bench.redfin.redfin_url_match import (
    RedfinUrlMatch,
    generate_task_config,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class BrowserConfig:
    """Browser launch configuration for stealth operation."""
    headless: bool = False
    viewport_width: int = 1366
    viewport_height: int = 768
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    locale: str = "en-US"
    
    # Anti-detection arguments
    launch_args: list = field(default_factory=lambda: [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--start-maximized",
        "--no-sandbox",
    ])


@dataclass
class TaskScenario:
    """Defines a Redfin search verification scenario."""
    task_id: str
    name: str
    description: str
    task_prompt: str
    gt_url: str  # Ground truth URL
    location: str
    timezone: str
    start_url: str = "https://www.redfin.com"
    tags: list = field(default_factory=list)
    
    def __post_init__(self):
        """Validate scenario configuration."""
        assert self.task_id, "task_id is required"
        assert self.gt_url, "gt_url is required"


# =============================================================================
# TASK SCENARIOS - Define your test cases here
# =============================================================================

SCENARIOS: list[TaskScenario] = [
    # Bellevue, WA - Multi-filter search
    TaskScenario(
        task_id="redfin/city/bellevue/001",
        name="Bellevue Single-Story Homes",
        description="Search for single-story homes in Bellevue with specific criteria",
        task_prompt=(
            "Search for single-story homes in Bellevue, WA with 3-4 bedrooms, "
            "under $2 million, built after 1980. Focus on homes listed in the past week."
        ),
        gt_url=(
            "https://www.redfin.com/city/1387/WA/Bellevue/filter/"
            "max-beds=4,max-price=2m,min-beds=3,min-year-built=1980,"
            "min-stories=1,property-type=house,max-days-on-market=1wk"
        ),
        location="Bellevue, WA, United States",
        timezone="America/Los_Angeles",
        tags=["bellevue", "single-story", "house", "filters"],
    ),
    
    # Seattle Rentals
    TaskScenario(
        task_id="redfin/city/seattle/rentals/001",
        name="Seattle Pet-Friendly Rentals",
        description="Search for pet-friendly rental apartments in Seattle",
        task_prompt=(
            "Find rental apartments in Seattle, WA that allow dogs. "
            "Looking for 2+ bedrooms, under $3,500/month, with in-unit washer/dryer."
        ),
        gt_url=(
            "https://www.redfin.com/city/16163/WA/Seattle/apartments-for-rent/filter/"
            "min-beds=2,max-price=3500,dogs-allowed,washer-dryer"
        ),
        location="Seattle, WA, United States",
        timezone="America/Los_Angeles",
        tags=["seattle", "rental", "pet-friendly", "apartment"],
    ),
    
    # San Francisco Condos
    TaskScenario(
        task_id="redfin/city/sanfrancisco/001",
        name="San Francisco Luxury Condos",
        description="Search for luxury condos in San Francisco",
        task_prompt=(
            "Search for condos in San Francisco, CA priced between $1M and $3M. "
            "Must have 2+ beds, 2+ baths, and parking. Include recently sold properties."
        ),
        gt_url=(
            "https://www.redfin.com/city/17151/CA/San-Francisco/filter/"
            "property-type=condo,min-price=1m,max-price=3m,min-beds=2,"
            "min-baths=2,has-parking,include=sold-3mo"
        ),
        location="San Francisco, CA, United States",
        timezone="America/Los_Angeles",
        tags=["san-francisco", "condo", "luxury", "parking"],
    ),
    
    # Austin Texas - New Construction
    TaskScenario(
        task_id="redfin/city/austin/001",
        name="Austin New Construction",
        description="Search for new construction homes in Austin",
        task_prompt=(
            "Find newly built homes in Austin, TX. Looking for houses built after 2022, "
            "3+ bedrooms, under $800k, with a pool."
        ),
        gt_url=(
            "https://www.redfin.com/city/30818/TX/Austin/filter/"
            "property-type=house,min-beds=3,max-price=800k,"
            "min-year-built=2022,pool-type=either"
        ),
        location="Austin, TX, United States",
        timezone="America/Chicago",
        tags=["austin", "new-construction", "pool", "house"],
    ),
    
    # New York Waterfront
    TaskScenario(
        task_id="redfin/city/newyork/001",
        name="NYC Waterfront Properties",
        description="Search for waterfront properties in New York",
        task_prompt=(
            "Search for waterfront properties in New York, NY. "
            "Looking for any property type with a view, priced over $2M."
        ),
        gt_url=(
            "https://www.redfin.com/city/30749/NY/New-York/filter/"
            "min-price=2m,water-front,has-view"
        ),
        location="New York, NY, United States",
        timezone="America/New_York",
        tags=["new-york", "waterfront", "view", "luxury"],
    ),
    
    # Denver Multi-Story Filter Test
    TaskScenario(
        task_id="redfin/city/denver/stories/001",
        name="Denver Multi-Story Homes",
        description="Search for homes with specific story count range",
        task_prompt=(
            "Find houses in Denver, CO that are 2-3 stories tall. "
            "Minimum 3 bedrooms, under $1.5M, built after 2000."
        ),
        gt_url=(
            "https://www.redfin.com/city/5155/CO/Denver/filter/"
            "property-type=house,min-beds=3,max-price=1.5m,"
            "min-stories=2,max-stories=3,min-year-built=2000"
        ),
        location="Denver, CO, United States",
        timezone="America/Denver",
        tags=["denver", "stories", "multi-story", "house"],
    ),
    
    # Bellevue Max-Stories Only Test
    TaskScenario(
        task_id="redfin/city/bellevue/stories/001",
        name="Bellevue Max-Stories Only",
        description="Search with only max-stories filter (single story homes)",
        task_prompt=(
            "Find single-story houses in Bellevue, WA. "
            "3-4 bedrooms, under $2M. Only 1-story homes."
        ),
        gt_url=(
            "https://www.redfin.com/city/1387/WA/Bellevue/filter/"
            "property-type=house,max-price=2M,min-beds=3,max-beds=4,max-stories=1"
        ),
        location="Bellevue, WA, United States",
        timezone="America/Los_Angeles",
        tags=["bellevue", "stories", "single-story", "max-only"],
    ),
    
    # Portland Exact Stories Test (min=max)
    TaskScenario(
        task_id="redfin/city/portland/stories/001",
        name="Portland Exact 2-Story Homes",
        description="Search with min-stories=max-stories (exactly 2 stories)",
        task_prompt=(
            "Find exactly 2-story houses in Portland, OR. "
            "4+ bedrooms, under $1M. Must be exactly 2 stories."
        ),
        gt_url=(
            "https://www.redfin.com/city/30772/OR/Portland/filter/"
            "property-type=house,min-beds=4,max-price=1m,"
            "min-stories=2,max-stories=2"
        ),
        location="Portland, OR, United States",
        timezone="America/Los_Angeles",
        tags=["portland", "stories", "exact-stories", "min-equals-max"],
    ),
]


# =============================================================================
# BROWSER MANAGER - Stealth browser configuration
# =============================================================================

class BrowserManager:
    """Manages browser lifecycle with stealth configuration."""
    
    def __init__(self, config: BrowserConfig = None):
        self.config = config or BrowserConfig()
        self.browser = None
        self.context = None
        self.page = None
    
    async def launch(self, playwright) -> tuple:
        """Launch browser with stealth configuration."""
        self.browser = await playwright.chromium.launch(
            headless=self.config.headless,
            args=self.config.launch_args,
        )
        
        self.context = await self.browser.new_context(
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height
            },
            user_agent=self.config.user_agent,
            locale=self.config.locale,
        )
        
        # Anti-detection scripts
        await self.context.add_init_script("""
            // Hide webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Override chrome.runtime
            window.chrome = { runtime: {} };
            
            // Override permissions query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        self.page = await self.context.new_page()
        
        return self.browser, self.context, self.page
    
    async def close(self) -> None:
        """Close browser and cleanup."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()


# =============================================================================
# RESULT REPORTER - Format and display results
# =============================================================================

class ResultReporter:
    """Formats and displays verification results."""
    
    @staticmethod
    def print_header(scenario: TaskScenario) -> None:
        """Print task header."""
        print("\n" + "=" * 80)
        print(f"REDFIN PROPERTY SEARCH VERIFICATION: {scenario.name}")
        print("=" * 80)
        print(f"Task ID:     {scenario.task_id}")
        print(f"Location:    {scenario.location}")
        print(f"Timezone:    {scenario.timezone}")
        print("-" * 80)
        print(f"TASK: {scenario.task_prompt}")
        print("-" * 80)
        print(f"Ground Truth URL:")
        print(f"  {scenario.gt_url[:80]}...")
        print("=" * 80)
    
    @staticmethod
    def print_instructions() -> None:
        """Print user instructions."""
        print("\n" + "-" * 40)
        print("INSTRUCTIONS:")
        print("-" * 40)
        print("1. Use the Redfin website to complete the search")
        print("2. Apply all the required filters")
        print("3. The system tracks your URL automatically")
        print("4. Press ENTER when ready to see verification results")
        print("-" * 40 + "\n")
    
    @staticmethod
    def print_result(
        result, 
        evaluator: RedfinUrlMatch, 
        scenario: TaskScenario,
        final_url: str
    ) -> None:
        """Print verification result with URL comparison."""
        print("\n" + "=" * 80)
        print("VERIFICATION RESULT")
        print("=" * 80)
        
        score_pct = result.score * 100
        status = "✅ PASS" if result.score >= 1.0 else "❌ FAIL"
        
        print(f"Status:  {status}")
        print(f"Score:   {score_pct:.0f}%")
        print("-" * 80)
        
        if result.score >= 1.0:
            print("Your URL matches the expected search criteria!")
        else:
            # Parse both URLs for comparison
            gt_parsed = evaluator._parse_redfin_url(scenario.gt_url)
            agent_parsed = evaluator._parse_redfin_url(final_url)
            
            print("URL COMPARISON:")
            print("-" * 80)
            
            # Location comparison
            print(f"\n📍 LOCATION:")
            print(f"   Expected: {gt_parsed['location_type']}/{gt_parsed['state']}/{gt_parsed['location']}")
            print(f"   Got:      {agent_parsed['location_type']}/{agent_parsed['state']}/{agent_parsed['location']}")
            
            loc_match = (
                gt_parsed['location_type'] == agent_parsed['location_type'] and
                gt_parsed['state'] == agent_parsed['state'] and
                gt_parsed['location'] == agent_parsed['location']
            )
            print(f"   Status:   {'✓ Match' if loc_match else '✗ Mismatch'}")
            
            # Rental type comparison
            print(f"\n🏠 LISTING TYPE:")
            print(f"   Expected: {'Rental' if gt_parsed['is_rental'] else 'For Sale'}")
            print(f"   Got:      {'Rental' if agent_parsed['is_rental'] else 'For Sale'}")
            rental_match = gt_parsed['is_rental'] == agent_parsed['is_rental']
            print(f"   Status:   {'✓ Match' if rental_match else '✗ Mismatch'}")
            
            # Filter comparison
            gt_filters = gt_parsed['filters']
            agent_filters = agent_parsed['filters']
            
            missing = set(gt_filters.keys()) - set(agent_filters.keys())
            extra = set(agent_filters.keys()) - set(gt_filters.keys())
            wrong = {k for k in agent_filters if k in gt_filters and agent_filters[k] != gt_filters[k]}
            matched = set(gt_filters.keys()) & set(agent_filters.keys()) - wrong
            
            print(f"\n🔧 FILTERS:")
            
            if matched:
                print(f"\n   ✓ Correct filters ({len(matched)}):")
                for f in sorted(matched):
                    print(f"     - {f} = {gt_filters[f]}")
            
            if wrong:
                print(f"\n   ✗ Wrong values ({len(wrong)}):")
                for f in sorted(wrong):
                    print(f"     - {f}")
                    print(f"       Expected: {gt_filters[f]}")
                    print(f"       Got:      {agent_filters[f]}")
            
            if missing:
                print(f"\n   ✗ Missing filters ({len(missing)}):")
                for f in sorted(missing):
                    print(f"     - {f} = {gt_filters[f]}")
            
            if extra:
                print(f"\n   ⚠ Extra filters ({len(extra)}):")
                for f in sorted(extra):
                    print(f"     - {f} = {agent_filters[f]}")
        
        print("\n" + "=" * 80)
        print("URLS:")
        print("-" * 80)
        print(f"Expected: {scenario.gt_url}")
        print(f"Got:      {final_url}")
        print("=" * 80 + "\n")
    
    @staticmethod
    def print_summary(results: list) -> None:
        """Print summary of all results."""
        if not results:
            return
        
        print("\n" + "=" * 80)
        print("SESSION SUMMARY")
        print("=" * 80)
        
        total = len(results)
        passed = sum(1 for r in results if r["score"] >= 1.0)
        
        print(f"Total Scenarios:  {total}")
        print(f"Passed:           {passed}")
        print(f"Success Rate:     {passed/total*100:.1f}%")
        
        print("-" * 80)
        for r in results:
            status = "✅" if r["score"] >= 1.0 else "❌"
            print(f"  {status} {r['task_id']}")
        
        print("=" * 80 + "\n")


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_scenario(scenario: TaskScenario) -> dict:
    """Run a single verification scenario."""
    
    # Create evaluator
    task_config = generate_task_config(
        task=scenario.task_prompt,
        gt_url=[scenario.gt_url],
        location=scenario.location,
        timezone=scenario.timezone,
        url=scenario.start_url,
    )
    
    evaluator = RedfinUrlMatch(gt_url=scenario.gt_url)
    reporter = ResultReporter()
    
    # Display task info
    reporter.print_header(scenario)
    reporter.print_instructions()
    
    input("Press ENTER to launch browser...")
    
    async with async_playwright() as p:
        # Launch browser
        browser_mgr = BrowserManager()
        browser, context, page = await browser_mgr.launch(p)
        
        # Initialize evaluator
        await evaluator.reset()
        
        # Navigate to start URL
        logger.info(f"Opening {scenario.start_url}")
        await page.goto(scenario.start_url, timeout=60000, wait_until="domcontentloaded")
        
        # Track initial URL
        await evaluator.update(url=page.url)
        
        # Set up navigation tracking
        async def on_navigation():
            try:
                current_url = page.url
                await evaluator.update(url=current_url)
                # Only print if it's a Redfin URL
                if "redfin.com" in current_url:
                    display_url = current_url[:80] + "..." if len(current_url) > 80 else current_url
                    print(f"📍 URL: {display_url}")
            except Exception as e:
                logger.debug(f"Navigation tracking error: {e}")
        
        page.on("framenavigated", lambda frame: asyncio.create_task(on_navigation()))
        
        print("\n🌐 Browser ready - you are now the agent!")
        print("Use Redfin filters to complete the search.\n")
        
        # Wait for user completion
        await asyncio.to_thread(
            input, 
            "Press ENTER when you've completed the task... "
        )
        
        # Get final URL
        final_url = page.url
        
        # Final evaluation
        await evaluator.update(url=final_url)
        result = await evaluator.compute()
        
        # Close browser
        await browser_mgr.close()
    
    # Display results
    reporter.print_result(result, evaluator, scenario, final_url)
    
    return {
        "task_id": scenario.task_id,
        "score": result.score,
        "final_url": final_url,
    }


async def run_interactive_menu() -> None:
    """Run interactive scenario selection menu."""
    
    print("\n" + "=" * 80)
    print("REDFIN PROPERTY SEARCH VERIFICATION SYSTEM")
    print("=" * 80)
    print("\nAvailable scenarios:\n")
    
    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"  [{i}] {scenario.name}")
        print(f"      {scenario.description}")
        print()
    
    print(f"  [A] Run all scenarios")
    print(f"  [Q] Quit")
    print()
    
    choice = input("Select scenario (1-{}, A, or Q): ".format(len(SCENARIOS))).strip().upper()
    
    results = []
    
    if choice == "Q":
        print("Goodbye!")
        return
    
    elif choice == "A":
        for scenario in SCENARIOS:
            result = await run_scenario(scenario)
            results.append(result)
            
            if scenario != SCENARIOS[-1]:
                cont = input("\nContinue to next scenario? (y/n): ").strip().lower()
                if cont != "y":
                    break
    
    elif choice.isdigit() and 1 <= int(choice) <= len(SCENARIOS):
        idx = int(choice) - 1
        result = await run_scenario(SCENARIOS[idx])
        results.append(result)
    
    else:
        print("Invalid choice. Please try again.")
        return
    
    # Print summary
    ResultReporter.print_summary(results)


async def main():
    """Main entry point."""
    
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    try:
        await run_interactive_menu()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye!")
    except Exception as e:
        logger.exception(f"Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
