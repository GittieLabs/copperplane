import sys
import json
import time

def mock_generate_component(query):
    """
    Mock function to simulate generating a KiCad component.
    Sleeps for 1.5 seconds to simulate API/Processing delay.
    """
    time.sleep(1.5)
    return {
        "status": "success",
        "symbol_created": f"{query.upper()}_symbol.kicad_sym",
        "footprint_created": f"{query.upper()}_footprint.kicad_mod",
        "message": f"Successfully generated {query} and injected it into active KiCad schematic."
    }

# Route Registry mapping string methods to Python functions
ROUTES = {
    "kicad.generate_component": mock_generate_component
}

def handle_request(line: str) -> str:
    """
    Parses a single JSON-RPC line, executes the routed function, 
    and returns a JSON-RPC formatted response string.
    """
    try:
        request = json.loads(line)
    except json.JSONDecodeError:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": "Parse error"},
            "id": None
        })

    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    # Validate Request Format
    if not method:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": "Invalid Request: Missing 'method'"},
            "id": req_id
        })

    # Validate Route Exists
    if method not in ROUTES:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": f"Method not found: {method}"},
            "id": req_id
        })

    # Execute Route Handler
    try:
        # Dynamically unpack params dictionary as kwargs
        if isinstance(params, dict):
            result = ROUTES[method](**params)
        else:
            result = ROUTES[method]()
            
        return json.dumps({
            "jsonrpc": "2.0",
            "result": result,
            "id": req_id
        })
        
    except Exception as e:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32000, "message": f"Server error: {str(e)}"},
            "id": req_id
        })

def main():
    """
    The infinite event loop listening to standard input.
    """
    for line in sys.stdin:
        if not line.strip():
            continue
            
        response = handle_request(line.strip())
        sys.stdout.write(response + '\n')
        sys.stdout.flush()  # CRITICAL: Ensures Tauri receives the payload immediately

if __name__ == '__main__':
    main()