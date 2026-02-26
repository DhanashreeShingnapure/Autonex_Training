"""
Homes.com Demo Runner (CDP Connect Mode) - FIXED

1. Close ALL Chrome windows.
2. Run Chrome in Debug Mode:
   Windows: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222 --user-data-dir="D:\\ChromeDebug"
   Mac: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome_dev_test"
3. Run this script.
"""

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import async_playwright

# Import the new verifier
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

# UPDATED SCENARIOS with correct URL patterns
SCENARIOS = [
    TaskScenario(
        name="Price Filter (Austin)",
        prompt="Find homes for sale in Austin TX with a minimum price of $500,000",
        # Pattern: /location/?price-min=X
        ground_truth_url="https://www.homes.com/austin-tx/?price-min=500000",
        category="price"
    ),
    TaskScenario(
        name="Beds Filter (Nashville)",
        prompt="Find homes in Nashville TN with at least 3 bedrooms",
        
        ground_truth_url="https://www.homes.com/nashville-tn/3-to-5-bedroom",
        category="beds"
    ),
    TaskScenario(
        name="Combined Filter (Miami)",
        prompt="Find homes in Miami FL with 3+ beds and price min $1M",
        ground_truth_url="https://www.homes.com/miami-fl/?beds-min=3&price-min=1000000",
        category="combined"
    ),
]

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
    
    async with async_playwright() as p:
        try:
            print(f"\n🔌 Connecting to Chrome on port 9222...")
            # Use 127.0.0.1 to avoid IPv6 errors
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            
            # Get active tab
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
            
            print("✅ Connected!")
            
            print("\n" + "=" * 50)
            print("AGENT INSTRUCTION")
            print("=" * 50)
            print(f"🎯 Perform: {scenario.prompt}")
            print("1. Go to Chrome.")
            print("2. Search & Filter (Click 'See Results' - DO NOT SAVE).")
            print("3. Wait for the URL parameters to update.")
            print("-" * 50)
            
            while True:
                input("\n⏸️  Press ENTER when URL is correct in Chrome... ")
                
                final_url = await get_current_url_robust(page)
                
                # Warn if homepage
                if final_url.strip("/").endswith("homes.com"):
                    print(f"⚠️  Still seeing Homepage: {final_url}")
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
                    print("📊 Mismatches:")
                    for m in result.details["mismatches"]:
                        print(f"   - {m['field']}: Expected '{m['expected']}' vs Got '{m['agent']}'")
            print("=" * 50)
            
            await browser.close()
            
        except Exception as e:
            print(f"\n❌ Error: {e}")

async def main():
    while True:
        print("\n=== Homes.com Verifier (Query Param) ===")
        for i, s in enumerate(SCENARIOS):
            print(f"{i+1}. {s.name}")
        print("0. Exit")
        
        choice = input("\nSelect scenario: ").strip()
        if choice == "0": break
        
        if choice.isdigit() and 0 < int(choice) <= len(SCENARIOS):
            await run_scenario(SCENARIOS[int(choice)-1])

if __name__ == "__main__":
    asyncio.run(main())