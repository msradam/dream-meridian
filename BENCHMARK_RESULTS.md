# DreamMeridian Benchmark Results

**Device:** Raspberry Pi 5 (16GB RAM), DietPi (aarch64)  
**Date:** December 3, 2025  
**Model:** xLAM-2-1B-fc-r (Q5_K_M quantization)

## Summary

| Metric | Value |
|--------|-------|
| Total queries | 57 |
| Correct | 54 |
| Wrong tool | 3 |
| Success rate | **94.7%** |
| Total time | 652.6s (~10.9 min) |
| Average time | 10.87s |

*Note: 3 geocode-only queries excluded. These are resolved by the geocoding layer before reaching the LLM, making the LLM tool call redundant.*

---

## Results by Location

| Location | Queries | Correct | Success Rate |
|----------|---------|---------|--------------|
| Cox's Bazar, Bangladesh | 19 | 19 | 100% |
| San Juan, Puerto Rico | 19 | 18 | 94.7% |
| Jakarta, Indonesia | 19 | 17 | 89.5% |

---

## Results by Tool Type

| Tool | Queries | Correct | Success Rate | Avg Time |
|------|---------|---------|--------------|----------|
| find_nearest_poi_with_route | 21 | 21 | 100% | 9.6s |
| calculate_route | 15 | 15 | 100% | 13.8s |
| generate_isochrone | 12 | 12 | 100% | 9.7s |
| list_pois | 9 | 6 | 66.7% | 10.2s |

---

## Successful Examples

### Find Nearest POI ✅

**Query:** "I need emergency shelter near Minillas"
```
GEOCODING
  📍 Minillas → (18.448591, -66.065125)

LLM TOOL CALL
  Tool: find_nearest_poi_with_route
  Args: {"poi_type": "shelter", "lat": 18.448591, "lon": -66.065125}

RESULTS
  Nearest shelter(s): 3 found
    🚶 Colegio de la Inmaculada — 12.0 min (999m)
    🚶 Pavilion — 14.9 min (1243m)
    🚶 Av. Mónica Puig Marchán — 28.9 min (2409m)

PERFORMANCE
  ⏱️ Total time: 9.18s
```

### Calculate Route ✅

**Query:** "How do I walk from Cipulir to Lebak Bulus"
```
GEOCODING
  📍 Lebak Bulus → (-6.301672, 106.779691)
  📍 Cipulir → (-6.238566, 106.773438)

LLM TOOL CALL
  Tool: calculate_route
  Args: {"start_lat": -6.238566, "start_lon": 106.773438, 
         "end_lat": -6.301672, "end_lon": 106.779691}

RESULTS
  📏 Distance:   8.48 km
  🚶 Walk time:  102 minutes
  🔗 Path nodes: 194

PERFORMANCE
  ⏱️ Total time: 12.72s
```

### Generate Isochrone ✅

**Query:** "What areas are reachable within 20 minutes on foot from Camp 13"
```
GEOCODING
  📍 Camp 13 → (21.179189, 92.140195)

LLM TOOL CALL
  Tool: generate_isochrone
  Args: {"lat": 21.179189, "lon": 92.140195, "max_minutes": 20}

RESULTS
  ⏱️ Max time:       20 minutes
  🔗 Reachable nodes: 1,812
  📐 Boundary points: 109

PERFORMANCE
  ⏱️ Total time: 8.66s
```

### List POIs ✅

**Query:** "List all clinics within 3km of Camp 10"
```
GEOCODING
  📍 Camp 10 → (21.189555, 92.154857)

LLM TOOL CALL
  Tool: list_pois
  Args: {"poi_type": "clinic", "lat": 21.189555, "lon": 92.154857, "radius_m": 3000}

RESULTS
  Found 18 clinic(s) within 3000m
    • MSF BKL Health Post 3 (491m)
    • MSF BKL OPD 1 (705m)
    • MSF-F OPD1 (828m)
    • MSF BKL Health Post 1 (961m)
    ... and 14 more

PERFORMANCE
  ⏱️ Total time: 9.98s
```

---

## Unsuccessful Examples

### Wrong Tool: Isochrone Instead of Find Nearest ❌

**Query:** "Where is the nearest school to Quintana"

**Expected:** `find_nearest_poi_with_route` with `poi_type: "school"`
```
GEOCODING
  📍 Quintana → (18.419962, -66.047770)

LLM TOOL CALL
  Tool: generate_isochrone  ← WRONG TOOL
  Args: {"lat": 18.419962, "lon": -66.04777, "max_minutes": 5}

RESULTS
  ⏱️ Max time:       5 minutes
  🔗 Reachable nodes: 49
  📐 Boundary points: 12
```

**Problem:** User asked for nearest school, got a 5-minute walkable area instead. No schools listed.

---

### Wrong Tool: Isochrone Instead of List POIs ❌

**Query:** "Show me banks within 2km of Pinangsia"

**Expected:** `list_pois` with `poi_type: "bank"` and `radius_m: 2000`
```
GEOCODING
  📍 Pinangsia → (-6.135585, 106.814641)

LLM TOOL CALL
  Tool: generate_isochrone  ← WRONG TOOL
  Args: {"lat": -6.135585, "lon": 106.814641, "max_minutes": 2}

RESULTS
  ⏱️ Max time:       2 minutes
  🔗 Reachable nodes: 11
  📐 Boundary points: 5
```

**Problem:** LLM confused "2km" with "2 minutes". User asked for banks, got a tiny walkable area instead.

---

### Wrong Tool: Isochrone Instead of Find Nearest ❌

**Query:** "Where is the nearest marketplace to Kalianyar"

**Expected:** `find_nearest_poi_with_route` with `poi_type: "marketplace"`
```
GEOCODING
  📍 Kalianyar → (-6.157785, 106.798784)

LLM TOOL CALL
  Tool: generate_isochrone  ← WRONG TOOL
  Args: {"lat": -6.157785, "lon": 106.798784, "max_minutes": 10}

RESULTS
  ⏱️ Max time:       10 minutes
  🔗 Reachable nodes: 351
  📐 Boundary points: 96
```

**Problem:** User asked for nearest marketplace, got a 10-minute walkable area instead.

---

## Failure Patterns

| Pattern | Count | Cause |
|---------|-------|-------|
| "nearest X" → isochrone | 2 | LLM defaults to isochrone for ambiguous "where is" queries |
| "within Nkm" → N minutes | 1 | LLM confused distance unit with time unit |

---

## Pathways to Improvement

### 1. Prompt Engineering (Low effort, Medium impact)

Add explicit examples to the system prompt showing when to use each tool:
```
- "nearest X" or "closest X" → find_nearest_poi_with_route
- "within N km" or "within N meters" → list_pois with radius_m
- "within N minutes" or "walkable area" → generate_isochrone
```

### 2. Few-Shot Examples (Medium effort, High impact)

Include 2-3 worked examples in the prompt for ambiguous cases:
```
User: "Where is the nearest pharmacy to Camp 6"
Tool: find_nearest_poi_with_route
Args: {"poi_type": "pharmacy", "lat": 21.203729, "lon": 92.156864}

User: "Show me hospitals within 2km of Condado"  
Tool: list_pois
Args: {"poi_type": "hospital", "lat": 18.455924, "lon": -66.07167, "radius_m": 2000}
```

### 3. Query Preprocessing (Medium effort, High impact)

Add a regex layer before LLM to detect patterns and hint the correct tool:
```python
if re.search(r'nearest|closest', query, re.I):
    hint = "Use find_nearest_poi_with_route"
elif re.search(r'within \d+\s*(km|m|meter)', query, re.I):
    hint = "Use list_pois with radius_m"
elif re.search(r'within \d+\s*(min|minute)', query, re.I):
    hint = "Use generate_isochrone"
```

### 4. Model Fine-Tuning (High effort, High impact)

Fine-tune xLAM on spatial query examples specific to this tool set. Would require:
- 500-1000 labeled query→tool pairs
- LoRA fine-tuning on the base model
- Re-quantization for deployment

### 5. Validation Layer (Low effort, Medium impact)

Add post-LLM validation to catch obvious mismatches:
```python
if "nearest" in query.lower() and tool_name == "generate_isochrone":
    # Re-prompt or override to find_nearest_poi_with_route
```

---

## LLM Performance

| Metric | Value |
|--------|-------|
| Inference speed | 8.6-10.3 tok/s |
| Average speed | 8.9 tok/s |
| Prompt tokens | 201-232 |
| Completion tokens | 38-82 |

---

## Graph Statistics

| Location | Nodes | Edges | POIs | Places |
|----------|-------|-------|------|--------|
| Cox's Bazar | 27,551 | 71,530 | 6,509 | 464 |
| San Juan | 24,602 | 61,055 | 11,351 | 405 |
| Jakarta | 208,281 | 508,954 | 41,028 | 331 |
| **Total** | **260,434** | **641,539** | **58,888** | **1,200** |

---

## Conclusion

**94.7% success rate** across 57 functional queries demonstrates strong natural language understanding for spatial tool selection. The system reliably handles:

- Multiple phrasings ("find me", "I need", "show me", "list all")
- 10 POI types (hospitals, clinics, pharmacies, banks, schools, shelters, fuel, markets, police, places of worship)
- Route calculations (0.66 km to 33.31 km)
- Isochrone analysis (5-20 minute walking radii)
- Three geographic contexts (24K to 208K nodes)

The 3 failures share a common pattern: ambiguous "where is" or distance/time confusion. These are addressable through prompt engineering or a lightweight preprocessing layer without model changes.
