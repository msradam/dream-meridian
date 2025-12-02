#!/usr/bin/env python3
"""
DreamMeridian - Spatial Intelligence Dashboard
Offline AI-powered spatial queries for humanitarian scenarios
"""
import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import psutil
import subprocess
import platform
import re
from pathlib import Path
from datetime import timedelta

# Import query engine
import importlib.util
spec = importlib.util.spec_from_file_location("dream_meridian", "dream-meridian.py")
dm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dm)

# ============================================================================
# Configuration
# ============================================================================
LLAMA_URL = "http://localhost:8080/v1/chat/completions"

CUSTOM_CSS = """
<style>
/* Clan Font Family */
@font-face {
    font-family: 'Clan';
    src: url('app/static/ClanOT-Book.woff2') format('woff2'),
         url('app/static/ClanOT-Book.woff') format('woff'),
         url('app/static/ClanOT-Book.ttf') format('truetype');
    font-weight: 400;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: 'Clan';
    src: url('app/static/ClanOT-Medium.woff2') format('woff2'),
         url('app/static/ClanOT-Medium.woff') format('woff'),
         url('app/static/ClanOT-Medium.ttf') format('truetype');
    font-weight: 500;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: 'Clan';
    src: url('app/static/ClanOT-Bold.woff2') format('woff2'),
         url('app/static/ClanOT-Bold.woff') format('woff'),
         url('app/static/ClanOT-Bold.ttf') format('truetype');
    font-weight: 700;
    font-style: normal;
    font-display: swap;
}

/* Apply Clan globally - override Streamlit */
html, body, [class*="css"], 
.stApp, .stApp *, 
.stMarkdown, .stMarkdown p, .stMarkdown span,
.stTextInput input, .stTextInput label,
.stSelectbox, .stSelectbox label, .stSelectbox div,
.stButton button, .stButton span,
.stMetric, .stMetric label, .stMetric [data-testid="stMetricValue"],
.stCaption, .stExpander,
section[data-testid="stSidebar"], section[data-testid="stSidebar"] *,
div[data-testid="stMarkdownContainer"], div[data-testid="stMarkdownContainer"] * {
    font-family: 'Clan', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Headers specifically */
h1, h2, h3, h4, h5, h6,
.stApp h1, .stApp h2, .stApp h3 {
    font-family: 'Clan', -apple-system, BlinkMacSystemFont, sans-serif !important;
    font-weight: 700 !important;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding-top: 1.5rem; padding-bottom: 1rem;}

/* Sidebar - always visible, no collapse */
section[data-testid="stSidebar"] {
    min-width: 300px !important;
    width: 300px !important;
}
section[data-testid="stSidebar"] > div {
    width: 300px !important;
}
section[data-testid="stSidebar"] .block-container {padding-top: 1rem;}
section[data-testid="stSidebar"] hr {
    margin: 0.75rem 0;
    border-color: rgba(255,255,255,0.1);
}

/* Tighten metric spacing */
div[data-testid="stMetric"] {padding: 0.4rem 0;}
div[data-testid="stMetric"] label {font-size: 0.7rem; opacity: 0.7;}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {font-size: 1.25rem;}

/* Smaller text overall */
.stApp p, .stApp span, .stApp div {font-size: 0.9rem;}
.stApp h2 {font-size: 1.5rem !important;}
.stCaption {font-size: 0.8rem !important;}

/* Subtle code blocks */
code {
    background: rgba(59, 130, 246, 0.15);
    color: #60a5fa;
    padding: 0.2rem 0.4rem;
    border-radius: 4px;
    font-size: 0.85rem;
}

/* Clean buttons */
.stButton > button {border-radius: 6px; font-weight: 500;}

/* System info card */
.system-card {
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(71, 85, 105, 0.4);
    border-radius: 8px;
    padding: 0.75rem;
    margin-bottom: 0.5rem;
}
.system-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}
.system-device {
    font-weight: 600;
    font-size: 0.9rem;
    color: #f1f5f9;
}
.system-os {
    font-size: 0.75rem;
    color: #94a3b8;
}
.system-uptime {
    font-size: 0.7rem;
    color: #64748b;
    background: rgba(100, 116, 139, 0.2);
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
}

/* Stats row */
.stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.5rem;
    margin-top: 0.5rem;
}
.stat-box {
    text-align: center;
    padding: 0.4rem;
    background: rgba(15, 23, 42, 0.5);
    border-radius: 6px;
}
.stat-value {
    font-size: 1rem;
    font-weight: 700;
    color: #f1f5f9;
    line-height: 1.2;
}
.stat-value.temp { color: #4ade80; }
.stat-value.temp-warm { color: #fbbf24; }
.stat-value.temp-hot { color: #f87171; }
.stat-label {
    font-size: 0.65rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* LLM status */
.llm-status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 500;
}
.llm-online {
    background: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.3);
    color: #4ade80;
}
.llm-offline {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #f87171;
}
.llm-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    animation: pulse 2s infinite;
}
.llm-online .llm-dot { background: #4ade80; }
.llm-offline .llm-dot { background: #f87171; }
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* Info badges */
.info-row {
    display: flex; gap: 0.5rem; flex-wrap: wrap;
    font-size: 0.8rem;
}
.info-row span {
    background: rgba(59, 130, 246, 0.1);
    border: 1px solid rgba(59, 130, 246, 0.2);
    color: #94a3b8;
    padding: 0.3rem 0.6rem;
    border-radius: 5px;
    font-weight: 500;
}

/* Section headers */
.section-header {
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #64748b;
    margin: 0.6rem 0 0.4rem 0;
}

/* Results panel */
.result-item {
    padding: 0.35rem 0;
    border-bottom: 1px solid rgba(71, 85, 105, 0.2);
    font-size: 0.85rem;
}
.result-item:last-child { border-bottom: none; }
.result-name {
    font-weight: 500;
    color: #f1f5f9;
}
.result-detail {
    font-size: 0.8rem;
    color: #94a3b8;
}

/* Geocoded badge */
.geo-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    background: rgba(251, 191, 36, 0.15);
    border: 1px solid rgba(251, 191, 36, 0.3);
    color: #fbbf24;
    padding: 0.2rem 0.4rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
    margin-bottom: 0.2rem;
}
.geo-coords {
    font-size: 0.65rem;
    color: #64748b;
    font-family: 'JetBrains Mono', monospace;
}

/* Map container */
iframe {
    border-radius: 10px !important;
    border: 1px solid rgba(71, 85, 105, 0.3) !important;
}
</style>
"""

# ============================================================================
# Hardware Information
# ============================================================================
@st.cache_data(ttl=60)
def get_static_hw_info() -> dict:
    """Get static hardware info (cached)."""
    info = {
        "device": "Unknown", "device_short": "Unknown",
        "os_name": "Unknown", "os_version": "",
        "cpu_model": "", "cpu_cores": 0, "cpu_arch": platform.machine(),
        "mem_total_gb": 0,
        "kernel": "",
        "hostname": platform.node(),
    }
    
    model_path = Path("/proc/device-tree/model")
    if model_path.exists():
        try:
            model = model_path.read_text().strip().replace("\x00", "")
            info["device"] = model
            short = model.replace("Raspberry Pi ", "Pi ")
            short = re.sub(r" Model ([A-Z])", r" \1", short)
            short = re.sub(r" Rev [\d.]+", "", short)
            info["device_short"] = short.strip()
        except: pass
    
    if Path("/boot/dietpi/.version").exists():
        try:
            lines = Path("/boot/dietpi/.version").read_text().strip().split('\n')
            v = {}
            for line in lines:
                if '=' in line:
                    k, val = line.split('=', 1)
                    v[k] = val.strip("'\"")
            core = v.get('G_DIETPI_VERSION_CORE', '')
            sub = v.get('G_DIETPI_VERSION_SUB', '')
            info["os_name"] = "DietPi"
            info["os_version"] = f"{core}.{sub}" if core else ""
        except:
            info["os_name"] = "DietPi"
    else:
        if Path("/etc/os-release").exists():
            try:
                for line in Path("/etc/os-release").read_text().split("\n"):
                    if line.startswith("ID="):
                        info["os_name"] = line.split("=")[1].strip('"').title()
                    elif line.startswith("VERSION_ID="):
                        info["os_version"] = line.split("=")[1].strip('"')
            except: pass
    
    if Path("/proc/cpuinfo").exists():
        try:
            cpuinfo = Path("/proc/cpuinfo").read_text()
            for line in cpuinfo.split("\n"):
                if line.startswith("model name") or line.startswith("Model"):
                    info["cpu_model"] = line.split(":")[1].strip()
                    break
            info["cpu_cores"] = cpuinfo.count("processor\t:")
        except: pass
    
    if not info["cpu_cores"]:
        info["cpu_cores"] = psutil.cpu_count(logical=True) or 0
    
    info["mem_total_gb"] = psutil.virtual_memory().total / (1024**3)
    info["kernel"] = platform.release()
    
    return info

def get_dynamic_stats() -> dict:
    """Get dynamic system stats."""
    stats = {
        "cpu_temp": None, "cpu_percent": 0, "cpu_freq": None,
        "mem_percent": 0, "mem_used_gb": 0,
        "disk_percent": 0,
        "uptime": "",
    }
    
    try:
        result = subprocess.run(["vcgencmd", "measure_temp"],
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            stats["cpu_temp"] = float(result.stdout.split("=")[1].replace("'C", ""))
    except:
        try:
            temp = Path("/sys/class/thermal/thermal_zone0/temp")
            if temp.exists():
                stats["cpu_temp"] = int(temp.read_text().strip()) / 1000
        except: pass
    
    stats["cpu_percent"] = psutil.cpu_percent(interval=0.1)
    try:
        freq = psutil.cpu_freq()
        if freq:
            stats["cpu_freq"] = freq.current
    except: pass
    
    mem = psutil.virtual_memory()
    stats["mem_percent"] = mem.percent
    stats["mem_used_gb"] = mem.used / (1024**3)
    
    try:
        stats["disk_percent"] = psutil.disk_usage("/").percent
    except: pass
    
    try:
        uptime_sec = float(Path("/proc/uptime").read_text().split()[0])
        td = timedelta(seconds=int(uptime_sec))
        if td.days > 0:
            stats["uptime"] = f"{td.days}d {td.seconds // 3600}h"
        else:
            h, rem = divmod(td.seconds, 3600)
            m = rem // 60
            stats["uptime"] = f"{h}h {m}m"
    except: pass
    
    return stats

def get_llm_status() -> dict:
    """Check LLM server status."""
    import requests
    status = {"online": False, "model": None, "backend": "CPU"}
    
    try:
        health = requests.get(LLAMA_URL.replace('/v1/chat/completions', '/health'), timeout=2)
        status["online"] = health.status_code == 200
        
        try:
            props = requests.get(LLAMA_URL.replace('/v1/chat/completions', '/props'), timeout=2)
            if props.status_code == 200:
                data = props.json()
                status["model"] = data.get("model_alias") or data.get("model", "").split("/")[-1]
        except: pass
    except: pass
    
    return status

# ============================================================================
# Location Discovery
# ============================================================================
def discover_locations() -> dict:
    """Find all built locations."""
    locations = {}
    for config_path in Path("data").glob("*/config.json"):
        try:
            with open(config_path) as f:
                cfg = json.load(f)
                locations[cfg["slug"]] = {
                    "name": cfg["name"],
                    "center": [cfg["center"]["lat"], cfg["center"]["lon"]],
                    "bounds": cfg["bounds"],
                    "nodes": cfg.get("nodes", 0),
                    "pois": cfg.get("pois", 0),
                    "places": cfg.get("places", 0),
                    "examples": cfg.get("examples", [
                        "Find hospitals nearby",
                        "Schools within 1km",
                        "15 min walkable area"
                    ])
                }
        except: continue
    return locations

# ============================================================================
# UI Components
# ============================================================================
@st.fragment(run_every="1s")
def render_system_panel():
    """Live system monitor panel with custom styling."""
    hw = get_static_hw_info()
    stats = get_dynamic_stats()
    llm = get_llm_status()
    
    # Temp color class
    temp_class = "temp"
    if stats["cpu_temp"]:
        if stats["cpu_temp"] > 70:
            temp_class = "temp-hot"
        elif stats["cpu_temp"] > 55:
            temp_class = "temp-warm"
    
    # System card
    st.markdown(f"""
    <div class="system-card">
        <div class="system-header">
            <div>
                <div class="system-device">{hw['device_short']}</div>
                <div class="system-os">{hw['os_name']} {hw['os_version']} · {hw['cpu_arch']} · {hw['cpu_cores']} cores</div>
            </div>
            <div class="system-uptime">⏱ {stats['uptime']}</div>
        </div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value {temp_class}">{stats['cpu_temp']:.0f}°</div>
                <div class="stat-label">Temp</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{stats['cpu_percent']:.0f}%</div>
                <div class="stat-label">CPU</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{stats['mem_percent']:.0f}%</div>
                <div class="stat-label">RAM</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{stats['disk_percent']:.0f}%</div>
                <div class="stat-label">Disk</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # LLM Status
    if llm["online"]:
        model_text = f" · {llm['model']}" if llm["model"] else ""
        st.markdown(f"""
        <div class="llm-status llm-online">
            <div class="llm-dot"></div>
            LLM Online{model_text}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="llm-status llm-offline">
            <div class="llm-dot"></div>
            LLM Offline
        </div>
        """, unsafe_allow_html=True)

# ============================================================================
# Map Rendering
# ============================================================================
POI_COLORS = {
    "hospital": "red", "clinic": "red", "doctors": "red",
    "pharmacy": "green", "school": "blue", "university": "blue",
    "shelter": "orange", "police": "darkblue", "fire_station": "red",
    "bank": "purple", "atm": "purple",
}

def create_map(result, location: dict) -> folium.Map:
    """Create Folium map with results."""
    m = folium.Map(location=location["center"], zoom_start=13, tiles="cartodbdark_matter")
    
    if not result or not result.success:
        return m
    
    for place, info in result.geocoded.items():
        folium.CircleMarker(
            [info['lat'], info['lon']], radius=8,
            color='#fbbf24', fill=True, fillColor='#fbbf24', fillOpacity=0.9,
            popup=f"📍 {place}"
        ).add_to(m)
    
    data = result.result
    tool = result.tool_name
    poi_type = data.get("poi_type", "location")
    color = POI_COLORS.get(poi_type, "gray")
    
    if tool == "list_pois":
        pois = data.get("pois", [])
        for poi in pois:
            name = poi.get('name') or f"Unnamed {poi_type}"
            popup = f"<b>{name}</b><br>📏 {poi.get('distance_m', 0):.0f}m"
            folium.Marker([poi['lat'], poi['lon']], popup=popup,
                         icon=folium.Icon(color=color, icon="info-sign")).add_to(m)
    
    elif tool == "find_nearest_poi_with_route":
        pois = data.get("nearest_pois", [])
        path = data.get("path", [])
        
        if path:
            coords = [[p["lat"], p["lon"]] for p in path]
            folium.PolyLine(coords, weight=4, color="#3b82f6", opacity=0.7).add_to(m)
            if "start" in data:
                folium.Marker([data["start"]["lat"], data["start"]["lon"]],
                             icon=folium.Icon(color="green", icon="play"), popup="Start").add_to(m)
        
        for i, poi in enumerate(pois):
            name = poi.get('name') or f"Unnamed"
            popup = f"<b>{name}</b><br>🚶 {poi['walk_minutes']:.0f} min"
            mc = color if i == 0 else "lightgray"
            folium.Marker([poi['lat'], poi['lon']], popup=popup,
                         icon=folium.Icon(color=mc, icon="info-sign")).add_to(m)
    
    elif tool in ["calculate_route", "find_along_route"]:
        path = data.get("path", [])
        if path:
            coords = [[p["lat"], p["lon"]] for p in path]
            folium.PolyLine(coords, weight=4, color="#3b82f6", opacity=0.8).add_to(m)
            folium.Marker(coords[0], icon=folium.Icon(color="green", icon="play")).add_to(m)
            folium.Marker(coords[-1], icon=folium.Icon(color="red", icon="stop")).add_to(m)
        for poi in data.get("pois", []):
            folium.Marker([poi['lat'], poi['lon']], popup=poi.get('name'),
                         icon=folium.Icon(color="orange")).add_to(m)
    
    elif tool == "generate_isochrone":
        import math
        boundary = data.get("boundary_points", [])
        args = result.tool_args
        cx = args.get("lat") or args.get("start_lat")
        cy = args.get("lon") or args.get("start_lon")
        if boundary and cx and cy:
            boundary.sort(key=lambda p: math.atan2(p["lat"]-cx, p["lon"]-cy))
            coords = [[p["lat"], p["lon"]] for p in boundary]
            folium.Polygon(coords, color="#a855f7", fill=True, fillOpacity=0.2).add_to(m)
            folium.Marker([cx, cy], icon=folium.Icon(color="purple", icon="user")).add_to(m)
    
    # Fit bounds
    points = [[i['lat'], i['lon']] for i in result.geocoded.values()]
    points += [[p['lat'], p['lon']] for p in data.get("nearest_pois", []) + data.get("pois", [])]
    points += [[p['lat'], p['lon']] for p in data.get("path", [])]
    points += [[p['lat'], p['lon']] for p in data.get("boundary_points", [])]
    if "start" in data:
        points.append([data["start"]["lat"], data["start"]["lon"]])
    if len(points) >= 2:
        m.fit_bounds(points, padding=[30, 30])
    
    return m

# ============================================================================
# Main Application
# ============================================================================
def main():
    st.set_page_config(page_title="DreamMeridian", page_icon="💠", layout="wide")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    
    locations = discover_locations()
    if not locations:
        st.error("No locations found. Run `python build_location.py` first.")
        return
    
    if "result" not in st.session_state:
        st.session_state.result = None
    if "current_location" not in st.session_state:
        st.session_state.current_location = list(locations.keys())[0]
    if "query_text" not in st.session_state:
        st.session_state.query_text = ""
    
    # ===== SIDEBAR =====
    with st.sidebar:
        st.selectbox(
            "Location", options=list(locations.keys()),
            format_func=lambda x: locations[x]["name"],
            key="location_select"
        )
        selected = st.session_state.location_select
        
        if selected != st.session_state.current_location:
            st.session_state.current_location = selected
            st.session_state.result = None
            st.session_state.query_text = ""
            st.rerun()
        
        loc = locations[selected]
        st.caption(f"{loc['nodes']:,} nodes · {loc['pois']:,} POIs")
        
        st.divider()
        
        render_system_panel()
        
        st.divider()
        
        st.markdown('<div class="section-header">Try asking</div>', unsafe_allow_html=True)
        for i, ex in enumerate(loc.get("examples", [])[:4]):
            if st.button(ex, key=f"ex_{i}", use_container_width=True):
                st.session_state.query_text = ex
                st.rerun()
    
    # ===== MAIN CONTENT =====
    loc = locations[selected]
    
    # Header row
    col_h1, col_h2 = st.columns([3, 2])
    with col_h1:
        st.markdown(f"## 💠 DreamMeridian")
        st.caption(f"Offline spatial intelligence for **{loc['name']}**")
    with col_h2:
        st.markdown("""
        <div class="info-row" style="justify-content: flex-end; margin-top: 0.5rem;">
            <span>🧠 xLAM-2-1B</span>
            <span>🗄️ DuckDB</span>
            <span>🛤️ NetworKit</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Query input
    query = st.text_input(
        "Query",
        value=st.session_state.query_text,
        placeholder=f"Ask about {loc['name'].split(',')[0]}...",
        label_visibility="collapsed"
    )
    st.session_state.query_text = query
    
    if st.button("Query", type="primary", disabled=not query):
        with st.spinner("Processing..."):
            result = dm.query(query, location=selected)
            st.session_state.result = result
            if not result.success:
                st.error(result.error)
    
    # Map (full width)
    map_obj = create_map(st.session_state.result, loc)
    st_folium(map_obj, height=450, use_container_width=True)
    
    # Results (below map)
    result = st.session_state.result
    
    if result and result.success:
        col_r1, col_r2, col_r3 = st.columns([1, 1, 2])
        
        with col_r1:
            st.metric("Query Time", f"{result.query_time:.2f}s")
            
            if result.geocoded:
                st.markdown('<div class="section-header">Geocoded</div>', unsafe_allow_html=True)
                for place, info in result.geocoded.items():
                    st.markdown(f"""
                    <div class="geo-badge">📍 {place}</div>
                    <div class="geo-coords">{info['lat']:.4f}, {info['lon']:.4f}</div>
                    """, unsafe_allow_html=True)
        
        with col_r2:
            st.markdown('<div class="section-header">Tool</div>', unsafe_allow_html=True)
            st.code(result.tool_name, language=None)
            
            data = result.result
            
            if "error" in data:
                st.error(data["error"])
            
            if "count" in data:
                poi_label = data.get('poi_type', 'POIs').replace('_', ' ').title()
                st.metric(poi_label, data['count'])
            
            if "distance_km" in data and "pois_found" not in data:
                st.metric("Route", f"{data['distance_km']:.1f} km · {int(data['walk_minutes'])} min")
            
            if "reachable_nodes" in data:
                st.metric(f"Reachable ({data['max_minutes']}m)", f"{data['reachable_nodes']:,}")
        
        with col_r3:
            data = result.result
            pois = data.get("nearest_pois") or data.get("pois", [])
            if pois:
                st.markdown('<div class="section-header">Results</div>', unsafe_allow_html=True)
                for poi in pois[:6]:
                    name = poi.get('name') or "Unnamed"
                    detail = ""
                    if "walk_minutes" in poi:
                        detail = f"· {poi['walk_minutes']:.0f} min"
                    elif "distance_m" in poi:
                        detail = f"· {poi['distance_m']:.0f}m"
                    st.markdown(f"""
                    <div class="result-item">
                        <span class="result-name">{name}</span>
                        <span class="result-detail">{detail}</span>
                    </div>
                    """, unsafe_allow_html=True)
                if len(pois) > 6:
                    st.caption(f"+{len(pois)-6} more")
            
            if st.checkbox("Show JSON", value=False):
                st.json(data)

if __name__ == "__main__":
    main()