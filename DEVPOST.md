## DreamMeridian: GeoAI on Pi

**Author: Adam Munawar Rahman, December 2025**

DreamMeridian answers natural language spatial queries entirely offline on a Raspberry Pi 5. Ask "Find hospitals within 2km of Camp 8W" or "How do I walk from Camp 3 to Camp 8W?" and get real answers with structured data in under 11 seconds. No internet, no cloud, ~$210 in hardware.

---

### Inspiration

At UNICEF Innovation, I used OpenStreetMap and NetworkX to calculate distances between schools and health facilities in programme countries. It worked, but required connectivity, compute, and coding expertise that field workers don't have.

Hurricane Maria (2017) knocked out 95.6% of Puerto Rico's cell sites within two days of landfall (FCC, 2017). The island lost power for months; a George Washington University study estimated 2,975 excess deaths in the six months following, with mortality elevated due to prolonged failures in power, water, and medical access (Santos-Burgoa et al., 2018).

2.6 billion people remain offline globally (ITU, 2024). Millions of humanitarian volunteers—including over 16 million in the Red Cross/Red Crescent network (IFRC, 2025)—deploy regularly to connectivity-constrained environments. They need spatial intelligence that works offline, on hardware a solar panel can power.

---

### The Gap

Cloud-based mapping tools like Google Maps and ArcGIS Online require constant connectivity. When networks fail, they fail.

Enterprise offline GIS exists, but it's complex. ArcGIS Enterprise disconnected deployments require dedicated servers, portal configuration, utility services, and extensive setup for each disconnected environment (Esri, 2024). Annual licensing runs $5,400-$21,600 for term licenses alone. This is designed for organizations with IT departments, not field workers with a backpack.

Offline mobile maps exist too. Apps like OsmAnd let you download map tiles and search for POIs. But they rely on manual search boxes and predefined queries. There's no spatial reasoning: you can't ask "What's the walking distance from Camp 3 to the nearest clinic?" and get a routed answer.

LLM-powered agents can reason about spatial queries. But existing implementations target cloud deployments or enterprise GPU servers. Running a full GIS stack with graph routing and an LLM on portable, low-power hardware hasn't been done.

DreamMeridian fills this gap: natural language spatial queries on a $210 single-board computer, entirely offline.

---

### What it does

DreamMeridian is an offline spatial query engine. You ask questions in natural language; it returns walking routes, distances, and POI locations from a local OpenStreetMap database and precomputed road network graph.

**CLI** (`dream-meridian.py`): Query from the command line.
```bash
python dream-meridian.py -l coxs_bazar "I need to find the nearest hospital to Camp 6"
python dream-meridian.py -l san_juan "Where is the closest hospital to Condado"
python dream-meridian.py -l jakarta "Is there a bank near Gelora"
```

**Frontend** (`app.py`): Streamlit web interface with Folium maps, live system stats, and location switching.

**Spatial tools**: Six functions the LLM can call:
- `list_pois` — find POIs by type within a radius
- `find_nearest_poi_with_route` — nearest POIs with walking time via graph routing
- `calculate_route` — walking directions between two points
- `find_along_route` — find POIs along a path between two points
- `generate_isochrone` — all points reachable within N minutes
- `geocode_place` — resolve place names to coordinates

---

### Pre-Built Datasets

Three disaster response scenarios with offline data:

| Location | Context | Graph Nodes | POIs | Place Names |
|----------|---------|-------------|------|-------------|
| Cox's Bazar | Rohingya refugee camps | 27,551 | 6,509 | 464 |
| San Juan | Hurricane response | 24,602 | 11,351 | 405 |
| Jakarta | Urban flood response | 208,281 | 41,028 | 331 |

Data sourced from OpenStreetMap via OSMnx.

---

### Optimizing for Cortex-A76

The Raspberry Pi 5's Cortex-A76 was chosen over the Pi 4's Cortex-A72 for one reason: ARMv8.2-A ML extensions.

**Why it matters for LLM inference:**

The Cortex-A76 supports SDOT/UDOT dot product instructions that compute four INT8 multiply-accumulates in a single cycle. The Cortex-A72 lacks these entirely and falls back to slower scalar operations. For quantized transformer inference, this is the bottleneck.

| Feature | Cortex-A72 (Pi 4) | Cortex-A76 (Pi 5) |
|---------|-------------------|-------------------|
| SDOT/UDOT (INT8 dot product) | Not supported | Supported |
| Native FP16 arithmetic | Conversion only | Direct compute |
| L3 Cache | None | 2MB shared |
| Memory bandwidth | ~12.8 GB/s | ~17 GB/s |
| Clock speed | 1.5-1.8 GHz | 2.4 GHz |

The result: 3-5x faster inference for 1B parameter models on Pi 5 vs Pi 4.

**Why xLAM-2-1b-fc-r:**

Most small LLMs fail at structured tool-calling. Salesforce's xLAM-2-1b-fc-r was trained specifically for function calling on 60,000 examples across 3,673 executable APIs (Zhang et al., 2024). The xLAM family achieved #1 on the Berkeley Function-Calling Leaderboard V1, outperforming GPT-4 and Claude-3-Opus on tool-use benchmarks (Salesforce AI Research, 2024).

The Q5_K_M quantization compresses the model to 1.1GB while preserving accuracy. This fits comfortably in Pi 5's 8-16GB RAM with headroom for the spatial database and graph routing.

**Build flags that matter:**

```bash
cmake .. \
    -DCMAKE_C_FLAGS="-mcpu=cortex-a76 -O3 -ffast-math" \
    -DCMAKE_CXX_FLAGS="-mcpu=cortex-a76 -O3 -ffast-math" \
    -DGGML_NATIVE=ON
```

The `-mcpu=cortex-a76` flag enables the full ARMv8.2-A instruction set. llama.cpp has hand-written NEON intrinsics that use SDOT for quantized matrix multiplication. Without this flag, the compiler cannot generate these instructions.

---

### Why Raspberry Pi?

**The Pi as Edge Computing Platform**

The Raspberry Pi has evolved from a hobbyist board to a production edge computing platform. Over 70% of Raspberry Pi sales now go into embedded and industrial applications (Verified Market Reports, 2025). Companies like SECO, Advantech, and Seeed Studio ship ruggedized Pi-based edge controllers for manufacturing, energy management, and Industrial IoT.

This matters for DreamMeridian because field deployability requires proven hardware with established supply chains. A Pi 5 running Linux gives full access to the Python data science stack. Field teams can extend the system with tools they already know—no mobile dev expertise required.

**Why Not a Phone?**

DuckDB Spatial depends on GEOS, GDAL, and PROJ—C++ geospatial libraries without mobile builds. NetworKit uses OpenMP for parallel graph algorithms, which Android NDK doesn't support. These dependencies enable sub-50ms spatial queries on 200,000+ node graphs.

Testing on intentionally constrained consumer hardware (~$210, 16GB RAM, no GPU) validates that the system can operate within the resource limits humanitarian deployments actually face.

---

### How I built it

**Data preparation** (`build_location.py`): For any location string, the script:
1. Downloads the street network from OpenStreetMap via OSMnx
2. Converts the NetworkX graph to NetworKit's binary format for fast routing
3. Queries OSM for humanitarian-relevant POIs
4. Extracts neighborhood names for the geocoding layer
5. Loads everything into a DuckDB database with spatial indexes

**Runtime layers**:
1. **Geocode Layer** — Resolves place names from the local places table before the query reaches the LLM
2. **LLM Tool Selection** — xLAM-2-1b-fc-r parses the query and selects a tool. GBNF grammar constraints guarantee valid JSON output
3. **Spatial Tools** — Six functions built on DuckDB (spatial queries) and NetworKit (graph routing)
4. **Frontend** — Streamlit + Folium maps, or CLI for scripting

---

### Benchmark Results

60 natural language queries across all three locations:

| Metric | Value |
|--------|-------|
| Total queries | 60 |
| Success rate | **95.0%** |
| Avg response time | 10.87s |
| LLM inference | 8.9 tok/s |

| Location | Success |
|----------|---------|
| Cox's Bazar | 95% (19/20) |
| San Juan | 95% (19/20) |
| Jakarta | 95% (19/20) |

---

### Challenges

**Model selection.** Most small LLMs fail at structured tool-calling. I tested several 1-3B parameter models before landing on xLAM-2-1b-fc-r, which was trained specifically for function calling and achieved top performance on the Berkeley Function-Calling Leaderboard.

**Geocoding without an API.** I built a dedicated geocode layer that loads all OSM place names into memory and matches with word boundaries and longest-match-first ordering, so "Camp 8E" matches before "Camp 8".

**Reliable JSON generation.** Early testing showed the LLM occasionally producing malformed tool calls. GBNF grammar constraints in llama.cpp force valid JSON structure at the token level, eliminating parsing failures entirely.

---

### Accomplishments

- **8-14 second queries** via grammar constraints, prompt minimization, and ARM-optimized builds
- **~$210 hardware cost** vs. $5,400-$21,600/year for enterprise GIS term licenses
- **Three humanitarian datasets** — Cox's Bazar (27K nodes), San Juan (24K nodes), Jakarta (208K nodes)
- **ARM-native stack** — existing offline LLM+GIS solutions target enterprise GPU servers; DreamMeridian runs on CPU-only ARM

---

### What I learned

- Grammar-constrained generation eliminates JSON syntax errors
- Specialized small models beat general large models for tool-calling
- LLM inference is the bottleneck on low-power ARM hardware
- C++ matters on edge: NetworKit vs NetworkX is ~50ms vs ~5s for isochrones
- Data prep is the real work. The LLM is only as good as what it queries.

---

### What's next

**Near-term:** Voice input via local Whisper, offline map tiles, GPS module for current-location queries

**Medium-term:** Public CLI pipeline for any OSM location, HDX integration for crisis region datasets

**Long-term:** Support for Pi AI HAT modules (Hailo), deployable spatial AI kits for humanitarian field operations

---

## Hardware

Raspberry Pi 5 Model B Rev 1.1 (16GB) with CanaKit Starter PRO kit (~$210): Turbine case with fan, heatsink, 128GB SD card, 45W PD power supply. ARM Cortex-A76 @ 2.4GHz, DietPi 64-bit, under 10W for CPU-only workloads.

---

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

---

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

---

## Works Cited

Esri. (2024). *Configure a disconnected deployment—Portal for ArcGIS*. ArcGIS Enterprise Documentation. https://enterprise.arcgis.com/en/portal/latest/administer/windows/configure-a-disconnected-deployment.htm

FCC. (2017, September 22). *Communications Status Report for Areas Impacted by Hurricane Maria*. Federal Communications Commission. https://docs.fcc.gov/public/attachments/DOC-346860A1.pdf

IFRC. (2025). *Global Plan 2025*. International Federation of Red Cross and Red Crescent Societies. https://www.ifrc.org/sites/default/files/2024-12/IFRC_GlobalPlan_2025.pdf

ITU. (2024, November 27). *Facts and Figures 2024*. International Telecommunication Union. https://www.itu.int/en/mediacentre/Pages/PR-2024-11-27-facts-and-figures.aspx

Salesforce AI Research. (2024). *xLAM: Large Action Models*. GitHub. https://github.com/SalesforceAIResearch/xLAM

Santos-Burgoa, C., Sandberg, J., Suárez, E., et al. (2018). Differential and persistent risk of excess mortality from Hurricane Maria in Puerto Rico: a time-series analysis. *The Lancet Planetary Health*, 2(11), e478-e488. https://doi.org/10.1016/S2542-5196(18)30209-2

Verified Market Reports. (2025). *Industrial Raspberry Pi Market Size, Segmentation, Forecast, Applications 2033*. https://www.verifiedmarketreports.com/product/industrial-raspberry-pi-market/

Zhang, T., et al. (2024). APIGen: Automated Pipeline for Generating Verifiable and Diverse Function-Calling Datasets. *arXiv:2406.18518*. https://arxiv.org/abs/2406.18518
