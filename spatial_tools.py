"""
./spatial_tools.py
Dream Meridian - Spatial Tools
Multi-location support: load_location("dhaka") loads data/dhaka/*
"""

import networkit as nk
import duckdb
import json
from pathlib import Path

# ============================================================================
# Global State (populated by load_location)
# ============================================================================
G_nk = None
node_mapping = {}
reverse_mapping = {}
con = None
current_location = None

# ============================================================================
# Location Loading
# ============================================================================

def get_available_locations() -> dict:
    """Discover all built locations."""
    locations = {}
    for config_path in Path("data").glob("*/config.json"):
        try:
            with open(config_path) as f:
                config = json.load(f)
                locations[config["slug"]] = {
                    "name": config["name"],
                    "center": config["center"],
                    "nodes": config.get("nodes", 0),
                    "pois": config.get("pois", 0),
                    "path": config_path.parent
                }
        except:
            continue
    return locations

def load_location(slug: str):
    """
    Load a location by slug. Call this when user switches cities.
    
    Example:
        load_location("dhaka")
        load_location("mandalay")
    """
    global G_nk, node_mapping, reverse_mapping, con, current_location
    
    # Skip if already loaded
    if current_location == slug and G_nk is not None:
        return
    
    base_path = Path("data") / slug
    
    if not base_path.exists():
        raise FileNotFoundError(f"Location not found: {base_path}")
    
    print(f"Loading {slug}...")
    
    # Load graph
    graph_path = base_path / f"{slug}.nkb"
    G_nk = nk.graphio.readGraph(str(graph_path), nk.Format.NetworkitBinary)
    print(f"  ✓ Graph: {G_nk.numberOfNodes():,} nodes, {G_nk.numberOfEdges():,} edges")
    
    # Load mappings
    mappings_path = base_path / f"{slug}_mappings.json"
    with open(mappings_path, 'r') as f:
        mappings = json.load(f)
        node_mapping = {int(k): v for k, v in mappings['nx_to_nk'].items()}
        reverse_mapping = {int(k): v for k, v in mappings['nk_to_nx'].items()}
    
    # Connect to database
    db_path = base_path / f"{slug}.duckdb"
    if con is not None:
        con.close()
    con = duckdb.connect(str(db_path), read_only=True)
    con.install_extension("spatial")
    con.load_extension("spatial")
    
    poi_count = con.execute("SELECT COUNT(*) FROM osm_features").fetchone()[0]
    print(f"  ✓ Database: {poi_count:,} POIs")
    
    current_location = slug
    print(f"  ✓ Ready: {slug}")

# ============================================================================
# Spatial Queries
# ============================================================================

def find_nearest_node(lat: float, lon: float) -> tuple:
    """Find nearest graph node to a lat/lon point."""
    result = con.execute("""
        SELECT node_id, lat, lon
        FROM nodes
        ORDER BY ST_Distance(geom, ST_Point(?, ?))
        LIMIT 1
    """, [lon, lat]).fetchone()
    return result

def list_pois(poi_type: str, lat: float, lon: float, radius_m: int = 1000) -> str:
    """List POIs of a given type within radius."""
    results = con.execute("""
        SELECT name, lat, lon,
               ST_Distance(geom, ST_Point(?, ?)) * 111000 as distance_m
        FROM osm_features
        WHERE tag_value = ?
          AND ST_Distance(geom, ST_Point(?, ?)) * 111000 < ?
        ORDER BY distance_m
        LIMIT 20
    """, [lon, lat, poi_type, lon, lat, radius_m]).fetchall()
    
    return json.dumps({
        "poi_type": poi_type,
        "count": len(results),
        "pois": [{"name": r[0], "lat": r[1], "lon": r[2], "distance_m": r[3]} for r in results]
    })

def count_pois(poi_type: str, lat: float, lon: float, radius_m: int = 1000) -> str:
    """Count POIs of a given type within radius."""
    result = con.execute("""
        SELECT COUNT(*)
        FROM osm_features
        WHERE tag_value = ?
          AND ST_Distance(geom, ST_Point(?, ?)) * 111000 < ?
    """, [poi_type, lon, lat, radius_m]).fetchone()
    
    return json.dumps({
        "poi_type": poi_type,
        "count": result[0],
        "radius_m": radius_m,
        "center": {"lat": lat, "lon": lon}
    })

def find_nearest_poi_with_route(poi_type: str, lat: float, lon: float, limit: int = 3) -> str:
    """Find nearest POIs and calculate walking routes to each."""
    # Get nearby POIs
    pois = con.execute("""
        SELECT name, lat, lon
        FROM osm_features
        WHERE tag_value = ?
          AND name IS NOT NULL
        ORDER BY ST_Distance(geom, ST_Point(?, ?))
        LIMIT ?
    """, [poi_type, lon, lat, limit]).fetchall()
    
    if not pois:
        return json.dumps({"poi_type": poi_type, "found": 0, "nearest_pois": []})
    
    # Find start node
    start_node = find_nearest_node(lat, lon)
    start_nk = node_mapping.get(start_node[0])
    
    results = []
    for name, poi_lat, poi_lon in pois:
        # Find end node
        end_node = find_nearest_node(poi_lat, poi_lon)
        end_nk = node_mapping.get(end_node[0])
        
        if start_nk is None or end_nk is None:
            continue
        
        # Calculate route
        dijkstra = nk.distance.Dijkstra(G_nk, start_nk, True, False, end_nk)
        dijkstra.run()
        
        distance_m = dijkstra.distance(end_nk)
        if distance_m < float('inf'):
            walk_minutes = distance_m / 83.33  # ~5 km/h walking
            results.append({
                "name": name,
                "lat": poi_lat,
                "lon": poi_lon,
                "distance_m": round(distance_m, 1),
                "walk_minutes": round(walk_minutes, 1)
            })
    
    results.sort(key=lambda x: x["walk_minutes"])
    
    return json.dumps({
        "poi_type": poi_type,
        "found": len(results),
        "nearest_pois": results
    })

def calculate_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> str:
    """Calculate walking route between two points."""
    start_node = find_nearest_node(start_lat, start_lon)
    end_node = find_nearest_node(end_lat, end_lon)
    
    start_nk = node_mapping.get(start_node[0])
    end_nk = node_mapping.get(end_node[0])
    
    if start_nk is None or end_nk is None:
        return json.dumps({"error": "Could not find route nodes"})
    
    dijkstra = nk.distance.Dijkstra(G_nk, start_nk, True, True, end_nk)
    dijkstra.run()
    
    distance_m = dijkstra.distance(end_nk)
    if distance_m == float('inf'):
        return json.dumps({"error": "No route found"})
    
    # Get path
    path_nk = dijkstra.getPath(end_nk)
    
    # Convert to lat/lon (sample every nth node for large paths)
    step = max(1, len(path_nk) // 100)
    path_coords = []
    for i in range(0, len(path_nk), step):
        nx_id = reverse_mapping.get(path_nk[i])
        if nx_id:
            node_data = con.execute(
                "SELECT lat, lon FROM nodes WHERE node_id = ?", [nx_id]
            ).fetchone()
            if node_data:
                path_coords.append({"lat": node_data[0], "lon": node_data[1]})
    
    # Always include last node
    if path_nk:
        nx_id = reverse_mapping.get(path_nk[-1])
        if nx_id:
            node_data = con.execute(
                "SELECT lat, lon FROM nodes WHERE node_id = ?", [nx_id]
            ).fetchone()
            if node_data and (not path_coords or path_coords[-1] != {"lat": node_data[0], "lon": node_data[1]}):
                path_coords.append({"lat": node_data[0], "lon": node_data[1]})
    
    return json.dumps({
        "distance_km": round(distance_m / 1000, 2),
        "walk_minutes": round(distance_m / 83.33, 0),
        "num_nodes": len(path_nk),
        "path": path_coords
    })

def generate_isochrone(lat: float, lon: float, max_minutes: int = 15) -> str:
    """Generate walkable area from a point."""
    start_node = find_nearest_node(lat, lon)
    start_nk = node_mapping.get(start_node[0])
    
    if start_nk is None:
        return json.dumps({"error": "Could not find start node"})
    
    max_distance = max_minutes * 83.33  # meters at 5 km/h
    
    dijkstra = nk.distance.Dijkstra(G_nk, start_nk, True, False)
    dijkstra.run()
    
    # Get all reachable nodes
    boundary_points = []
    reachable = 0
    
    for nk_id in range(G_nk.numberOfNodes()):
        dist = dijkstra.distance(nk_id)
        if dist <= max_distance:
            reachable += 1
            # Only include boundary nodes (distance close to max)
            if dist > max_distance * 0.8:
                nx_id = reverse_mapping.get(nk_id)
                if nx_id:
                    node_data = con.execute(
                        "SELECT lat, lon FROM nodes WHERE node_id = ?", [nx_id]
                    ).fetchone()
                    if node_data:
                        boundary_points.append({
                            "lat": node_data[0],
                            "lon": node_data[1],
                            "walk_minutes": round(dist / 83.33, 1)
                        })
    
    # Sample boundary if too many points
    if len(boundary_points) > 100:
        step = len(boundary_points) // 100
        boundary_points = boundary_points[::step]
    
    return json.dumps({
        "max_minutes": max_minutes,
        "reachable_nodes": reachable,
        "boundary_points": boundary_points
    })

def geocode_place(place_name: str) -> str:
    """Get coordinates for a place name."""
    results = con.execute("""
        SELECT lat, lon, name
        FROM osm_features
        WHERE name ILIKE ?
        LIMIT 10
    """, [f"%{place_name}%"]).fetchall()
    
    if not results:
        return json.dumps({"error": f"Place not found: {place_name}"})
    
    # Return centroid of matches
    lats = [r[0] for r in results]
    lons = [r[1] for r in results]
    
    return json.dumps({
        "place": place_name,
        "lat": sum(lats) / len(lats),
        "lon": sum(lons) / len(lons),
        "matches": len(results)
    })

# ============================================================================
# Tool Executor
# ============================================================================

TOOLS = {
    "list_pois": list_pois,
    "count_pois": count_pois,
    "find_nearest_poi_with_route": find_nearest_poi_with_route,
    "calculate_route": calculate_route,
    "generate_isochrone": generate_isochrone,
    "geocode_place": geocode_place,
}

def execute_tool(tool_name: str, **kwargs) -> str:
    """Execute a tool by name with given arguments."""
    if tool_name not in TOOLS:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    
    try:
        return TOOLS[tool_name](**kwargs)
    except Exception as e:
        return json.dumps({"error": str(e)})