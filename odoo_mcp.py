import json
import datetime
import os
import xmlrpc.client
import socket
import time
from typing import Any, List, Dict, Optional
from mcp.server.fastmcp import FastMCP

# Get port from environment variable (Railway/Render sets this, defaults to 8001 for local dev)
PORT = int(os.environ.get("PORT", 8001))

# Odoo configuration
ODOO_URL = os.getenv('ODOO_URL')
ODOO_DB = os.getenv('ODOO_DB')
ODOO_USER = os.getenv('ODOO_USER')
ODOO_PASSWORD = os.getenv('ODOO_PASSWORD')
TIMEOUT = 30

# Security blacklist - operations that should never be allowed
SECURITY_BLACKLIST = {
    ('res.users', 'unlink'),  # Never delete users
    ('ir.model', 'unlink'),   # Never delete models
    ('ir.model.fields', 'unlink'),  # Never delete fields
    ('ir.module.module', 'button_immediate_uninstall'),  # Never uninstall modules
}

def create_server_proxy(url):
    """Create ServerProxy with timeout"""
    transport = xmlrpc.client.Transport()
    transport.timeout = TIMEOUT
    return xmlrpc.client.ServerProxy(url, transport=transport)

def get_odoo_connection():
    """Establish connection to Odoo with better error handling"""
    try:
        common = create_server_proxy(f'{ODOO_URL}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
        if not uid:
            raise Exception("Authentication failed - check username/password")
        models = create_server_proxy(f'{ODOO_URL}/xmlrpc/2/object')
        return models, uid
    except socket.timeout:
        raise Exception(f"Connection timeout after {TIMEOUT} seconds - Odoo server may be down")
    except socket.error as e:
        raise Exception(f"Network error: {str(e)} - Cannot reach Odoo at {ODOO_URL}")
    except xmlrpc.client.Fault as fault:
        raise Exception(f"Odoo XML-RPC error: {fault.faultString}")
    except Exception as e:
        raise

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

@mcp.tool()
def odoo_discover_models(search_term: str = "") -> str:
    """
    Discover available Odoo models by searching in model registry.
    
    Args:
        search_term: Optional search term to filter models by name or description
    
    Returns:
        JSON string with discovered models information
    """
    try:
        models, uid = get_odoo_connection()
        domain = []
        if search_term:
            domain = ['|', ('name', 'ilike', search_term), ('info', 'ilike', search_term)]
        
        ir_models = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'ir.model', 'search_read',
            [domain],
            {'fields': ['name', 'model', 'info'], 'limit': 50, 'order': 'name'}
        )
        
        if not ir_models:
            return json.dumps({
                "status": "success",
                "message": f"No models found matching '{search_term}'",
                "models": []
            })
        
        result = {
            "status": "success",
            "total_found": len(ir_models),
            "search_term": search_term if search_term else "all models",
            "models": []
        }
        
        for model in ir_models:
            model_info = {
                "model": model['model'],
                "name": model['name'],
                "description": model.get('info', 'No description')
            }
            result["models"].append(model_info)
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Error discovering models: {str(e)}"})

@mcp.tool()
def odoo_get_model_fields(model_name: str) -> str:
    """
    Get detailed information about all fields of a specific Odoo model.
    
    Args:
        model_name: The technical name of the model (e.g., 'res.partner')
    
    Returns:
        JSON string with model fields information
    """
    try:
        models, uid = get_odoo_connection()
        
        # First check if model exists
        model_exists = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'ir.model', 'search_count',
            [[('model', '=', model_name)]]
        )
        
        if not model_exists:
            return json.dumps({
                "status": "error",
                "message": f"Model '{model_name}' not found"
            })
        
        # Get all fields for the model
        fields = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'ir.model.fields', 'search_read',
            [[('model', '=', model_name)]],
            {
                'fields': ['name', 'field_description', 'ttype', 'required', 
                          'readonly', 'relation', 'relation_field', 'help'],
                'order': 'name'
            }
        )
        
        if not fields:
            return json.dumps({
                "status": "success",
                "message": f"No fields found for model '{model_name}'",
                "model": model_name,
                "fields": []
            })
        
        result = {
            "status": "success",
            "model": model_name,
            "total_fields": len(fields),
            "fields": []
        }
        
        for field in fields:
            field_info = {
                "name": field['name'],
                "label": field.get('field_description', 'N/A'),
                "type": field['ttype'],
                "required": bool(field.get('required')),
                "readonly": bool(field.get('readonly'))
            }
            
            if field.get('relation'):
                field_info["relation"] = field['relation']
                if field.get('relation_field'):
                    field_info["relation_field"] = field['relation_field']
            
            if field.get('help'):
                field_info["help"] = field['help']
            
            result["fields"].append(field_info)
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Error getting model fields: {str(e)}"})

@mcp.tool()
def odoo_search(
    model: str, 
    domain: Optional[List[Any]] = None, 
    fields: Optional[List[str]] = None, 
    limit: int = 10,
    offset: int = 0, 
    order: Optional[str] = None
) -> str:
    """
    Search and retrieve records from any Odoo model with advanced filtering.
    
    Args:
        model: The Odoo model to search in (e.g., 'res.partner')
        domain: Odoo domain filter (e.g., [['name', 'ilike', 'john']])
        fields: List of fields to return (if None, returns all fields)
        limit: Maximum number of records to return (default: 10, max: 100)
        offset: Number of records to skip (for pagination)
        order: Sort order (e.g., 'name desc, id')
    
    Returns:
        JSON string with search results
    """
    try:
        models, uid = get_odoo_connection()
        
        # Validate and set defaults
        if domain is None:
            domain = []
        if limit > 100:
            limit = 100  # Cap at 100 for performance
        
        # First, check if the model exists
        model_exists = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'ir.model', 'search_count',
            [[('model', '=', model)]]
        )
        
        if not model_exists:
            return json.dumps({
                "status": "error",
                "message": f"Model '{model}' not found"
            })
        
        # Prepare search parameters
        search_params = {
            'limit': limit,
            'offset': offset
        }
        
        if fields:
            search_params['fields'] = fields
        
        if order:
            search_params['order'] = order
        
        # Execute search
        records = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            model, 'search_read',
            [domain],
            search_params
        )
        
        # Get total count for pagination info
        total_count = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            model, 'search_count',
            [domain]
        )
        
        result = {
            "status": "success",
            "model": model,
            "total_count": total_count,
            "returned_count": len(records),
            "offset": offset,
            "limit": limit,
            "domain": domain,
            "records": records
        }
        
        # Add pagination info if needed
        if total_count > limit + offset:
            result["has_more"] = True
            result["next_offset"] = offset + limit
        else:
            result["has_more"] = False
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Error searching: {str(e)}"})

@mcp.tool()
def odoo_execute(
    model: str, 
    method: str, 
    args: Optional[List[Any]] = None, 
    kwargs: Optional[Dict[str, Any]] = None
) -> str:
    """
    Execute any method on an Odoo model. This is a powerful generic wrapper.
    
    Args:
        model: The Odoo model name (e.g., 'res.partner')
        method: The method to execute (e.g., 'create', 'write', 'search')
        args: List of positional arguments for the method
        kwargs: Dictionary of keyword arguments for the method
    
    Returns:
        JSON string with execution results
    """
    try:
        # Security check
        if (model, method) in SECURITY_BLACKLIST:
            return json.dumps({
                "status": "error",
                "message": f"Operation '{method}' on model '{model}' is not allowed for security reasons"
            })
        
        # Validate dangerous operations
        if method in ['unlink', 'button_immediate_uninstall'] and model not in ['sale.order', 'purchase.order', 'stock.picking']:
            return json.dumps({
                "status": "warning",
                "message": f"Method '{method}' is restricted. Please use with caution."
            })
        
        models, uid = get_odoo_connection()
        
        # Default args and kwargs if not provided
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        
        result = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            model, method,
            args,
            kwargs
        )
        
        return json.dumps({
            "status": "success",
            "model": model,
            "method": method,
            "result": result,
            "timestamp": datetime.datetime.now().isoformat()
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Error executing method: {str(e)}"})

if __name__ == "__main__":
    # Run the server with SSE transport
    mcp.run(transport="sse")