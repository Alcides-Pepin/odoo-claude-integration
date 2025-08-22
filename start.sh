#!/bin/bash
# Start the official MCP server with virtual environment

cd /app
source venv/bin/activate
exec python3 mcp_server.py