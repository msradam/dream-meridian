# test_all_tools_v4.py - Comprehensive test with all 8 tools including new ones
import requests
import json
import time
import numpy as np
from spatial_tools_optimized import TOOLS_OPTIMIZED, load_city, execute_tool

# Load precomputed embeddings
print("Loading precomputed tool embeddings...")
tool_embeddings = np.load('data/tool_embeddings_mpnet.npy')
print(f"✓ Loaded embeddings shape: {tool_embeddings.shape}")

# Load embedding model for query encoding
from sentence_transformers import SentenceTransformer
print("Loading mpnet-base-v2 for query encoding...")
embedder = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

def select_relevant_tools(query, top_k=2):
    """Select top-k most relevant tools based on semantic similarity"""
    query_embedding = embedder.encode([query])
    similarities = np.dot(query_embedding, tool_embeddings.T)[0]
    top_indices = np.argsort(similarities)[-top_k:][::-1]
    selected = [TOOLS_OPTIMIZED[i] for i in top_indices]
    
    print(f"Selected tools: {[t['function']['name'] for t in selected]}")
    print(f"Similarities: {[f'{similarities[i]:.3f}' for i in top_indices]}")
    
    return selected, similarities[top_indices]

# Load city
load_city("dhaka")

# Comprehensive test queries covering all 8 tools
TEST_QUERIES = [
    # Tool 1: geocode_place
    {
        "query": "Find the coordinates for Uttara Hospital",
        "expected_tool": "geocode_place",
        "category": "geocoding"
    },
    {
        "query": "What are the GPS coordinates of Dhanmondi Lake?",
        "expected_tool": "geocode_place",
        "category": "geocoding"
    },
    
    # Tool 2: generate_isochrone
    {
        "query": "Show me everywhere I can walk to in 15 minutes from 23.8747, 90.3967",
        "expected_tool": "generate_isochrone",
        "category": "reachability"
    },
    {
        "query": "What areas are accessible within 10 minutes walking from this location: 23.8700, 90.3950",
        "expected_tool": "generate_isochrone",
        "category": "reachability"
    },
    {
        "query": "Find all hospitals I can reach in 15 minutes walking from 23.8747, 90.3967",
        "expected_tool": "generate_isochrone",
        "category": "reachability_with_pois"
    },
    
    # Tool 3: find_nearest_poi_with_route
    {
        "query": "Which hospital is actually closest by walking distance from 23.8700, 90.3950?",
        "expected_tool": "find_nearest_poi_with_route",
        "category": "nearest_walking"
    },
    {
        "query": "Find the nearest 3 restaurants with actual walking routes from 23.8103, 90.4125",
        "expected_tool": "find_nearest_poi_with_route",
        "category": "nearest_walking"
    },
    {
        "query": "Show me nearby pharmacies with real walking distances, not straight-line",
        "expected_tool": "find_nearest_poi_with_route",
        "category": "nearest_walking"
    },
    
    # Tool 4: count_pois
    {
        "query": "Count hospitals within 2km of 23.8103, 90.4125",
        "expected_tool": "count_pois",
        "category": "single_count"
    },
    {
        "query": "How many schools exist near 23.8747, 90.3967?",
        "expected_tool": "count_pois",
        "category": "single_count"
    },
    
    # Tool 5: list_pois
    {
        "query": "List restaurant names and locations near 23.8103, 90.4125",
        "expected_tool": "list_pois",
        "category": "single_list"
    },
    {
        "query": "Show me all pharmacy names with their distances from 23.8747, 90.3967",
        "expected_tool": "list_pois",
        "category": "single_list"
    },
    
    # Tool 6: calculate_route
    {
        "query": "Calculate walking distance from 23.8103, 90.4125 to 23.8200, 90.4200",
        "expected_tool": "calculate_route",
        "category": "route"
    },
    {
        "query": "What is the pedestrian path between these two coordinates: 23.8747, 90.3967 and 23.8700, 90.3950?",
        "expected_tool": "calculate_route",
        "category": "route"
    },
    
    # Tool 7: count_pois_multiple_types
    {
        "query": "Compare hospitals, pharmacies, and schools within 1.5km of 23.8103, 90.4125",
        "expected_tool": "count_pois_multiple_types",
        "category": "multi_count"
    },
    {
        "query": "Batch count: schools, libraries, and banks within 2km of 23.8747, 90.3967",
        "expected_tool": "count_pois_multiple_types",
        "category": "multi_count"
    },
    {
        "query": "Count several POI categories simultaneously: cafes, restaurants, and bars near 23.8103, 90.4125",
        "expected_tool": "count_pois_multiple_types",
        "category": "multi_count"
    },
    
    # Tool 8: create_map - This one is tricky, usually called after data collection
    # We'll test if the LLM recognizes visualization intent
    {
        "query": "Create a map showing all hospitals around 23.8103, 90.4125",
        "expected_tool": "list_pois",  # Should collect data first
        "category": "visualization_intent"
    },
    
    # Complex reasoning tests
    {
        "query": "If I'm at 23.8700, 90.3950 and need a hospital urgently, which is fastest to reach by foot?",
        "expected_tool": "find_nearest_poi_with_route",
        "category": "emergency_routing"
    },
    {
        "query": "Are there more schools or hospitals in the Uttara area near 23.8747, 90.3967?",
        "expected_tool": "count_pois_multiple_types",
        "category": "comparison_query"
    },
    {
        "query": "Find a place called Uttara Medical College and then show me pharmacies nearby",
        "expected_tool": "geocode_place",
        "category": "multi_step_geocode"
    },
]

MODEL_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:1.5b"

results = []

print("\n" + "="*80)
print("COMPREHENSIVE TEST: ALL 8 TOOLS WITH MPNET EMBEDDINGS")
print("="*80)

for i, test_case in enumerate(TEST_QUERIES, 1):
    query = test_case["query"]
    expected = test_case["expected_tool"]
    category = test_case["category"]
    
    print(f"\n[Test {i}/{len(TEST_QUERIES)}] Category: {category}")
    print(f"Query: {query}")
    print(f"Expected tool: {expected}")
    print("-" * 80)
    
    # Tool selection
    tool_selection_start = time.time()
    relevant_tools, similarities = select_relevant_tools(query, top_k=2)
    tool_selection_time = time.time() - tool_selection_start
    
    # LLM call
    messages = [{"role": "user", "content": query}]
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": relevant_tools,
        "stream": False,
        "options": {
            "num_ctx": 1024,
            "num_predict": 512,
            "temperature": 0.1
        }
    }
    
    llm_start = time.time()
    response = requests.post(MODEL_URL, json=payload)
    llm_time = time.time() - llm_start
    
    result = response.json()
    
    # Extract tool call
    actual_tool = None
    tool_args = None
    if 'message' in result and 'tool_calls' in result['message']:
        tool_call = result['message']['tool_calls'][0]['function']
        actual_tool = tool_call['name']
        tool_args = tool_call['arguments']
    
    # Determine success
    success = actual_tool == expected
    
    # Store results
    test_result = {
        "query": query,
        "category": category,
        "expected": expected,
        "actual": actual_tool,
        "success": success,
        "tool_selection_time": tool_selection_time,
        "llm_time": llm_time,
        "total_time": tool_selection_time + llm_time,
        "prompt_tokens": result.get('prompt_eval_count', 0),
        "completion_tokens": result.get('eval_count', 0),
        "similarities": similarities.tolist(),
        "selected_tools": [t['function']['name'] for t in relevant_tools]
    }
    results.append(test_result)
    
    # Print result
    status = "✓ PASS" if success else "✗ FAIL"
    print(f"Actual tool: {actual_tool} {status}")
    print(f"Timing: {tool_selection_time:.3f}s (selection) + {llm_time:.2f}s (LLM) = {test_result['total_time']:.2f}s")
    print(f"Tokens: {test_result['prompt_tokens']} prompt, {test_result['completion_tokens']} completion")
    
    # Show tool arguments if available
    if tool_args:
        print(f"Arguments: {json.dumps(tool_args, indent=2)}")

# Summary statistics
print("\n" + "="*80)
print("TEST SUMMARY")
print("="*80)

total_tests = len(results)
passed = sum(1 for r in results if r['success'])
failed = total_tests - passed

print(f"\nAccuracy: {passed}/{total_tests} ({100*passed/total_tests:.1f}%)")
print(f"Passed: {passed}")
print(f"Failed: {failed}")

# Timing stats
avg_tool_selection = np.mean([r['tool_selection_time'] for r in results])
avg_llm_time = np.mean([r['llm_time'] for r in results])
avg_total = np.mean([r['total_time'] for r in results])
avg_prompt_tokens = np.mean([r['prompt_tokens'] for r in results])
avg_completion_tokens = np.mean([r['completion_tokens'] for r in results])

print(f"\nAverage Timing:")
print(f"  Tool selection: {avg_tool_selection:.3f}s")
print(f"  LLM inference: {avg_llm_time:.2f}s")
print(f"  Total: {avg_total:.2f}s")

print(f"\nAverage Tokens:")
print(f"  Prompt: {avg_prompt_tokens:.0f}")
print(f"  Completion: {avg_completion_tokens:.0f}")
print(f"  Total: {avg_prompt_tokens + avg_completion_tokens:.0f}")

# Performance by category
print(f"\nPerformance by Category:")
categories = {}
for r in results:
    cat = r['category']
    if cat not in categories:
        categories[cat] = {'total': 0, 'passed': 0, 'times': []}
    categories[cat]['total'] += 1
    if r['success']:
        categories[cat]['passed'] += 1
    categories[cat]['times'].append(r['total_time'])

for cat, stats in sorted(categories.items()):
    accuracy = 100 * stats['passed'] / stats['total']
    avg_time = np.mean(stats['times'])
    print(f"  {cat:30s}: {stats['passed']}/{stats['total']} ({accuracy:.0f}%) - avg {avg_time:.1f}s")

# Tool selection frequency
print(f"\nTool Selection Frequency:")
tool_selections = {}
for r in results:
    for tool in r['selected_tools']:
        if tool not in tool_selections:
            tool_selections[tool] = 0
        tool_selections[tool] += 1

for tool, count in sorted(tool_selections.items(), key=lambda x: x[1], reverse=True):
    print(f"  {tool:35s}: selected {count:2d} times")

# Tool accuracy breakdown
print(f"\nPer-Tool Accuracy:")
tool_accuracy = {}
for r in results:
    expected = r['expected']
    if expected not in tool_accuracy:
        tool_accuracy[expected] = {'total': 0, 'correct': 0}
    tool_accuracy[expected]['total'] += 1
    if r['success']:
        tool_accuracy[expected]['correct'] += 1

for tool, stats in sorted(tool_accuracy.items()):
    accuracy = 100 * stats['correct'] / stats['total']
    print(f"  {tool:35s}: {stats['correct']}/{stats['total']} ({accuracy:.0f}%)")

# Failed cases detail
if failed > 0:
    print(f"\nFailed Cases Detail:")
    for r in results:
        if not r['success']:
            print(f"\n  Query: {r['query'][:70]}...")
            print(f"    Expected: {r['expected']}")
            print(f"    Got: {r['actual']}")
            print(f"    Selected tools: {r['selected_tools']}")
            print(f"    Similarities: {[f'{s:.3f}' for s in r['similarities']]}")

# Speed analysis
print(f"\nSpeed Analysis:")
fastest = min(results, key=lambda x: x['total_time'])
slowest = max(results, key=lambda x: x['total_time'])
print(f"  Fastest: {fastest['total_time']:.2f}s - {fastest['query'][:50]}...")
print(f"  Slowest: {slowest['total_time']:.2f}s - {slowest['query'][:50]}...")

print("\n" + "="*80)
print("SYSTEM PERFORMANCE SUMMARY")
print("="*80)
print(f"Total tools available: 8")
print(f"Tools used per query: 2 (via semantic selection)")
print(f"Overall accuracy: {100*passed/total_tests:.1f}%")
print(f"Average latency: {avg_total:.2f}s")
print(f"Token efficiency: ~{avg_prompt_tokens:.0f} tokens/query (vs ~800 for all 8 tools)")
print("="*80)
