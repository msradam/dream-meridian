## Hardware Tested
- Raspberry Pi 5 Model B (16GB RAM)
- DietPi OS 64-bit
- CanaKit Starter PRO kit (~$210)
- ARM Cortex-A76 @ 2.4GHz, 4 cores

---

# DreamMeridian: Step-by-Step Build & Run Instructions

**Target Device**: Raspberry Pi 5 (4GB+ RAM) running DietPi or Raspberry Pi OS 64-bit

> *Tested on DietPi. Raspberry Pi OS is untested but should work identically—both are Debian-based and share the same package repositories and ARM64 toolchain.*

**1. System Preparation**
First, update the system and install the required build tools for the Cortex-A76 optimization.
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git cmake build-essential python3-venv libopenblas-dev
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Clone and Setup Environment**
```bash
git clone https://github.com/msradam/dream-meridian
cd dream-meridian
uv sync
```

**3. Compile llama.cpp with Cortex-A76 Optimizations**
This step is critical. I compile specifically for the Pi 5's architecture to enable FP16 and Dot Product instructions.
```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
mkdir build && cd build

# Configure with ARM-specific flags
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_FLAGS="-mcpu=cortex-a76 -O3 -ffast-math -fno-finite-math-only" \
    -DCMAKE_CXX_FLAGS="-mcpu=cortex-a76 -O3 -ffast-math -fno-finite-math-only" \
    -DGGML_NATIVE=ON \
    -DGGML_LTO=ON \
    -DLLAMA_CURL=OFF

# Build the server
cmake --build . --config Release -j4
cd ../..
```

**4. Download Model**
Place the xLAM model in the `models/` directory. Pre-built location data for Cox's Bazar, San Juan, and Jakarta is included in the repository.
```bash
mkdir -p models
uv run --with huggingface-hub hf download \
    Salesforce/xLAM-2-1b-fc-r-gguf \
    xLAM-2-1B-fc-r-Q5_K_M.gguf \
    --local-dir ./models
```

**5. Run the System**
You will need two terminal windows.

**Terminal 1: Start the LLM Server**
```bash
./llama.cpp/build/bin/llama-server \
    -m models/xLAM-2-1B-fc-r-Q5_K_M.gguf \
    --grammar-file tool_grammar.gbnf \
    -c 2048 -t 4 --mlock \
    --host 0.0.0.0 --port 8080
```

**Terminal 2: Start the Interface**
```bash
# Option A: Web Dashboard (GUI)
uv run streamlit run app.py --server.port 8501

# Option B: Command Line
uv run python dream-meridian.py -l <location> "<query>"
```

Access the dashboard at `http://<your-pi-ip>:8501`.

---

### Apple Silicon (macOS) - Alternative Rapid Test Setup

For rapid testing on M1/M2/M3/M4 Macs. Tested on M3 MacBook Air.

**1. Prerequisites**
```bash
brew install cmake
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Clone and Setup**
```bash
git clone https://github.com/msradam/dream-meridian
cd dream-meridian
uv sync
```

**3. Compile llama.cpp with Metal Support**
Metal provides GPU acceleration on Apple Silicon.
```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
mkdir build && cd build

cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DGGML_METAL=ON

cmake --build . --config Release -j
cd ../..
```

**4. Download Model**
```bash
mkdir -p models
uv run --with huggingface-hub hf download \
    Salesforce/xLAM-2-1b-fc-r-gguf \
    xLAM-2-1B-fc-r-Q5_K_M.gguf \
    --local-dir ./models
```

**5. Run the System**
Same as Pi—two terminal windows.

**Terminal 1: Start the LLM Server**
```bash
./llama.cpp/build/bin/llama-server \
    -m models/xLAM-2-1B-fc-r-Q5_K_M.gguf \
    --grammar-file tool_grammar.gbnf \
    -c 2048 -t 4 --mlock \
    --host 0.0.0.0 --port 8080
```

**Terminal 2: Start the Interface**
```bash
# Option A: Web Dashboard (GUI)
uv run streamlit run app.py --server.port 8501

# Option B: Command Line
uv run python dream-meridian.py -l <location> "<query>"
```

Access the dashboard at `http://localhost:8501`.

---

### Queries to Try

**Cox's Bazar, Bangladesh (Rohingya Refugee Camps)**
```bash
uv run python dream-meridian.py -l coxs_bazar "I need to find the nearest hospital to Camp 6"
uv run python dream-meridian.py -l coxs_bazar "How do I walk from Camp 3 to Camp 8W"
uv run python dream-meridian.py -l coxs_bazar "Show me everywhere I can walk to in 15 minutes from Camp 8W"
```

**San Juan, Puerto Rico (Hurricane Response)**
```bash
uv run python dream-meridian.py -l san_juan "Where is the closest hospital to Condado"
uv run python dream-meridian.py -l san_juan "How do I get from Condado to Santurce on foot"
uv run python dream-meridian.py -l san_juan "Show me a 20 minute walking radius from Condado"
```

**Jakarta, Indonesia (Urban Flood Response)**
```bash
uv run python dream-meridian.py -l jakarta "Is there a bank near Gelora"
uv run python dream-meridian.py -l jakarta "What is the distance on foot from Pinangsia to Kalianyar"
uv run python dream-meridian.py -l jakarta "What can I reach in 15 minutes walking from Serdang"
```