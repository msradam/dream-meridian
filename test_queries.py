# test_queries.py - Test spatial queries with LLM reasoning

import requests
import json
import spatial_tools

# Configuration
CITY = "dhaka"
MODEL = "qwen2.5:7b"
OLLAMA_URL = "http://localhost:11434/api/chat"

# Load city data
spatial_tools.load_city(CITY)

from spatial_tools import TOOLS, execute_tool

# ============================================================================
# QUERY DEFINITIONS - Easily swappable!
# ============================================================================

# Dhaka coordinates for reference
DHAKA_COORDS = {
    'old_dhaka': (23.7104, 90.4074),
    'gulshan': (23.7925, 90.4078),
    'kamrangirchar': (23.7247, 90.3641),
    'mirpur': (23.8223, 90.3654),
    'uttara': (23.8759, 90.3795),
}

QUERIES = [
    # Healthcare access comparison
    {
        'query': f"Compare hospital access between Old Dhaka ({DHAKA_COORDS['old_dhaka'][0]}, {DHAKA_COORDS['old_dhaka'][1]}) "
                 f"and Gulshan ({DHAKA_COORDS['gulshan'][0]}, {DHAKA_COORDS['gulshan'][1]}). "
                 f"Which area has better healthcare access?",
        'description': "Healthcare Equity Analysis"
    },
    
    # Education infrastructure
    {
        'query': f"How many schools are within 1km of Uttara ({DHAKA_COORDS['uttara'][0]}, {DHAKA_COORDS['uttara'][1]})? "
                 f"List them and create a map.",
        'description': "Education Infrastructure Mapping"
    },
    
    # Emergency routing
    {
        'query': f"Find the nearest hospital to Kamrangirchar ({DHAKA_COORDS['kamrangirchar'][0]}, {DHAKA_COORDS['kamrangirchar'][1]}). "
                 f"Calculate the walking route and tell me the distance.",
        'description': "Emergency Hospital Route"
    },
    
    # Multi-service assessment
    {
        'query': f"In Mirpur ({DHAKA_COORDS['mirpur'][0]}, {DHAKA_COORDS['mirpur'][1]}), "
                 f"count hospitals, schools, and pharmacies within 2km. Which service is most lacking?",
        'description': "Multi-Service Infrastructure Assessment"
    },
    
    # Visualization example
    {
        'query': f"Find all hospitals within 2km of Old Dhaka ({DHAKA_COORDS['old_dhaka'][0]}, {DHAKA_COORDS['old_dhaka'][1]}). "
                 f"Create a map showing their locations titled 'Old Dhaka Healthcare Access'.",
        'description': "Healthcare Visualization"
    },
]

# ============================================================================
# TEST EXECUTION
# ============================================================================

def run_query(query_dict):
    """Execute a single query with LLM"""
    query = query_dict['query']
    description = query_dict['description']
    
    print("\n" + "="*70)
    print(description)
    print("="*70)
    print(f"\nQuery: {query}\n")
    print("-"*70)
    
    messages = [{"role": "user", "content": query}]
    
    for iteration in range(8):  # Allow multi-step reasoning
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": messages,
                "tools": TOOLS,
                "stream": False
            }
        )
        
        result = response.json()
        message = result.get("message", {})
        
        if "tool_calls" in message:
            print(f"🔧 Step {iteration + 1}:")
            
            for tool_call in message["tool_calls"]:
                func_name = tool_call["function"]["name"]
                func_args = tool_call["function"]["arguments"]
                if isinstance(func_args, str):
                    func_args = json.loads(func_args)
                
                # Display tool call
                if func_name == "create_map":
                    print(f"  → {func_name}('{func_args.get('title', 'N/A')}', {len(func_args.get('data_points', []))} points)")
                else:
                    args_str = ', '.join(f'{k}={v}' for k, v in list(func_args.items())[:3])
                    if len(func_args) > 3:
                        args_str += '...'
                    print(f"  → {func_name}({args_str})")
                
                # Execute tool
                tool_result = execute_tool(func_name, **func_args)
                
                # Show results
                result_data = json.loads(tool_result)
                if func_name == "create_map" and result_data.get('status') == 'success':
                    print(f"     ✓ {result_data['message']}")
                
                # Add to conversation
                messages.append(message)
                messages.append({"role": "tool", "content": tool_result})
        else:
            # Final answer
            print(f"\n📊 Analysis:")
            content = message.get('content', 'N/A')
            for line in content.split('\n'):
                if line.strip():
                    print(f"  {line}")
            print()
            break

def main():
    print("\n" + "="*70)
    print("DREAMMERIDIAN - SPATIAL INTELLIGENCE TESTING")
    print("="*70)
    print(f"\nCity: {CITY.title()}")
    print(f"Model: {MODEL}")
    print(f"Queries: {len(QUERIES)}")
    print("="*70)
    
    for i, query_dict in enumerate(QUERIES, 1):
        print(f"\n[Query {i}/{len(QUERIES)}]")
        run_query(query_dict)
        print("="*70)
    
    print("\n" + "="*70)
    print("✅ ALL QUERIES COMPLETE")
    print("="*70)
    print("\nDreamMeridian demonstrates:")
    print("  • Natural language spatial queries")
    print("  • Multi-step LLM reasoning")
    print("  • Graph-based routing (ARM-optimized)")
    print("  • Spatial database queries")
    print("  • Interactive map generation")
    print("\nCheck outputs/ folder for generated maps!")
    print("\n🌍 Offline spatial intelligence for humanitarian response")

if __name__ == "__main__":
    main()