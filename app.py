"""
Dream Meridian - Spatial Intelligence Frontend
Multi-location support for humanitarian scenarios
"""
import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import json
import time
import psutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# ============================================================================
# Configuration
# ============================================================================
LLAMA_URL = "http://localhost:8080/v1/chat/completions"

# ============================================================================
# Location Discovery
# ============================================================================
def discover_locations() -> dict:
    """Find all built locations by scanning for config.json files."""
    locations = {}
    for config_path in Path("data").glob("*/config.json"):
        try:
            with open(config_path) as f:
                config = json.load(f)
                slug = config["slug"]
                locations[slug] = {
                    "name": config["name"],
                    "center": [config["center"]["lat"], config["center"]["lon"]],
                    "bounds": config["bounds"],
                    "nodes": config.get("nodes", 0),
                    "edges": config.get("edges", 0),
                    "pois": config.get("pois", 0)
                }
        except (json.JSONDecodeError, KeyError):
            continue
    return locations

# ============================================================================
# Backend Integration
# ============================================================================
def load_backend(location_slug: str):
    """Load spatial tools for a specific location."""
    try:
        import spatial_tools
        import geocode_layer
        
        spatial_tools.load_location(location_slug)
        geocode_layer.load_location(location_slug)
        
        return spatial_tools, geocode_layer
    except ImportError as e:
        st.warning(f"⚠️ Backend modules not found: {e}")
        return None, None
    except Exception as e:
        st.warning(f"⚠️ Failed to load backend: {e}")
        return None, None

# ============================================================================
# System Stats
# ============================================================================
def get_pi_stats() -> dict:
    """Get Raspberry Pi system statistics."""
    stats = {"cpu_temp": None, "cpu_percent": None, "mem_used": None, 
             "mem_total": None, "mem_percent": None, "device": "Unknown"}
    
    # CPU Temperature
    try:
        result = subprocess.run(["vcgencmd", "measure_temp"],
                                capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            stats["cpu_temp"] = float(result.stdout.strip().split("=")[1].replace("'C", ""))
    except:
        try:
            temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
            if temp_path.exists():
                stats["cpu_temp"] = int(temp_path.read_text().strip()) / 1000
        except:
            pass
    
    # CPU & Memory
    try:
        stats["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        stats["mem_used"] = mem.used / (1024 ** 3)
        stats["mem_total"] = mem.total / (1024 ** 3)
        stats["mem_percent"] = mem.percent
    except:
        pass
    
    # Device info
    try:
        model_path = Path("/proc/device-tree/model")
        if model_path.exists():
            stats["device"] = model_path.read_text().strip().replace("\x00", "")
    except:
        pass
    
    return stats

def check_llm_server() -> bool:
    """Check if llama-server is responding."""
    try:
        r = requests.get(LLAMA_URL.replace('/v1/chat/completions', '/health'), timeout=1)
        return r.status_code == 200
    except:
        try:
            requests.get(LLAMA_URL.replace('/v1/chat/completions', ''), timeout=1)
            return True
        except:
            return False

@st.fragment(run_every="2s")
def render_system_stats():
    """Render live system stats."""
    stats = get_pi_stats()
    
    st.markdown("### 🖥️ System Monitor")
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
        <span style="display: inline-block; width: 8px; height: 8px; background: #22c55e; 
                     border-radius: 50%; animation: pulse 2s infinite;"></span>
        <span style="font-size: 11px; color: #6b7280;">LIVE</span>
    </div>
    <style>@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }</style>
    """, unsafe_allow_html=True)
    
    if stats["device"] != "Unknown":
        st.caption(f"**{stats['device']}**")
    
    col1, col2 = st.columns(2)
    with col1:
        if stats["cpu_temp"] is not None:
            st.metric("🌡️ CPU", f"{stats['cpu_temp']:.1f}°C")
        if stats["cpu_percent"] is not None:
            st.metric("⚡ Load", f"{stats['cpu_percent']:.0f}%")
    with col2:
        if stats["mem_percent"] is not None:
            st.metric("🧠 RAM", f"{stats['mem_percent']:.0f}%")
            st.caption(f"{stats['mem_used']:.1f}/{stats['mem_total']:.1f} GB")
    
    # Temperature bar
    if stats["cpu_temp"] is not None:
        temp = stats["cpu_temp"]
        temp_pct = min(temp / 85 * 100, 100)
        color = "#22c55e" if temp < 60 else "#eab308" if temp < 75 else "#ef4444"
        st.markdown(f"""
        <div style="background: #374151; border-radius: 4px; height: 8px; margin-top: 8px;">
            <div style="background: {color}; width: {temp_pct}%; height: 100%; border-radius: 4px;"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 10px; color: #9ca3af;">
            <span>0°C</span><span>85°C</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Server status
    llm_online = check_llm_server()
    st.markdown(f"{'🟢' if llm_online else '🔴'} **LLM:** {'Online' if llm_online else 'Offline'}")

# ============================================================================
# Query Processing
# ============================================================================
SYSTEM_PROMPT = """Select ONE tool. Output JSON only.
Tools:
- geocode_place(place_name) - Get coordinates for a place name
- list_pois(poi_type,lat,lon,radius_m) - List POIs with distances
- count_pois(poi_type,lat,lon,radius_m) - Count POIs in area
- find_nearest_poi_with_route(poi_type,start_lat,start_lon) - Nearest POIs with walking distance
- generate_isochrone(start_lat,start_lon,max_minutes) - Walkable area from point
- calculate_route(start_lat,start_lon,end_lat,end_lon) - Walking route between points"""

@dataclass
class QueryResult:
    tool_name: str
    tool_args: dict
    result: dict
    geocoded: dict
    query_time: float
    modified_query: str

def process_query(user_query: str, spatial_tools, geocode_layer) -> QueryResult | None:
    """Process natural language query."""
    start_time = time.time()
    
    if spatial_tools is None:
        return _demo_result(user_query, start_time)
    
    try:
        modified_query, geocoded = geocode_layer.geocode_query(user_query)
        
        response = requests.post(LLAMA_URL, json={
            "model": "xLAM",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": modified_query}
            ]
        }, timeout=60)
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        tool_call = json.loads(content)
        
        result = json.loads(spatial_tools.execute_tool(tool_call['name'], **tool_call['arguments']))
        
        return QueryResult(
            tool_name=tool_call['name'],
            tool_args=tool_call['arguments'],
            result=result,
            geocoded=geocoded,
            query_time=time.time() - start_time,
            modified_query=modified_query
        )
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to LLM server. Is llama-server running?")
        return None
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        return None

def _demo_result(query: str, start_time: float) -> QueryResult:
    """Demo data when backend unavailable."""
    return QueryResult(
        tool_name="find_nearest_poi_with_route",
        tool_args={"poi_type": "hospital", "start_lat": 23.75, "start_lon": 90.39},
        result={
            "poi_type": "hospital", "found": 2,
            "nearest_pois": [
                {"name": "Demo Hospital 1", "walk_minutes": 7.0, "lat": 23.752, "lon": 90.385},
                {"name": "Demo Hospital 2", "walk_minutes": 12.5, "lat": 23.758, "lon": 90.392}
            ]
        },
        geocoded={"Demo": {"place": "Demo", "lat": 23.75, "lon": 90.39, "matches": 10}},
        query_time=time.time() - start_time,
        modified_query=query + " [DEMO]"
    )

# ============================================================================
# Map Rendering
# ============================================================================
POI_COLORS = {"hospital": "red", "school": "blue", "pharmacy": "green",
              "restaurant": "orange", "bank": "purple", "default": "gray"}

def create_map(result: QueryResult | None, location: dict, location_slug: str) -> folium.Map:
    """Create Folium map with results."""
    center = location["center"]
    
    # Use online tiles
    m = folium.Map(location=center, zoom_start=13, tiles="cartodbpositron")
    
    if result is None:
        return m
    
    # Geocoded markers
    for place, info in result.geocoded.items():
        folium.CircleMarker(
            [info['lat'], info['lon']], radius=8, color='black',
            fill=True, fillColor='yellow', fillOpacity=0.7,
            popup=f"📍 {place}"
        ).add_to(m)
    
    data = result.result
    tool = result.tool_name
    
    # POI markers
    if tool in ["list_pois", "find_nearest_poi_with_route"]:
        pois = data.get("nearest_pois") or data.get("pois", [])
        color = POI_COLORS.get(result.tool_args.get("poi_type", "default"), "gray")
        for poi in pois:
            popup = f"<b>{poi.get('name', 'Unknown')}</b>"
            if "walk_minutes" in poi:
                popup += f"<br>🚶 {poi['walk_minutes']:.1f} min"
            folium.Marker([poi['lat'], poi['lon']], popup=popup,
                          icon=folium.Icon(color=color)).add_to(m)
    
    # Count circle
    elif tool == "count_pois":
        args = result.tool_args
        folium.Circle([args.get("lat"), args.get("lon")], radius=args.get("radius_m", 1000),
                      color="blue", fill=True, fillOpacity=0.2,
                      popup=f"{data.get('count', 0)} found").add_to(m)
    
    # Route
    elif tool == "calculate_route":
        path = data.get("path", [])
        if path:
            coords = [[p["lat"], p["lon"]] for p in path]
            folium.PolyLine(coords, weight=4, color="blue", opacity=0.8).add_to(m)
            folium.Marker(coords[0], icon=folium.Icon(color="green", icon="play")).add_to(m)
            folium.Marker(coords[-1], icon=folium.Icon(color="red", icon="stop")).add_to(m)
    
    # Isochrone
    elif tool == "generate_isochrone":
        import math
        boundary = data.get("boundary_points", [])
        if boundary:
            args = result.tool_args
            cx, cy = args.get("start_lat"), args.get("start_lon")
            boundary.sort(key=lambda p: math.atan2(p["lat"]-cx, p["lon"]-cy))
            coords = [[p["lat"], p["lon"]] for p in boundary]
            folium.Polygon(coords, color="purple", fill=True, fillOpacity=0.25).add_to(m)
            folium.Marker([cx, cy], icon=folium.Icon(color="purple", icon="user")).add_to(m)
    
    # Fit bounds
    points = [[info['lat'], info['lon']] for info in result.geocoded.values()]
    for poi in data.get("nearest_pois", []) + data.get("pois", []):
        points.append([poi['lat'], poi['lon']])
    for p in data.get("path", []):
        points.append([p['lat'], p['lon']])
    if len(points) >= 2:
        m.fit_bounds(points, padding=[20, 20])
    
    return m

# ============================================================================
# Main App
# ============================================================================
def main():
    st.set_page_config(page_title="Dream Meridian", page_icon="🗺️", layout="wide")
    
    # Discover locations
    locations = discover_locations()
    
    if not locations:
        st.error("❌ No locations found! Run `python build_location.py` first.")
        st.code('python build_location.py "Dhaka, Bangladesh" dhaka\npython build_location.py "Mandalay, Myanmar" mandalay')
        return
    
    # Session state
    if "result" not in st.session_state:
        st.session_state.result = None
    if "current_location" not in st.session_state:
        st.session_state.current_location = list(locations.keys())[0]
    
    # Sidebar
    with st.sidebar:
        # Location selector
        st.markdown("### 🌍 Location")
        selected = st.selectbox(
            "Select city",
            options=list(locations.keys()),
            format_func=lambda x: locations[x]["name"],
            key="location_select"
        )
        
        # Handle location change
        if selected != st.session_state.current_location:
            st.session_state.current_location = selected
            st.session_state.result = None
            st.rerun()
        
        loc = locations[selected]
        st.caption(f"📍 {loc['nodes']:,} nodes · {loc['pois']:,} POIs")
        
        st.divider()
        render_system_stats()
        
        st.divider()
        st.markdown("### 💡 Examples")
        examples = [
            "Find hospitals near city center",
            "How many schools within 1km?",
            "Show 15 minute walkable area",
        ]
        for ex in examples:
            if st.button(ex, key=ex, use_container_width=True):
                st.session_state.pending_query = ex
    
    # Load backend for selected location
    spatial_tools, geocode_layer = load_backend(selected)
    
    # Header
    st.title("🗺️ Dream Meridian")
    loc_name = locations[selected]["name"]
    st.markdown(f"*Offline spatial intelligence for **{loc_name}** — powered by on-device AI*")
    
    # Tech bar
    st.markdown(f"""
    <div style="background: linear-gradient(90deg, #1e3a5f 0%, #2d5a87 100%); 
                padding: 8px 16px; border-radius: 8px; margin-bottom: 16px;
                display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
        <span style="color: #94a3b8; font-size: 13px;">
            🧠 <strong style="color: white;">xLAM-2-1B</strong>
            <span style="color: #64748b;">Q5_K_M</span>
        </span>
        <span style="color: #94a3b8; font-size: 13px;">
            🗄️ <strong style="color: white;">DuckDB</strong> +
            🛤️ <strong style="color: white;">NetworKit</strong>
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        query = st.text_input(
            "Ask a spatial question:",
            placeholder=f"e.g., Find hospitals in {loc_name.split(',')[0]}",
            value=st.session_state.get("pending_query", ""),
            key="query_input"
        )
        if "pending_query" in st.session_state:
            del st.session_state.pending_query
        
        if st.button("🔍 Search", type="primary", use_container_width=True) and query:
            with st.spinner("Processing..."):
                result = process_query(query, spatial_tools, geocode_layer)
                if result:
                    st.session_state.result = result
        
        st.subheader("🗺️ Map")
        map_obj = create_map(st.session_state.result, loc, selected)
        st_folium(map_obj, height=500, use_container_width=True)
    
    with col2:
        result = st.session_state.result
        if result:
            st.subheader("⏱️ Performance")
            st.metric("Query Time", f"{result.query_time:.2f}s")
            
            if result.geocoded:
                st.subheader("📍 Geocoded")
                for place, info in result.geocoded.items():
                    st.markdown(f"**{place}**")
                    st.caption(f"({info['lat']:.4f}, {info['lon']:.4f})")
            
            st.subheader("🔧 Tool")
            st.code(result.tool_name)
            
            st.subheader("📊 Results")
            data = result.result
            
            if "count" in data:
                st.metric(data.get('poi_type', 'POIs').title(), data['count'])
            
            pois = data.get("nearest_pois") or data.get("pois", [])
            for poi in pois[:5]:
                st.markdown(f"**{poi.get('name', 'Unknown')}**")
                if "walk_minutes" in poi:
                    st.caption(f"🚶 {poi['walk_minutes']:.1f} min")
            
            if "distance_km" in data:
                c1, c2 = st.columns(2)
                c1.metric("Distance", f"{data['distance_km']:.2f} km")
                c2.metric("Time", f"{data['walk_minutes']:.0f} min")
            
            with st.expander("Raw JSON"):
                st.json(data)
        else:
            st.info("👆 Enter a query to see results")
    
    # Footer
    st.divider()
    pi_stats = get_pi_stats()
    device = pi_stats["device"] if pi_stats["device"] != "Unknown" else "ARM Device"
    st.markdown(f"""
    <div style="text-align: center; color: #64748b; font-size: 12px;">
        🔌 <strong>AI runs 100% on-device</strong> on <strong>{device}</strong> · 
        ARM AI Developer Challenge 2025
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()