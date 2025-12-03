#!/usr/bin/env python3
"""
Quick benchmark: 10 queries across locations.
Run on both Pi and Mac, compare results.

Usage: uv run python benchmark_quick.py
"""

import time
import json
import sys

# Import query engine
import importlib.util
spec = importlib.util.spec_from_file_location("dream_meridian", "dream-meridian.py")
dm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dm)

QUERIES = [
    ("coxs_bazar", "Find the nearest hospital to Camp 6"),
    ("coxs_bazar", "How do I walk from Camp 3 to Camp 9"),
    ("coxs_bazar", "Show 15 minute walkable area from Camp 8W"),
    ("san_juan", "Find the nearest clinic to Condado"),
    ("san_juan", "Walking route from Santurce to Miramar"),
    ("san_juan", "List pharmacies within 1km of Ocean Park"),
    ("jakarta", "Find nearest hospital to Menteng"),
    ("jakarta", "How far to walk from Gambir to Kemang"),
    ("jakarta", "Schools within 2km of Gelora"),
    ("coxs_bazar", "Clinics near Camp 10"),
]

def run_benchmark():
    results = []
    
    print(f"{'='*60}")
    print("DreamMeridian Quick Benchmark")
    print(f"{'='*60}\n")
    
    # Warmup: load all locations + run one query each
    print("Warming up...", flush=True)
    for loc in ["coxs_bazar", "san_juan", "jakarta"]:
        dm.query("Find nearest hospital", location=loc)
    print("Warmup complete.\n")
    
    total_start = time.time()
    
    for i, (location, query) in enumerate(QUERIES, 1):
        print(f"[{i:2}/10] {location}: {query[:40]}...", end=" ", flush=True)
        
        start = time.time()
        result = dm.query(query, location=location)
        elapsed = time.time() - start
        
        status = "✓" if result.success else "✗"
        print(f"{status} {elapsed:.2f}s")
        
        results.append({
            "location": location,
            "query": query,
            "success": result.success,
            "time": elapsed,
            "tool": result.tool_name if result.success else None,
        })
    
    total_time = time.time() - total_start
    times = [r["time"] for r in results]
    successes = sum(1 for r in results if r["success"])
    
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"  Success:  {successes}/10")
    print(f"  Total:    {total_time:.2f}s")
    print(f"  Mean:     {sum(times)/len(times):.2f}s")
    print(f"  Min:      {min(times):.2f}s")
    print(f"  Max:      {max(times):.2f}s")
    print(f"{'='*60}\n")
    
    # Save results
    import platform
    from pathlib import Path
    
    # Detect device: Pi has "Linux" + "aarch64", Mac has "Darwin"
    is_pi = platform.system() == "Linux" and "aarch64" in platform.machine()
    device = "pi5" if is_pi else "mac"
    
    benchmarks_dir = Path("benchmarks")
    benchmarks_dir.mkdir(exist_ok=True)
    filename = benchmarks_dir / f"benchmark_{device}.json"
    
    with open(filename, "w") as f:
        json.dump({
            "device": device,
            "platform": platform.platform(),
            "processor": platform.processor(),
            "total_time": total_time,
            "mean_time": sum(times)/len(times),
            "results": results,
        }, f, indent=2)
    
    print(f"Saved to {filename}")

if __name__ == "__main__":
    run_benchmark()