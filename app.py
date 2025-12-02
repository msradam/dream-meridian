#!/usr/bin/env python3
"""
Dream Meridian - Spatial Intelligence Frontend
Multi-location support for humanitarian scenarios
"""
import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import psutil
import subprocess
from pathlib import Path

# Import the query engine from dream-meridian.py
import importlib.util
spec = importlib.util.spec_from_file_location("dream_meridian", "dream-meridian.py")
dream_meridian = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dream_meridian)

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
                    "pois": config.get("pois", 0),
                    "examples": config.get("examples", [
                        "Find hospitals nearby",
                        "How many schools within 1km?",
                        "Show 15 minute walkable area"
                    ])
                }
        except (json.JSONDecodeError, KeyError):
            continue
    return locations

# ============================================================================
# System Stats
# ============================================================================
def get_pi_stats() -> dict:
    """Get Raspberry Pi system statistics."""
    stats = {"cpu_temp": None, "cpu_percent": None, "mem_used": None, 
             "mem_total": None, "mem_percent": None, "device": "Unknown"}
    
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
    
    try:
        stats["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        stats["mem_used"] = mem.used / (1024 ** 3)
        stats["mem_total"] = mem.total / (1024 ** 3)
        stats["mem_percent"] = mem.percent
    except:
        pass
    
    try:
        model_path = Path("/proc/device-tree/model")
        if model_path.exists():
            stats["device"] = model_path.read_text().strip().replace("\x00", "")
    except:
        pass
    
    return stats

def check_llm_server() -> bool:
    """Check if llama-server is responding."""
    import requests
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
    """Render live system stats with compact layout."""
    stats = get_pi_stats()
    
    st.markdown("### 🖥️ System")
    
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">
        <span style="display: inline-block; width: 8px; height: 8px; background: #22c55e; 
                     border-radius: 50%; animation: pulse 2s infinite;"></span>
        <span style="font-size: 11px; color: #6b7280;">LIVE</span>
    </div>
    <style>@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }</style>
    """, unsafe_allow_html=True)
    
    if stats["device"] != "Unknown":
        device = stats["device"].replace("Raspberry Pi ", "Pi ").replace(" Model ", " ").replace(" Rev ", "r")
        st.caption(f"**{device}**")
    
    cpu_temp = f"{stats['cpu_temp']:.0f}°" if stats["cpu_temp"] else "N/A"
    cpu_load = f"{stats['cpu_percent']:.0f}%" if stats["cpu_percent"] is not None else "N/A"
    ram_pct = f"{stats['mem_percent']:.0f}%" if stats["mem_percent"] is not None else "N/A"
    ram_used = f"{stats['mem_used']:.1f}/{stats['mem_total']:.1f}G" if stats["mem_used"] else ""
    
    st.markdown(f"""
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 13px;">
        <div>
            <div style="color: #6b7280; font-size: 11px;">🌡️ Temp</div>
            <div style="font-size: 22px; font-weight: 600;">{cpu_temp}</div>
        </div>
        <div>
            <div style="color: #6b7280; font-size: 11px;">⚡ CPU</div>
            <div style="font-size: 22px; font-weight: 600;">{cpu_load}</div>
        </div>
        <div>
            <div style="color: #6b7280; font-size: 11px;">🧠 RAM</div>
            <div style="font-size: 22px; font-weight: 600;">{ram_pct}</div>
        </div>
        <div>
            <div style="color: #6b7280; font-size: 11px;">📦 Mem</div>
            <div style="font-size: 14px; margin-top: 6px;">{ram_used}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if stats["cpu_temp"] is not None:
        temp = stats["cpu_temp"]
        temp_pct = min(temp / 85 * 100, 100)
        color = "#22c55e" if temp < 60 else "#eab308" if temp < 75 else "#ef4444"
        st.markdown(f"""
        <div style="background: #374151; border-radius: 4px; height: 6px; margin: 12px 0 4px 0;">
            <div style="background: {color}; width: {temp_pct}%; height: 100%; border-radius: 4px;"></div>
        </div>
        """, unsafe_allow_html=True)
    
    llm_online = check_llm_server()
    st.markdown(f"{'🟢' if llm_online else '🔴'} **LLM:** {'Online' if llm_online else 'Offline'}")

# ============================================================================
# Map Rendering
# ============================================================================
POI_COLORS = {
    "hospital": "red", "clinic": "red", "doctors": "red",
    "pharmacy": "green", "school": "blue", "shelter": "orange",
    "police": "darkblue", "fire_station": "red", "bank": "purple",
    "default": "gray"
}

def create_map(result, location: dict, location_slug: str) -> folium.Map:
    """Create Folium map with results."""
    center = location["center"]
    m = folium.Map(location=center, zoom_start=13, tiles="cartodbdark_matter")
    
    if result is None or not result.success:
        return m
    
    for place, info in result.geocoded.items():
        folium.CircleMarker(
            [info['lat'], info['lon']], radius=10, color='#fbbf24',
            fill=True, fillColor='#fbbf24', fillOpacity=0.8,
            popup=f"📍 {place}"
        ).add_to(m)
    
    data = result.result
    tool = result.tool_name
    poi_type = data.get("poi_type", "location")
    
    if tool in ["list_pois", "find_nearest_poi_with_route"]:
        pois = data.get("nearest_pois") or data.get("pois", [])
        color = POI_COLORS.get(poi_type, "gray")
        
        for poi in pois:
            name = poi.get('name')
            popup = f"<b>{name}</b>" if name else f"<i>Unnamed {poi_type}</i>"
            
            if "walk_minutes" in poi:
                popup += f"<br>🚶 {poi['walk_minutes']:.1f} min"
            elif "distance_m" in poi:
                dist = poi['distance_m']
                popup += f"<br>📏 {dist/1000:.1f} km" if dist >= 1000 else f"<br>📏 {dist:.0f} m"
            
            folium.Marker([poi['lat'], poi['lon']], popup=popup,
                          icon=folium.Icon(color=color, icon="info-sign")).add_to(m)
        
        if "center" in data:
            center_pt = data["center"]
            folium.Circle([center_pt["lat"], center_pt["lon"]], 
                          radius=data.get("radius_m", 1000),
                          color="#3b82f6", fill=True, fillOpacity=0.1, weight=2).add_to(m)
    
    elif tool == "calculate_route":
        path = data.get("path", [])
        if path:
            coords = [[p["lat"], p["lon"]] for p in path]
            folium.PolyLine(coords, weight=5, color="#3b82f6", opacity=0.9).add_to(m)
            folium.Marker(coords[0], icon=folium.Icon(color="green", icon="play"), popup="Start").add_to(m)
            folium.Marker(coords[-1], icon=folium.Icon(color="red", icon="stop"), popup="End").add_to(m)
    
    elif tool == "generate_isochrone":
        import math
        boundary = data.get("boundary_points", [])
        if boundary:
            args = result.tool_args
            cx = args.get("lat") or args.get("start_lat")
            cy = args.get("lon") or args.get("start_lon")
            
            if cx and cy:
                boundary.sort(key=lambda p: math.atan2(p["lat"]-cx, p["lon"]-cy))
                coords = [[p["lat"], p["lon"]] for p in boundary]
                folium.Polygon(coords, color="#a855f7", fill=True, fillOpacity=0.25, weight=2).add_to(m)
                folium.Marker([cx, cy], icon=folium.Icon(color="purple", icon="user"), popup="Start").add_to(m)
    
    # Fit bounds
    points = [[info['lat'], info['lon']] for info in result.geocoded.values()]
    points += [[p['lat'], p['lon']] for p in data.get("nearest_pois", []) + data.get("pois", [])]
    points += [[p['lat'], p['lon']] for p in data.get("path", [])]
    points += [[p['lat'], p['lon']] for p in data.get("boundary_points", [])]
    
    if len(points) >= 2:
        m.fit_bounds(points, padding=[30, 30])
    elif len(points) == 1:
        m.location = points[0]
    
    return m

# ============================================================================
# Main App
# ============================================================================
def main():
    st.set_page_config(page_title="Dream Meridian", page_icon="🗺️", layout="wide")
    
    locations = discover_locations()
    
    if not locations:
        st.error("❌ No locations found! Run `python build_location.py` first.")
        return
    
    # Session state initialization
    if "result" not in st.session_state:
        st.session_state.result = None
    if "current_location" not in st.session_state:
        st.session_state.current_location = list(locations.keys())[0]
    if "query_text" not in st.session_state:
        st.session_state.query_text = ""
    
    # ========== SIDEBAR ==========
    with st.sidebar:
        st.markdown("### 🌍 Location")
        selected = st.selectbox(
            "Select city", options=list(locations.keys()),
            format_func=lambda x: locations[x]["name"],
            key="location_select", label_visibility="collapsed"
        )
        
        if selected != st.session_state.current_location:
            st.session_state.current_location = selected
            st.session_state.result = None
            st.session_state.query_text = ""
            st.rerun()
        
        loc = locations[selected]
        st.caption(f"📍 {loc['nodes']:,} nodes · {loc['pois']:,} POIs")
        
        st.divider()
        render_system_stats()
        
        st.divider()
        st.markdown("### 💡 Try asking")
        for i, ex in enumerate(loc.get("examples", [])[:3]):
            if st.button(ex, key=f"ex_{i}_{selected}", use_container_width=True):
                st.session_state.query_text = ex
                st.rerun()
    
    # ========== MAIN CONTENT ==========
    st.title("🗺️ Dream Meridian")
    loc_name = locations[selected]["name"]
    st.markdown(f"*Offline spatial intelligence for **{loc_name}** — powered by on-device AI*")
    
    st.markdown("""
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
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Query input (outside form for dynamic updates)
        query = st.text_input(
            "Ask a spatial question:",
            value=st.session_state.query_text,
            placeholder=f"e.g., {loc.get('examples', ['Find hospitals nearby'])[0]}",
            key="query_input"
        )
        
        # Update stored query text
        st.session_state.query_text = query
        
        # Search button
        if st.button("🔍 Search", type="primary", use_container_width=True, disabled=not query):
            with st.spinner("Processing..."):
                result = dream_meridian.query(query, location=selected)
                st.session_state.result = result
                if not result.success:
                    st.error(f"❌ {result.error}")
        
        st.subheader("🗺️ Map")
        map_obj = create_map(st.session_state.result, loc, selected)
        st_folium(map_obj, height=500, use_container_width=True)
    
    with col2:
        result = st.session_state.result
        
        if result and result.success:
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
            
            if "error" in data:
                st.error(data["error"])
            
            if "count" in data:
                poi_type = data.get('poi_type', 'POIs').replace('_', ' ').title()
                st.metric(poi_type, data['count'])
            
            pois = data.get("nearest_pois") or data.get("pois", [])
            if pois:
                for poi in pois[:8]:
                    name = poi.get('name')
                    poi_type_str = data.get('poi_type', 'location')
                    st.markdown(f"**{name}**" if name else f"*Unnamed {poi_type_str}*")
                    
                    if "walk_minutes" in poi:
                        st.caption(f"🚶 {poi['walk_minutes']:.1f} min walk")
                    elif "distance_m" in poi:
                        dist = poi['distance_m']
                        st.caption(f"📏 {dist/1000:.1f} km" if dist >= 1000 else f"📏 {dist:.0f} m")
                
                if len(pois) > 8:
                    st.caption(f"*+ {len(pois) - 8} more*")
            
            if "distance_km" in data:
                c1, c2 = st.columns(2)
                c1.metric("Distance", f"{data['distance_km']:.2f} km")
                c2.metric("Walking", f"{data['walk_minutes']:.0f} min")
            
            if "reachable_nodes" in data:
                st.metric(f"Reachable ({data['max_minutes']} min)", f"{data['reachable_nodes']:,} nodes")
            
            with st.expander("Raw JSON"):
                st.json(data)
        
        elif result and not result.success:
            st.error(f"Query failed: {result.error}")
        else:
            st.info("👆 Enter a query to see results")
    
    # Footer
    st.divider()
    pi_stats = get_pi_stats()
    device = pi_stats["device"] if pi_stats["device"] != "Unknown" else "ARM Device"
    st.markdown(f"""
    <div style="text-align: center; color: #64748b; font-size: 12px;">
        📌 <strong>100% on-device AI</strong> running on <strong>{device}</strong> · 
        ARM AI Developer Challenge 2025
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()