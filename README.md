# 💠 DreamMeridian

**Offline AI-Powered Spatial Intelligence for ARM Devices**

DreamMeridian is a fully offline spatial query system that runs entirely on ARM-based devices like Raspberry Pi 5. It combines a quantized LLM (xLAM-2-1B) with high-performance graph routing and spatial databases to answer natural language questions about geographic data—without any cloud connectivity.

Built for humanitarian scenarios where internet access is unreliable: refugee camp navigation, disaster response coordination, and field operations planning.

![ARM](https://img.shields.io/badge/ARM-Cortex--A76-blue)
![Offline](https://img.shields.io/badge/Offline-100%25-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 🎯 Key Features

- **100% Offline**: All AI inference runs locally on ARM CPU—no cloud, no API keys
- **Natural Language Queries**: Ask questions like "Find hospitals near Camp 6" or "Show 15 minute walkable area from Condado"
- **Real Routing**: Actual walking routes calculated on road network graphs (not straight-line distances)
- **Multiple Locations**: Pre-built datasets for Cox's Bazar (refugee camps) and San Juan (disaster response)
- **Sub-10 Second Response**: Optimized for Raspberry Pi 5 with ARM NEON/dotprod instructions

---

## 🏗️ Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                        Natural Language Query                    │
│                "Find nearest hospital to Camp 6"                 │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  xLAM-2-1B (Q5_K_M)  │  Tool-calling LLM optimized for ARM      │
│  via llama.cpp       │  NEON + dotprod + Flash Attention        │
└─────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
┌──────────────────────────┐    ┌──────────────────────────────────┐
│  Geocoding Layer         │    │  Spatial Tools                   │
│  Place name → lat/lon    │    │  • list_pois                     │
│  "Camp 6" → (21.20,92.16)│    │  • find_nearest_poi_with_route   │
└──────────────────────────┘    │  • calculate_route               │
                                │  • find_along_route              │
                                │  • generate_isochrone            │
                                └──────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
┌──────────────────────────┐    ┌──────────────────────────────────┐
│  DuckDB + Spatial        │    │  NetworKit Graph Engine          │
│  POI queries, geocoding  │    │  Dijkstra routing on road network│
│  ~6K-11K POIs per city   │    │  ~25K-28K nodes per city         │
└──────────────────────────┘    └──────────────────────────────────┘
```

---

## 📋 Requirements

### Hardware
- **Raspberry Pi 5** (4GB+ RAM recommended) or any ARM64 device
- ~3GB storage for models and data
- Tested on: Pi 5 8GB running DietPi/Raspberry Pi OS

### Software Prerequisites
```bash
# System packages (Debian/Ubuntu/DietPi/Raspberry Pi OS)
sudo apt update
sudo apt install -y build-essential cmake git python3 python3-venv

# uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # or restart shell
```

---

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/msradam/dream-meridian.git
cd dream-meridian
```

### 2. Install Python Dependencies
```bash
uv sync
```

This creates a virtual environment and installs all dependencies in seconds.

### 3. Build llama.cpp (ARM-Optimized)
```bash
# Clone llama.cpp
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp && mkdir build && cd build

# Configure for Cortex-A76 (Pi 5)
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_FLAGS="-mcpu=cortex-a76 -O3 -ffast-math -fno-finite-math-only" \
    -DCMAKE_CXX_FLAGS="-mcpu=cortex-a76 -O3 -ffast-math -fno-finite-math-only" \
    -DGGML_NATIVE=ON \
    -DGGML_LTO=ON \
    -DLLAMA_CURL=OFF

# Build (takes ~10 minutes on Pi 5)
cmake --build . -j4 --config Release

# Return to project root
cd ../..
```

### 4. Download the LLM
```bash
mkdir -p models

# Download xLAM-2-1B quantized model (~1.1GB)
uv run --with huggingface-hub hf download \
    Salesforce/xLAM-2-1b-fc-r-gguf \
    xLAM-2-1B-fc-r-Q5_K_M.gguf \
    --local-dir ./models
```

### 5. Verify Installation
```bash
# Check all components
ls -la llama.cpp/build/bin/llama-server  # Should exist
ls -la models/*.gguf                      # Should show ~1.1GB file
ls -la data/                              # Should show coxs_bazar, san_juan, dhaka
```

---

## 🎮 Running DreamMeridian

### Start the LLM Server
```bash
./llama.cpp/build/bin/llama-server \
    -m ./models/xLAM-2-1B-fc-r-Q5_K_M.gguf \
    --grammar-file tool_grammar.gbnf \
    -c 2048 -t 4 --mlock \
    --host 0.0.0.0 --port 8080
```

Wait for "server is listening on http://0.0.0.0:8080" message.

### Option A: Command Line Interface
```bash
# Basic query
uv run python dream-meridian.py -l coxs_bazar "Find hospitals near Camp 6"

# Different location
uv run python dream-meridian.py -l san_juan "Find shelters near Condado"

# With explicit coordinates
uv run python dream-meridian.py -l coxs_bazar "Find clinics within 1km of latitude 21.2 longitude 92.16"
```

### Option B: Streamlit Dashboard
```bash
uv run streamlit run app.py --server.port 8501
```

Then open http://[pi-ip-address]:8501 in your browser.

---

## 📍 Available Locations

| Location | Context | Nodes | POIs | Key Features |
|----------|---------|-------|------|--------------|
| `coxs_bazar` | Rohingya refugee camps | 27,551 | 6,509 | Camp 1-20, MSF clinics, NGO offices |
| `san_juan` | Hurricane disaster response | 24,602 | 11,351 | Shelters, hospitals, coastal areas |
| `dhaka` | Urban navigation | 89,000+ | 14,000+ | Dense city center |

---

## 💬 Example Queries

### Cox's Bazar (Humanitarian)
```bash
# Find medical facilities
"Find hospitals near Camp 6"
"Where is the closest clinic to Camp 8W"
"List pharmacies within 2km of Camp 5"

# Navigation
"Calculate walking route from Camp 6 to Camp 9"
"How far is it to walk from Camp 3 to Camp 10"

# Accessibility analysis
"Show 15 minute walkable area from Camp 6"
"What areas can I reach in 10 minutes from Camp 8E"

# Route planning
"Find hospitals along the route from Camp 5 to Camp 9"
"What clinics are on the way from Camp 6 to Camp 7"
```

### San Juan (Disaster Response)
```bash
# Emergency services
"Find nearest hospital to Condado"
"Where is the closest shelter to Ocean Park"
"List police stations near Santurce"

# Evacuation planning
"Calculate walking route from Condado to Santurce"
"Find shelters along route from Ocean Park to Miramar"

# Coverage analysis
"Show 10 minute walkable area from Puerta de Tierra"
"What medical facilities are within 2km of Condado"
```

---

## 🔧 Spatial Tools

| Tool | Description | Example |
|------|-------------|---------|
| `list_pois` | List POIs of a type within radius | "List hospitals within 2km of Camp 6" |
| `find_nearest_poi_with_route` | Find nearest POI with walking route | "Find nearest clinic to Condado" |
| `calculate_route` | Walking route between two points | "Route from Camp 6 to Camp 9" |
| `find_along_route` | Find POIs along a walking path | "Hospitals along route from A to B" |
| `generate_isochrone` | Walkable area from a point | "15 minute walking radius from Camp 6" |
| `geocode_place` | Convert place name to coordinates | "Where is Camp 6 located" |

---

## ⚡ Performance

Tested on Raspberry Pi 5 (8GB RAM, DietPi OS):

| Metric | Value |
|--------|-------|
| Model load time | ~8 seconds |
| Query response (cold) | 5-10 seconds |
| Query response (warm) | 3-6 seconds |
| Memory usage | ~1.4 GB |
| CPU utilization | 4 cores @ 100% during inference |

ARM optimizations enabled:
- NEON SIMD ✓
- ARM FMA ✓
- FP16 vector arithmetic ✓
- Dot product instructions ✓
- Flash Attention ✓

---

## 📁 Project Structure
```
dream-meridian/
├── dream-meridian.py      # Main query engine
├── spatial_tools.py       # Spatial query functions
├── geocode_layer.py       # Place name resolution
├── app.py                 # Streamlit dashboard
├── tool_grammar.gbnf      # GBNF grammar for tool calls
├── pyproject.toml         # Python dependencies (uv)
├── data/
│   ├── coxs_bazar/        # Cox's Bazar dataset
│   ├── san_juan/          # San Juan dataset
│   └── dhaka/             # Dhaka dataset
├── models/                # LLM models (gitignored)
└── llama.cpp/             # Built llama.cpp (gitignored)
```

---

## 🛠️ Troubleshooting

### LLM server won't start
```bash
# Check if port is in use
lsof -i :8080

# Kill existing process
pkill -f llama-server
```

### Out of memory
```bash
# Reduce context size
./llama.cpp/build/bin/llama-server \
    -m ./models/xLAM-2-1B-fc-r-Q5_K_M.gguf \
    -c 1024 -t 4 \  # Reduced from 2048
    --host 0.0.0.0 --port 8080
```

### Slow queries
```bash
# Ensure mlock is enabled (keeps model in RAM)
# Add --mlock flag to server command

# Check CPU governor
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
# Should be "performance" not "powersave"
```

### Place name not found
```bash
# Check available places
uv run python -c "
import duckdb
con = duckdb.connect('data/coxs_bazar/coxs_bazar.duckdb')
print(con.execute('SELECT name FROM places LIMIT 20').fetchall())
"
```

---

## 🙏 Acknowledgments

- **xLAM-2** by Salesforce AI Research - Tool-calling LLM
- **llama.cpp** by Georgi Gerganov - Efficient inference engine
- **NetworKit** - High-performance graph algorithms
- **DuckDB** - Embedded analytical database
- **OpenStreetMap** - Geographic data

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

---

## 🏆 ARM AI Developer Challenge 2025

This project was built for the [ARM AI Developer Challenge](https://arm.devpost.com), demonstrating on-device AI inference for humanitarian applications on ARM-powered mobile devices.

**Key Innovation**: Natural language spatial queries running entirely offline on a $80 single-board computer, enabling field workers in connectivity-constrained environments to access critical geographic intelligence.
