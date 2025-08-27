import json
import datetime
import os
import xmlrpc.client
import socket
import time
from mcp.server.fastmcp import FastMCP

# Get port from environment variable (Railway/Render sets this, defaults to 8001 for local dev)
PORT = int(os.environ.get("PORT", 8001))

# Odoo configuration
ODOO_URL = os.getenv('ODOO_URL')
ODOO_DB = os.getenv('ODOO_DB')
ODOO_USER = os.getenv('ODOO_USER')
ODOO_PASSWORD = os.getenv('ODOO_PASSWORD')
TIMEOUT = 30

def create_server_proxy(url):
    """Create ServerProxy with timeout"""
    transport = xmlrpc.client.Transport()
    transport.timeout = TIMEOUT
    return xmlrpc.client.ServerProxy(url, transport=transport)

# Initialize FastMCP server with host and port in constructor
mcp = FastMCP("odoo-mcp", host="0.0.0.0", port=PORT)

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
            "server": "Odoo MCP Server"
        }
        return json.dumps(response, indent=2)
    except Exception as e:
        return json.dumps({"error": f"An error occurred: {str(e)}"})

@mcp.tool()
def odoo_health_check() -> str:
    """
    Check if Odoo connection is healthy and database is accessible.
    
    Performs comprehensive tests including:
    - Connection to Odoo server
    - Authentication verification
    - Database access to core models
    - Performance measurement
    
    Returns:
        JSON string with detailed health check report
    """
    try:
        result = "Odoo Health Check Report\n" + "="*30 + "\n\n"
        
        # Test 1: Basic connection
        try:
            result += "1. Connection Test: "
            common = create_server_proxy(f'{ODOO_URL}/xmlrpc/2/common')
            version = common.version()
            result += f"✓ OK (Odoo {version.get('server_version', 'Unknown')})\n"
        except socket.timeout:
            result += f"✗ FAILED - Timeout after {TIMEOUT}s\n"
            result += f"   → Check if Odoo is running at {ODOO_URL}\n"
            return json.dumps({"status": "error", "report": result})
        except Exception as e:
            result += f"✗ FAILED - {str(e)}\n"
            return json.dumps({"status": "error", "report": result})
        
        # Test 2: Authentication
        try:
            result += "2. Authentication Test: "
            uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
            if uid:
                result += f"✓ OK (UID: {uid})\n"
            else:
                result += "✗ FAILED - Invalid credentials\n"
                return json.dumps({"status": "error", "report": result})
        except Exception as e:
            result += f"✗ FAILED - {str(e)}\n"
            return json.dumps({"status": "error", "report": result})
        
        # Test 3: Database access
        try:
            result += "3. Database Access Test: "
            models = create_server_proxy(f'{ODOO_URL}/xmlrpc/2/object')
            
            # Test core models
            core_models = ['res.partner', 'res.users', 'ir.model']
            failed_models = []
            
            for model in core_models:
                try:
                    count = models.execute_kw(
                        ODOO_DB, uid, ODOO_PASSWORD,
                        model, 'search_count',
                        [[]]
                    )
                except:
                    failed_models.append(model)
            
            if not failed_models:
                result += "✓ OK (Core models accessible)\n"
            else:
                result += f"✗ PARTIAL - Failed models: {', '.join(failed_models)}\n"
        except Exception as e:
            result += f"✗ FAILED - {str(e)}\n"
            return json.dumps({"status": "error", "report": result})
        
        # Test 4: Performance check
        try:
            result += "4. Performance Test: "
            start = time.time()
            models.execute_kw(
                ODOO_DB, uid, ODOO_PASSWORD,
                'res.partner', 'search_count',
                [[]]
            )
            elapsed = time.time() - start
            if elapsed < 1:
                result += f"✓ OK ({elapsed:.2f}s)\n"
            elif elapsed < 5:
                result += f"⚠ SLOW ({elapsed:.2f}s)\n"
            else:
                result += f"✗ VERY SLOW ({elapsed:.2f}s)\n"
        except Exception as e:
            result += f"✗ FAILED - {str(e)}\n"
        
        # Summary
        result += "\nSummary: "
        if "✗ FAILED" in result:
            result += "❌ System has issues - check failed tests above"
            status = "error"
        elif "⚠" in result:
            result += "⚠️ System operational with warnings"
            status = "warning"
        else:
            result += "✅ All systems operational"
            status = "success"
        
        return json.dumps({
            "status": status,
            "report": result,
            "timestamp": datetime.datetime.now().isoformat()
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Health check failed: {str(e)}"})

if __name__ == "__main__":
    # Run the server with SSE transport
    mcp.run(transport="sse")