"""
Zillow Demo Runner

Interactive demo for testing Zillow URL verification.
Allows manual testing of AI agent navigation tasks.

Usage:
    python -m navi_bench.zillow.demo_zillow
"""

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from loguru import logger

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from navi_bench.zillow.zillow_url_match import ZillowUrlMatch


@dataclass
class TaskScenario:
    """A verification scenario for Zillow."""
    name: str
    prompt: str
    ground_truth_url: str
    category: str = "general"


# ============================================================================
# PREDEFINED TEST SCENARIOS
# ============================================================================

SCENARIOS = [
    TaskScenario(
        name="Basic Price Filter",
        prompt="Find homes for sale in Los Angeles, CA with a minimum price of $500,000",
        ground_truth_url='https://www.zillow.com/homes/for_sale/Los-Angeles,-CA_rb/?searchQueryState={"filterState":{"price":{"min":500000}}}',
        category="price"
    ),
    TaskScenario(
        name="Price Range",
        prompt="Find homes in San Francisco, CA between $800,000 and $1,500,000",
        ground_truth_url='https://www.zillow.com/homes/for_sale/San-Francisco,-CA_rb/?searchQueryState={"filterState":{"price":{"min":800000,"max":1500000}}}',
        category="price"
    ),
    TaskScenario(
        name="Bedrooms Filter",
        prompt="Find homes for sale in Seattle, WA with at least 3 bedrooms",
        ground_truth_url='https://www.zillow.com/homes/for_sale/Seattle,-WA_rb/?searchQueryState={"filterState":{"beds":{"min":3}}}',
        category="beds_baths"
    ),
    TaskScenario(
        name="Multi-Filter Combination",
        prompt="Find houses in Austin, TX with 4+ bedrooms, 3+ bathrooms, priced under $800,000",
        ground_truth_url='https://www.zillow.com/homes/for_sale/Austin,-TX_rb/?searchQueryState={"filterState":{"beds":{"min":4},"baths":{"min":3},"price":{"max":800000},"isHouse":{"value":true}}}',
        category="combined"
    ),
    TaskScenario(
        name="House Only",
        prompt="Find only houses (no condos or townhomes) for sale in Denver, CO",
        ground_truth_url='https://www.zillow.com/homes/for_sale/Denver,-CO_rb/?searchQueryState={"filterState":{"isHouse":{"value":true}}}',
        category="property_type"
    ),
    TaskScenario(
        name="Rental Search",
        prompt="Find apartments for rent in New York City under $3,000/month",
        ground_truth_url='https://www.zillow.com/homes/for_rent/New-York,-NY_rb/?searchQueryState={"filterState":{"price":{"max":3000},"isApartment":{"value":true}}}',
        category="rental"
    ),
    TaskScenario(
        name="Pet-Friendly Rental",
        prompt="Find pet-friendly rentals in Portland, OR that allow dogs",
        ground_truth_url='https://www.zillow.com/homes/for_rent/Portland,-OR_rb/?searchQueryState={"filterState":{"dogsAllowed":{"value":true}}}',
        category="rental"
    ),
    TaskScenario(
        name="Pool & View",
        prompt="Find homes with a pool and mountain view in Phoenix, AZ",
        ground_truth_url='https://www.zillow.com/homes/for_sale/Phoenix,-AZ_rb/?searchQueryState={"filterState":{"hasPool":{"value":true},"hasMountainView":{"value":true}}}',
        category="features"
    ),
    TaskScenario(
        name="New Construction",
        prompt="Find newly built homes (2020+) in Miami, FL",
        ground_truth_url='https://www.zillow.com/homes/for_sale/Miami,-FL_rb/?searchQueryState={"filterState":{"built":{"min":2020}}}',
        category="property_details"
    ),
    TaskScenario(
        name="Luxury Homes",
        prompt="Find luxury homes in Beverly Hills, CA over $5,000,000 with at least 5 bedrooms",
        ground_truth_url='https://www.zillow.com/homes/for_sale/Beverly-Hills,-CA_rb/?searchQueryState={"filterState":{"price":{"min":5000000},"beds":{"min":5}}}',
        category="luxury"
    ),
]


class BrowserConfig:
    """Browser configuration for stealth mode."""
    headless: bool = False
    viewport_width: int = 1280
    viewport_height: int = 800
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    locale: str = "en-US"
    launch_args: list = None
    
    def __init__(self):
        self.launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ]


class BrowserManager:
    """Manages browser lifecycle with stealth configuration."""
    
    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
    
    async def launch(self) -> Page:
        """Launch browser and return page."""
        self.playwright = await async_playwright().start()
        
        self.browser = await self.playwright.chromium.launch(
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
        """)
        
        self.page = await self.context.new_page()
        return self.page
    
    async def close(self):
        """Close browser."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


class ResultReporter:
    """Reports verification results."""
    
    @staticmethod
    def print_result(scenario: TaskScenario, result):
        """Print detailed result."""
        print("\n" + "=" * 70)
        print("VERIFICATION RESULT")
        print("=" * 70)
        
        print(f"\n📋 Scenario: {scenario.name}")
        print(f"📝 Prompt: {scenario.prompt}")
        print(f"🏷️  Category: {scenario.category}")
        
        print(f"\n🔗 Ground Truth URL:")
        print(f"   {scenario.ground_truth_url[:80]}...")
        
        print(f"\n🌐 Agent URL:")
        print(f"   {result.agent_url[:80]}..." if len(result.agent_url) > 80 else f"   {result.agent_url}")
        
        if result.match:
            print(f"\n✅ RESULT: PASS (Score: {result.score})")
        else:
            print(f"\n❌ RESULT: FAIL (Score: {result.score})")
            
            if result.details.get("mismatches"):
                print("\n📊 Mismatches:")
                for mismatch in result.details["mismatches"]:
                    print(f"   - {mismatch}")
        
        if result.details.get("extra_filters"):
            print(f"\nℹ️  Extra filters (allowed): {result.details['extra_filters']}")
        
        print("\n" + "=" * 70)


def show_menu():
    """Display scenario selection menu."""
    print("\n" + "=" * 70)
    print("ZILLOW URL VERIFIER - DEMO")
    print("=" * 70)
    print("\nAvailable scenarios:\n")
    
    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"  {i:2}. [{scenario.category.upper():12}] {scenario.name}")
        print(f"      └─ {scenario.prompt[:60]}...")
    
    print(f"\n  {len(SCENARIOS)+1:2}. Run all scenarios automatically")
    print(f"  {len(SCENARIOS)+2:2}. Enter custom ground truth URL")
    print("   0. Exit")
    
    print("\n" + "-" * 70)


async def run_scenario(scenario: TaskScenario, auto_mode: bool = False):
    """Run a single verification scenario."""
    print(f"\n🚀 Starting scenario: {scenario.name}")
    print(f"📝 Task: {scenario.prompt}")
    print("-" * 50)
    
    # Initialize verifier
    verifier = ZillowUrlMatch(scenario.ground_truth_url)
    
    # Launch browser
    browser_mgr = BrowserManager()
    page = await browser_mgr.launch()
    
    # Navigate to Zillow
    print("\n🌐 Opening Zillow.com...")
    await page.goto("https://www.zillow.com")
    await page.wait_for_timeout(2000)
    
    # Track URL changes
    urls_visited = []
    
    def on_navigation(frame):
        if frame == page.main_frame:
            urls_visited.append(page.url)
            print(f"   📍 URL: {page.url[:60]}...")
    
    page.on("framenavigated", on_navigation)
    
    print("\n" + "=" * 50)
    print("MANUAL TASK")
    print("=" * 50)
    print(f"\n🎯 Your task: {scenario.prompt}")
    print("\nNavigate to Zillow and apply the required filters.")
    print("The browser will track your URL changes.")
    
    # Wait for user
    await asyncio.to_thread(
        input,
        "\n⏸️  Press ENTER when you've completed the task... "
    )
    
    # Get final URL
    final_url = page.url
    
    # Verify
    await verifier.update(url=final_url)
    result = await verifier.compute()
    
    # Close browser
    await browser_mgr.close()
    
    # Report
    ResultReporter.print_result(scenario, result)
    
    return result


async def run_custom():
    """Run with custom ground truth URL."""
    print("\n" + "=" * 50)
    print("CUSTOM SCENARIO")
    print("=" * 50)
    
    gt_url = input("\n🔗 Enter ground truth URL: ").strip()
    prompt = input("📝 Enter task description: ").strip()
    
    scenario = TaskScenario(
        name="Custom Scenario",
        prompt=prompt,
        ground_truth_url=gt_url,
        category="custom"
    )
    
    return await run_scenario(scenario)


async def main():
    """Main entry point."""
    while True:
        show_menu()
        
        try:
            choice = input("\n👉 Select scenario (0 to exit): ").strip()
            
            if choice == "0":
                print("\n👋 Goodbye!")
                break
            
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(SCENARIOS):
                await run_scenario(SCENARIOS[choice_num - 1])
            elif choice_num == len(SCENARIOS) + 1:
                print("\n🔄 Running all scenarios...")
                for scenario in SCENARIOS:
                    await run_scenario(scenario)
            elif choice_num == len(SCENARIOS) + 2:
                await run_custom()
            else:
                print("❌ Invalid choice")
        
        except ValueError:
            print("❌ Please enter a number")
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!")
            break


if __name__ == "__main__":
    asyncio.run(main())
