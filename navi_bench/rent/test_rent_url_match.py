import json
import asyncio
import sys
from pathlib import Path
from typing import List

# Import the new verifier
try:
    from rent_url_match import RentUrlMatch
except ImportError:
    sys.path.append(str(Path(__file__).parent))
    from rent_url_match import RentUrlMatch

async def run_verification_tests(json_path: str):
    print(f"📂 Loading tasks from: {json_path}")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: JSON file '{json_path}' not found.")
        return

    total_tests = 0
    passed_tests = 0
    failed_tests = 0

    print(f"\n🚀 Running Verification on {len(tasks)} Tasks...\n")

    for task in tasks:
        task_id = task.get("task_id", "Unknown ID")
        config = task.get("task_generation_config_json", {})
        
        # Extract GT URLs
        raw_gt = config.get("gt_urls", [])
        gt_urls_flat = []
        for item in raw_gt:
            if isinstance(item, list):
                gt_urls_flat.extend(item)
            elif isinstance(item, str):
                gt_urls_flat.append(item)
        
        if not gt_urls_flat:
            print(f"⚠️ Skipping {task_id}: No GT URLs found.")
            continue

        ground_truth_url = gt_urls_flat[0]
        
        print(f"🔹 Task: {task_id}")
        
        for test_url in gt_urls_flat:
            total_tests += 1
            
            # Initialize Rent verifier
            verifier = RentUrlMatch(gt_urls=ground_truth_url)
            
            await verifier.update(url=test_url)
            result = await verifier.compute()

            print(f"   🔗 URL: {test_url}")
            
            if result.match:
                passed_tests += 1
                print(f"   ✅ PASS")
                print(f"      Parsed Data: {result.details.get('gt_parsed')}")
                print("-" * 50)
            else:
                failed_tests += 1
                print(f"   ❌ FAIL: {test_url}")
                print(f"      Reason: {result.details.get('mismatches')}")
                print(f"      Parsed Agent: {result.details.get('agent_parsed')}")
                print(f"      Parsed GT:    {result.details.get('gt_parsed')}")
                print("-" * 50)

    print("\n📊 SUMMARY")
    print(f"Total URL Checks: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    
    if total_tests > 0:
        accuracy = (passed_tests / total_tests) * 100
        print(f"Accuracy: {accuracy:.2f}%")

if __name__ == "__main__":
    # Change this to match your actual rent.com JSON filename
    json_path = "rent/rent_tasks.json" 
    asyncio.run(run_verification_tests(json_path))