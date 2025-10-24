"""
Simple HTTP API server for GitHub Actions automation endpoints.
Runs separately from the MCP server.
"""

from fastapi import FastAPI, BackgroundTasks
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

@app.get("/test_activity_report")
async def test_activity_report():
    """Test activity report generation for user 7"""
    try:
        # Calculer la semaine précédente
        today = datetime.date.today()
        last_monday = today - datetime.timedelta(days=today.weekday() + 7)
        last_sunday = last_monday + datetime.timedelta(days=6)
        start_date = last_monday.isoformat()
        end_date = last_sunday.isoformat()

        # Importer la fonction activity_report
        from tools.activity_report import odoo_activity_report

        # Générer le rapport
        result = odoo_activity_report(
            user_id=7,
            start_date=start_date,
            end_date=end_date,
            project_id=151,
            task_column_id=726
        )

        return json.loads(result)

    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)

@app.get("/test_pdf_attachment")
async def test_pdf_attachment():
    """Test PDF generation and attachment to Odoo task"""
    try:
        # Import the test tool
        from tools.test_pdf import test_pdf_attachment as _test_pdf_attachment

        # Use default test project and column
        result = _test_pdf_attachment(
            project_id=151,
            task_column_id=726
        )

        return json.loads(result)

    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)

def generate_all_activity_reports(start_date: str, end_date: str):
    """
    Background task: Generate activity reports for all users in automation_config.
    This runs asynchronously to avoid HTTP timeouts.
    """
    from automation_config import ACTIVITY_REPORTS
    from tools.activity_report import odoo_activity_report

    print(f"[INFO] Starting generation of {len(ACTIVITY_REPORTS)} activity reports...")
    print(f"[INFO] Period: {start_date} to {end_date}")

    successful = 0
    failed = 0

    for config in ACTIVITY_REPORTS:
        try:
            print(f"[INFO] Generating report for user_id={config['user_id']}...")

            result = odoo_activity_report(
                user_id=config["user_id"],
                start_date=start_date,
                end_date=end_date,
                project_id=config["project_id"],
                task_column_id=config["task_column_id"]
            )

            result_data = json.loads(result)
            if result_data.get("status") == "success":
                successful += 1
                print(f"[SUCCESS] Report generated for user_id={config['user_id']}, task_id={result_data.get('task_id')}")
            else:
                failed += 1
                print(f"[ERROR] Failed for user_id={config['user_id']}: {result_data.get('message')}")

        except Exception as e:
            failed += 1
            print(f"[ERROR] Exception for user_id={config['user_id']}: {str(e)}")

    print(f"[INFO] Activity reports batch complete: {successful} successful, {failed} failed out of {len(ACTIVITY_REPORTS)} total")

def generate_all_business_reports(start_date: str, end_date: str):
    """
    Background task: Generate business reports for all teams in automation_config.
    This runs asynchronously to avoid HTTP timeouts.
    """
    from automation_config import BUSINESS_REPORTS
    from tools.business_report import odoo_business_report

    print(f"[INFO] Starting generation of {len(BUSINESS_REPORTS)} business reports...")
    print(f"[INFO] Period: {start_date} to {end_date}")

    successful = 0
    failed = 0

    for idx, config in enumerate(BUSINESS_REPORTS, 1):
        try:
            user_ids = config["user_ids"]
            print(f"[INFO] Generating business report {idx}/{len(BUSINESS_REPORTS)} for user_ids={user_ids}...")

            result = odoo_business_report(
                user_ids=user_ids,
                start_date=start_date,
                end_date=end_date,
                project_id=config["project_id"],
                task_column_id=config["task_column_id"]
            )

            result_data = json.loads(result)
            if result_data.get("status") == "success":
                successful += 1
                print(f"[SUCCESS] Business report generated for user_ids={user_ids}, task_id={result_data.get('task_id')}")
            else:
                failed += 1
                print(f"[ERROR] Failed for user_ids={user_ids}: {result_data.get('message')}")

        except Exception as e:
            failed += 1
            print(f"[ERROR] Exception for user_ids={user_ids}: {str(e)}")

    print(f"[INFO] Business reports batch complete: {successful} successful, {failed} failed out of {len(BUSINESS_REPORTS)} total")

@app.get("/generate_weekly_activity_reports")
async def generate_weekly_activity_reports(background_tasks: BackgroundTasks):
    """
    Generate weekly activity reports for all users defined in automation_config.
    Reports are generated asynchronously in the background to avoid timeouts.
    """
    try:
        from automation_config import ACTIVITY_REPORTS

        # Calculate last week (Monday to Sunday)
        today = datetime.date.today()
        last_monday = today - datetime.timedelta(days=today.weekday() + 7)
        last_sunday = last_monday + datetime.timedelta(days=6)
        start_date = last_monday.isoformat()
        end_date = last_sunday.isoformat()

        # Launch background task
        background_tasks.add_task(generate_all_activity_reports, start_date, end_date)

        return {
            "status": "success",
            "message": "Activity reports generation started in background",
            "period": f"{start_date} to {end_date}",
            "total_users": len(ACTIVITY_REPORTS),
            "note": "Reports are being generated asynchronously. Check Odoo project 151 for results."
        }

    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)

@app.get("/auto_business_reports")
async def auto_business_reports(background_tasks: BackgroundTasks):
    """
    Generate weekly business reports for all teams defined in automation_config.
    Reports are generated asynchronously in the background to avoid timeouts.
    """
    try:
        from automation_config import BUSINESS_REPORTS

        # Calculate last week (Monday to Sunday)
        today = datetime.date.today()
        last_monday = today - datetime.timedelta(days=today.weekday() + 7)
        last_sunday = last_monday + datetime.timedelta(days=6)
        start_date = last_monday.isoformat()
        end_date = last_sunday.isoformat()

        # Launch background task
        background_tasks.add_task(generate_all_business_reports, start_date, end_date)

        return {
            "status": "success",
            "message": "Business reports generation started in background",
            "period": f"{start_date} to {end_date}",
            "total_reports": len(BUSINESS_REPORTS),
            "note": "Reports are being generated asynchronously. Check respective Odoo projects for results."
        }

    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8002))
    uvicorn.run(app, host="0.0.0.0", port=port)
