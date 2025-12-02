#!/usr/bin/env python3
"""
./dream-meridian.py
💠 DreamMeridian - Offline Spatial Intelligence

Core query engine with CLI interface.

Usage:
    python dream-meridian.py "Find hospitals near Dhanmondi"
    python dream-meridian.py -l dhaka "Schools within 1km of Gulshan"
    python dream-meridian.py --list
    python dream-meridian.py --health
"""

import argparse
import json
import sys
import time
import requests
from dataclasses import dataclass, asdict
from pathlib import Path

import spatial_tools
import geocode_layer

# ============================================================================
# Configuration
# ============================================================================

LLAMA_URL = "http://localhost:8080/v1/chat/completions"

SYSTEM_PROMPT = """Select ONE tool. Output JSON only.

Valid poi_type values: hospital, clinic, doctors, pharmacy, police, fire_station, 
shelter, school, university, bank, atm, supermarket, marketplace, drinking_water, 
water_point, fuel, bus_station, place_of_worship

Tools:
- geocode_place(place_name) - Get coordinates for a place name
- list_pois(poi_type,lat,lon,radius_m) - List POIs with count and distances
- find_nearest_poi_with_route(poi_type,lat,lon) - Nearest POIs with walking time
- generate_isochrone(lat,lon,max_minutes) - Walkable area from point
- calculate_route(start_lat,start_lon,end_lat,end_lon) - Walking route between points"""

# ============================================================================
# Terminal Colors
# ============================================================================

class C:
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'
    CYAN = '\033[36m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    MAGENTA = '\033[35m'
    BLUE = '\033[34m'
    WHITE = '\033[97m'
    RED = '\033[31m'

# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class LLMStats:
    """Stats from llama.cpp inference."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    prompt_ms: float = 0
    completion_ms: float = 0
    tokens_per_sec: float = 0
    
    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class QueryResult:
    """Result of a spatial query."""
    tool_name: str
    tool_args: dict
    result: dict
    geocoded: dict
    query_time: float
    modified_query: str
    llm_stats: LLMStats = None
    success: bool = True
    error: str = None
    
    def to_dict(self) -> dict:
        d = asdict(self)
        if self.llm_stats:
            d['llm_stats'] = self.llm_stats.to_dict()
        return d

# ============================================================================
# Location Management
# ============================================================================

def list_locations() -> dict:
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
                    "places": config.get("places", 0)
                }
        except (json.JSONDecodeError, KeyError):
            continue
    return locations

def load_location(slug: str) -> bool:
    """Load spatial data for a location."""
    try:
        spatial_tools.load_location(slug)
        geocode_layer.load_location(slug)
        return True
    except FileNotFoundError:
        return False

def get_current_location() -> str:
    """Return currently loaded location slug."""
    return spatial_tools.current_location

# ============================================================================
# Health Checks
# ============================================================================

def check_llm_server(url: str = LLAMA_URL) -> dict:
    """Check if llama-server is responding."""
    health_url = url.replace('/v1/chat/completions', '/health')
    try:
        r = requests.get(health_url, timeout=2)
        return {"online": r.status_code == 200, "url": url}
    except requests.exceptions.RequestException:
        return {"online": False, "url": url}

def health_check() -> dict:
    """Full system health check."""
    locations = list_locations()
    llm = check_llm_server()
    current = get_current_location()
    
    return {
        "llm_server": llm,
        "locations_available": len(locations),
        "locations": list(locations.keys()),
        "current_location": current,
        "spatial_tools_loaded": spatial_tools.G_nk is not None,
        "database_connected": spatial_tools.con is not None
    }

# ============================================================================
# Query Processing
# ============================================================================

def query(user_query: str, location: str = None, llm_url: str = LLAMA_URL) -> QueryResult:
    """Process a natural language spatial query."""
    start_time = time.time()
    
    # Load location if specified and different
    if location and location != get_current_location():
        if not load_location(location):
            return QueryResult(
                tool_name="", tool_args={}, result={},
                geocoded={}, query_time=time.time() - start_time,
                modified_query=user_query,
                success=False, error=f"Location not found: {location}"
            )
    
    # Check if any location is loaded
    if spatial_tools.G_nk is None:
        return QueryResult(
            tool_name="", tool_args={}, result={},
            geocoded={}, query_time=time.time() - start_time,
            modified_query=user_query,
            success=False, error="No location loaded. Use load_location() first."
        )
    
    # Geocode place names in query
    try:
        modified_query, geocoded = geocode_layer.geocode_query(user_query)
    except Exception:
        modified_query, geocoded = user_query, {}
    
    # Call LLM for tool selection
    try:
        response = requests.post(llm_url, json={
            "model": "xLAM",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": modified_query}
            ]
        }, timeout=120)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        return QueryResult(
            tool_name="", tool_args={}, result={},
            geocoded=geocoded, query_time=time.time() - start_time,
            modified_query=modified_query,
            success=False, error="Cannot connect to LLM server. Is llama-server running?"
        )
    except requests.exceptions.Timeout:
        return QueryResult(
            tool_name="", tool_args={}, result={},
            geocoded=geocoded, query_time=time.time() - start_time,
            modified_query=modified_query,
            success=False, error="LLM request timed out."
        )
    
    # Parse LLM response
    llm_stats = LLMStats()
    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        tool_call = json.loads(content)
        tool_name = tool_call["name"]
        tool_args = tool_call["arguments"]
        
        # Extract llama.cpp timing stats
        if "usage" in data:
            llm_stats.prompt_tokens = data["usage"].get("prompt_tokens", 0)
            llm_stats.completion_tokens = data["usage"].get("completion_tokens", 0)
        if "timings" in data:
            llm_stats.prompt_ms = data["timings"].get("prompt_ms", 0)
            llm_stats.completion_ms = data["timings"].get("predicted_ms", 0)
            llm_stats.tokens_per_sec = data["timings"].get("predicted_per_second", 0)
    except (json.JSONDecodeError, KeyError) as e:
        return QueryResult(
            tool_name="", tool_args={}, result={"raw_response": content if 'content' in dir() else str(e)},
            geocoded=geocoded, query_time=time.time() - start_time,
            modified_query=modified_query,
            success=False, error=f"Failed to parse LLM response: {e}"
        )
    
    # Execute spatial tool
    try:
        result_json = spatial_tools.execute_tool(tool_name, **tool_args)
        result = json.loads(result_json)
    except Exception as e:
        return QueryResult(
            tool_name=tool_name, tool_args=tool_args, result={},
            geocoded=geocoded, query_time=time.time() - start_time,
            modified_query=modified_query,
            success=False, error=f"Tool execution failed: {e}"
        )
    
    return QueryResult(
        tool_name=tool_name,
        tool_args=tool_args,
        result=result,
        geocoded=geocoded,
        query_time=time.time() - start_time,
        modified_query=modified_query,
        llm_stats=llm_stats,
        success=True
    )

# ============================================================================
# CLI Formatting
# ============================================================================

def format_result_rich(result: QueryResult, location_info: dict = None) -> str:
    """Format QueryResult with rich terminal output."""
    lines = []
    
    if not result.success:
        lines.append(f"{C.RED}✗ Error: {result.error}{C.RESET}")
        return "\n".join(lines)
    
    # GEOCODING
    if result.geocoded:
        lines.append(f"{C.DIM}GEOCODING{C.RESET}")
        for place, info in result.geocoded.items():
            lines.append(f"  📍 {C.YELLOW}{place}{C.RESET} → {C.DIM}({info['lat']:.6f}, {info['lon']:.6f}){C.RESET}")
        lines.append("")
    
    # LLM TOOL CALL
    lines.append(f"{C.DIM}LLM TOOL CALL{C.RESET}")
    lines.append(f"  {C.BOLD}Tool:{C.RESET}  {C.CYAN}{result.tool_name}{C.RESET}")
    
    # Format args nicely
    args_str = json.dumps(result.tool_args, separators=(', ', ': '))
    lines.append(f"  {C.BOLD}Args:{C.RESET}  {C.DIM}{args_str}{C.RESET}")
    lines.append("")
    
    # RESULTS
    data = result.result
    lines.append(f"{C.DIM}RESULTS{C.RESET}")
    
    if "error" in data:
        lines.append(f"  {C.RED}Error: {data['error']}{C.RESET}")
    
    elif result.tool_name == "list_pois":
        poi_type = data.get('poi_type', 'POI')
        count = data.get('count', 0)
        radius = result.tool_args.get('radius_m', 1000)
        lines.append(f"  Found {C.BOLD}{C.GREEN}{count}{C.RESET} {poi_type}(s) within {C.CYAN}{radius}m{C.RESET}")
        pois = data.get("pois", [])
        for poi in pois[:6]:
            name = poi.get("name", "Unnamed")
            dist = poi.get("distance_m", 0)
            lines.append(f"    • {name} {C.DIM}({dist:.0f}m){C.RESET}")
        if len(pois) > 6:
            lines.append(f"    {C.DIM}... and {len(pois) - 6} more{C.RESET}")
    
    elif result.tool_name == "find_nearest_poi_with_route":
        poi_type = data.get('poi_type', 'POI')
        found = data.get('found', 0)
        lines.append(f"  Nearest {poi_type}(s): {C.GREEN}{found} found{C.RESET}")
        for poi in data.get("nearest_pois", [])[:5]:
            name = poi.get("name", "Unnamed")
            walk = poi.get("walk_minutes", 0)
            dist = poi.get("distance_m", 0)
            lines.append(f"    🚶 {C.BOLD}{name}{C.RESET} — {C.CYAN}{walk:.1f} min{C.RESET} {C.DIM}({dist:.0f}m){C.RESET}")
    
    elif result.tool_name == "calculate_route":
        dist_km = data.get('distance_km', 0)
        walk_min = data.get('walk_minutes', 0)
        num_nodes = data.get('num_nodes', 0)
        lines.append(f"  📏 Distance:   {C.CYAN}{dist_km:.2f} km{C.RESET}")
        lines.append(f"  🚶 Walk time:  {C.GREEN}{walk_min:.0f} minutes{C.RESET}")
        lines.append(f"  🔗 Path nodes: {C.DIM}{num_nodes}{C.RESET}")
    
    elif result.tool_name == "generate_isochrone":
        max_min = data.get('max_minutes', 0)
        reachable = data.get('reachable_nodes', 0)
        boundary = len(data.get('boundary_points', []))
        lines.append(f"  ⏱️  Max time:       {C.CYAN}{max_min} minutes{C.RESET}")
        lines.append(f"  🔗 Reachable nodes: {C.GREEN}{reachable:,}{C.RESET}")
        lines.append(f"  📐 Boundary points: {C.DIM}{boundary}{C.RESET}")
    
    elif result.tool_name == "geocode_place":
        place = data.get('place', 'Unknown')
        lat = data.get('lat', 0)
        lon = data.get('lon', 0)
        matches = data.get('matches', 0)
        lines.append(f"  📍 {C.YELLOW}{place}{C.RESET} → ({lat:.6f}, {lon:.6f})")
        lines.append(f"  🔍 {matches} match(es)")
    
    else:
        lines.append(f"  {json.dumps(data, indent=2)}")
    
    lines.append("")
    
    # PERFORMANCE
    lines.append(f"{C.DIM}PERFORMANCE{C.RESET}")
    lines.append(f"  ⏱️  Total time:  {C.GREEN}{result.query_time:.2f}s{C.RESET}")
    
    # LLM stats from llama.cpp
    if result.llm_stats and result.llm_stats.tokens_per_sec > 0:
        stats = result.llm_stats
        lines.append(f"  🧠 LLM inference:")
        lines.append(f"     Prompt:     {C.DIM}{stats.prompt_tokens} tokens ({stats.prompt_ms:.0f}ms){C.RESET}")
        lines.append(f"     Completion: {C.DIM}{stats.completion_tokens} tokens ({stats.completion_ms:.0f}ms){C.RESET}")
        lines.append(f"     Speed:      {C.CYAN}{stats.tokens_per_sec:.1f} tok/s{C.RESET}")
    
    if location_info:
        lines.append(f"  🗺️  Graph: {C.DIM}{location_info.get('nodes', 0):,} nodes · {location_info.get('pois', 0):,} POIs{C.RESET}")
    
    return "\n".join(lines)


def format_result_simple(result: QueryResult) -> str:
    """Format QueryResult for simple terminal output."""
    lines = []
    
    if not result.success:
        return f"Error: {result.error}"
    
    lines.append(f"Tool: {result.tool_name}")
    lines.append(f"Time: {result.query_time:.2f}s")
    
    if result.geocoded:
        places = ", ".join(f"{k} ({v['lat']:.4f}, {v['lon']:.4f})" for k, v in result.geocoded.items())
        lines.append(f"Geocoded: {places}")
    
    lines.append("")
    
    data = result.result
    if "error" in data:
        lines.append(f"Error: {data['error']}")
    elif "count" in data:
        lines.append(f"{data.get('poi_type', 'POIs').title()}: {data['count']}")
    elif "nearest_pois" in data or "pois" in data:
        pois = data.get("nearest_pois") or data.get("pois", [])
        lines.append(f"Found {len(pois)} {data.get('poi_type', 'POIs')}:")
        for poi in pois[:10]:
            name = poi.get("name", "Unknown")
            if "walk_minutes" in poi:
                lines.append(f"  • {name} ({poi['walk_minutes']:.1f} min walk)")
            elif "distance_m" in poi:
                lines.append(f"  • {name} ({poi['distance_m']:.0f}m)")
            else:
                lines.append(f"  • {name}")
    elif "distance_km" in data:
        lines.append(f"Distance: {data['distance_km']:.2f} km")
        lines.append(f"Walking time: {data['walk_minutes']:.0f} min")
    elif "reachable_nodes" in data:
        lines.append(f"Reachable in {data['max_minutes']} min: {data['reachable_nodes']} nodes")
    
    return "\n".join(lines)

# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="💠 DreamMeridian - Offline Spatial Intelligence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "Find hospitals near Dhanmondi"
  %(prog)s -l dhaka "Schools within 1km of Gulshan"
  %(prog)s --location san_juan "Pharmacies near Old San Juan"
  %(prog)s --list
  %(prog)s --health
        """
    )
    
    parser.add_argument("query", nargs="?", help="Natural language spatial query")
    parser.add_argument("-l", "--location", help="Location slug (default: first available)")
    parser.add_argument("--list", action="store_true", help="List available locations")
    parser.add_argument("--health", action="store_true", help="Check system health")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output (include raw JSON)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--simple", action="store_true", help="Simple output (no colors)")
    parser.add_argument("--llm-url", default=LLAMA_URL, help="LLM server URL")
    
    args = parser.parse_args()
    
    # List locations
    if args.list:
        locations = list_locations()
        if not locations:
            print("No locations found. Run build_location.py first.")
            sys.exit(1)
        print(f"\n{C.BOLD}{C.BLUE}💠 DreamMeridian{C.RESET} — Available locations:\n")
        for slug, info in locations.items():
            print(f"  {C.CYAN}{slug}{C.RESET}: {info['name']}")
            print(f"    {C.DIM}{info['nodes']:,} nodes · {info['pois']:,} POIs · {info.get('places', 0):,} places{C.RESET}")
        print()
        sys.exit(0)
    
    # Health check
    if args.health:
        health = health_check()
        if args.json:
            print(json.dumps(health, indent=2))
        else:
            llm_status = f"{C.GREEN}✓ Online{C.RESET}" if health["llm_server"]["online"] else f"{C.RED}✗ Offline{C.RESET}"
            print(f"\n{C.BOLD}{C.BLUE}💠 DreamMeridian{C.RESET} Health Check\n")
            print(f"  LLM Server:  {llm_status}")
            print(f"  Locations:   {health['locations_available']} available")
            if health["locations"]:
                print(f"               {C.DIM}{', '.join(health['locations'])}{C.RESET}")
            print(f"  Current:     {health['current_location'] or 'None loaded'}")
            print()
        sys.exit(0)
    
    # Query
    if not args.query:
        parser.print_help()
        sys.exit(1)
    
    # Determine location
    location = args.location
    locations = list_locations()
    if not location:
        if not locations:
            print("Error: No locations found. Run build_location.py first.")
            sys.exit(1)
        location = list(locations.keys())[0]
    
    location_info = locations.get(location, {})
    
    # Execute query
    result = query(args.query, location=location, llm_url=args.llm_url)
    
    # Output
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    elif args.simple:
        print(format_result_simple(result))
    else:
        print()
        print(format_result_rich(result, location_info))
    
    if args.verbose and not args.json:
        print(f"\n{C.DIM}Raw JSON:{C.RESET}")
        print(json.dumps(result.result, indent=2))
    
    sys.exit(0 if result.success else 1)

if __name__ == "__main__":
    main()