## DreamMeridian: GeoAI on Pi

**Author: Adam Munawar Rahman, December 2025**

DreamMeridian answers natural language spatial queries entirely offline on a Raspberry Pi 5. Ask "Find hospitals within 2km of Camp 8W" or "How do I walk from Camp 3 to Camp 8W?" and get real answers with structured data in under 11 seconds. No internet, no cloud, ~$210 in hardware.

### Inspiration

At UNICEF Innovation, I used OpenStreetMap and NetworkX to calculate distances between schools and health facilities in programme countries. It worked—but required connectivity, compute, and coding expertise that field workers don't have.

Hurricane Maria (2017) knocked out roughly 95% of Puerto Rico's cell sites immediately after landfall (FCC Communications Status Report, Sept. 22, 2017). The island lost power for months; a George Washington University study estimated 2,975 excess deaths in the six months following, with mortality elevated due to prolonged failures in power, water, and medical access (Santos-Burgoa et al., GWU/Lancet Planetary Health, 2018).

2.6 billion people remain offline globally (ITU Facts and Figures 2024). Millions of humanitarian volunteers—including over 16 million in the Red Cross/Red Crescent network (IFRC Global Plan 2025)—deploy regularly to connectivity-constrained environments. They need spatial intelligence that works offline, on hardware a solar panel can power.

### What it does

DreamMeridian is an offline spatial query engine. You ask questions in natural language; it returns walking routes, distances, and POI locations from a local OpenStreetMap database and precomputed road network graph.

**CLI** (`dream-meridian.py`): Query from the command line.
```bash
python dream-meridian.py -l coxs_bazar "I need to find the nearest hospital to Camp 6"
python dream-meridian.py -l san_juan "Where is the closest hospital to Condado"
python dream-meridian.py -l jakarta "Is there a bank near Gelora"
```

**Frontend** (`app.py`): Streamlit web interface with Folium maps, live system stats, and location switching. Runs locally on the Pi.

**Spatial tools**: Six functions the LLM can call:
- `list_pois` — find POIs by type within a radius
- `find_nearest_poi_with_route` — nearest POIs with walking time via graph routing
- `find_along_route` — find POIs along a path between two points
- `calculate_route` — walking directions between two points
- `generate_isochrone` — all points reachable within N minutes
- `geocode_place` — resolve place names to coordinates

**Data builder** (`build_location.py`): Downloads OSM street networks and POIs for any location, builds the graph and spatial database. Run once per location; the device is then self-sufficient.

### Pre-Built Datasets

Three disaster response scenarios with offline data:

| Location | Context | Graph Nodes | POIs | Place Names |
|----------|---------|-------------|------|-------------|
| Cox's Bazar | Rohingya refugee camps | 27,551 | 6,509 | 464 |
| San Juan | Hurricane response | 24,602 | 11,351 | 405 |
| Jakarta | Urban flood response | 208,281 | 41,028 | 331 |

Data sourced from OpenStreetMap via OSMnx.

### How I built it

**Data preparation** (`build_location.py`): The build script follows standard humanitarian GIS workflows. For any location string (e.g., "Cox's Bazar, Bangladesh"), it:

1. Downloads the street network from OpenStreetMap via OSMnx
2. Converts the NetworkX graph to NetworKit's binary format for fast routing
3. Queries OSM for humanitarian-relevant POIs—hospitals, clinics, pharmacies, schools, water points, shelters, police stations, banks, markets, fuel stations, places of worship
4. Extracts neighborhood and locality names for the geocoding layer
5. Loads everything into a DuckDB database with spatial indexes

**Runtime layers**:

1. **Geocode Layer** — Resolves place names ("Condado" → `lat 18.456, lon -66.072`) from the local places table before the query reaches the LLM.

2. **LLM Tool Selection** — xLAM-2-1b-fc-r parses the query and selects a tool. Grammar constraints guarantee valid JSON output.

3. **Spatial Tools** — Six functions built on DuckDB (spatial queries) and NetworKit (graph routing).

4. **Frontend** — Streamlit + Folium maps with live system stats, or CLI for scripting.

### Why Raspberry Pi, Not a Phone?

Smartphones are everywhere in field environments and can run LLMs with proper optimization. But DreamMeridian needs a specific data science stack beyond the LLM.

DuckDB Spatial depends on GEOS, GDAL, and PROJ—C++ geospatial libraries that don't have mobile builds. NetworKit uses OpenMP for parallel graph algorithms, which Android NDK doesn't support. These dependencies are what make sub-50ms spatial queries and isochrone generation on 200,000+ node graphs possible.

A Pi 5 running Linux gives us the full Python + C userspace for these libraries, plus compatibility with the broader ecosystem (pandas, OSMnx, Folium). Field teams can extend the system with tools they already know—no mobile dev expertise required.

**The Pi as ARM Edge Proof of Concept**

The Raspberry Pi has become the de facto prototyping platform for edge computing deployments. DreamMeridian leverages this ecosystem: the Pi 5 serves as a proof of concept demonstrating that LLM-powered spatial intelligence can run on consumer-grade ARM hardware with full access to the Python data science stack. Testing on intentionally constrained consumer hardware (~$210, 16GB RAM, no GPU) validates that the system can operate within the resource limits humanitarian deployments actually face.

### ARM Optimization

The Pi 5's Cortex-A76 has SIMD instructions (NEON) that process multiple numbers in a single CPU cycle. Each layer of the stack leverages ARM appropriately:

**llama.cpp** is the most optimized—it has hand-written ARM code for the math that dominates LLM inference. Building with `-mcpu=cortex-a76` enables these fast paths.

**DuckDB** and **NumPy** benefit from ARM's pre-built binaries and compiler optimizations.

**NetworKit** parallelizes across the Pi's 4 CPU cores for graph algorithms.

### Benchmark Results

Full benchmark suite of 57 natural language queries across all three locations.

| Metric | Value |
|--------|-------|
| Total queries | 57 |
| Success rate | **94.7%** |
| Avg response time | 10.87s |
| LLM inference | 8.9 tok/s |

**By location:**
- Cox's Bazar: 19/19 (100%)
- San Juan: 18/19 (94.7%)
- Jakarta: 17/19 (89.5%)

**By tool:** Route calculation and nearest-POI queries achieved 100% accuracy. The 3 failures were tool selection errors on ambiguous phrasing—addressable through prompt engineering. See [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) for detailed analysis.

### Challenges

**Model selection.** Most small LLMs fail at structured tool-calling. xLAM-2-1b-fc-r, Salesforce's April 2025 "Tiny Giant" release, achieved #1 on the Berkeley Function-Calling Leaderboard—state-of-the-art performance outperforming GPT-4o and Claude 3.5 on function-calling benchmarks.

**Geocoding without an API.** I built a dedicated geocode layer that loads all OSM place names into memory and matches with word boundaries and longest-match-first ordering—so "Camp 8E" matches before "Camp 8".

### Accomplishments

- **8-14 second queries** via grammar constraints, prompt minimization, and ARM-optimized builds
- **~$210 hardware cost** vs. $4,500-36,000/year for enterprise GIS licensing
- **Three humanitarian datasets** — Cox's Bazar (27K nodes), San Juan (24K nodes), Jakarta (208K nodes)
- **ARM-native stack** — existing offline LLM+GIS solutions target enterprise GPU servers; DreamMeridian runs on CPU-only ARM with integrated graph routing

### What I learned

- Grammar-constrained generation eliminates JSON syntax errors—no post-hoc parsing failures
- Specialized small models beat general large models for tool-calling
- LLM inference is the bottleneck on low-power ARM hardware
- C++ matters on edge: NetworKit vs NetworkX is ~50ms vs ~5s for isochrones
- Data prep is the real work. The LLM is only as good as what it queries.

### What's next

**Near-term:**
- Voice input via local Whisper (speech-to-text on device)
- Offline map tiles for fully air-gapped deployment
- GPS module via Pi GPIO for current-location queries

**Medium-term:**
- Public CLI pipeline for downloading DreamMeridian-ready datasets for any OSM location
- Integration with HDX (Humanitarian Data Exchange) for pre-built crisis region datasets

**Long-term:**
- Support for Pi AI HAT modules (Hailo, etc.) for additional TOPS
- Deployable spatial AI kits for humanitarian field operations

## Hardware

Raspberry Pi 5 Model B Rev 1.1 (16GB) with CanaKit Starter PRO kit (~$210): Turbine case with fan, heatsink, 128GB SD card, 45W PD power supply. ARM Cortex-A76 @ 2.4GHz, DietPi 64-bit, under 10W for CPU-only workloads.

## Step-by-step Instructions

**1. System Preparation**
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git cmake build-essential python3-venv libopenblas-dev
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Clone and Setup**
```bash
git clone https://github.com/msradam/dream-meridian.git
cd dream-meridian
uv sync
```

**3. Compile llama.cpp with ARM Optimizations**
```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp && mkdir build && cd build

cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_FLAGS="-mcpu=cortex-a76 -O3 -ffast-math -fno-finite-math-only" \
    -DCMAKE_CXX_FLAGS="-mcpu=cortex-a76 -O3 -ffast-math -fno-finite-math-only" \
    -DGGML_NATIVE=ON \
    -DGGML_LTO=ON

cmake --build . --config Release -j4
cd ../..
```

**4. Download Model**
```bash
mkdir -p models
uv run --with huggingface-hub huggingface-cli download \
    Salesforce/xLAM-2-1b-fc-r-gguf \
    xLAM-2-1B-fc-r-Q5_K_M.gguf \
    --local-dir ./models
```

**5. Run the System**

**Terminal 1: Start LLM Server**
```bash
./llama.cpp/build/bin/llama-server \
    -m models/xLAM-2-1B-fc-r-Q5_K_M.gguf \
    --grammar-file tool_grammar.gbnf \
    -c 2048 -t 4 --mlock \
    --host 0.0.0.0 --port 8080
```

**Terminal 2: Run Queries**
```bash
# Web Dashboard
uv run streamlit run app.py --server.port 8501

# Command Line
uv run python dream-meridian.py -l coxs_bazar "I need to find the nearest hospital to Camp 6"
```

## Queries to Try

**Cox's Bazar (Refugee Camps)**
```bash
uv run python dream-meridian.py -l coxs_bazar "I need to find the nearest hospital to Camp 6"
uv run python dream-meridian.py -l coxs_bazar "How do I walk from Camp 3 to Camp 8W"
uv run python dream-meridian.py -l coxs_bazar "Show me everywhere I can walk to in 15 minutes from Camp 8W"
```

**San Juan (Hurricane Response)**
```bash
uv run python dream-meridian.py -l san_juan "Where is the closest hospital to Condado"
uv run python dream-meridian.py -l san_juan "How do I get from Condado to Santurce on foot"
uv run python dream-meridian.py -l san_juan "Show me a 20 minute walking radius from Condado"
```

**Jakarta (Urban Flood Response)**
```bash
uv run python dream-meridian.py -l jakarta "Is there a bank near Gelora"
uv run python dream-meridian.py -l jakarta "What is the distance on foot from Pinangsia to Kalianyar"
uv run python dream-meridian.py -l jakarta "What can I reach in 15 minutes walking from Serdang"
```
