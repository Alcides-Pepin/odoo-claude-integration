"""
Odoo MCP Server - Main Entry Point

A Model Context Protocol (MCP) server that provides tools for interacting with Odoo.
This is the refactored lightweight entry point that imports and initializes all modules.
"""

import json
import datetime
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse
from config import PORT
from services.odoo_client import get_odoo_connection
from tools.data import odoo_execute

# Import tool modules (they will register themselves)
import tools.discovery
import tools.data
import tools.business_report
import tools.activity_report


# Initialize FastMCP server with host and port
mcp = FastMCP("odoo-mcp", host="0.0.0.0", port=PORT)

# Initialize all tool modules by passing them the mcp instance
tools.discovery.init_mcp(mcp)
tools.data.init_mcp(mcp)
tools.business_report.init_mcp(mcp)
tools.activity_report.init_mcp(mcp)


# Test automation endpoint for GitHub Actions
# FastMCP doesn't have @mcp.get() decorator, so we access the underlying Starlette app
async def test_automation(request):
    """Test endpoint - creates a simple task every 5 min for GitHub Actions testing"""
    try:
        models, uid = get_odoo_connection()

        now = datetime.datetime.now().isoformat()
        task_data = {
            'name': f'[TEST AUTO] {now}',
            'project_id': 151,
            'stage_id': 756,
            'description': f'<p>Tâche de test générée automatiquement à {now}</p>'
        }

        result = odoo_execute(
            model='project.task',
            method='create',
            args=[task_data]
        )

        response_data = json.loads(result)
        if response_data.get('status') == 'success':
            task_id = response_data.get('result')
            return JSONResponse({
                "status": "success",
                "message": f"Test task created at {now}",
                "task_id": task_id,
                "timestamp": now
            })
        else:
            raise Exception(f"Task creation failed: {response_data.get('error')}")

    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)

# Register the route on the underlying Starlette app
from starlette.routing import Route
mcp.app.routes.append(Route("/test_automation", test_automation, methods=["GET"]))


if __name__ == "__main__":
    # Run the server
    mcp.run(transport="sse")
