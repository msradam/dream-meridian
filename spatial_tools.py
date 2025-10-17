# spatial_tools.py - Core spatial intelligence toolkit

import json
import duckdb
import networkit as nk
import os

# ============================================================================
# GLOBAL STATE
# ============================================================================

CITY = None
G_nk = None
NX_TO_NK = None
NK_TO_NX = None
DB_PATH = None

def load_city(city_name="dhaka"):
    """Load graph and database for a specific city"""
    global CITY, G_nk, NX_TO_NK, NK_TO_NX, DB_PATH
    
    CITY = city_name
    DB_PATH = f'data/{city_name}.duckdb'
    
    print(f"Loading {city_name.title()}...")
    
    # Load NetworKit graph
    graph_path = f"data/{city_name}.nkb"
    if not os.path.exists(graph_path):
        raise FileNotFoundError(f"Graph not found: {graph_path}. Run build_location.py first.")
    
    G_nk = nk.graphio.readGraph(graph_path, nk.Format.NetworkitBinary)
    
    # Load node mappings
    mapping_path = f'data/{city_name}_mappings.json'
    with open(mapping_path, 'r') as f:
        mappings = json.load(f)
        NX_TO_NK = {int(k): v for k, v in mappings['nx_to_nk'].items()}
        NK_TO_NX = {int(k): v for k, v in mappings['nk_to_nx'].items()}
    
    print(f"✓ Loaded {G_nk.numberOfNodes():,} nodes, {G_nk.numberOfEdges():,} edges\n")

def get_db():
    """Get DuckDB connection"""
    con = duckdb.connect(DB_PATH, read_only=True)
    con.load_extension("spatial")
    return con

# ============================================================================
# ROUTING TOOLS
# ============================================================================

def find_nearest_node(lat: float, lon: float) -> int:
    """Find nearest graph node to coordinates"""
    con = get_db()
    result = con.execute("""
        SELECT node_id
        FROM nodes
        ORDER BY ST_Distance(geom, ST_Point(?, ?))
        LIMIT 1
    """, [lon, lat]).fetchone()
    con.close()
    
    osm_node_id = result[0]
    return NX_TO_NK[osm_node_id]

def get_node_coordinates(nk_node: int) -> tuple:
    """Get lat/lon for a NetworKit node"""
    osm_node = NK_TO_NX[nk_node]
    con = get_db()
    coords = con.execute(
        "SELECT lat, lon FROM nodes WHERE node_id = ?", 
        [osm_node]
    ).fetchone()
    con.close()
    return coords if coords else (None, None)

def calculate_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> str:
    """Calculate walking route between two points"""
    try:
        start_node = find_nearest_node(start_lat, start_lon)
        end_node = find_nearest_node(end_lat, end_lon)
        
        dijkstra = nk.distance.Dijkstra(G_nk, source=start_node, 
                                        storePaths=True, target=end_node)
        dijkstra.run()
        
        distances = dijkstra.getDistances()
        
        if distances[end_node] >= float('inf'):
            return json.dumps({"error": "No route found"})
        
        path = dijkstra.getPath(end_node)
        distance_m = distances[end_node]
        
        # Convert path to coordinates
        path_coords = []
        for nk_node in path:
            lat, lon = get_node_coordinates(nk_node)
            if lat is not None:
                path_coords.append({"lat": lat, "lon": lon})
        
        return json.dumps({
            "distance_m": round(distance_m, 1),
            "distance_km": round(distance_m / 1000, 2),
            "num_nodes": len(path),
            "path": path_coords
        })
        
    except Exception as e:
        return json.dumps({"error": str(e)})

# ============================================================================
# POI QUERY TOOLS
# ============================================================================

def count_pois(poi_type: str, lat: float, lon: float, radius_m: float = 1000) -> str:
    """Count POIs within radius"""
    con = get_db()
    radius_deg = radius_m / 111000
    
    count = con.execute("""
        SELECT COUNT(*)
        FROM osm_features
        WHERE category = 'amenity' AND amenity = ?
        AND ST_Distance(geom, ST_Point(?, ?)) < ?
    """, [poi_type, lon, lat, radius_deg]).fetchone()[0]
    
    con.close()
    
    return json.dumps({
        'poi_type': poi_type,
        'count': count,
        'radius_m': radius_m,
        'location': {'lat': lat, 'lon': lon}
    })

def list_pois(poi_type: str, lat: float, lon: float, radius_m: float = 1000, limit: int = 20) -> str:
    """List POIs with distances"""
    con = get_db()
    radius_deg = radius_m / 111000
    
    pois = con.execute("""
        SELECT name, lat, lon,
               ST_Distance(geom, ST_Point(?, ?)) * 111000 as distance_m
        FROM osm_features
        WHERE category = 'amenity' AND amenity = ?
        AND ST_Distance(geom, ST_Point(?, ?)) < ?
        AND name IS NOT NULL
        ORDER BY distance_m
        LIMIT ?
    """, [lon, lat, poi_type, lon, lat, radius_deg, limit]).fetchall()
    
    con.close()
    
    results = [{
        'name': p[0],
        'lat': p[1],
        'lon': p[2],
        'distance_m': round(p[3], 1),
        'type': poi_type
    } for p in pois]
    
    return json.dumps({
        'poi_type': poi_type,
        'count': len(results),
        'pois': results
    })

def count_pois_multiple_types(poi_types: list, lat: float, lon: float, radius_m: float = 1000) -> str:
    """Count multiple POI types at once"""
    con = get_db()
    radius_deg = radius_m / 111000
    
    results = {}
    for poi_type in poi_types:
        count = con.execute("""
            SELECT COUNT(*)
            FROM osm_features
            WHERE category = 'amenity' AND amenity = ?
            AND ST_Distance(geom, ST_Point(?, ?)) < ?
        """, [poi_type, lon, lat, radius_deg]).fetchone()[0]
        
        results[poi_type] = count
    
    con.close()
    
    return json.dumps({
        'location': {'lat': lat, 'lon': lon},
        'radius_m': radius_m,
        'counts': results
    })

# ============================================================================
# VISUALIZATION
# ============================================================================

def create_map(data_points: list, title: str = "DreamMeridian Analysis", 
               center_lat: float = None, center_lon: float = None) -> str:
    """Create interactive kepler.gl map"""
    try:
        import pandas as pd
        from keplergl import KeplerGl
        
        if not data_points:
            return json.dumps({'error': 'No data points provided'})
        
        df = pd.DataFrame(data_points)
        
        if center_lat is None:
            center_lat = df['lat'].mean()
        if center_lon is None:
            center_lon = df['lon'].mean()
        
        map_config = {
            'version': 'v1',
            'config': {
                'mapState': {
                    'latitude': center_lat,
                    'longitude': center_lon,
                    'zoom': 13
                }
            }
        }
        
        map_1 = KeplerGl(height=800, config=map_config)
        map_1.add_data(data=df, name=title)
        
        os.makedirs('outputs', exist_ok=True)
        
        timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_')).rstrip()
        filename = f"outputs/{safe_title.replace(' ', '_')}_{timestamp}.html"
        
        map_1.save_to_html(file_name=filename)
        
        return json.dumps({
            'status': 'success',
            'filepath': filename,
            'num_points': len(data_points),
            'message': f'Map saved to {filename}'
        })
        
    except ImportError:
        return json.dumps({'error': 'Run: pip install keplergl pandas'})
    except Exception as e:
        return json.dumps({'error': str(e)})

# ============================================================================
# LLM TOOL DEFINITIONS
# ============================================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "count_pois",
            "description": "Count POIs (hospitals, schools, pharmacies, restaurants, cafes, banks, libraries) within radius",
            "parameters": {
                "type": "object",
                "properties": {
                    "poi_type": {"type": "string"},
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                    "radius_m": {"type": "number", "description": "Radius in meters (default 1000)"}
                },
                "required": ["poi_type", "lat", "lon"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_pois",
            "description": "List POIs with names and distances. Use for detailed POI information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "poi_type": {"type": "string"},
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                    "radius_m": {"type": "number"},
                    "limit": {"type": "integer", "description": "Max results (default 20)"}
                },
                "required": ["poi_type", "lat", "lon"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_route",
            "description": "Calculate walking route distance between two locations",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_lat": {"type": "number"},
                    "start_lon": {"type": "number"},
                    "end_lat": {"type": "number"},
                    "end_lon": {"type": "number"}
                },
                "required": ["start_lat", "start_lon", "end_lat", "end_lon"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "count_pois_multiple_types",
            "description": "Count multiple POI types at once for efficiency",
            "parameters": {
                "type": "object",
                "properties": {
                    "poi_types": {"type": "array", "items": {"type": "string"}},
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                    "radius_m": {"type": "number"}
                },
                "required": ["poi_types", "lat", "lon"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_map",
            "description": "Create interactive map visualization. Use AFTER gathering POI data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_points": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "lat": {"type": "number"},
                                "lon": {"type": "number"},
                                "name": {"type": "string"},
                                "type": {"type": "string"}
                            }
                        }
                    },
                    "title": {"type": "string"},
                    "center_lat": {"type": "number"},
                    "center_lon": {"type": "number"}
                },
                "required": ["data_points", "title"]
            }
        }
    }
]

# ============================================================================
# TOOL EXECUTION
# ============================================================================

def execute_tool(tool_name: str, **kwargs) -> str:
    """Execute a tool by name"""
    if tool_name == "count_pois":
        return count_pois(**kwargs)
    elif tool_name == "list_pois":
        return list_pois(**kwargs)
    elif tool_name == "calculate_route":
        return calculate_route(**kwargs)
    elif tool_name == "count_pois_multiple_types":
        return count_pois_multiple_types(**kwargs)
    elif tool_name == "create_map":
        return create_map(**kwargs)
    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})