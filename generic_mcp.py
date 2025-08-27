import json
import datetime
import os
from mcp.server.fastmcp import FastMCP

# Get port from environment variable (Railway/Render sets this, defaults to 8001 for local dev)
PORT = int(os.environ.get("PORT", 8001))

# Initialize FastMCP server with host and port in constructor
mcp = FastMCP("generic-mcp", host="0.0.0.0", port=PORT)

@mcp.tool()
def ping() -> str:
    """
    Simple ping function to test if the MCP server is running.
    
    Returns:
        JSON string confirming the server is working
    """
    try:
        response = {
            "status": "ok",
            "message": "Oui le serveur marche",
            "timestamp": datetime.datetime.now().isoformat(),
            "server": "Generic MCP Server"
        }
        return json.dumps(response, indent=2)
    except Exception as e:
        return json.dumps({"error": f"An error occurred: {str(e)}"})

if __name__ == "__main__":
    # Run the server with SSE transport
    mcp.run(transport="sse")