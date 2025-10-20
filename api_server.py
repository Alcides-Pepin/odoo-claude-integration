"""
Simple HTTP API server for GitHub Actions automation endpoints.
Runs separately from the MCP server.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import datetime
import json
import os

# Import des fonctions Odoo
from services.odoo_client import get_odoo_connection
from tools.data import odoo_execute

app = FastAPI(title="Odoo MCP Automation API")

@app.get("/")
async def root():
    return {"status": "ok", "message": "Odoo MCP Automation API"}

@app.get("/test_automation")
async def test_automation():
    """Test endpoint - creates a simple task for GitHub Actions testing"""
    try:
        models, uid = get_odoo_connection()

        now = datetime.datetime.now().isoformat()
        task_data = {
            'name': f'[TEST AUTO] {now}',
            'project_id': 151,
            'stage_id': 726,
            'description': f'<p>Tâche de test générée automatiquement à {now}</p>',
            'user_ids': [(4, 7)]  # Assigner à user_id 7
        }

        result = odoo_execute(
            model='project.task',
            method='create',
            args=[task_data]
        )

        response_data = json.loads(result)
        if response_data.get('status') == 'success':
            return {
                "status": "success",
                "message": f"Test task created at {now}",
                "task_id": response_data.get('result'),
                "timestamp": now
            }
        else:
            raise Exception(f"Task creation failed: {response_data.get('error')}")

    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8002))
    uvicorn.run(app, host="0.0.0.0", port=port)
