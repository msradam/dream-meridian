# spatial_tools_optimized.py - Optimized tool descriptions for better semantic separation

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
# GEOCODING
# ============================================================================

def geocode_place(place_name: str, category: str = None, max_results: int = 5) -> str:
    """Convert place name to coordinates using local OSM data"""
    con = get_db()
    
    # Build query based on whether category is specified
    if category:
        query = """
            SELECT name, category, amenity, shop, tourism, leisure, healthcare, lat, lon
            FROM osm_features
            WHERE name LIKE ? AND category = ?
            LIMIT ?
        """
        params = [f'%{place_name}%', category, max_results]
    else:
        query = """
            SELECT name, category, amenity, shop, tourism, leisure, healthcare, lat, lon
            FROM osm_features
            WHERE name LIKE ?
            LIMIT ?
        """
        params = [f'%{place_name}%', max_results]
    
    results = con.execute(query, params).fetchall()
    con.close()
    
    if not results:
        return json.dumps({
            'status': 'not_found',
            'query': place_name,
            'message': 'No matching places found'
        })
    
    places = []
    for r in results:
        place_type = r[2] or r[3] or r[4] or r[5] or r[6]  # First non-null type
        places.append({
            'name': r[0],
            'category': r[1],
            'type': place_type,
            'lat': r[7],
            'lon': r[8]
        })
    
    return json.dumps({
        'status': 'success',
        'query': place_name,
        'results': places,
        'count': len(places)
    })

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
            "walk_minutes": round(distance_m / 83.33, 1),
            "num_nodes": len(path),
            "path": path_coords
        })
        
    except Exception as e:
        return json.dumps({"error": str(e)})

def generate_isochrone(start_lat: float, start_lon: float, max_minutes: int, 
                       include_pois: bool = False, poi_types: list = None) -> str:
    """Calculate all locations reachable within time budget from starting point"""
    try:
        # Walking speed: 5 km/h = 83.33 m/min
        max_distance_m = max_minutes * 83.33
        
        start_node = find_nearest_node(start_lat, start_lon)
        
        # Run single-source shortest path
        dijkstra = nk.distance.Dijkstra(G_nk, source=start_node, storePaths=False)
        dijkstra.run()
        
        distances = dijkstra.getDistances()
        
        # Find all reachable nodes
        reachable_nodes = []
        for nk_node in range(G_nk.numberOfNodes()):
            if distances[nk_node] <= max_distance_m:
                lat, lon = get_node_coordinates(nk_node)
                if lat is not None:
                    reachable_nodes.append({
                        'lat': lat,
                        'lon': lon,
                        'distance_m': round(distances[nk_node], 1),
                        'walk_minutes': round(distances[nk_node] / 83.33, 1)
                    })
        
        result = {
            'start': {'lat': start_lat, 'lon': start_lon},
            'max_minutes': max_minutes,
            'max_distance_m': round(max_distance_m, 1),
            'reachable_nodes': len(reachable_nodes),
            'boundary_points': reachable_nodes
        }
        
        # Optionally include POIs within the reachable area
        if include_pois and poi_types:
            con = get_db()
            
            # Get bounding box of reachable area
            lats = [n['lat'] for n in reachable_nodes]
            lons = [n['lon'] for n in reachable_nodes]
            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)
            
            pois = []
            for poi_type in poi_types:
                poi_results = con.execute("""
                    SELECT name, lat, lon, category, amenity
                    FROM osm_features
                    WHERE category = 'amenity' AND amenity = ?
                    AND lat BETWEEN ? AND ?
                    AND lon BETWEEN ? AND ?
                    AND name IS NOT NULL
                """, [poi_type, min_lat, max_lat, min_lon, max_lon]).fetchall()
                
                for p in poi_results:
                    pois.append({
                        'name': p[0],
                        'lat': p[1],
                        'lon': p[2],
                        'type': poi_type
                    })
            
            con.close()
            result['accessible_pois'] = pois
            result['accessible_pois_count'] = len(pois)
        
        return json.dumps(result)
        
    except Exception as e:
        return json.dumps({"error": str(e)})

def find_nearest_poi_with_route(poi_type: str, start_lat: float, start_lon: float, 
                                max_results: int = 3, max_radius_m: float = 5000) -> str:
    """Find nearest POIs and calculate actual walking routes to each"""
    try:
        con = get_db()
        radius_deg = max_radius_m / 111000
        
        # Get POIs within radius
        pois = con.execute("""
            SELECT name, lat, lon,
                   ST_Distance(geom, ST_Point(?, ?)) * 111000 as straight_distance_m
            FROM osm_features
            WHERE category = 'amenity' AND amenity = ?
            AND ST_Distance(geom, ST_Point(?, ?)) < ?
            AND name IS NOT NULL
            ORDER BY straight_distance_m
            LIMIT ?
        """, [start_lon, start_lat, poi_type, start_lon, start_lat, radius_deg, max_results * 2]).fetchall()
        
        con.close()
        
        if not pois:
            return json.dumps({
                'poi_type': poi_type,
                'found': 0,
                'message': f'No {poi_type} found within {max_radius_m}m'
            })
        
        # Calculate actual walking routes
        start_node = find_nearest_node(start_lat, start_lon)
        dijkstra = nk.distance.Dijkstra(G_nk, source=start_node, storePaths=False)
        dijkstra.run()
        distances = dijkstra.getDistances()
        
        results = []
        for poi in pois:
            name, lat, lon, straight_dist = poi
            
            # Find nearest graph node to POI
            poi_node = find_nearest_node(lat, lon)
            walk_distance_m = distances[poi_node]
            
            if walk_distance_m < float('inf'):
                results.append({
                    'name': name,
                    'lat': lat,
                    'lon': lon,
                    'straight_distance_m': round(straight_dist, 1),
                    'walk_distance_m': round(walk_distance_m, 1),
                    'walk_minutes': round(walk_distance_m / 83.33, 1),
                    'detour_factor': round(walk_distance_m / straight_dist, 2) if straight_dist > 0 else 1.0
                })
            
            if len(results) >= max_results:
                break
        
        # Sort by actual walking distance
        results.sort(key=lambda x: x['walk_distance_m'])
        
        return json.dumps({
            'poi_type': poi_type,
            'start': {'lat': start_lat, 'lon': start_lon},
            'found': len(results),
            'nearest_pois': results
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
# OPTIMIZED LLM TOOL DEFINITIONS
# ============================================================================

TOOLS_OPTIMIZED = [
    {
        "type": "function",
        "function": {
            "name": "geocode_place",
            "description": "Convert place name to geographic coordinates using local database search",
            "parameters": {
                "type": "object",
                "properties": {
                    "place_name": {"type": "string", "description": "Name of place to search for"},
                    "category": {"type": "string", "description": "Optional: filter by category (amenity, shop, tourism, leisure, healthcare)"},
                    "max_results": {"type": "integer", "description": "Maximum number of results (default 5)"}
                },
                "required": ["place_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_isochrone",
            "description": "Calculate all locations reachable within walking time budget from origin point",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_lat": {"type": "number"},
                    "start_lon": {"type": "number"},
                    "max_minutes": {"type": "integer", "description": "Maximum walking time (5, 10, 15, 30, 45, or 60)"},
                    "include_pois": {"type": "boolean", "description": "Include accessible POIs (default false)"},
                    "poi_types": {"type": "array", "items": {"type": "string"}, "description": "POI types to find if include_pois=true"}
                },
                "required": ["start_lat", "start_lon", "max_minutes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_nearest_poi_with_route",
            "description": "Find nearest POIs with actual walking distances, not straight-line distance",
            "parameters": {
                "type": "object",
                "properties": {
                    "poi_type": {"type": "string"},
                    "start_lat": {"type": "number"},
                    "start_lon": {"type": "number"},
                    "max_results": {"type": "integer", "description": "Number of nearest POIs (default 3)"},
                    "max_radius_m": {"type": "number", "description": "Maximum search radius in meters (default 5000)"}
                },
                "required": ["poi_type", "start_lat", "start_lon"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "count_pois",
            "description": "Count quantity of a single POI category within radius",
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
            "description": "Retrieve names and locations of specific POIs with distances",
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
            "description": "Compute pedestrian path distance between two geographic coordinates",
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
            "description": "Batch comparison: count several different POI categories simultaneously for cross-category analysis",
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
            "description": "Generate interactive visualization after POI data collection",
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

# Keep original TOOLS for backward compatibility
TOOLS = [tool for tool in TOOLS_OPTIMIZED]  # For now, just use optimized versions

# ============================================================================
# TOOL EXECUTION
# ============================================================================

def execute_tool(tool_name: str, **kwargs) -> str:
    """Execute a tool by name"""
    if tool_name == "geocode_place":
        return geocode_place(**kwargs)
    elif tool_name == "generate_isochrone":
        return generate_isochrone(**kwargs)
    elif tool_name == "find_nearest_poi_with_route":
        return find_nearest_poi_with_route(**kwargs)
    elif tool_name == "count_pois":
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
