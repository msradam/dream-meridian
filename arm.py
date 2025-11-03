#!/usr/bin/env python3
"""
ARM Optimization Stress Test - DreamMeridian Workload
Tests what ARM optimization actually improves: matrix operations in long-context tool calling
"""

import requests
import time
import subprocess

MODEL = "qwen2.5:1.5b"
API = "http://localhost:11434/api/generate"

# Complex spatial reasoning queries that stress:
# 1. Long context (tool descriptions + reasoning)
# 2. Structured output (JSON tool calls)
# 3. Multi-step reasoning (attention-heavy)
TOOL_CALLING_PROMPTS = [
    {
        "name": "multi_step_spatial_reasoning",
        "prompt": """You have access to these spatial analysis tools:

1. geocode(place_name: str) -> {lat: float, lon: float}
   Converts place names to coordinates
   
2. find_nearest_poi(poi_type: str, lat: float, lon: float, max_results: int) -> list[{name, lat, lon, distance_m}]
   Finds nearest points of interest with actual walking distances
   
3. count_pois(poi_type: str, lat: float, lon: float, radius_m: float) -> int
   Counts POIs within radius
   
4. count_pois_multiple_types(poi_types: list[str], lat: float, lon: float, radius_m: float) -> dict
   Counts multiple POI types simultaneously
   
5. calculate_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> {distance_m, walk_minutes}
   Calculates walking route between two points
   
6. generate_isochrone(lat: float, lon: float, max_minutes: int, poi_types: list[str]) -> list[accessible_pois]
   Shows all locations reachable within time budget

Query: "I'm at Uttara Hospital in Dhaka. I need to find an area that has good access to both schools and pharmacies - specifically, I want to be within 10 minutes walking of at least 3 schools and 2 pharmacies. Can you help me identify such locations nearby and calculate the actual walking distances?"

Think step by step about which tools to use in which order, then generate the complete tool call sequence with actual coordinates and parameters. Explain your reasoning for each step.""",
        "tokens": 600
    },
    {
        "name": "comparative_spatial_analysis",
        "prompt": """You are analyzing spatial accessibility in Dhaka, Bangladesh. You have these tools:

geocode(place_name), find_nearest_poi(type, lat, lon, max_results), count_pois(type, lat, lon, radius), 
count_pois_multiple_types(types[], lat, lon, radius), calculate_route(start_lat, start_lon, end_lat, end_lon),
generate_isochrone(lat, lon, max_minutes, poi_types[]), list_pois(type, lat, lon, radius)

Task: "Compare healthcare accessibility between Gulshan and Uttara neighborhoods. For each area:
1. Find the central coordinates
2. Count hospitals, pharmacies, and clinics within 2km
3. Identify the 5 nearest hospitals with actual walking distances
4. Calculate what healthcare facilities are reachable within 15 minutes walking
5. Provide a quantitative comparison of which area has better healthcare access

Generate the complete analysis plan with all tool calls, parameters, and expected reasoning steps. Include specific coordinate values and explain your methodology.""",
        "tokens": 800
    },
    {
        "name": "complex_routing_with_constraints",
        "prompt": """Given these geospatial tools: geocode, find_nearest_poi, count_pois, count_pois_multiple_types, 
calculate_route, generate_isochrone, list_pois

Scenario: "A family is relocating to Dhaka and needs to find optimal housing. Their constraints:
- Must be within 1.5km of at least 2 good schools
- Must be within 1km of a hospital
- Must be within 500m of a pharmacy
- Prefer areas with multiple restaurants nearby
- Need to calculate commute distance to Gulshan-1 Circle

Start from three candidate locations: Dhanmondi Lake area (23.7461°N, 90.3742°E), 
Uttara Sector 7 (23.8759°N, 90.3795°E), and Banani (23.7937°N, 90.4066°E).

For each location, use the appropriate tools to evaluate against all constraints. 
Generate structured tool calls with reasoning, calculate scores, and recommend the best location.
Explain the complete methodology including which tools to call in which sequence and why.""",
        "tokens": 1000
    }
]

def get_cpu_info():
    """Get key system metrics"""
    temp = subprocess.run(['vcgencmd', 'measure_temp'], capture_output=True, text=True)
    freq = subprocess.run(['vcgencmd', 'measure_clock', 'arm'], capture_output=True, text=True)
    
    temp_c = temp.stdout.split('=')[1].split("'")[0] if temp.returncode == 0 else "?"
    freq_ghz = int(freq.stdout.split('=')[1]) / 1e9 if freq.returncode == 0 else 0
    
    # Check ARM features
    features = subprocess.run(['grep', 'Features', '/proc/cpuinfo'], capture_output=True, text=True)
    feat_line = features.stdout.split(':')[1].strip() if features.returncode == 0 else ""
    
    return {
        'temp': temp_c,
        'freq': f"{freq_ghz:.2f}",
        'neon': '✓' if 'asimd' in feat_line else '✗',
        'fp16': '✓' if 'fphp' in feat_line else '✗',
        'dotprod': '✓' if 'asimddp' in feat_line else '✗'
    }

def run_inference(prompt, max_tokens):
    """Run single inference and return metrics"""
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": 4096,  # Larger context for tool descriptions
            "num_predict": max_tokens,
            "temperature": 0.1,
            "num_thread": 4
        }
    }
    
    start = time.time()
    resp = requests.post(API, json=payload)
    elapsed = time.time() - start
    
    data = resp.json()
    prompt_tokens = data.get('prompt_eval_count', 0)
    completion_tokens = data.get('eval_count', 0)
    tok_per_sec = completion_tokens / elapsed if elapsed > 0 else 0
    
    return elapsed, prompt_tokens, completion_tokens, tok_per_sec

def main():
    print("\n" + "="*70)
    print("ARM STRESS TEST: Spatial Tool Calling Workload")
    print("="*70)
    print("\nThis tests ARM optimization on your actual use case:")
    print("  • Long context (tool descriptions + reasoning)")
    print("  • Structured output (JSON generation)")
    print("  • Multi-step reasoning (attention-heavy)")
    print("  • Matrix operations (what fp16/dotprod accelerate)")
    
    # System info
    info = get_cpu_info()
    print(f"\nSystem Info:")
    print(f"  Temperature: {info['temp']}°C")
    print(f"  Frequency:   {info['freq']} GHz")
    print(f"  ARM Features: NEON={info['neon']} FP16={info['fp16']} DOTPROD={info['dotprod']}")
    
    # Run stress tests
    print(f"\n" + "="*70)
    print("Running 3 spatial reasoning workloads...")
    print("="*70)
    
    all_results = []
    
    for test_case in TOOL_CALLING_PROMPTS:
        print(f"\n{'='*70}")
        print(f"Test: {test_case['name']}")
        print(f"{'='*70}")
        print(f"Prompt length: {len(test_case['prompt'])} chars")
        print(f"Expected output: {test_case['tokens']} tokens")
        print(f"Description: {test_case['prompt'][:80]}...")
        
        print(f"\nRunning inference...", end=" ", flush=True)
        
        try:
            elapsed, prompt_tok, completion_tok, tps = run_inference(
                test_case['prompt'],
                test_case['tokens']
            )
            
            all_results.append({
                'name': test_case['name'],
                'elapsed': elapsed,
                'prompt_tokens': prompt_tok,
                'completion_tokens': completion_tok,
                'tok_per_sec': tps
            })
            
            print(f"✓")
            print(f"  Elapsed: {elapsed:.2f}s")
            print(f"  Context: {prompt_tok} tokens processed")
            print(f"  Generated: {completion_tok} tokens")
            print(f"  Throughput: {tps:.2f} tok/s")
            
            # Cool down between tests
            print(f"\n  Cooling down (5s)...")
            time.sleep(5)
            
        except Exception as e:
            print(f"✗ Error: {e}")
            continue
    
    # Summary
    print(f"\n" + "="*70)
    print("BENCHMARK SUMMARY")
    print("="*70)
    
    if all_results:
        avg_tps = sum(r['tok_per_sec'] for r in all_results) / len(all_results)
        total_tokens = sum(r['completion_tokens'] for r in all_results)
        total_context = sum(r['prompt_tokens'] for r in all_results)
        total_time = sum(r['elapsed'] for r in all_results)
        
        print(f"\nOverall Performance:")
        print(f"  Average throughput: {avg_tps:.2f} tokens/second")
        print(f"  Total tokens generated: {total_tokens}")
        print(f"  Total context processed: {total_context} tokens")
        print(f"  Total inference time: {total_time:.1f}s")
        
        print(f"\nPer-Test Results:")
        for r in all_results:
            print(f"  {r['name']:40s}: {r['tok_per_sec']:6.2f} tok/s ({r['completion_tokens']} tokens)")
        
        # Final system state
        final_info = get_cpu_info()
        print(f"\nFinal State:")
        print(f"  Temperature: {final_info['temp']}°C")
        print(f"  Status: {'⚠️  Thermal stress' if float(final_info['temp']) > 75 else '✓ Within limits'}")
        
        print(f"\n" + "="*70)
        print("This workload stresses:")
        print("  ✓ Matrix multiplication (every transformer layer)")
        print("  ✓ Attention computation (scales with context length)")
        print("  ✓ Quantized operations (Q4_K_M unpacking)")
        print("  ✓ Structured output generation (JSON parsing)")
        print("="*70)
        
        return avg_tps
    else:
        print("\n✗ No successful test runs")
        return 0

if __name__ == "__main__":
    try:
        tps = main()
        print()
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        print("Make sure Ollama is running: ollama serve")
