import asyncio
import sys
from dataclasses import dataclass, field

from playwright.async_api import async_playwright
from loguru import logger

from navi_bench.seatgeek.seatgeek_info_gathering import (
    SeatGeekInfoGathering,
    generate_task_config_deterministic_seatgeek,
)

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
    
    # Anti-detection arguments (Crucial for Ticketmaster)
    launch_args: list = field(default_factory=lambda: [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--start-maximized",
        "--no-sandbox",
        "--disable-web-security",
    ])

@dataclass
class TaskScenario:
    """Defines a verification task scenario."""
    task_id: str
    name: str
    description: str
    url: str
    task_prompt: str
    queries: list
    location: str
    timezone: str
    eventType: str
    tags: list = field(default_factory=list)
    
    def __post_init__(self):
        """Validate scenario configuration."""
        assert self.task_id, "task_id is required"
        assert self.queries, "queries cannot be empty"

# =============================================================================
# TASK SCENARIOS - Ticketmaster Specific
# =============================================================================

SCENARIOS: list[TaskScenario] = [
    # PRIMARY TASK: General Concert Check
    TaskScenario(
        task_id="seatgeek/eagles-tickets/las-vegas-nevada-sphere-2026-04-11-8-30-pm/concert/18070060",
        name="Eagles Concert - Any Availability",
        description="Search for eagles concert tickets",
        url="https://www.seatgeek.com/",
        task_prompt=(
            "Search for eagles concert tickets. "
            "Find any upcoming eagles event and check ticket availability."
        ),
        queries=[[{
            "event_names": ["eagles"],  
        }]],
        location="United States",
        timezone="America/New_York",
        eventType="concerts",
        tags=["eagles", "concert", "music"],
    ),

    TaskScenario(
        task_id="seatgeek/taylor-swift-tickets/us-any-date/concert",
        name="Taylor Swift Concert - Any Availability",
        description="Search for Taylor Swift concert tickets",
        url="https://www.seatgeek.com/",
        task_prompt=(
            "Search for Taylor Swift concert tickets. "
            "Find any upcoming Taylor Swift event and check ticket availability."
        ),
        queries=[[{
            "event_names": ["taylor swift"],
        }]],
        location="United States",
        timezone="America/New_York",
        eventType="concerts",
        tags=["taylor swift", "concert", "music"],
    ),

    TaskScenario(
        task_id="seatgeek/lakers-tickets/us-any-date/sports",
        name="Los Angeles Lakers Game - Any Availability",
        description="Search for Los Angeles Lakers tickets",
        url="https://www.seatgeek.com/",
        task_prompt=(
            "Search for Los Angeles Lakers game tickets. "
            "Find any upcoming Lakers game and check ticket availability."
        ),
        queries=[[{
            "event_names": ["los angeles lakers"],
        }]],
        location="United States",
        timezone="America/Los_Angeles",
        eventType="nba",
        tags=["lakers", "nba", "basketball"],
    ),

    TaskScenario(
        task_id="seatgeek/cowboys-tickets/us-any-date/sports",
        name="Dallas Cowboys Game - Any Availability",
        description="Search for Dallas Cowboys tickets",
        url="https://www.seatgeek.com/",
        task_prompt=(
            "Search for Dallas Cowboys game tickets. "
            "Find any upcoming Cowboys event and check ticket availability."
        ),
        queries=[[{
            "event_names": ["dallas cowboys"],
        }]],
        location="United States",
        timezone="America/Chicago",
        eventType="nfl",
        tags=["cowboys", "nfl", "football"],
    ),

    TaskScenario(
        task_id="seatgeek/hamilton-tickets/us-any-date/theater",
        name="Hamilton Show - Any Availability",
        description="Search for Hamilton tickets",
        url="https://www.seatgeek.com/",
        task_prompt=(
            "Search for Hamilton theater tickets. "
            "Find any upcoming Hamilton show and check ticket availability."
        ),
        queries=[[{
            "event_names": ["hamilton"],
        }]],
        location="United States",
        timezone="America/New_York",
        eventType="theater",
        tags=["hamilton", "broadway", "theater"],
    ),

    TaskScenario(
        task_id="seatgeek/drake-tickets/us-any-date/concert",
        name="Drake Concert - Any Availability",
        description="Search for Drake concert tickets",
        url="https://www.seatgeek.com/",
        task_prompt=(
            "Search for Drake concert tickets. "
            "Find any upcoming Drake event and check ticket availability."
        ),
        queries=[[{
            "event_names": ["drake"],
        }]],
        location="United States",
        timezone="America/New_York",
        eventType="concerts",
        tags=["drake", "concert", "music"],
    ),

    TaskScenario(
        task_id="seatgeek/ed-sheeran-tickets/us-any-date/concert",
        name="Ed Sheeran Concert - Any Availability",
        description="Search for Ed Sheeran concert tickets",
        url="https://www.seatgeek.com/",
        task_prompt=(
            "Search for Ed Sheeran concert tickets. "
            "Find any upcoming Ed Sheeran event and check ticket availability."
        ),
        queries=[[{
            "event_names": ["ed sheeran"],
        }]],
        location="United States",
        timezone="America/New_York",
        eventType="concerts",
        tags=["ed sheeran", "concert", "music"],
    ),

    TaskScenario(
        task_id="seatgeek/knicks-tickets/us-any-date/sports",
        name="New York Knicks Game - Any Availability",
        description="Search for New York Knicks tickets",
        url="https://www.seatgeek.com/",
        task_prompt=(
            "Search for New York Knicks game tickets. "
            "Find any upcoming Knicks event and check ticket availability."
        ),
        queries=[[{
            "event_names": ["new york knicks"],
        }]],
        location="United States",
        timezone="America/New_York",
        eventType="nba",
        tags=["knicks", "nba", "basketball"],
    ),

    TaskScenario(
        task_id="seatgeek/heat-tickets/us-any-date/sports",
        name="Miami Heat Game - Any Availability",
        description="Search for Miami Heat tickets",
        url="https://www.seatgeek.com/",
        task_prompt=(
            "Search for Miami Heat game tickets. "
            "Find any upcoming Heat event and check ticket availability."
        ),
        queries=[[{
            "event_names": ["miami heat"],
        }]],
        location="United States",
        timezone="America/New_York",
        eventType="nba",
        tags=["heat", "nba", "basketball"],
    ),
    TaskScenario(
        task_id="seatgeek/ufc-tickets/us-any-date/sports",
        name="UFC Event - Any Availability",
        description="Search for UFC event tickets",
        url="https://www.seatgeek.com/",
        task_prompt=(
            "Search for UFC event tickets. "
            "Find any upcoming UFC event and check ticket availability."
        ),
        queries=[[{
            "event_names": ["UFC Event"],
        }]],
        location="United States",
        timezone="America/New_York",
        eventType="mma",
        tags=["ufc", "mma", "fight"],
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
        
        # Anti-detection scripts - highly important for PerimeterX/DataDome
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
            
            // WebGL fingerprint spoofing
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Inc.';
                if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                return getParameter.call(this, parameter);
            };
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
        print(f"SEATGEEK VERIFICATION: {scenario.name}")
        print("=" * 80)
        print(f"Task ID:     {scenario.task_id}")
        print(f"EventType:    {scenario.eventType}")
        print(f"Location:    {scenario.location}")
        print("-" * 80)
        print(f"TASK: {scenario.task_prompt}")
        print("-" * 80)
        print(f"Looking for: {scenario.queries[0][0]}")
        print("=" * 80)
    
    @staticmethod
    def print_instructions() -> None:
        """Print user instructions."""
        print("\n" + "-" * 40)
        print("INSTRUCTIONS:")
        print("-" * 40)
        print("1. Use the Seatgeek website to complete the task")
        print("2. Search for events and navigate to listings")
        print("3. Press ENTER in this terminal when ready to see verification results")
        print("-" * 40 + "\n")
    
    @staticmethod
    def print_result(result, evaluator: SeatGeekInfoGathering, scenario: TaskScenario) -> None:
        """Print verification result with debugging info."""
        print("\n" + "=" * 80)
        print("VERIFICATION RESULT")
        print("=" * 80)
        
        score_pct = result.score * 100
        status = "✅ PASS" if result.score >= 1.0 else "⚠️ PARTIAL" if result.score > 0 else "❌ FAIL"
        
        print(f"Status:           {status}")
        print(f"Score:            {score_pct:.1f}%")
        print(f"Queries Matched:  {result.n_covered}/{result.n_queries}")
        print(f"Pages Navigated:  {len(evaluator._navigation_stack)}")
        print("-" * 80)

        for i, covered in enumerate(result.is_query_covered):
            status_icon = "✓" if covered else "✗"
            print(f"  Query {i+1}: [{status_icon}] {'Matched' if covered else 'Not matched'}")
        
        # Show scraped events for debugging
        print("-" * 80)
        print("EVENTS SCRAPED DURING SESSION:")
        all_events = []
        for page_infos in evaluator._all_infos:
            for event in page_infos:
                if event.get("eventName") and event.get("eventName") != "unknown" and event not in all_events:
                    all_events.append(event)
        
        if all_events:
            for i, event in enumerate(all_events[:10], 1):  # Show first 10
                name = event.get("eventName", "unknown").title()
                city = event.get("city") or "?"
                date = event.get("date") or "?"
                price = event.get("pricePerTicket")
                source = event.get("source") or "?"
                
                price_str = f"${price}" if price else "?"
                print(f"  {i}. {name}")
                print(f"     📍 {city} | 📅 {date} | 💰 {price_str} | 🔗 {source}")
        else:
            print("  No usable events scraped (Check if blocked by anti-bot)")
        
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
        print("=" * 80 + "\n")

# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_scenario(scenario: TaskScenario) -> dict:
    """Run a single verification scenario."""
    
    evaluator = SeatGeekInfoGathering(queries=scenario.queries)
    reporter = ResultReporter()
    
    reporter.print_header(scenario)
    reporter.print_instructions()
    
    input("Press ENTER to launch browser...")
    
    async with async_playwright() as p:
        browser_mgr = BrowserManager()
        browser, context, page = await browser_mgr.launch(p)
        
        await evaluator.reset()
        evaluator.attach_to_context(context)
        
        logger.info(f"Opening {scenario.url}")
        try:
            await page.goto(scenario.url, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            logger.warning(f"Initial navigation timeout/error: {e}")
            
        await evaluator.update(page=page)
        
        print("\n🌐 Browser ready - you are now the agent!")
        print("Navigate through seatgeek to complete the task.\n")
        
        await asyncio.to_thread(
            input, 
            "Press ENTER when you've completed the task... "
        )
        
        try:
            await evaluator.update(page=page)
        except Exception as e:
            logger.warning(f"Final update failed: {e}")
        
        result = await evaluator.compute()
        await browser_mgr.close()
    
    reporter.print_result(result, evaluator, scenario)
    
    return {
        "task_id": scenario.task_id,
        "score": result.score,
        "n_covered": result.n_covered,
        "n_queries": result.n_queries,
        "pages_navigated": len(evaluator._navigation_stack),
    }

async def run_interactive_menu() -> None:
    """Run interactive scenario selection menu."""
    
    print("\n" + "=" * 80)
    print("SEATGEEK TICKET VERIFICATION")
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
    
    ResultReporter.print_summary(results)


async def main():
    """Main entry point."""
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