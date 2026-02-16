from mcp.server.fastmcp import FastMCP

import tools.discovery
import tools.data
import tools.business_report
import tools.activity_report

mcp = FastMCP("odoo-mcp")

tools.discovery.init_mcp(mcp)
tools.data.init_mcp(mcp)
tools.business_report.init_mcp(mcp)
tools.activity_report.init_mcp(mcp)

if __name__ == "__main__":
    mcp.run(transport="stdio")  # stdio pour Claude Desktop
