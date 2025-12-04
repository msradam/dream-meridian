#!/usr/bin/env python3
"""
DreamMeridian Benchmark
Usage: uv run python benchmark_quick.py
"""

import time
import json
import platform
import subprocess
from pathlib import Path

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


def detect_device() -> tuple[str, str]:
    """Detect device type and return (device_id, architecture)."""
    system = platform.system()
    machine = platform.machine()
    kernel = platform.release().lower()
    
    if system == "Linux":
        # Steam Deck: SteamOS or neptune/valve kernel
        if "neptune" in kernel or "valve" in kernel:
            return "steamdeck", "x86-64 Zen 2"
        try:
            with open("/etc/os-release") as f:
                if "steamos" in f.read().lower():
                    return "steamdeck", "x86-64 Zen 2"
        except FileNotFoundError:
            pass
        
        # Raspberry Pi
        pi_model = Path("/proc/device-tree/model")
        if pi_model.exists():
            model = pi_model.read_text().strip().replace("\x00", "")
            if "Pi 5" in model:
                return "pi5", "ARM Cortex-A76"
            elif "Pi 4" in model:
                return "pi4", "ARM Cortex-A72"
            return "pi", "ARM"
        
        return "linux", machine
    
    elif system == "Darwin":
        if "arm" in machine.lower():
            try:
                r = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                   capture_output=True, text=True, timeout=2)
                chip = r.stdout.strip()
                for m in ["M4", "M3", "M2", "M1"]:
                    if m in chip:
                        return f"mac_{m.lower()}", f"Apple {m}"
            except Exception:
                pass
            return "mac_silicon", "Apple Silicon"
        return "mac_intel", "x86-64 Intel"
    
    return "unknown", machine


def run_benchmark():
    device, arch = detect_device()
    
    print(f"{'='*60}")
    print(f"DreamMeridian Benchmark")
    print(f"{'='*60}")
    print(f"  Device: {device} ({arch})")
    print(f"  Platform: {platform.platform()}")
    print(f"{'='*60}\n")
    
    print("Warming up...", flush=True)
    for loc in ["coxs_bazar", "san_juan", "jakarta"]:
        dm.query("Find nearest hospital", location=loc)
    print("Done.\n")
    
    results = []
    total_start = time.time()
    
    for i, (location, query) in enumerate(QUERIES, 1):
        print(f"[{i:2}/10] {location}: {query[:40]}...", end=" ", flush=True)
        
        start = time.time()
        result = dm.query(query, location=location)
        elapsed = time.time() - start
        
        print(f"{'✓' if result.success else '✗'} {elapsed:.2f}s")
        
        llm_stats = None
        if result.llm_stats and result.llm_stats.tokens_per_sec > 0:
            llm_stats = {
                "prompt_tokens": result.llm_stats.prompt_tokens,
                "completion_tokens": result.llm_stats.completion_tokens,
                "tokens_per_sec": result.llm_stats.tokens_per_sec,
            }
        
        results.append({
            "location": location,
            "query": query,
            "success": result.success,
            "time": elapsed,
            "tool": result.tool_name if result.success else None,
            "llm_stats": llm_stats,
        })
    
    total_time = time.time() - total_start
    times = [r["time"] for r in results]
    successes = sum(1 for r in results if r["success"])
    
    tok_speeds = [r["llm_stats"]["tokens_per_sec"] for r in results 
                  if r["llm_stats"] and r["llm_stats"]["tokens_per_sec"] > 0]
    avg_tok = sum(tok_speeds) / len(tok_speeds) if tok_speeds else 0
    
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"  Device:    {device} ({arch})")
    print(f"  Success:   {successes}/10")
    print(f"  Total:     {total_time:.2f}s")
    print(f"  Mean:      {sum(times)/len(times):.2f}s")
    print(f"  Min:       {min(times):.2f}s")
    print(f"  Max:       {max(times):.2f}s")
    if avg_tok > 0:
        print(f"  Avg tok/s: {avg_tok:.1f}")
    print(f"{'='*60}\n")
    
    benchmarks_dir = Path("benchmarks")
    benchmarks_dir.mkdir(exist_ok=True)
    filename = benchmarks_dir / f"benchmark_{device}.json"
    
    with open(filename, "w") as f:
        json.dump({
            "device": device,
            "architecture": arch,
            "platform": platform.platform(),
            "total_time": round(total_time, 2),
            "mean_time": round(sum(times)/len(times), 2),
            "min_time": round(min(times), 2),
            "max_time": round(max(times), 2),
            "avg_tokens_per_sec": round(avg_tok, 1),
            "success_rate": successes / len(QUERIES),
            "results": results,
        }, f, indent=2)
    
    print(f"Saved to {filename}")


if __name__ == "__main__":
    run_benchmark()