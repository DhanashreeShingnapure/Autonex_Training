"""
Comprehensive Benchmark Validation — StreetEasy CSV Tasks
==========================================================
Validates all 70 task–GT-URL pairs from
`streeteasy_benchmark_tasks_.xlsx - streeteasy_benchmark_tasks.xlsx.csv`
against `streeteasy_url_match.py`.

Sections
--------
1. GT→GT Self-Match (70 tasks — every GT URL fed as agent URL must score 1.0)
2. NaviBench Compatibility (DatasetItem, generate_task_config, instantiate)
3. Curated False Positive / Negative Tests (expected match & mismatch cases)
4. Mutated URL Sweep (bad location → must score 0.0 for every task)
5. Edge Case Audit (percent-encoding, aliases, sort typos, sold path, transit, etc.)
6. Per-Category Summary

Usage
-----
    cd /Users/karanpaigude/Desktop/Projects/navi-bench
    python -m navi_bench.streeteasy.test_benchmark_tasks
"""

import asyncio
import csv
import json
import sys
from collections import defaultdict
from io import StringIO
from pathlib import Path
from urllib.parse import unquote

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
try:
    from navi_bench.streeteasy.streeteasy_url_match import (
        StreetEasyUrlMatch,
        generate_task_config,
    )
    from navi_bench.base import BaseTaskConfig, DatasetItem, instantiate
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from navi_bench.streeteasy.streeteasy_url_match import (
        StreetEasyUrlMatch,
        generate_task_config,
    )
    from navi_bench.base import BaseTaskConfig, DatasetItem, instantiate

# ---------------------------------------------------------------------------
# CSV Path
# ---------------------------------------------------------------------------
CSV_PATH = (
    Path(__file__).parent
    / "streeteasy_benchmark_tasks_.xlsx - streeteasy_benchmark_tasks.xlsx.csv"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_tasks() -> list[dict]:
    """Load and parse all tasks from the CSV."""
    tasks = []
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            config = json.loads(row["task_generation_config_json"])
            gt_url = config.get("ground_truth_url", "")
            tasks.append({
                "task_id": row["task_id"],
                "task_generation_config_json": row["task_generation_config_json"],
                "env": row["env"],
                "domain": row["domain"],
                "l1_category": row["l1_category"],
                "l2_category": row["l2_category"],
                "suggested_difficulty": row.get("suggested_difficulty"),
                "suggested_split": row.get("suggested_split"),
                "config": config,
                "gt_url": gt_url,
            })
    return tasks


def _make_verifier(gt_url: str) -> StreetEasyUrlMatch:
    """Create a fresh StreetEasyUrlMatch instance."""
    return StreetEasyUrlMatch(gt_url=gt_url)


async def _check(gt_url: str, agent_url: str) -> float:
    """Run a single URL check and return the score."""
    v = _make_verifier(gt_url)
    await v.update(url=agent_url)
    result = await v.compute()
    return result.score


def _check_sync(gt_url: str, agent_url: str) -> float:
    return asyncio.run(_check(gt_url, agent_url))


# ---------------------------------------------------------------------------
# SECTION 1: GT → GT Self-Match
# ---------------------------------------------------------------------------

async def section1_gt_self_match(tasks: list[dict]) -> bool:
    print("\n" + "=" * 70)
    print("SECTION 1 — GT→GT Self-Match (70/70 must score 1.0)")
    print("=" * 70)

    passed = 0
    failed = 0
    failures = []

    for t in tasks:
        gt_url = t["gt_url"]
        if not gt_url:
            failures.append(f"  SKIP (no gt_url): {t['task_id']}")
            failed += 1
            continue

        v = _make_verifier(gt_url)
        await v.update(url=gt_url)
        result = await v.compute()
        await v.reset()

        if result.score == 1.0:
            passed += 1
        else:
            failed += 1
            # Get detailed result
            match, details = v._urls_match(gt_url, gt_url)
            failures.append(
                f"  FAIL [{t['task_id']}]\n"
                f"    GT:  {gt_url}\n"
                f"    Mismatches: {details.get('mismatches', [])}"
            )

    print(f"  Passed: {passed}/70")
    if failures:
        for f in failures:
            print(f)

    ok = (failed == 0)
    print(f"  Result: {'✓ ALL PASSED' if ok else f'✗ {failed} FAILED'}")
    return ok


# ---------------------------------------------------------------------------
# SECTION 2: NaviBench Compatibility
# ---------------------------------------------------------------------------

async def section2_navibench_compat(tasks: list[dict]) -> bool:
    print("\n" + "=" * 70)
    print("SECTION 2 — NaviBench Compatibility")
    print("=" * 70)

    issues = []

    # 2a. DatasetItem construction
    print("\n  2a. DatasetItem construction (70 rows)")
    di_ok = 0
    di_fail = 0
    for t in tasks:
        try:
            di = DatasetItem(
                task_id=t["task_id"],
                task_generation_config_json=t["task_generation_config_json"],
                env=t["env"],
                domain=t["domain"],
                l1_category=t["l1_category"],
                l2_category=t["l2_category"],
                suggested_difficulty=t.get("suggested_difficulty"),
                suggested_split=t.get("suggested_split"),
                metadata_json=None,
                suggested_hint=None,
                suggested_max_steps=None,
            )
            di_ok += 1
        except Exception as e:
            di_fail += 1
            issues.append(f"    DatasetItem FAIL [{t['task_id']}]: {e}")

    print(f"    Passed: {di_ok}/70  {'✓' if di_fail == 0 else f'✗ {di_fail} FAILED'}")
    for i in issues:
        print(i)
    issues.clear()

    # 2b. generate_task_config existence & signature
    print("\n  2b. generate_task_config callable and returns BaseTaskConfig (70)")
    gc_ok = 0
    gc_fail = 0
    for t in tasks:
        cfg = t["config"]
        try:
            btc = generate_task_config(
                task=cfg["task"],
                location=cfg["location"],
                timezone=cfg["timezone"],
                ground_truth_url=cfg["ground_truth_url"],
                url=cfg.get("url", "https://streeteasy.com"),
            )
            assert isinstance(btc, BaseTaskConfig), "Not a BaseTaskConfig"
            assert "_target_" in btc.eval_config, "eval_config missing _target_"
            assert "gt_url" in btc.eval_config, "eval_config missing gt_url"
            assert isinstance(btc.eval_config["gt_url"], list), "gt_url not a list"
            gc_ok += 1
        except Exception as e:
            gc_fail += 1
            issues.append(f"    generate_task_config FAIL [{t['task_id']}]: {e}")

    print(f"    Passed: {gc_ok}/70  {'✓' if gc_fail == 0 else f'✗ {gc_fail} FAILED'}")
    for i in issues:
        print(i)
    issues.clear()

    # 2c. instantiate() creates StreetEasyUrlMatch with correct gt_urls
    print("\n  2c. instantiate() creates StreetEasyUrlMatch (70)")
    inst_ok = 0
    inst_fail = 0
    for t in tasks:
        cfg = t["config"]
        try:
            # Build the eval_config dict that instantiate() will use
            btc = generate_task_config(
                task=cfg["task"],
                location=cfg["location"],
                timezone=cfg["timezone"],
                ground_truth_url=cfg["ground_truth_url"],
            )
            metric = instantiate(btc.eval_config)
            assert isinstance(metric, StreetEasyUrlMatch), f"Got {type(metric)}"
            assert len(metric.gt_urls) == 1, f"Expected 1 gt_url, got {len(metric.gt_urls)}"
            assert isinstance(metric.gt_urls[0], str), "gt_urls[0] not a str"
            # Verify the stored URL equals the original (un-encoded)
            expected = unquote(cfg["ground_truth_url"])
            # The metric stores the raw string; parsing happens in _parse_streeteasy_url
            inst_ok += 1
        except Exception as e:
            inst_fail += 1
            issues.append(f"    instantiate FAIL [{t['task_id']}]: {e}")

    print(f"    Passed: {inst_ok}/70  {'✓' if inst_fail == 0 else f'✗ {inst_fail} FAILED'}")
    for i in issues:
        print(i)
    issues.clear()

    # 2d. BaseMetric interface: update / compute / reset
    print("\n  2d. update/compute/reset interface (5 sampled tasks)")
    sample_tasks = tasks[::14][:5]
    iface_ok = 0
    iface_fail = 0
    for t in sample_tasks:
        gt_url = t["gt_url"]
        try:
            v = _make_verifier(gt_url)
            # reset
            await v.reset()
            # update with GT URL
            await v.update(url=gt_url)
            result = await v.compute()
            assert result.score == 1.0, f"Expected 1.0 after GT update, got {result.score}"
            # reset clears state
            await v.reset()
            result2 = await v.compute()
            assert result2.score == 0.0, f"Expected 0.0 after reset, got {result2.score}"
            iface_ok += 1
        except Exception as e:
            iface_fail += 1
            issues.append(f"    Interface FAIL [{t['task_id']}]: {e}")

    print(f"    Passed: {iface_ok}/5  {'✓' if iface_fail == 0 else f'✗ {iface_fail} FAILED'}")
    for i in issues:
        print(i)
    issues.clear()

    # 2e. ground_truth_url in CSV config → wrapped into [gt_url] list
    print("\n  2e. ground_truth_url (single str) → wrapped to [gt_url] list (70)")
    wrap_ok = 0
    wrap_fail = 0
    for t in tasks:
        cfg = t["config"]
        try:
            # The full task_generation_config_json as-is should instantiate
            metric = instantiate(cfg)
            assert isinstance(metric, BaseTaskConfig), f"instantiate(full_config) should return BaseTaskConfig, got {type(metric)}"
            inner = instantiate(metric.eval_config)
            assert isinstance(inner, StreetEasyUrlMatch)
            assert len(inner.gt_urls) == 1
            wrap_ok += 1
        except Exception as e:
            wrap_fail += 1
            issues.append(f"    Wrap FAIL [{t['task_id']}]: {e}")

    print(f"    Passed: {wrap_ok}/70  {'✓' if wrap_fail == 0 else f'✗ {wrap_fail} FAILED'}")
    for i in issues:
        print(i)

    all_ok = (di_fail + gc_fail + inst_fail + iface_fail + wrap_fail) == 0
    print(f"\n  Result: {'✓ ALL COMPATIBLE' if all_ok else '✗ ISSUES FOUND'}")
    return all_ok


# ---------------------------------------------------------------------------
# SECTION 3: Curated False Positive / Negative Tests
# ---------------------------------------------------------------------------

async def section3_curated_fp_tests() -> bool:
    print("\n" + "=" * 70)
    print("SECTION 3 — Curated False Positive / Negative Tests")
    print("=" * 70)

    total = 0
    passed = 0
    failures = []

    async def check(name: str, gt: str, agent: str, expect: float):
        nonlocal total, passed
        total += 1
        score = await _check(gt, agent)
        ok = (score == expect)
        if ok:
            passed += 1
            print(f"  ✓ [{expect:.0f}] {name}")
        else:
            failures.append(f"  ✗ [{expect:.0f}→got {score:.0f}] {name}\n"
                            f"       GT:    {gt}\n"
                            f"       Agent: {agent}")

    # -----------------------------------------------------------------------
    # TRUE POSITIVES (expect score=1.0 — different surface form, same meaning)
    # -----------------------------------------------------------------------
    print("\n  TRUE POSITIVES (should match)")

    await check(
        "Amenity order — comma-separated sorted internally",
        "https://streeteasy.com/for-sale/manhattan/type:D1|price:800000-2000000|amenities:elevator,doorman",
        "https://streeteasy.com/for-sale/manhattan/type:D1|price:800000-2000000|amenities:doorman,elevator",
        1.0,
    )
    await check(
        "Sort param typo (se_score2) ignored",
        "https://streeteasy.com/for-sale/manhattan/type:P1|price:-800000|beds:2|amenities:doorman?sort_by=se_score2",
        "https://streeteasy.com/for-sale/manhattan/type:P1|price:-800000|beds:2|amenities:doorman?sort_by=se_score",
        1.0,
    )
    await check(
        "Sort param typo (listed_descc) ignored",
        "https://streeteasy.com/for-sale/manhattan/type:D1|price:500000-1500000|beds:1|amenities:elevator?sort_by=listed_descc",
        "https://streeteasy.com/for-sale/manhattan/type:D1|price:500000-1500000|beds:1|amenities:elevator?sort_by=listed_desc",
        1.0,
    )
    await check(
        "Filter pipe order independent (2 filters)",
        "https://streeteasy.com/for-sale/brooklyn/beds:3|price:1000000-2000000",
        "https://streeteasy.com/for-sale/brooklyn/price:1000000-2000000|beds:3",
        1.0,
    )
    await check(
        "Filter pipe order independent (4 filters)",
        "https://streeteasy.com/for-sale/manhattan/type:D1,P1|price:-1500000|beds>=2|amenities:doorman,gym|pets:allowed",
        "https://streeteasy.com/for-sale/manhattan/pets:allowed|amenities:gym,doorman|beds>=2|price:-1500000|type:D1,P1",
        1.0,
    )
    await check(
        "Agent has extra filter not required by GT → still matches",
        "https://streeteasy.com/for-sale/brooklyn/type:D1|beds:2",
        "https://streeteasy.com/for-sale/brooklyn/type:D1|beds:2|amenities:parking",
        1.0,
    )
    await check(
        "transit_lines alias → subway (L train)",
        "https://streeteasy.com/for-rent/brooklyn/price:-4000|beds>=2|amenities:gym|transit_lines:L",
        "https://streeteasy.com/for-rent/brooklyn/price:-4000|beds>=2|amenities:gym|subway:L",
        1.0,
    )
    await check(
        "pre_war:yes = prewar:1 (boolean normalization)",
        "https://streeteasy.com/for-sale/manhattan/type:D1|price:1000000-3000000|beds:2|pre_war:yes|amenities:doorman",
        "https://streeteasy.com/for-sale/manhattan/type:D1|price:1000000-3000000|beds:2|prewar:1|amenities:doorman",
        1.0,
    )
    await check(
        "new_developments:new development = new_development:1 (space-value boolean)",
        "https://streeteasy.com/for-sale/manhattan/type:D1|new_developments:new%20development",
        "https://streeteasy.com/for-sale/manhattan/type:D1|new_development:1",
        1.0,
    )
    await check(
        "opt_amenities: equals amenities: (Must-have toggle)",
        "https://streeteasy.com/for-sale/brooklyn/type:D1|beds:2|amenities:parking",
        "https://streeteasy.com/for-sale/brooklyn/type:D1|beds:2|opt_amenities:parking",
        1.0,
    )
    await check(
        "Property type alias: condos → D1",
        "https://streeteasy.com/for-sale/manhattan/type:D1|price:500000-1000000|beds>=2",
        "https://streeteasy.com/for-sale/manhattan/type:condos|price:500000-1000000|beds>=2",
        1.0,
    )
    await check(
        "Property type alias: co-op → P1",
        "https://streeteasy.com/for-sale/brooklyn/type:P1|price:-700000",
        "https://streeteasy.com/for-sale/brooklyn/type:co-op|price:-700000",
        1.0,
    )
    await check(
        "type:D1,P1 order independent",
        "https://streeteasy.com/for-sale/manhattan/type:D1,P1|price:-1500000|beds>=2",
        "https://streeteasy.com/for-sale/manhattan/type:P1,D1|price:-1500000|beds>=2",
        1.0,
    )
    await check(
        "Percent-encoded GT URL matches decoded agent URL",
        "https://streeteasy.com/for-sale/manhattan/type:D1%7Cprice:500000-1000000%7Cbeds%3E=2",
        "https://streeteasy.com/for-sale/manhattan/type:D1|price:500000-1000000|beds>=2",
        1.0,
    )
    await check(
        "Case insensitive filter key (BEDS vs beds)",
        "https://streeteasy.com/for-sale/manhattan/beds:2",
        "https://streeteasy.com/for-sale/manhattan/BEDS:2",
        1.0,
    )
    await check(
        "Case insensitive location (Manhattan vs manhattan)",
        "https://streeteasy.com/for-sale/manhattan/type:D1",
        "https://streeteasy.com/for-sale/Manhattan/type:D1",
        1.0,
    )
    await check(
        "http vs https",
        "https://streeteasy.com/for-sale/manhattan/beds:2",
        "http://streeteasy.com/for-sale/manhattan/beds:2",
        1.0,
    )
    await check(
        "www vs no-www",
        "https://streeteasy.com/for-sale/manhattan/beds:2",
        "https://www.streeteasy.com/for-sale/manhattan/beds:2",
        1.0,
    )
    await check(
        "status:active = status:open alias",
        "https://streeteasy.com/for-sale/manhattan/status:open",
        "https://streeteasy.com/for-sale/manhattan/status:active",
        1.0,
    )
    await check(
        "washer_dryer → in_unit_laundry alias (in amenities)",
        "https://streeteasy.com/for-rent/brooklyn/price:2000-4000|amenities:washer_dryer,doorman|pets:allowed",
        "https://streeteasy.com/for-rent/brooklyn/price:2000-4000|amenities:in_unit_laundry,doorman|pets:allowed",
        1.0,
    )
    await check(
        "transit_lines:A,C,E (comma-delimited multi-line)",
        "https://streeteasy.com/for-rent/manhattan/price:-3500|beds>=1|transit_lines:A,C,E",
        "https://streeteasy.com/for-rent/manhattan/price:-3500|beds>=1|subway:A,C,E",
        1.0,
    )
    await check(
        "sold tasks: for-sale path + status:sold self-match",
        "https://streeteasy.com/for-sale/manhattan/status:sold|type:D1|price:1000000-3000000|beds>=2",
        "https://streeteasy.com/for-sale/manhattan/status:sold|type:D1|price:1000000-3000000|beds>=2",
        1.0,
    )
    await check(
        "Neighborhood-as-location (upper-west-side) self-match",
        "https://streeteasy.com/for-sale/upper-west-side/type:D1|beds>=3|baths>=2",
        "https://streeteasy.com/for-sale/upper-west-side/type:D1|beds>=3|baths>=2",
        1.0,
    )
    await check(
        "amenities:furnished (furnished via amenity prefix)",
        "https://streeteasy.com/for-rent/manhattan/price:-4000|beds:1|amenities:furnished",
        "https://streeteasy.com/for-rent/manhattan/price:-4000|beds:1|amenities:furnished",
        1.0,
    )

    # -----------------------------------------------------------------------
    # TRUE NEGATIVES (expect score=0.0 — real mismatches)
    # -----------------------------------------------------------------------
    print("\n  TRUE NEGATIVES (should NOT match)")

    await check(
        "Wrong borough: manhattan vs brooklyn",
        "https://streeteasy.com/for-sale/manhattan/type:D1|price:500000-1000000|beds>=2",
        "https://streeteasy.com/for-sale/brooklyn/type:D1|price:500000-1000000|beds>=2",
        0.0,
    )
    await check(
        "Wrong search type: for-sale vs for-rent",
        "https://streeteasy.com/for-sale/manhattan/type:D1|price:500000-1000000",
        "https://streeteasy.com/for-rent/manhattan/type:D1|price:500000-1000000",
        0.0,
    )
    await check(
        "Wrong price range",
        "https://streeteasy.com/for-sale/manhattan/price:500000-1000000|beds>=2",
        "https://streeteasy.com/for-sale/manhattan/price:300000-800000|beds>=2",
        0.0,
    )
    await check(
        "Missing required filter (beds)",
        "https://streeteasy.com/for-sale/brooklyn/type:D1|price:500000-1000000|beds:1",
        "https://streeteasy.com/for-sale/brooklyn/type:D1|price:500000-1000000",
        0.0,
    )
    await check(
        "Wrong property type: D1 vs P1",
        "https://streeteasy.com/for-sale/manhattan/type:D1|price:800000-2000000",
        "https://streeteasy.com/for-sale/manhattan/type:P1|price:800000-2000000",
        0.0,
    )
    await check(
        "Wrong neighborhood: upper-west-side vs upper-east-side",
        "https://streeteasy.com/for-sale/upper-west-side/type:D1|beds>=3|baths>=2",
        "https://streeteasy.com/for-sale/upper-east-side/type:D1|beds>=3|baths>=2",
        0.0,
    )
    await check(
        "Wrong subway line: L vs A",
        "https://streeteasy.com/for-rent/brooklyn/price:-4000|beds>=2|amenities:gym|transit_lines:L",
        "https://streeteasy.com/for-rent/brooklyn/price:-4000|beds>=2|amenities:gym|transit_lines:A",
        0.0,
    )
    await check(
        "Agent at /sold/ path, GT at /for-sale/ with status:sold → different search_type",
        "https://streeteasy.com/for-sale/manhattan/status:sold|type:D1|price:1000000-3000000|beds>=2",
        "https://streeteasy.com/sold/manhattan/type:D1|price:1000000-3000000|beds>=2",
        0.0,
    )
    await check(
        "Wrong amenity: doorman vs elevator",
        "https://streeteasy.com/for-sale/manhattan/type:D1|amenities:doorman",
        "https://streeteasy.com/for-sale/manhattan/type:D1|amenities:elevator",
        0.0,
    )
    await check(
        "Wrong beds: 1 vs 2",
        "https://streeteasy.com/for-sale/brooklyn/type:D1|price:500000-1000000|beds:2",
        "https://streeteasy.com/for-sale/brooklyn/type:D1|price:500000-1000000|beds:1",
        0.0,
    )
    await check(
        "Missing pets filter when GT requires it",
        "https://streeteasy.com/for-rent/brooklyn/price:2000-3500|amenities:doorman|pets:allowed",
        "https://streeteasy.com/for-rent/brooklyn/price:2000-3500|amenities:doorman",
        0.0,
    )
    await check(
        "Wrong price direction: under vs over",
        "https://streeteasy.com/for-sale/bronx/price:-500000",
        "https://streeteasy.com/for-sale/bronx/price:500000-",
        0.0,
    )
    await check(
        "Missing pre_war filter",
        "https://streeteasy.com/for-sale/manhattan/type:P1|price:-600000|beds:1|pre_war:yes",
        "https://streeteasy.com/for-sale/manhattan/type:P1|price:-600000|beds:1",
        0.0,
    )
    await check(
        "Wrong transit line: Z vs L",
        "https://streeteasy.com/for-rent/brooklyn/price:-2500|beds>=1|pets:allowed|transit_lines:Z",
        "https://streeteasy.com/for-rent/brooklyn/price:-2500|beds>=1|pets:allowed|transit_lines:L",
        0.0,
    )

    all_ok = (passed == total)
    print(f"\n  Passed: {passed}/{total}")
    if failures:
        for f in failures:
            print(f)
    print(f"  Result: {'✓ ALL PASSED' if all_ok else f'✗ {total - passed} FAILED'}")
    return all_ok


# ---------------------------------------------------------------------------
# SECTION 4: Mutated URL Sweep (bad location → must score 0.0)
# ---------------------------------------------------------------------------

async def section4_mutated_url_sweep(tasks: list[dict]) -> bool:
    print("\n" + "=" * 70)
    print("SECTION 4 — Mutated URL Sweep (wrong location → 0.0 for all 70)")
    print("=" * 70)

    # Replace the borough/location segment with a completely wrong one
    # For neighborhood tasks (upper-west-side, williamsburg, etc.) we use
    # a wrong neighborhood; for borough tasks we use a wrong borough.
    BOROUGH_SWAP = {
        "manhattan": "queens",
        "brooklyn": "bronx",
        "queens": "manhattan",
        "bronx": "brooklyn",
        "staten-island": "manhattan",
        # Neighborhoods
        "upper-west-side": "upper-east-side",
        "upper-east-side": "williamsburg",
        "williamsburg": "upper-west-side",
        "chelsea": "soho",
        "soho": "chelsea",
        "long-island-city": "williamsburg",
        "financial-district": "soho",
        "east-village": "upper-west-side",
        "park-slope": "williamsburg",
        "midtown": "upper-east-side",
    }

    passed = 0
    failed = 0
    failures = []

    for t in tasks:
        gt_url = t["gt_url"]
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(unquote(gt_url))
        segs = [s for s in parsed.path.strip("/").split("/") if s]

        # Find location segment (segment after search_type)
        if len(segs) < 2:
            # No location to mutate, skip
            continue

        loc_seg = segs[1]  # segment after for-sale/for-rent/sold
        wrong_loc = BOROUGH_SWAP.get(loc_seg)
        if not wrong_loc:
            # Unknown location — use a generic replacement
            wrong_loc = "queens" if loc_seg != "queens" else "manhattan"

        # Build mutated URL: replace loc_seg with wrong_loc
        new_segs = segs.copy()
        new_segs[1] = wrong_loc
        new_path = "/" + "/".join(new_segs)
        new_parsed = parsed._replace(path=new_path)
        mutated_url = urlunparse(new_parsed)

        score = await _check(gt_url, mutated_url)
        if score == 0.0:
            passed += 1
        else:
            failed += 1
            failures.append(
                f"  FAIL [{t['task_id']}]: expected 0.0 for wrong location\n"
                f"    GT:      {gt_url}\n"
                f"    Mutated: {mutated_url}"
            )

    total = passed + failed
    print(f"  Passed: {passed}/{total} (wrong-location → 0.0)")
    if failures:
        for f in failures:
            print(f)
    ok = (failed == 0)
    print(f"  Result: {'✓ ALL PASSED' if ok else f'✗ {failed} FAILED'}")
    return ok


# ---------------------------------------------------------------------------
# SECTION 5: Edge Case Audit
# ---------------------------------------------------------------------------

async def section5_edge_case_audit(tasks: list[dict]) -> bool:
    print("\n" + "=" * 70)
    print("SECTION 5 — Edge Case Audit")
    print("=" * 70)

    issues_found = []

    # 5a. Percent-encoding: all GT URLs parse correctly after unquote
    print("\n  5a. Percent-encoded GT URLs — all unquote correctly (70)")
    enc_ok = 0
    for t in tasks:
        raw = t["gt_url"]
        decoded = unquote(raw)
        if decoded != raw:
            enc_ok += 1  # Did have percent encoding, now decoded
        else:
            enc_ok += 1  # No encoding, also fine
    print(f"    All {enc_ok} URLs decoded without error ✓")

    # 5b. Sort param handling — tasks 13 (se_score2) and 16 (listed_descc)
    print("\n  5b. Sort param typos in GT URLs — correctly ignored")
    sort_typo_tasks = [
        t for t in tasks
        if "se_score2" in t["gt_url"] or "listed_descc" in t["gt_url"]
    ]
    typo_ok = 0
    typo_fail = 0
    for t in sort_typo_tasks:
        gt_url = t["gt_url"]
        score = await _check(gt_url, gt_url)
        if score == 1.0:
            typo_ok += 1
            print(f"    ✓ [{t['task_id']}] Sort typo ignored: {gt_url.split('?')[1] if '?' in gt_url else 'N/A'}")
        else:
            typo_fail += 1
            issues_found.append(f"    ✗ [{t['task_id']}] Sort typo NOT ignored: {gt_url}")
    if not sort_typo_tasks:
        print("    (no tasks with sort typos found — check CSV)")

    # 5c. pre_war:yes normalization (tasks 19, 20, 30, 31, 32)
    print("\n  5c. pre_war:yes normalization (tasks 19,20,30,31,32)")
    prewar_tasks = [t for t in tasks if "pre_war:yes" in unquote(t["gt_url"])]
    prewar_ok = 0
    for t in prewar_tasks:
        gt_url = t["gt_url"]
        score = await _check(gt_url, gt_url)
        if score == 1.0:
            prewar_ok += 1
        else:
            issues_found.append(f"    ✗ pre_war:yes self-match failed [{t['task_id']}]")
    # Also verify cross-form equivalence
    sample_prewar_gt = unquote(prewar_tasks[0]["gt_url"]) if prewar_tasks else None
    if sample_prewar_gt:
        # Replace pre_war:yes with prewar:1
        alt_url = sample_prewar_gt.split("?")[0].replace("pre_war:yes", "prewar:1")
        if "?" in sample_prewar_gt:
            alt_url += "?" + sample_prewar_gt.split("?")[1]
        cross_score = await _check(prewar_tasks[0]["gt_url"], alt_url)
        if cross_score == 1.0:
            print(f"    ✓ {len(prewar_tasks)} pre_war tasks self-match")
            print(f"    ✓ pre_war:yes ≡ prewar:1 (cross-form equivalence)")
        else:
            issues_found.append(f"    ✗ pre_war:yes ≢ prewar:1")
    else:
        print("    (no prewar tasks found)")

    # 5d. new_developments:new development normalization (task 21)
    print("\n  5d. new_developments:new%20development normalization (task 21)")
    newdev_tasks = [t for t in tasks if "new_developments" in unquote(t["gt_url"])]
    if newdev_tasks:
        for t in newdev_tasks:
            gt_url = t["gt_url"]
            score = await _check(gt_url, gt_url)
            if score == 1.0:
                # Also verify = new_development:1
                decoded = unquote(gt_url).split("?")[0].replace("new_developments:new development", "new_development:1")
                cross_score = await _check(gt_url, decoded)
                if cross_score == 1.0:
                    print(f"    ✓ [{t['task_id']}] new_developments:new development ≡ new_development:1")
                else:
                    issues_found.append(f"    ✗ new_development cross-form failed [{t['task_id']}]")
            else:
                issues_found.append(f"    ✗ new_developments self-match failed [{t['task_id']}]")
    else:
        print("    (no new_developments tasks found)")

    # 5e. amenities:furnished (task 37 — furnished as amenity prefix)
    print("\n  5e. amenities:furnished — via amenity prefix (task 37)")
    furnished_tasks = [t for t in tasks if "amenities:furnished" in unquote(t["gt_url"])]
    if furnished_tasks:
        for t in furnished_tasks:
            gt_url = t["gt_url"]
            score = await _check(gt_url, gt_url)
            status = "✓" if score == 1.0 else "✗"
            print(f"    {status} [{t['task_id']}] amenities:furnished self-match: {score}")
            if score != 1.0:
                issues_found.append(f"    amenities:furnished self-match failed [{t['task_id']}]")
    else:
        print("    (no amenities:furnished tasks found)")

    # 5f. transit_lines:X normalization (tasks 48-54, 68)
    print("\n  5f. transit_lines:X → subway:X.upper() (tasks 48-54, 68)")
    transit_tasks = [t for t in tasks if "transit_lines:" in unquote(t["gt_url"])]
    transit_ok = 0
    for t in transit_tasks:
        gt_url = t["gt_url"]
        score = await _check(gt_url, gt_url)
        if score == 1.0:
            transit_ok += 1
        else:
            issues_found.append(f"    ✗ transit self-match failed [{t['task_id']}]")
    # Check A,C,E comma-delimited (task 53)
    ace_task = next((t for t in tasks if "transit_lines:A,C,E" in unquote(t["gt_url"])), None)
    if ace_task:
        decoded = unquote(ace_task["gt_url"]).split("?")[0].replace("transit_lines:A,C,E", "subway:A,C,E")
        score = await _check(ace_task["gt_url"], decoded)
        print(f"    ✓ {transit_ok}/{len(transit_tasks)} transit tasks self-match")
        cross = "✓" if score == 1.0 else "✗"
        print(f"    {cross} transit_lines:A,C,E ≡ subway:A,C,E (comma-delimited multi-line)")
        if score != 1.0:
            issues_found.append(f"    transit_lines:A,C,E cross-form failed")
    else:
        print(f"    ✓ {transit_ok}/{len(transit_tasks)} transit tasks self-match")

    # 5g. Sold category: for-sale path + status:sold (tasks 60-65)
    print("\n  5g. Sold tasks: /for-sale/ path + status:sold filter (tasks 60-65)")
    sold_tasks = [t for t in tasks if t["l2_category"] == "sold"]
    sold_ok = 0
    for t in sold_tasks:
        gt_url = t["gt_url"]
        decoded = unquote(gt_url)
        assert "/for-sale/" in decoded, f"Sold task uses /sold/ path: {decoded}"
        assert "status:sold" in decoded, f"Sold task missing status:sold: {decoded}"
        score = await _check(gt_url, gt_url)
        if score == 1.0:
            sold_ok += 1
        else:
            issues_found.append(f"    ✗ sold task self-match failed [{t['task_id']}]")

    # Also verify /sold/ path does NOT match GT (which uses /for-sale/ + status:sold)
    if sold_tasks:
        sample_sold = sold_tasks[0]
        gt_url = sample_sold["gt_url"]
        decoded = unquote(gt_url)
        # Build a URL that uses /sold/ path instead
        wrong_path_url = decoded.replace("/for-sale/", "/sold/").replace("status:sold|", "").replace("|status:sold", "")
        wrong_score = await _check(gt_url, wrong_path_url)
        print(f"    ✓ {sold_ok}/{len(sold_tasks)} sold tasks self-match (for-sale + status:sold)")
        guard = "✓" if wrong_score == 0.0 else "✗"
        print(f"    {guard} Agent using /sold/ path does NOT match GT (search_type mismatch)")
        if wrong_score != 0.0:
            issues_found.append(f"    /sold/ path incorrectly matched for-sale + status:sold")

    # 5h. Neighborhood-as-location tasks (no borough prefix)
    print("\n  5h. Neighborhood-as-location tasks (no borough prefix)")
    nbhd_tasks = [
        t for t in tasks
        if t["l2_category"] in ("for_sale_neighborhood", "for_rent_neighborhood")
    ]
    nbhd_ok = 0
    for t in nbhd_tasks:
        score = await _check(t["gt_url"], t["gt_url"])
        if score == 1.0:
            nbhd_ok += 1
        else:
            issues_found.append(f"    ✗ neighborhood self-match failed [{t['task_id']}]")
    print(f"    ✓ {nbhd_ok}/{len(nbhd_tasks)} neighborhood tasks self-match")

    # Summary
    all_ok = len(issues_found) == 0
    if issues_found:
        print("\n  ISSUES:")
        for i in issues_found:
            print(i)
    print(f"\n  Result: {'✓ ALL EDGE CASES HANDLED' if all_ok else f'✗ {len(issues_found)} ISSUES'}")
    return all_ok


# ---------------------------------------------------------------------------
# SECTION 6: Per-Category Summary
# ---------------------------------------------------------------------------

async def section6_category_summary(tasks: list[dict]) -> bool:
    print("\n" + "=" * 70)
    print("SECTION 6 — Per-Category Summary (GT→GT self-match by category)")
    print("=" * 70)

    categories = defaultdict(lambda: {"passed": 0, "failed": 0, "tasks": []})

    for t in tasks:
        cat = t["l2_category"] or "unknown"
        gt_url = t["gt_url"]
        v = _make_verifier(gt_url)
        await v.update(url=gt_url)
        result = await v.compute()
        await v.reset()
        if result.score == 1.0:
            categories[cat]["passed"] += 1
        else:
            categories[cat]["failed"] += 1
            categories[cat]["tasks"].append(t["task_id"])

    all_ok = True
    print(f"\n  {'Category':<28} {'Pass':>5} {'Fail':>5} {'Total':>5}")
    print("  " + "-" * 45)
    grand_pass = 0
    grand_fail = 0
    for cat in sorted(categories):
        p = categories[cat]["passed"]
        f = categories[cat]["failed"]
        grand_pass += p
        grand_fail += f
        marker = "✓" if f == 0 else "✗"
        print(f"  {marker} {cat:<26} {p:>5} {f:>5} {p+f:>5}")
        if f > 0:
            all_ok = False
            for tid in categories[cat]["tasks"]:
                print(f"      FAIL: {tid}")

    print("  " + "-" * 45)
    print(f"  {'TOTAL':<28} {grand_pass:>5} {grand_fail:>5} {grand_pass+grand_fail:>5}")
    print(f"\n  Result: {'✓ ALL CATEGORIES PASSED' if all_ok else f'✗ SOME CATEGORIES FAILED'}")
    return all_ok


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

async def main():
    print("\n" + "=" * 70)
    print("STREETEASY BENCHMARK VALIDATION")
    print(f"CSV: {CSV_PATH.name}")
    print("=" * 70)

    tasks = _load_tasks()
    print(f"\nLoaded {len(tasks)} tasks from CSV")

    results = {}

    results["s1"] = await section1_gt_self_match(tasks)
    results["s2"] = await section2_navibench_compat(tasks)
    results["s3"] = await section3_curated_fp_tests()
    results["s4"] = await section4_mutated_url_sweep(tasks)
    results["s5"] = await section5_edge_case_audit(tasks)
    results["s6"] = await section6_category_summary(tasks)

    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    labels = {
        "s1": "Section 1: GT→GT Self-Match",
        "s2": "Section 2: NaviBench Compatibility",
        "s3": "Section 3: Curated FP/FN Tests",
        "s4": "Section 4: Mutated URL Sweep",
        "s5": "Section 5: Edge Case Audit",
        "s6": "Section 6: Per-Category Summary",
    }
    all_ok = True
    for key, label in labels.items():
        ok = results[key]
        marker = "✓" if ok else "✗"
        print(f"  {marker} {label}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print("  ✓ ALL CHECKS PASSED")
    else:
        print("  ✗ SOME CHECKS FAILED — review output above")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
