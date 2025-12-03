# DreamMeridian: Step-by-Step Build & Run Instructions

**Target Device**: Raspberry Pi 5 (4GB+ RAM) running DietPi or Raspberry Pi OS 64-bit

---

## Prerequisites
```bash
# Install system dependencies
sudo apt update
sudo apt install -y build-essential cmake git

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

---

## Step 1: Clone Repository
```bash
git clone https://github.com/msradam/dream-meridian.git
cd dream-meridian
```

---

## Step 2: Install Python Dependencies
```bash
uv sync
```

---

## Step 3: Build llama.cpp for ARM
```bash
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp && mkdir build && cd build

cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_FLAGS="-mcpu=cortex-a76 -O3 -ffast-math -fno-finite-math-only" \
    -DCMAKE_CXX_FLAGS="-mcpu=cortex-a76 -O3 -ffast-math -fno-finite-math-only" \
    -DGGML_NATIVE=ON \
    -DGGML_LTO=ON \
    -DLLAMA_CURL=OFF

cmake --build . -j4 --config Release
cd ../..
```

*Build time: ~10 minutes on Pi 5*

---

## Step 4: Download LLM Model
```bash
mkdir -p models
uv run --with huggingface-hub hf download \
    Salesforce/xLAM-2-1b-fc-r-gguf \
    xLAM-2-1B-fc-r-Q5_K_M.gguf \
    --local-dir ./models
```

*Download size: ~1.1GB*

---

## Step 5: Start LLM Server
```bash
./llama.cpp/build/bin/llama-server \
    -m ./models/xLAM-2-1B-fc-r-Q5_K_M.gguf \
    --grammar-file tool_grammar.gbnf \
    -c 2048 -t 4 --mlock \
    --host 0.0.0.0 --port 8080
```

Wait for: `server is listening on http://0.0.0.0:8080`

---

## Step 6: Run Queries

**Option A: Command Line** (new terminal)
```bash
uv run python dream-meridian.py -l coxs_bazar "Find hospitals near Camp 6"
uv run python dream-meridian.py -l san_juan "Find shelters near Condado"
```

**Option B: Web Dashboard**
```bash
uv run streamlit run app.py --server.port 8501
```
Open `http://<pi-ip>:8501` in browser.

---

## Verification

Successful query output includes:
- Tool selection (e.g., `find_nearest_poi_with_route`)
- Walking distance and time
- GPS coordinates
- Response time (typically 8-13 seconds)

---

## Hardware Tested

- Raspberry Pi 5 Model B (16GB RAM)
- DietPi OS 64-bit
- CanaKit Starter PRO kit (~$210)
