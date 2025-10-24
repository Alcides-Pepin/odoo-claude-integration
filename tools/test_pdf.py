"""
Test PDF tool module.

Contains a test tool to validate PDF generation with WeasyPrint
and PDF attachment to Odoo tasks via ir.attachment.
"""

import json
import datetime
import base64
from config import ODOO_URL

# The mcp instance will be injected by the main module
mcp = None


def init_mcp(mcp_instance):
    """Initialize the mcp instance for this module"""
    global mcp
    mcp = mcp_instance

    # Register the test tool
    mcp.tool()(test_pdf_attachment)


# Import odoo_execute from data module
def odoo_execute(*args, **kwargs):
    """Wrapper to call odoo_execute from tools.data"""
    from tools.data import odoo_execute as _odoo_execute
    return _odoo_execute(*args, **kwargs)


def generate_pdf_from_html(html_content: str) -> bytes:
    """
    Convert HTML to PDF using WeasyPrint.

    Args:
        html_content: HTML string to convert

    Returns:
        bytes: PDF content as bytes
    """
    try:
        from weasyprint import HTML

        # Generate PDF in memory (no temporary file needed)
        pdf_bytes = HTML(string=html_content).write_pdf()

        return pdf_bytes

    except Exception as e:
        raise Exception(f"Error generating PDF from HTML: {str(e)}")


def attach_pdf_to_task(task_id: int, pdf_bytes: bytes, filename: str) -> int:
    """
    Attach a PDF file to an Odoo task via ir.attachment.

    Args:
        task_id: ID of the task to attach the PDF to
        pdf_bytes: PDF content as bytes
        filename: Name for the attachment file

    Returns:
        int: ID of the created attachment
    """
    try:
        # Encode PDF to base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

        # Create attachment data
        attachment_data = {
            'res_model': 'project.task',
            'res_id': task_id,
            'name': filename,
            'type': 'binary',
            'datas': pdf_base64,
            'mimetype': 'application/pdf'
        }

        # Create the attachment in Odoo
        result = odoo_execute(
            model='ir.attachment',
            method='create',
            args=[attachment_data]
        )

        response = json.loads(result)
        if response.get('status') == 'success':
            attachment_id = response.get('result')
            print(f"[SUCCESS] Created attachment #{attachment_id}: {filename}")
            return attachment_id
        else:
            raise Exception(f"Attachment creation failed: {response.get('error', 'Unknown error')}")

    except Exception as e:
        raise Exception(f"Error attaching PDF to task: {str(e)}")


def test_pdf_attachment(project_id: int, task_column_id: int) -> str:
    """
    Test tool to validate PDF generation and attachment to Odoo.

    Creates a simple task with a "Hello World" PDF attachment to test:
    1. WeasyPrint PDF generation
    2. ir.attachment file upload
    3. PDF attachment to project.task

    Args:
        project_id: ID of the project where the test task will be created
        task_column_id: ID of the task column/stage where the task will be placed

    Returns:
        JSON string with test results
    """
    try:
        print(f"[INFO] Starting PDF attachment test...")

        # STEP 1: Generate simple HTML with styling
        print(f"[INFO] Generating test HTML...")
        test_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 40px;
                    background-color: #f0f0f0;
                }
                .container {
                    background-color: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                h1 {
                    color: #007bff;
                    border-bottom: 3px solid #007bff;
                    padding-bottom: 10px;
                }
                .info-box {
                    background-color: #e7f3ff;
                    border-left: 4px solid #007bff;
                    padding: 15px;
                    margin: 20px 0;
                }
                .success {
                    color: #28a745;
                    font-weight: bold;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }
                th, td {
                    border: 1px solid #dee2e6;
                    padding: 12px;
                    text-align: left;
                }
                th {
                    background-color: #f8f9fa;
                    font-weight: bold;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎉 Hello World - PDF Test</h1>

                <div class="info-box">
                    <p class="success">✓ WeasyPrint PDF generation is working!</p>
                    <p class="success">✓ HTML to PDF conversion successful!</p>
                </div>

                <h2>Test Details</h2>
                <table>
                    <tr>
                        <th>Property</th>
                        <th>Value</th>
                    </tr>
                    <tr>
                        <td>Generated at</td>
                        <td>""" + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</td>
                    </tr>
                    <tr>
                        <td>Tool</td>
                        <td>WeasyPrint</td>
                    </tr>
                    <tr>
                        <td>Purpose</td>
                        <td>Validate PDF generation and Odoo attachment</td>
                    </tr>
                    <tr>
                        <td>Status</td>
                        <td><span class="success">SUCCESS</span></td>
                    </tr>
                </table>

                <h2>Features Tested</h2>
                <ul>
                    <li>✓ HTML structure rendering</li>
                    <li>✓ CSS styling (colors, borders, shadows)</li>
                    <li>✓ Table formatting</li>
                    <li>✓ Custom fonts and typography</li>
                    <li>✓ Unicode emoji support 🎨 📄 ✨</li>
                </ul>

                <p style="margin-top: 30px; font-style: italic; color: #6c757d;">
                    If you can read this PDF, the entire chain is working correctly!
                </p>
            </div>
        </body>
        </html>
        """

        # STEP 2: Generate PDF from HTML
        print(f"[INFO] Converting HTML to PDF with WeasyPrint...")
        pdf_bytes = generate_pdf_from_html(test_html)
        pdf_size = len(pdf_bytes)
        print(f"[SUCCESS] PDF generated successfully ({pdf_size} bytes)")

        # STEP 3: Create a test task in Odoo
        print(f"[INFO] Creating test task in Odoo...")
        now = datetime.datetime.now().isoformat()
        task_name = f"[TEST PDF] {now}"
        task_description = """
        <h2>Test de génération et attachement de PDF</h2>
        <p>Cette tâche a été créée pour tester:</p>
        <ul>
            <li>✓ Génération de PDF avec WeasyPrint</li>
            <li>✓ Upload de fichier binaire via ir.attachment</li>
            <li>✓ Attachement de PDF à une tâche Odoo</li>
        </ul>
        <p><strong>Vérifiez les fichiers joints pour voir le PDF généré!</strong></p>
        """

        result = odoo_execute(
            model='project.task',
            method='create',
            args=[{
                'name': task_name,
                'project_id': project_id,
                'stage_id': task_column_id,
                'description': task_description
            }]
        )

        response = json.loads(result)
        if response.get('status') != 'success':
            raise Exception(f"Task creation failed: {response.get('error', 'Unknown error')}")

        task_id = response.get('result')
        task_url = f"{ODOO_URL}/web#id={task_id}&model=project.task&view_type=form"
        print(f"[SUCCESS] Task created with ID {task_id}")

        # STEP 4: Attach PDF to the task
        print(f"[INFO] Attaching PDF to task...")
        pdf_filename = f"test_pdf_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        attachment_id = attach_pdf_to_task(task_id, pdf_bytes, pdf_filename)

        # Return success response
        return json.dumps({
            "status": "success",
            "message": "PDF generation and attachment test completed successfully!",
            "task_id": task_id,
            "task_name": task_name,
            "task_url": task_url,
            "attachment_id": attachment_id,
            "attachment_filename": pdf_filename,
            "pdf_size_bytes": pdf_size,
            "timestamp": now,
            "tests_passed": [
                "WeasyPrint PDF generation",
                "HTML to PDF conversion with CSS styling",
                "ir.attachment creation via XML-RPC",
                "PDF attachment to project.task"
            ]
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"PDF attachment test failed: {str(e)}"
        })
