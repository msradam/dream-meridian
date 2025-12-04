# 💠 DreamMeridian: GeoAI on Pi

**Author: Adam Munawar Rahman, December 2025**

DreamMeridian answers natural language spatial queries entirely on-device on a Raspberry Pi 5. Ask "Find hospitals within 2km of Camp 8W" in Cox's Bazar, "How do I walk from Condado to Santurce?" in San Juan, or "Is there a pharmacy near Gelora?" in Jakarta, and get real answers with walking routes and distances in under 11 seconds. No internet, no cloud, no GPU. Just a $120 ARM board running at under 10 watts.

---

## Inspiration

At UNICEF Innovation, I built algorithms to calculate distances between schools and health facilities across programme countries. It worked, but required connectivity, cloud compute, and coding expertise that field workers don't have.

Hurricane Maria showed what happens when that infrastructure fails. Within two days, 95.6% of Puerto Rico's cell sites went down (FCC, 2017). The island lost power for months; excess mortality reached 2,975 in the six months following (Santos-Burgoa et al., 2018). 

This pattern repeats. After the 2023 Turkey-Syria earthquake, connectivity failed across affected regions during the critical 72-hour rescue window. The 2022 Tonga eruption severed the undersea cable for five weeks. When networks fail, cloud-based tools fail with them.

And 2.6 billion people remain offline globally even without disasters (ITU, 2024). Millions of humanitarian workers, including over 16 million volunteers in the Red Cross/Red Crescent network (IFRC, 2025), deploy regularly to connectivity-constrained environments.

> "There is a gap in getting information and data to local-level responders, humanitarians or governments at the smallest geographic level." — **MapAction Operations Director**

**The gap**: Offline data collection has mature solutions. KoBoToolbox serves 32,000+ organizations with 300+ million submissions. Offline map viewing is well-addressed. QField brings substantial QGIS capability to mobile. Offline POI search and routing exist in consumer apps like OsmAnd. 

But **natural language spatial queries on low-power edge hardware** remain unavailable. A field worker can collect a GPS point, view a map, and search for nearby POIs, but cannot ask "How many people live within walking distance of this clinic?" without exporting to desktop GIS software or reaching headquarters. Free tools like QGIS with PostGIS and the QNEAT3 plugin provide powerful offline analysis including isochrones, but require technical expertise to deploy and operate.

DreamMeridian fills this gap: natural language spatial queries on an ARM-based single-board computer, entirely offline. No GIS training required to run queries.

---

## What It Does

DreamMeridian is an on-device spatial query engine. You ask questions in natural language; it returns walking routes, distances, and POI locations from a local OpenStreetMap database and precomputed road network graph.

### Why Spatial Queries Matter for Humanitarian Operations

UNHCR mandates that 80% of refugees must be within one hour's walk of a health facility. Sphere standards require households within 500 meters of water points. These standards can be verified with existing GIS tools like QGIS, but not easily in the field without specialized training.

DreamMeridian enables queries like:

- "Show areas more than 500m from a water point"
- "How many clinics are within 30 minutes walk of Camp 6?"
- "What's the walking route from the distribution point to the shelter?"

### Interfaces

- **CLI** (`dream-meridian.py`): Query from the command line
- **Web Dashboard** (`app.py`): Streamlit interface with Folium maps and live system stats

### Spatial Tools

6 functions the LLM can call:

| Tool | Purpose | Example Query |
|------|---------|---------------|
| `list_pois` | POIs by type within radius | "List clinics within 2km of Camp 6" |
| `find_nearest_poi_with_route` | Nearest POI with walking directions | "Find nearest hospital to Condado" |
| `calculate_route` | Walking route between two points | "How do I walk from Camp 3 to Camp 8W" |
| `find_along_route` | POIs along a path | "Pharmacies between Ocean Park and Puerta de Tierra" |
| `generate_isochrone` | Walkable area from a point | "15 minute walking radius from Camp 5" |
| `geocode_place` | Place name → coordinates | "Where is Gelora" |

---

## Why DreamMeridian

Offline data collection tools (KoBoToolbox, ODK) dominate humanitarian operations but cannot perform spatial analysis. Offline GIS tools (QField, QGIS) provide spatial queries but require GIS expertise. Consumer navigation apps (OsmAnd) offer routing and POI search but lack compound spatial reasoning like isochrones from natural language. You can navigate to a point and search for nearby hospitals, but you can't ask "Which communities are more than one hour from a health facility?"

DreamMeridian brings together **natural language spatial queries**, **offline graph routing**, and **accessible interfaces** on ARM edge hardware. This combination is unavailable in existing open-source tools.

The system handles:

- Multiple phrasings ("find me," "I need," "show me," "where is")
- 10 POI types
- Routes from 0.66km to 33km
- Isochrone analysis up to 20 minutes
- Three geographic contexts (24K to 208K nodes)

All with 95% accuracy on hardware costing ~$150.

The code is designed for extension: swap the datasets via `build_location.py`, adjust POI types, deploy to other ARM devices. The benchmark methodology and failure analysis provide a clear path for improvement.

---

## Pre-Built Datasets

Three disaster response scenarios with offline data:

| Location | Context | Graph Nodes | POIs | Place Names |
|----------|---------|-------------|------|-------------|
| Cox's Bazar, Bangladesh | Rohingya refugee camps | 27,551 | 6,509 | 464 |
| San Juan, Puerto Rico | Hurricane response | 24,602 | 11,351 | 405 |
| Jakarta, Indonesia | Urban flood response | 208,281 | 41,028 | 331 |

Data sourced from OpenStreetMap via OSMnx (Boeing, 2025). 

POI types: hospitals, clinics, pharmacies, schools, shelters, banks, markets, fuel stations, police, places of worship.

---

## ARM Optimization

### Why Raspberry Pi 5

The Cortex-A76 was chosen over Pi 4's Cortex-A72 for its dot product extensions. The A76 supports SDOT/UDOT instructions that accelerate INT8 multiply-accumulate operations, which are critical for quantized LLM inference (ARM Cortex-A76 Technical Reference Manual). The A72 lacks these entirely, falling back to slower scalar operations. 

Published benchmarks show the Pi 5 delivers 2 to 3x the CPU performance of Pi 4 (Raspberry Pi, 2023), with the Cortex-A76 at 2.4GHz compared to the Cortex-A72 at 1.5GHz. This architectural advantage, combined with higher clock speed and improved memory bandwidth, yields substantially faster inference for quantized LLM workloads.

Additional advantages: native FP16 arithmetic (vs conversion-only on A72), 2MB shared L3 cache, and improved LPDDR4X memory bandwidth (Raspberry Pi Product Specifications).

### Raspberry Pi in Humanitarian Contexts

Raspberry Pi hardware is already deployed in humanitarian contexts:

- **RACHEL-Pi**: According to World Possible, their user surveys indicate RACHEL has reached an estimated 500,000+ learners across refugee camps and remote schools in countries including Guatemala, Kenya, and Tanzania

- **UNICEF Pi4L**: Deployed to support Syrian refugee education in Lebanon (2014-2016)

- **Jangala Big Box**: Pi-based connectivity for Calais camp and Kakuma (Kenya); won 2019 Tech4Good Africa award

DreamMeridian adds spatial intelligence to this proven hardware platform.

### Full-Stack ARM Efficiency

Every layer optimized for ARM edge deployment:

- **llama.cpp**: The llama.cpp developers implemented hand-written NEON intrinsics with DotProd acceleration for quantized inference. Built with `-mcpu=cortex-a76` to enable ARMv8.2-A optimizations.

- **DuckDB**: Official ARM64 binaries with columnar-vectorized execution. Processes 2048-tuple batches that benefit from compiler auto-vectorization targeting NEON.

- **NetworKit**: OpenMP parallelization scales across all 4 Cortex-A76 cores. Graph algorithms are memory-bound, benefiting from Pi 5's improved LPDDR4X bandwidth.

- **DietPi**: Minimal Linux distribution with ~400MB base footprint. No GUI overhead, services trimmed to essentials.

The result: a full GIS + LLM stack in under 4GB RAM.

### Why xLAM-2-1B

Small LLMs typically struggle with structured tool-calling, which is why specialized models like xLAM exist. Salesforce's xLAM-2-1b-fc-r was trained specifically for function calling on 60,000 examples across 3,673 executable APIs (Liu et al., 2024). The xLAM model family achieved top-tier rankings on the Berkeley Function-Calling Leaderboard, with xLAM-7B(fc) outperforming GPT-4 on tool-use benchmarks (Salesforce AI Research, 2024).

Q5_K_M quantization compresses the model to ~1.1GB while preserving accuracy, fitting comfortably in Pi 5's RAM with headroom for the spatial database and graph routing.

---

## How I Built It

### Data Preparation

`build_location.py`: For any location string (e.g., "Cox's Bazar, Bangladesh"), this one-time online process:

1. Resolves the string to geographic coordinates via OSM's Nominatim
2. Downloads the street network within a bounding box via OSMnx
3. Converts the NetworkX graph to NetworKit's binary format for fast routing
4. Queries OSM for humanitarian-relevant POIs
5. Extracts neighborhood and locality names for the geocoding layer
6. Loads everything into a DuckDB database with spatial indexes

This can run on the Pi itself or on a separate machine. The resulting `.duckdb` and `.nkb` files are portable and compact enough for FTP transfer and version control:

```
coxs_bazar/   5.5MB .duckdb + 1.5MB .nkb  = ~7MB
san_juan/     6.3MB .duckdb + 1.3MB .nkb  = ~8MB  
jakarta/      21MB .duckdb  + 11MB .nkb   = ~32MB
```

### Runtime Pipeline

Fully on-device, fully offline:

```
User Query → Geocode Layer → LLM (xLAM) → Tool Selection → Spatial Tools → Result + Map
                  ↓                              ↓
           "Camp 6" → coords          DuckDB queries + NetworKit routing
```

All inference and spatial computation happens locally. No network calls at runtime. I simulated field conditions by disconnecting the Pi from the network and running the full query suite successfully.

### Map Visualization

The web dashboard uses online map tiles (Carto Dark Matter) as a background layer. When offline, the UI remains fully functional: routes, POI markers, and coordinates render correctly, just without the map background. 

Offline tile caching is supported via `build_location.py --tiles`, but I used online tiles during development since pre-caching three test regions at multiple zoom levels requires multi-gigabyte downloads through rate-limited per-coordinate retrieval, which slows iteration. For field deployment, tiles would be pre-cached once per region. 

The CLI operates fully offline without any map tiles.

### Key Implementation Decisions

- **GBNF grammar constraints**: Forces valid JSON tool calls at the token level, virtually eliminating parsing failures in testing

- **Dedicated geocode layer**: Loads all OSM place names into memory, matches with word boundaries and longest-match-first ordering (so "Camp 8E" matches before "Camp 8")

- **NetworKit over NetworkX**: C++ graph library with OpenMP parallelism. Published benchmarks show NetworKit outperforming NetworkX by 10x to 2000x depending on the algorithm (Staudt et al., 2016; timlrx, 2020), which translates to sub-second routing on graphs where NetworkX would take minutes.

---

## Benchmark Results

### Cross-Platform Performance

10-query informal benchmark across all three locations (warm cache, post-warmup):

| Platform | Architecture | Mean | tok/s | TDP | Cost |
|----------|-------------|------|-------|-----|------|
| M3 MacBook Air | Apple Silicon | 1.14s | 60.3 | ~20W | ~$1,099 |
| Steam Deck | x86-64 Zen 2 | 3.94s | 20.4 | ~15W | ~$400 |
| Raspberry Pi 5 | ARM Cortex-A76 | 8.60s | 9.5 | ~5W | ~$120 |

All platforms achieved 100% success rate (10/10 queries correctly selected the appropriate tool and executed successfully).

### ARM vs x86 Power Efficiency

The Steam Deck comparison isolates the architecture question: similar thermal envelope, similar-era silicon, different ISA.

| Metric | Pi 5 (ARM) | Steam Deck (x86) |
|--------|------------|------------------|
| Speed | 1x | 2.2x faster |
| Power draw (est.) | ~5W | ~15W |
| **Queries per Wh (est.)** | **~84** | **~61** |

The Pi 5 delivers an estimated **38% more queries per watt-hour**. On a 100Wh battery: ~84 queries (ARM) vs ~61 queries (x86). 

Power draw figures are approximate based on typical load measurements; actual consumption varies with workload. In disaster zones running on solar or generator power, efficiency matters more than speed.

### Pi 5 Detailed Results

60-query suite:

| Metric | Value |
|--------|-------|
| Success rate | **95.0%** (57/60) |
| Avg response time | 10.87s |
| LLM inference | 8.9 tok/s |

The 3 failures share a common pattern: the LLM defaulted to isochrone generation for ambiguous "where is nearest" queries. This is addressable through prompt engineering or by encouraging users to phrase queries more specifically (e.g., "find nearest hospital" rather than "where is a hospital").

---

## Hardware

**Target Hardware / Development Platform**: Raspberry Pi 5 16GB with CanaKit Starter PRO kit

| Component | Price |
|-----------|-------|
| Raspberry Pi 5 16GB (MSRP) | $120 |
| CanaKit case + fan + heatsink | ~$30 |
| 128GB microSD (pre-loaded) | ~$15 |
| 45W USB-C PD power supply | ~$20 |
| Cables + card reader | ~$15 |
| **Bundle Total** | **$209.99** |

Minimum viable configuration (board + power + SD): ~$150

**Specs**: ARM Cortex-A76 @ 2.4GHz, 16GB LPDDR4X, DietPi 64-bit. 

Power draw: ~2.7W idle, ~7W under stress (Tom's Hardware, 2023). LLM inference workloads may draw slightly higher depending on sustained load.

### Hardware Verification

As shown in screenshots and video demo:

```
root@DietPi:~/dream-meridian# cat /proc/device-tree/model && echo ""
Raspberry Pi 5 Model B Rev 1.1

root@DietPi:~/dream-meridian# lscpu | grep -E "Model name|Architecture|CPU\(s\):"
Architecture:            aarch64
CPU(s):                  4
Model name:              Cortex-A76
```

---

## Challenges

**Model selection and latency**: Tested several 1-3B parameter models before landing on xLAM-2-1b-fc-r. General-purpose small LLMs failed at structured tool-calling and ran slower; xLAM paired with GBNF grammar constraints delivered both accurate tool selection and faster inference.

**Geocoding without an API**: Built a dedicated layer that loads OSM place names into memory and matches with word boundaries, handling cases like "Camp 8E" vs "Camp 8" correctly.

**Reliable JSON generation**: Early testing showed occasional malformed tool calls. GBNF grammar constraints in llama.cpp force valid JSON structure at the token level, virtually eliminating parsing failures in production.

---

## What I Learned

- Specialized small models beat general large models for structured tasks. xLAM outperformed larger LLMs on tool selection because it was trained specifically for function calling.

- Grammar-constrained generation dramatically reduces JSON parsing errors.

- LLM inference is the bottleneck on edge hardware; optimization efforts should focus there first.

- C++ matters at the edge: NetworKit vs NetworkX shows 10x to 100x+ speedups on shortest-path algorithms according to published benchmarks. Critical when every query runs on a battery-powered device.

- Data preparation is the real work. The LLM is only as good as what it can query.

---

## What's Next

**Near-term**: Voice input via local Whisper, offline map tile caching, GPS module for current-location queries

**Medium-term**: Public CLI pipeline for any OSM location, HDX integration for crisis region datasets, tool chaining for compound multi-step queries (e.g., "Find the nearest hospital, then show pharmacies along the route")

**Long-term**: Support for Pi AI HAT+ modules (Hailo-8L NPU), ruggedized enclosures with solar integration, deployable spatial AI kits for humanitarian field operations

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
    -DGGML_LTO=ON \
    -DLLAMA_CURL=OFF

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

**Terminal 1 - Start LLM Server:**

```bash
./llama.cpp/build/bin/llama-server \
    -m models/xLAM-2-1B-fc-r-Q5_K_M.gguf \
    --grammar-file tool_grammar.gbnf \
    -c 2048 -t 4 --mlock \
    --host 0.0.0.0 --port 8080
```

**Terminal 2 - Run Queries:**

```bash
# CLI
uv run python dream-meridian.py -l coxs_bazar "Find nearest hospital to Camp 6"

# Web Dashboard
uv run streamlit run app.py --server.port 8501
```

---

## Example Queries

### Cox's Bazar (Refugee Camps)

```bash
uv run python dream-meridian.py -l coxs_bazar "I need to find the nearest hospital to Camp 6"
uv run python dream-meridian.py -l coxs_bazar "How do I walk from Camp 3 to Camp 8W"
uv run python dream-meridian.py -l coxs_bazar "Show me everywhere I can walk to in 15 minutes from Camp 8W"
```

### San Juan (Hurricane Response)

```bash
uv run python dream-meridian.py -l san_juan "Where is the closest hospital to Condado"
uv run python dream-meridian.py -l san_juan "How do I get from Condado to Santurce on foot"
uv run python dream-meridian.py -l san_juan "Show me a 20 minute walking radius from Condado"
```

### Jakarta (Urban Flood Response)

```bash
uv run python dream-meridian.py -l jakarta "Find the nearest hospital to Bambu Apus"
uv run python dream-meridian.py -l jakarta "How do I walk from Cipulir to Lebak Bulus"
uv run python dream-meridian.py -l jakarta "What can I reach in 15 minutes walking from Serdang"
```

---

## Works Cited

ARM. (2018). *Cortex-A76 Technical Reference Manual*. https://developer.arm.com/documentation/100798/

Boeing, G. (2025). Modeling and Analyzing Urban Networks and Amenities with OSMnx. *Geographical Analysis*, 57(4), 567-577. https://doi.org/10.1111/gean.70009

Centre for Humanitarian Data. (2023). *Data Policy Podcast: Interview with MapAction*. https://centre.humdata.org/

Esri. (2024). *Configure a disconnected deployment - Portal for ArcGIS*. https://enterprise.arcgis.com/en/portal/latest/administer/windows/configure-a-disconnected-deployment.htm

FCC. (2017). *Communications Status Report for Areas Impacted by Hurricane Maria*. https://docs.fcc.gov/public/attachments/DOC-346860A1.pdf

IFRC. (2025). *Global Plan 2025*. https://www.ifrc.org/sites/default/files/2024-12/IFRC_GlobalPlan_2025.pdf

ITU. (2024). *Facts and Figures 2024*. https://www.itu.int/en/mediacentre/Pages/PR-2024-11-27-facts-and-figures.aspx

KoBoToolbox. (2024). *About KoBoToolbox*. https://www.kobotoolbox.org/about-us/

Liu, Z., et al. (2024). APIGen: Automated Pipeline for Generating Verifiable and Diverse Function-Calling Datasets. *arXiv:2406.18518*. https://arxiv.org/abs/2406.18518

Raspberry Pi. (2023). *Benchmarking Raspberry Pi 5*. https://www.raspberrypi.com/news/benchmarking-raspberry-pi-5/

Raspberry Pi. (2024). *Processors Documentation*. https://www.raspberrypi.com/documentation/computers/processors.html

Raspberry Pi. (2024). *Raspberry Pi 4 Model B Specifications*. https://www.raspberrypi.com/products/raspberry-pi-4-model-b/specifications/

Raspberry Pi. (2024). *Raspberry Pi 5 Product Page*. https://www.raspberrypi.com/products/raspberry-pi-5/

Salesforce AI Research. (2024). *xLAM: Large Action Models*. https://github.com/SalesforceAIResearch/xLAM

Santos-Burgoa, C., et al. (2018). Differential and persistent risk of excess mortality from Hurricane Maria in Puerto Rico. *The Lancet Planetary Health*, 2(11), e478-e488. https://doi.org/10.1016/S2542-5196(18)30209-2

Sphere Association. (2018). *The Sphere Handbook: Humanitarian Charter and Minimum Standards in Humanitarian Response* (4th ed.). https://spherestandards.org/handbook/

Staudt, C. L., Sazonovs, A., & Meyerhenke, H. (2016). NetworKit: A Tool Suite for Large-scale Complex Network Analysis. *Network Science*, 4(4), 508-530. https://doi.org/10.1017/nws.2016.20

timlrx. (2020). *Benchmark of popular graph/network packages v2*. https://www.timlrx.com/blog/benchmark-of-popular-graph-network-packages-v2

Tom's Hardware. (2023). *Raspberry Pi 5 Review*. https://www.tomshardware.com/reviews/raspberry-pi-5

UNHCR. (2024). *Emergency Handbook: Health*. https://emergency.unhcr.org/protection/health

World Possible. (2024). *RACHEL: Remote Area Community Hotspot for Education and Learning*. https://worldpossible.org/rachel