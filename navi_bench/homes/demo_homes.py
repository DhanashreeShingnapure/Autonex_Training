"""
Homes.com Demo Runner (Clean Persistent Profile)

Automates the browser launch using a persistent user profile.
FIX: Removed '--no-sandbox' and added a 'warm-up' navigation to bypass Akamai blocks.
"""

import asyncio
import os
import shutil
import sys
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Third-party imports
from playwright.async_api import async_playwright, BrowserContext, Page

# Local import
try:
    from homes_url_match import HomesUrlMatch
except ImportError:
    sys.path.append(str(Path(__file__).parent))
    from homes_url_match import HomesUrlMatch


@dataclass
class TaskScenario:
    name: str
    prompt: str
    ground_truth_url: str
    category: str = "general"

SCENARIOS = [
    TaskScenario(
        name="Price Filter (Austin)",
        prompt="Find homes for sale in Austin TX with a minimum price of $500,000",
        ground_truth_url="https://www.homes.com/austin-tx/?price-min=500000",
        category="price"
    ),
    TaskScenario(
        name="Beds Filter (Nashville)",
        prompt="Find homes in Nashville TN with at least 3 bedrooms",
        ground_truth_url="https://www.homes.com/nashville-tn/3-bedroom/",
        category="beds"
    ),
    TaskScenario(
        name="Combined Filter (Miami)",
        prompt="Find homes in Miami FL with 3+ beds and price min $1M",
        ground_truth_url="https://www.homes.com/miami-fl/?beds-min=3&price-min=1000000",
        category="combined"
    ),
]


class PersistentBrowser:
    """
    Manages a persistent Chrome session that looks like a real user.
    """
    def __init__(self):
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Create a folder for the profile
        self.user_data_dir = os.path.join(os.getcwd(), "chrome_profile")
        # Note: Do not delete this folder automatically, as we want to save 'good' cookies.

    async def launch(self) -> Page:
        self.playwright = await async_playwright().start()
        
        print(f"🚀 Launching Chrome with Persistent Profile...")
        print(f"📂 Profile Path: {self.user_data_dir}")

        # LAUNCH PERSISTENT CONTEXT
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=False,
            channel="chrome",  # Uses real Google Chrome
            
            # CRITICAL FIX: Only use safe, non-suspicious arguments
            ignore_default_args=["--enable-automation"],
            args=[
                "--disable-blink-features=AutomationControlled", 
                "--disable-infobars",
                "--start-maximized",
                # REMOVED: --no-sandbox (This was triggering the block)
                # REMOVED: --disable-dev-shm-usage
            ],
            
            viewport=None, # Allow window to choose size
            locale="en-US",
            timezone_id="America/New_York",
        )

        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        
        # Manual Stealth Injection
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.navigator.chrome = { runtime: {} };
        """)

        return self.page

    async def close(self):
        if self.context: await self.context.close()
        if self.playwright: await self.playwright.stop()


async def get_current_url_robust(page):
    """Fetches URL using JS to bypass loading state."""
    try:
        return await page.evaluate("window.location.href")
    except:
        return page.url


async def run_scenario(scenario: TaskScenario):
    print(f"\n🚀 Starting scenario: {scenario.name}")
    print(f"📝 Prompt: {scenario.prompt}")
    print("-" * 50)
    
    verifier = HomesUrlMatch(scenario.ground_truth_url)
    browser_mgr = PersistentBrowser()
    
    try:
        page = await browser_mgr.launch()
        
        # --- WARM UP STEP ---
        # Go to a neutral site first to establish a "normal" session
        print("🌐 Warming up session (visiting Google)...")
        await page.goto("https://www.google.com", wait_until="domcontentloaded")
        await page.wait_for_timeout(random.randint(1000, 2000))
        
        print("🌐 Navigating to Homes.com...")
        try:
            # We use a short timeout because Homes.com might hang/load infinitely
            await page.goto("https://www.homes.com", timeout=15000, wait_until="domcontentloaded")
        except:
            print("⚠️  Navigation timeout (expected behavior for anti-bot sites). Continuing...")

        # Check for Access Denied immediately
        title = await page.title()
        if "Access Denied" in title or "Security" in title:
            print("\n❌ CRITICAL ERROR: Still blocked by Akamai.")
            print("   Action: Please delete the 'chrome_profile' folder and try again.")
            print("   If this persists, switch back to 'CDP Connect Mode' (manual launch).")
            return

        print("\n" + "=" * 50)
        print("AGENT ACTION REQUIRED")
        print("=" * 50)
        print(f"🎯 Perform: {scenario.prompt}")
        print("1. Search & Filter in the opened window.")
        print("2. Wait for URL update.")
        print("-" * 50)
        
        while True:
            input("\n⏸️  Press ENTER when URL is correct in Chrome... ")
            final_url = await get_current_url_robust(page)
            
            if final_url.strip("/").endswith("homes.com") or "google.com" in final_url:
                print(f"⚠️  Script sees: {final_url}")
                print("   Please perform the search first.")
                continue
            break

        print(f"\n📍 Verifying URL: {final_url}")
        
        await verifier.update(url=final_url)
        result = await verifier.compute()
        
        print("\n" + "=" * 50)
        print("VERIFICATION RESULT")
        if result.match:
            print(f"✅ PASS")
        else:
            print(f"❌ FAIL")
            if result.details.get("mismatches"):
                for m in result.details["mismatches"]:
                    print(f"   - {m['field']}: Expected '{m['expected']}' vs Got '{m['agent']}'")
        print("=" * 50)

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await browser_mgr.close()


async def main():
    while True:
        print("\n=== Homes.com Auto-Launcher (Clean) ===")
        for i, s in enumerate(SCENARIOS):
            print(f"{i+1}. {s.name}")
        print("0. Exit")
        
        choice = input("\nSelect scenario: ").strip()
        if choice == "0": break
        
        if choice.isdigit() and 0 < int(choice) <= len(SCENARIOS):
            await run_scenario(SCENARIOS[int(choice)-1])

if __name__ == "__main__":
    asyncio.run(main())