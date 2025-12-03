# DreamMeridian: GeoAI on Pi

**Author: Adam Munawar Rahman, December 2025**

DreamMeridian answers natural language spatial queries entirely on-device on a Raspberry Pi 5. Ask "Find hospitals within 2km of Camp 8W" in Cox's Bazar, "How do I walk from Condado to Santurce?" in San Juan, or "Is there a pharmacy near Gelora?" in Jakarta—and get real answers with walking routes and distances in under 11 seconds. No internet, no cloud, no GPU. Just a $120 ARM board running at under 10 watts.

---

## Inspiration

At UNICEF Innovation, I built algorithms to calculate distances between schools and health facilities across programme countries. It worked—but required connectivity, cloud compute, and coding expertise that field workers don't have.

Hurricane Maria showed what happens when that infrastructure fails. Within two days, 95.6% of Puerto Rico's cell sites went down (FCC, 2017). The island lost power for months; excess mortality reached 2,975 in the six months following (Santos-Burgoa et al., 2018). 

This pattern repeats globally. After the 2023 Turkey-Syria earthquake, connectivity was compromised during the critical 72-hour rescue window. In Gaza, telecommunications blackouts lasted days to weeks. The 2022 Tonga eruption severed the undersea cable for five weeks. When networks fail, cloud-based tools fail with them.

And 2.6 billion people remain offline globally even without disasters (ITU, 2024). Millions of humanitarian workers—including over 16 million in the Red Cross/Red Crescent network (IFRC, 2025)—deploy regularly to connectivity-constrained environments.

> "There is a gap in getting information and data to local-level responders, humanitarians or governments at the smallest geographic level." — **MapAction Operations Director**

**The gap**: Offline data collection is solved—KoBoToolbox serves 32,000+ organizations with 300+ million submissions. Offline map viewing is solved—QField provides full QGIS spatial capability on mobile. But **offline spatial queries with accessible interfaces** remain unavailable. A field worker can collect a GPS point and view a map, but cannot ask "How many people live within walking distance of this clinic?" without exporting to desktop GIS software or reaching headquarters. Free tools like QGIS with PostGIS provide powerful offline analysis, but require technical expertise to deploy and operate.

DreamMeridian fills this gap: natural language spatial queries on an ARM-based single-board computer, entirely offline. No GIS training required.

---

## What It Does

DreamMeridian is an on-device spatial query engine. You ask questions in natural language; it returns walking routes, distances, and POI locations from a local OpenStreetMap database and precomputed road network graph.

### Why Spatial Queries Matter for Humanitarian Operations

UNHCR mandates that 80% of refugees must be within one hour's walk of a health facility. Sphere standards require households within 500 meters of water points. These standards cannot be verified in the field without spatial queries—yet no offline tool supports them.

DreamMeridian enables queries like:
- "Show areas more than 500m from a water point"
- "How many clinics are within 30 minutes walk of Camp 6?"
- "What's the walking route from the distribution point to the shelter?"

**Interfaces**:
- **CLI** (`dream-meridian.py`): Query from the command line
- **Web Dashboard** (`app.py`): Streamlit interface with Folium maps and live system stats

**Spatial Tools** (6 functions the LLM can call):

| Tool | Purpose | Example Query |
|------|---------|---------------|
| `list_pois` | POIs by type within radius | "List clinics within 2km of Camp 6" |
| `find_nearest_poi_with_route` | Nearest POI with walking directions | "Find nearest hospital to Condado" |
| `calculate_route` | Walking route between two points | "How do I walk from Camp 3 to Camp 8W" |
| `find_along_route` | POIs along a path | "Pharmacies between Ocean Park and Puerta de Tierra" |
| `generate_isochrone` | Walkable area from a point | "15 minute walking radius from Camp 5" |
| `geocode_place` | Place name → coordinates | "Where is Gelora" |

---

## Pre-Built Datasets

Three disaster response scenarios with offline data:

| Location | Context | Graph Nodes | POIs | Place Names |
|----------|---------|-------------|------|-------------|
| Cox's Bazar, Bangladesh | Rohingya refugee camps | 27,551 | 6,509 | 464 |
| San Juan, Puerto Rico | Hurricane response | 24,602 | 11,351 | 405 |
| Jakarta, Indonesia | Urban flood response | 208,281 | 41,028 | 331 |

Data sourced from OpenStreetMap via OSMnx. POI types: hospitals, clinics, pharmacies, schools, shelters, banks, markets, fuel stations, police, places of worship.

---

## ARM Optimization

### Why Raspberry Pi 5

The Cortex-A76 was chosen over Pi 4's Cortex-A72 for one reason: **ARMv8.2-A ML extensions**. The A76 supports SDOT/UDOT dot product instructions that accelerate INT8 multiply-accumulate operations. The A72 lacks these entirely, falling back to slower scalar operations. For quantized LLM inference, this is the bottleneck—resulting in 2–3× faster inference on Pi 5 vs Pi 4 for 1B parameter models.

| Feature | Cortex-A72 (Pi 4) | Cortex-A76 (Pi 5) |
|---------|-------------------|-------------------|
| INT8 dot product (SDOT/UDOT) | ❌ | ✅ |
| Native FP16 arithmetic | Conversion only | Direct compute |
| L3 Cache | None | 2MB shared |
| Clock speed | 1.5–1.8 GHz | 2.4 GHz |

### Raspberry Pi in Humanitarian Contexts

Raspberry Pi hardware has proven viable in humanitarian deployments:

- **RACHEL-Pi**: Serves 500,000+ learners across refugee camps and remote schools in Guatemala, Kenya, Tanzania, and Papua New Guinea
- **UNICEF Pi4L**: Deployed 60 units serving 30,000+ Syrian refugees in Lebanon (2014-2016)
- **Jangala Big Box**: Pi-based connectivity for Calais camp and Kakuma (Kenya); won 2019 Tech4Good Africa award
- **OpenEMR on Pi**: Electronic medical records for refugee camps in Kenya, Pakistan, Nepal

DreamMeridian builds on this foundation, adding spatial intelligence to proven edge hardware.

### Full-Stack ARM Efficiency

Every layer was selected for ARM edge deployment:

- **llama.cpp**: Hand-written NEON intrinsics with DotProd acceleration for quantized inference. Built with `-mcpu=cortex-a76` to enable ARMv8.2-A optimizations.
- **DuckDB**: Official ARM64 binaries with columnar-vectorized execution. Processes 2048-tuple batches that benefit from compiler auto-vectorization targeting NEON.
- **NetworKit**: OpenMP parallelization scales across all 4 Cortex-A76 cores. Graph algorithms are memory-bound, benefiting from Pi 5's improved LPDDR4X bandwidth.
- **DietPi**: Minimal Linux distribution with ~400MB base footprint. No GUI overhead, services trimmed to essentials.

The result: a full GIS + LLM stack in under 4GB RAM, with LLM inference as the only compute-intensive operation.

### Why xLAM-2-1B

Most small LLMs fail at structured tool-calling. Salesforce's xLAM-2-1b-fc-r was trained specifically for function calling on 60,000 examples across 3,673 executable APIs (Liu et al., 2024). The xLAM family achieved #1 on the Berkeley Function-Calling Leaderboard, outperforming GPT-4 on tool-use benchmarks (Salesforce AI Research, 2024).

Q5_K_M quantization compresses the model to ~1.1GB while preserving accuracy, fitting comfortably in Pi 5's RAM with headroom for the spatial database and graph routing.

---

## How I Built It

**Data Preparation** (`build_location.py`): For any location string (e.g., "Cox's Bazar, Bangladesh"):
1. Resolves the string to geographic coordinates via OSM's Nominatim
2. Downloads the street network within a bounding box via OSMnx
3. Converts the NetworkX graph to NetworKit's binary format for fast routing
4. Queries OSM for humanitarian-relevant POIs
5. Extracts neighborhood and locality names for the geocoding layer
6. Loads everything into a DuckDB database with spatial indexes

**Runtime Pipeline**:
```
User Query → Geocode Layer → LLM (xLAM) → Tool Selection → Spatial Tools → Result + Map
                  ↓                              ↓
           "Camp 6" → coords          DuckDB queries + NetworKit routing
```

**Key Implementation Decisions**:
- **GBNF grammar constraints**: Forces valid JSON tool calls at the token level, eliminating parsing failures entirely
- **Dedicated geocode layer**: Loads all OSM place names into memory, matches with word boundaries and longest-match-first ordering (so "Camp 8E" matches before "Camp 8")
- **NetworKit over NetworkX**: C++ graph library with OpenMP parallelism achieves ~50ms routing vs multi-second times for equivalent NetworkX operations

---

## Benchmark Results

60 natural language queries across all three locations:

| Metric | Value |
|--------|-------|
| Total queries | 60 |
| Success rate | **95.0%** |
| Avg response time | 10.87s |
| LLM inference speed | 8.9 tok/s |

| Location | Success |
|----------|---------|
| Cox's Bazar | 95% (19/20) |
| San Juan | 95% (19/20) |
| Jakarta | 95% (19/20) |

Tool selection was scored as correct if the LLM chose the appropriate tool for the query intent (e.g., "nearest X" → `find_nearest_poi_with_route`, "within N km" → `list_pois`). Three queries failed due to the LLM confusing distance units with time or defaulting to isochrone for ambiguous "where is" phrasing.

---

## Hardware

**Test Platform**: Raspberry Pi 5 16GB with CanaKit Starter PRO kit

| Component | Price |
|-----------|-------|
| Raspberry Pi 5 16GB (MSRP) | $120 |
| CanaKit case + fan + heatsink | ~$30 |
| 128GB microSD (pre-loaded) | ~$15 |
| 45W USB-C PD power supply | ~$20 |
| Cables + card reader | ~$15 |
| **Bundle Total** | **$209.99** |

Minimum viable configuration (board + power + SD): ~$150

**Specs**: ARM Cortex-A76 @ 2.4GHz, 16GB LPDDR4X, DietPi 64-bit. Power draw: 2–3W idle, <10W under full inference load.

---

## Challenges

**Model selection**: Tested several 1–3B parameter models before landing on xLAM-2-1b-fc-r. General-purpose small LLMs failed at structured tool-calling; a specialized function-calling model was required.

**Geocoding without an API**: Built a dedicated layer that loads OSM place names into memory and matches with word boundaries, handling cases like "Camp 8E" vs "Camp 8" correctly.

**Reliable JSON generation**: Early testing showed occasional malformed tool calls. GBNF grammar constraints in llama.cpp force valid JSON structure at the token level—zero parsing failures in production.

**Power considerations**: The Pi 5 draws more power than its predecessors under AI load. Field deployment would require solar backup and substantial battery capacity—this system is designed for base camp or vehicle deployment, not handheld use.

---

## What I Learned

- Specialized small models beat general large models for structured tasks—xLAM outperformed larger LLMs on tool selection because it was trained specifically for function calling
- Grammar-constrained generation eliminates JSON parsing errors entirely
- LLM inference is the bottleneck on edge hardware; every optimization dollar should go there first
- C++ matters at the edge: NetworKit vs NetworkX is ~50ms vs multi-second times for isochrones on 200K+ node graphs
- Data preparation is the real work—the LLM is only as good as what it can query

---

## What's Next

**Near-term**: Voice input via local Whisper, offline map tile caching, GPS module for current-location queries

**Medium-term**: Public CLI pipeline for any OSM location, HDX integration for crisis region datasets, tool chaining for compound multi-step queries (e.g., "Find the nearest hospital, then show pharmacies along the route")

**Long-term**: Support for Pi AI HAT+ modules (Hailo-8L NPU), ruggedized enclosures with solar integration, deployable spatial AI kits for humanitarian field operations

---

## What Makes This Project Notable

Offline data collection tools (KoBoToolbox, ODK) dominate humanitarian operations but cannot perform spatial analysis. Offline GIS tools (QField) provide spatial queries but require GIS expertise. Consumer navigation apps (OsmAnd) offer routing but lack operational context—you can navigate to a point, but you can't ask "Which communities are more than one hour from a health facility?"

DreamMeridian is the first open-source system combining **natural language spatial queries**, **offline graph routing**, and **accessible interfaces** on ARM edge hardware—enabling field workers to ask "Find clinics within 30 minutes walk" without GIS training or internet connectivity.

The system handles multiple phrasings ("find me," "I need," "show me," "where is"), 10 POI types, routes from 0.66km to 33km, isochrone analysis up to 20 minutes, and three geographic contexts (24K to 208K nodes)—all with 95% accuracy on hardware costing ~$150.

The code is designed for extension: swap the datasets via `build_location.py`, adjust POI types, deploy to other ARM devices. The benchmark methodology and failure analysis provide a clear path for improvement.

---

## Step-by-Step Instructions

> Full instructions including Apple Silicon (macOS) setup are available in `INSTALL.md` in the repository.

### 1. System Preparation
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git cmake build-essential python3-venv libopenblas-dev
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and Setup
```bash
git clone https://github.com/msradam/dream-meridian.git
cd dream-meridian
uv sync
```

### 3. Compile llama.cpp with ARM Optimizations
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

### 4. Download Model
```bash
mkdir -p models
uv run --with huggingface-hub hf download \
    Salesforce/xLAM-2-1b-fc-r-gguf \
    xLAM-2-1B-fc-r-Q5_K_M.gguf \
    --local-dir ./models
```

### 5. Run the System

**Terminal 1 — Start LLM Server:**
```bash
./llama.cpp/build/bin/llama-server \
    -m models/xLAM-2-1B-fc-r-Q5_K_M.gguf \
    --grammar-file tool_grammar.gbnf \
    -c 2048 -t 4 --mlock \
    --host 0.0.0.0 --port 8080
```

**Terminal 2 — Run Queries:**
```bash
# CLI
uv run python dream-meridian.py -l coxs_bazar "Find nearest hospital to Camp 6"

# Web Dashboard
uv run streamlit run app.py --server.port 8501
```

---

## Example Queries

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
uv run python dream-meridian.py -l jakarta "Find the nearest hospital to Bambu Apus"
uv run python dream-meridian.py -l jakarta "How do I walk from Cipulir to Lebak Bulus"
uv run python dream-meridian.py -l jakarta "What can I reach in 15 minutes walking from Serdang"
```

---

## Works Cited

Centre for Humanitarian Data. (2023). *Data Policy Podcast: Interview with MapAction*. https://centre.humdata.org/

Esri. (2024). *Configure a disconnected deployment—Portal for ArcGIS*. https://enterprise.arcgis.com/en/portal/latest/administer/windows/configure-a-disconnected-deployment.htm

FCC. (2017). *Communications Status Report for Areas Impacted by Hurricane Maria*. https://docs.fcc.gov/public/attachments/DOC-346860A1.pdf

IFRC. (2025). *Global Plan 2025*. https://www.ifrc.org/sites/default/files/2024-12/IFRC_GlobalPlan_2025.pdf

ITU. (2024). *Facts and Figures 2024*. https://www.itu.int/en/mediacentre/Pages/PR-2024-11-27-facts-and-figures.aspx

KoBoToolbox. (2024). *About KoBoToolbox*. https://www.kobotoolbox.org/about-us/

Liu, Z., et al. (2024). APIGen: Automated Pipeline for Generating Verifiable and Diverse Function-Calling Datasets. *arXiv:2406.18518*. https://arxiv.org/abs/2406.18518

Salesforce AI Research. (2024). *xLAM: Large Action Models*. https://github.com/SalesforceAIResearch/xLAM

Santos-Burgoa, C., et al. (2018). Differential and persistent risk of excess mortality from Hurricane Maria in Puerto Rico. *The Lancet Planetary Health*, 2(11), e478–e488. https://doi.org/10.1016/S2542-5196(18)30209-2

Sphere Association. (2018). *The Sphere Handbook: Humanitarian Charter and Minimum Standards in Humanitarian Response* (4th ed.). https://spherestandards.org/handbook/

UNHCR. (2024). *Emergency Handbook: Health*. https://emergency.unhcr.org/protection/health

World Possible. (2024). *RACHEL: Remote Area Community Hotspot for Education and Learning*. https://worldpossible.org/rachel