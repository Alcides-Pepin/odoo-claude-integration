"""
Odoo MCP Server - Main Entry Point

A Model Context Protocol (MCP) server that provides tools for interacting with Odoo.
This is the refactored lightweight entry point that imports and initializes all modules.
"""

from mcp.server.fastmcp import FastMCP
from config import PORT

# Import tool modules (they will register themselves)
import tools.discovery
import tools.data
import tools.business_report
import tools.activity_report
import tools.test_pdf


# Initialize FastMCP server with host and port
mcp = FastMCP("odoo-mcp", host="0.0.0.0", port=PORT)

# Initialize all tool modules by passing them the mcp instance
tools.discovery.init_mcp(mcp)
tools.data.init_mcp(mcp)
tools.business_report.init_mcp(mcp)
tools.activity_report.init_mcp(mcp)
tools.test_pdf.init_mcp(mcp)


if __name__ == "__main__":
    # Run the server
    mcp.run(transport="sse")
