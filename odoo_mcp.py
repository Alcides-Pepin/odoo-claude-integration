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

@mcp.tool()
def odoo_business_report(
    user_id: int,
    start_date: str, 
    end_date: str,
    project_id: int,
    task_column_id: int
) -> str:
    """
    Generate a comprehensive business report for a user over a specified period.
    Collects revenue, metrics, and top clients data from Odoo and creates a task with the report.
    
    Args:
        user_id: ID of the Odoo user/salesperson to generate report for
        start_date: Start date in ISO format (YYYY-MM-DD)
        end_date: End date in ISO format (YYYY-MM-DD)
        project_id: ID of the project where the report task will be created
        task_column_id: ID of the task column/stage where the report will be placed
    
    Returns:
        JSON string with the complete business report data
    """
    try:
        # Validate date format
        try:
            datetime.datetime.fromisoformat(start_date)
            datetime.datetime.fromisoformat(end_date)
        except ValueError:
            return json.dumps({
                "status": "error",
                "message": "Invalid date format. Use YYYY-MM-DD format."
            })
        
        # Validate that start_date is before end_date
        if start_date >= end_date:
            return json.dumps({
                "status": "error", 
                "message": "start_date must be before end_date"
            })
        
        # Test Odoo connection first
        models, uid = get_odoo_connection()
        
        # Verify user exists
        user_check = odoo_search(
            model='res.users',
            domain=[['id', '=', user_id]],
            fields=['name'],
            limit=1
        )
        user_response = json.loads(user_check)
        if not (user_response.get('status') == 'success' and user_response.get('records')):
            return json.dumps({
                "status": "error",
                "message": f"User with ID {user_id} not found"
            })
        
        user_name = user_response['records'][0]['name']
        
        # Collect all report data
        report_data = {
            "user_info": {
                "user_id": user_id,
                "user_name": user_name,
                "start_date": start_date,
                "end_date": end_date
            },
            "revenue_data": collect_revenue_data(start_date, end_date, user_id),
            "metrics_data": collect_metrics_data(start_date, end_date, user_id),
            "top_clients_data": collect_top_clients_data(user_id)
        }
        
        # Create task with formatted report
        task_id = create_report_task(report_data, project_id, task_column_id)
        
        return json.dumps({
            "status": "success",
            "message": f"Business report generated successfully for {user_name}",
            "period": f"{start_date} to {end_date}",
            "task_id": task_id,
            "task_name": f"Rapport d'activité - {user_name} ({start_date} au {end_date})",
            "report_data": report_data,
            "timestamp": datetime.datetime.now().isoformat()
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Error generating business report: {str(e)}"
        })

# Business report helper functions

# Hard-coded IDs - update if CRM stages or categories change
STAGE_IDS = {
    "rdv_degustation": 2,
    "passer_voir": 6
}

CATEGORY_IDS = {
    "recommandation": 320,
    "top_1": 776,
    "top_2": 777,
    "top_3": 767,
    "top_4": 779,
    "top_5": 780,
    "tip_top": 781
}

def get_company_name(company_id: int):
    """
    Get company name by ID for dynamic labeling
    
    Args:
        company_id: ID of the company
    
    Returns:
        Company name or fallback string
    """
    try:
        result = odoo_search(
            model='res.company',
            domain=[['id', '=', company_id]],
            fields=['name'],
            limit=1
        )
        
        response = json.loads(result)
        if response.get('status') == 'success' and response.get('records'):
            # Clean name for use as key (remove accents, spaces, etc.)
            name = response['records'][0]['name']
            return name.lower().replace('é', 'e').replace(' ', '_')
        return f"company_{company_id}"
        
    except Exception as e:
        return f"company_{company_id}"

def get_company_revenue(company_id: int, start_date: str, end_date: str, user_id: int, with_opportunities=None):
    """
    Generic function to get company revenue based on opportunities filter
    
    Args:
        company_id: ID of the company
        start_date: Start date in ISO format
        end_date: End date in ISO format  
        user_id: ID of the user/salesperson
        with_opportunities: True for invoices WITH opportunities, False for WITHOUT, None for ALL
    
    Returns:
        Total revenue amount
    """
    try:
        # Build domain for account.move (invoices)
        domain = [
            ['company_id', '=', company_id],
            ['invoice_date', '>=', start_date],
            ['invoice_date', '<=', end_date],
            ['invoice_user_id', '=', user_id],
            ['move_type', '=', 'out_invoice'],  # Only customer invoices
            ['state', '=', 'posted']  # Only validated invoices
        ]
        
        # Add opportunities filter
        if with_opportunities is True:
            # For invoices with opportunities - check if related sale order has opportunity
            domain.append(['invoice_line_ids.sale_line_ids.order_id.opportunity_id', '!=', False])
        elif with_opportunities is False:
            # For invoices without opportunities - check if related sale order has NO opportunity
            domain.append(['invoice_line_ids.sale_line_ids.order_id.opportunity_id', '=', False])
        # If None, no opportunity filter (total)
        
        # Search invoices
        result = odoo_search(
            model='account.move',
            domain=domain,
            fields=['amount_total'],
            limit=100  # Should be enough for weekly reports
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            records = response.get('records', [])
            total_revenue = sum(record.get('amount_total', 0) for record in records)
            return total_revenue
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error calculating revenue: {str(e)}")

def collect_revenue_data(start_date: str, end_date: str, user_id: int):
    """
    Collect all revenue data for the business report using dynamic company detection
    
    Args:
        start_date: Start date in ISO format
        end_date: End date in ISO format
        user_id: ID of the user/salesperson
    
    Returns:
        Dictionary with all revenue metrics for user's companies
    """
    try:
        # Get user's company IDs
        result = odoo_search(
            model='res.users',
            domain=[['id', '=', user_id]],
            fields=['company_ids'],
            limit=1
        )
        
        response = json.loads(result)
        if not (response.get('status') == 'success' and response.get('records')):
            raise Exception(f"User {user_id} not found")
        
        company_ids = response['records'][0].get('company_ids', [])
        if not company_ids:
            raise Exception(f"User {user_id} has no associated companies")
        
        # Calculate revenue for each company the user belongs to
        revenue_data = {}
        for company_id in company_ids:
            company_key = get_company_name(company_id)
            
            revenue_data[f"ca_{company_key}_with_rdv"] = get_company_revenue(
                company_id, start_date, end_date, user_id, with_opportunities=True
            )
            revenue_data[f"ca_{company_key}_without_rdv"] = get_company_revenue(
                company_id, start_date, end_date, user_id, with_opportunities=False
            )
            revenue_data[f"ca_{company_key}_total"] = get_company_revenue(
                company_id, start_date, end_date, user_id, with_opportunities=None
            )
        
        return revenue_data
        
    except Exception as e:
        raise Exception(f"Error collecting revenue data: {str(e)}")

def get_appointments_placed(start_date: str, end_date: str, user_id: int):
    """
    Get number of appointments placed (opportunities at RDV dégustation stage)
    
    Args:
        start_date: Start date in ISO format
        end_date: End date in ISO format
        user_id: ID of the user/salesperson
    
    Returns:
        Number of appointments placed
    """
    try:
        result = odoo_search(
            model='crm.lead',
            domain=[
                ['create_date', '>=', start_date],
                ['create_date', '<=', end_date],
                ['user_id', '=', user_id],
                ['stage_id', '=', STAGE_IDS["rdv_degustation"]]
            ],
            fields=['id']
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('returned_count', 0)
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error getting appointments placed: {str(e)}")

def get_passer_voir_count(start_date: str, end_date: str, user_id: int):
    """
    Get number of 'Passer Voir' visits (opportunities at Passer Voir stage)
    
    Args:
        start_date: Start date in ISO format
        end_date: End date in ISO format
        user_id: ID of the user/salesperson
    
    Returns:
        Number of Passer Voir visits
    """
    try:
        result = odoo_search(
            model='crm.lead',
            domain=[
                ['create_date', '>=', start_date],
                ['create_date', '<=', end_date],
                ['user_id', '=', user_id],
                ['stage_id', '=', STAGE_IDS["passer_voir"]]
            ],
            fields=['id']
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('returned_count', 0)
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error getting Passer Voir count: {str(e)}")

def get_appointments_realized(start_date: str, end_date: str, user_id: int):
    """
    Get number of appointments realized (wine tastings created)
    
    Args:
        start_date: Start date in ISO format
        end_date: End date in ISO format
        user_id: ID of the user/salesperson
    
    Returns:
        Number of appointments realized
    """
    try:
        result = odoo_search(
            model='wine.tasting',
            domain=[
                ['create_date', '>=', start_date],
                ['create_date', '<=', end_date],
                ['opportunity_id.user_id', '=', user_id]
            ],
            fields=['id']
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('returned_count', 0)
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error getting appointments realized: {str(e)}")

def get_orders_count(start_date: str, end_date: str, user_id: int):
    """
    Get number of orders created (by quote date)
    
    Args:
        start_date: Start date in ISO format
        end_date: End date in ISO format
        user_id: ID of the user/salesperson
    
    Returns:
        Number of orders
    """
    try:
        result = odoo_search(
            model='sale.order',
            domain=[
                ['date_order', '>=', start_date],
                ['date_order', '<=', end_date],
                ['user_id', '=', user_id]
            ],
            fields=['id']
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('returned_count', 0)
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error getting orders count: {str(e)}")

def get_new_clients_count(start_date: str, end_date: str, user_id: int):
    """
    Get number of new clients (contacts with first order in period)
    Note: This is complex logic - simplified version for now
    
    Args:
        start_date: Start date in ISO format
        end_date: End date in ISO format
        user_id: ID of the user/salesperson
    
    Returns:
        Number of new clients
    """
    try:
        # Get all orders in period for this user
        result = odoo_search(
            model='sale.order',
            domain=[
                ['create_date', '>=', start_date],
                ['create_date', '<=', end_date],
                ['user_id', '=', user_id]
            ],
            fields=['partner_id']
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            # Get unique partner IDs from orders in this period
            partner_ids = list(set([order['partner_id'][0] for order in response.get('records', []) if order.get('partner_id')]))
            
            # For each partner, check if they have any orders before start_date
            new_clients_count = 0
            for partner_id in partner_ids:
                # Check if partner has any previous orders
                previous_orders = odoo_search(
                    model='sale.order',
                    domain=[
                        ['partner_id', '=', partner_id],
                        ['create_date', '<', start_date]
                    ],
                    fields=['id'],
                    limit=1
                )
                
                prev_response = json.loads(previous_orders)
                if prev_response.get('status') == 'success' and prev_response.get('returned_count', 0) == 0:
                    new_clients_count += 1
            
            return new_clients_count
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error getting new clients count: {str(e)}")

def get_recommendations_count(start_date: str, end_date: str, user_id: int):
    """
    Get number of recommendations (contacts with 'Recommandation' tag)
    
    Args:
        start_date: Start date in ISO format
        end_date: End date in ISO format
        user_id: ID of the user/salesperson
    
    Returns:
        Number of recommendations
    """
    try:
        result = odoo_search(
            model='res.partner',
            domain=[
                ['user_id', '=', user_id],
                ['create_date', '>=', start_date],
                ['create_date', '<=', end_date],
                ['category_id', 'in', [CATEGORY_IDS["recommandation"]]]
            ],
            fields=['id']
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('returned_count', 0)
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error getting recommendations count: {str(e)}")

def get_deliveries_count(start_date: str, end_date: str, user_id: int):
    """
    Get number of deliveries completed
    
    Args:
        start_date: Start date in ISO format
        end_date: End date in ISO format
        user_id: ID of the user/salesperson
    
    Returns:
        Number of deliveries
    """
    try:
        result = odoo_search(
            model='stock.picking',
            domain=[
                ['date_done', '>=', start_date],
                ['date_done', '<=', end_date],
                ['user_id', '=', user_id]
            ],
            fields=['id']
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('returned_count', 0)
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error getting deliveries count: {str(e)}")

def collect_metrics_data(start_date: str, end_date: str, user_id: int):
    """
    Collect all business metrics for the report
    
    Args:
        start_date: Start date in ISO format
        end_date: End date in ISO format
        user_id: ID of the user/salesperson
    
    Returns:
        Dictionary with all metrics
    """
    try:
        return {
            "rdv_places": get_appointments_placed(start_date, end_date, user_id),
            "passer_voir": get_passer_voir_count(start_date, end_date, user_id),
            "rdv_realises": get_appointments_realized(start_date, end_date, user_id),
            "nombre_commandes": get_orders_count(start_date, end_date, user_id),
            "nouveaux_clients": get_new_clients_count(start_date, end_date, user_id),
            "recommandations": get_recommendations_count(start_date, end_date, user_id),
            "livraisons": get_deliveries_count(start_date, end_date, user_id)
        }
        
    except Exception as e:
        raise Exception(f"Error collecting metrics data: {str(e)}")

def get_top_contact(user_id: int, category_id: int):
    """
    Get first contact with specific top category for a user
    
    Args:
        user_id: ID of the user/salesperson
        category_id: ID of the category tag
    
    Returns:
        Contact name or None if not found
    """
    try:
        result = odoo_search(
            model='res.partner',
            domain=[
                ['user_id', '=', user_id],
                ['category_id', 'in', [category_id]]
            ],
            fields=['name'],
            limit=1
        )
        
        response = json.loads(result)
        if response.get('status') == 'success' and response.get('records'):
            return response['records'][0]['name']
        return None
        
    except Exception as e:
        raise Exception(f"Error getting top contact: {str(e)}")

def get_tip_top_contacts(user_id: int):
    """
    Get all contacts with 'Tip Top' category for a user
    
    Args:
        user_id: ID of the user/salesperson
    
    Returns:
        List of contact names
    """
    try:
        result = odoo_search(
            model='res.partner',
            domain=[
                ['user_id', '=', user_id],
                ['category_id', 'in', [CATEGORY_IDS["tip_top"]]]
            ],
            fields=['name'],
            limit=50  # Reasonable limit for tip top contacts
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            return [contact['name'] for contact in response.get('records', [])]
        return []
        
    except Exception as e:
        raise Exception(f"Error getting tip top contacts: {str(e)}")

def collect_top_clients_data(user_id: int):
    """
    Collect all top clients data for the report
    
    Args:
        user_id: ID of the user/salesperson
    
    Returns:
        Dictionary with all top clients
    """
    try:
        return {
            "top_1": get_top_contact(user_id, CATEGORY_IDS["top_1"]),
            "top_2": get_top_contact(user_id, CATEGORY_IDS["top_2"]),
            "top_3": get_top_contact(user_id, CATEGORY_IDS["top_3"]),
            "top_4": get_top_contact(user_id, CATEGORY_IDS["top_4"]),
            "top_5": get_top_contact(user_id, CATEGORY_IDS["top_5"]),
            "tip_top": get_tip_top_contacts(user_id)
        }
        
    except Exception as e:
        raise Exception(f"Error collecting top clients data: {str(e)}")

def format_currency(amount):
    """
    Format amount as currency
    
    Args:
        amount: Numeric amount
    
    Returns:
        Formatted string with € symbol
    """
    if amount is None or amount == 0:
        return "0 €"
    return f"{amount:,.0f} €".replace(",", " ")

def generate_report_html_table(report_data):
    """
    Generate HTML table for business report in Odoo WYSIWYG format
    
    Args:
        report_data: Complete report data dictionary
    
    Returns:
        HTML string with formatted table
    """
    try:
        user_info = report_data.get('user_info', {})
        revenue_data = report_data.get('revenue_data', {})
        metrics_data = report_data.get('metrics_data', {})
        top_clients_data = report_data.get('top_clients_data', {})
        
        html = f"""
        <div class="container">
            <h2>Rapport d'activité - {user_info.get('user_name', 'N/A')}</h2>
            <p><strong>Période:</strong> {user_info.get('start_date', 'N/A')} au {user_info.get('end_date', 'N/A')}</p>
            
            <table class="table table-bordered table-striped" style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <thead style="background-color: #f8f9fa;">
                    <tr>
                        <th style="border: 1px solid #dee2e6; padding: 12px; text-align: left; font-weight: bold;">Métrique</th>
                        <th style="border: 1px solid #dee2e6; padding: 12px; text-align: right; font-weight: bold;">Valeur</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        # Revenue section
        for key, value in revenue_data.items():
            if key.endswith('_total'):
                company_name = key.replace('ca_', '').replace('_total', '').title()
                label = f"CA {company_name} Total"
                style = "background-color: #e9ecef; font-weight: bold;"
            elif key.endswith('_with_rdv'):
                company_name = key.replace('ca_', '').replace('_with_rdv', '').title()
                label = f"CA {company_name} avec RDV"
                style = ""
            elif key.endswith('_without_rdv'):
                company_name = key.replace('ca_', '').replace('_without_rdv', '').title()
                label = f"CA {company_name} sans RDV"
                style = ""
            else:
                label = key.replace('_', ' ').title()
                style = ""
                
            html += f"""
                    <tr style="{style}">
                        <td style="border: 1px solid #dee2e6; padding: 10px;">{label}</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{format_currency(value)}</td>
                    </tr>
            """
        
        # Metrics section
        metrics_labels = {
            "rdv_places": "Rendez-vous placés",
            "passer_voir": "Passer Voir",
            "rdv_realises": "Rendez-vous réalisés", 
            "nombre_commandes": "Nombre de commandes",
            "nouveaux_clients": "Nouveaux clients",
            "recommandations": "Recommandations",
            "livraisons": "Livraisons"
        }
        
        for key, value in metrics_data.items():
            label = metrics_labels.get(key, key.replace('_', ' ').title())
            html += f"""
                    <tr>
                        <td style="border: 1px solid #dee2e6; padding: 10px;">{label}</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{value if value is not None else 0}</td>
                    </tr>
            """
        
        # Top clients section
        top_labels = {
            "top_1": "Top 1",
            "top_2": "Top 2",
            "top_3": "Top 3",
            "top_4": "Top 4", 
            "top_5": "Top 5",
            "tip_top": "Tip Top"
        }
        
        for key, value in top_clients_data.items():
            label = top_labels.get(key, key.replace('_', ' ').title())
            
            if key == "tip_top" and isinstance(value, list):
                display_value = ", ".join(value) if value else "Aucun"
            else:
                display_value = value if value else "Aucun"
                
            html += f"""
                    <tr>
                        <td style="border: 1px solid #dee2e6; padding: 10px;">{label}</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{display_value}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
        
        return html
        
    except Exception as e:
        raise Exception(f"Error generating HTML table: {str(e)}")

def create_report_task(report_data, project_id, task_column_id):
    """
    Create an Odoo task with the business report
    
    Args:
        report_data: Complete report data dictionary
        project_id: ID of the project
        task_column_id: ID of the task column/stage
    
    Returns:
        Created task ID
    """
    try:
        user_info = report_data.get('user_info', {})
        user_name = user_info.get('user_name', 'N/A')
        start_date = user_info.get('start_date', 'N/A')
        end_date = user_info.get('end_date', 'N/A')
        
        # Generate task title
        task_name = f"Rapport d'activité - {user_name} ({start_date} au {end_date})"
        
        # Generate HTML table
        html_description = generate_report_html_table(report_data)
        
        # Create task using odoo_execute
        result = odoo_execute(
            model='project.task',
            method='create',
            args=[{
                'name': task_name,
                'project_id': project_id,
                'stage_id': task_column_id,
                'description': html_description,
                'user_ids': [(4, user_info.get('user_id'))]  # Assign to the user
            }]
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            task_id = response.get('result')
            return task_id
        else:
            raise Exception(f"Task creation failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error creating report task: {str(e)}")

if __name__ == "__main__":
    # Run the server with SSE transport
    mcp.run(transport="sse")

@mcp.tool()
def odoo_activity_report(
    user_id: int,
    start_date: str, 
    end_date: str,
    project_id: int,
    task_column_id: int
) -> str:
    """
    Generate a comprehensive activity report for a user over a specified period.
    Collects activities, tasks, and projects data from Odoo and creates a task with the report.
    
    Args:
        user_id: ID of the Odoo user to generate report for
        start_date: Start date in ISO format (YYYY-MM-DD)
        end_date: End date in ISO format (YYYY-MM-DD)
        project_id: ID of the project where the report task will be created
        task_column_id: ID of the task column/stage where the report will be placed
    
    Returns:
        JSON string with the complete activity report data
    """
    try:
        # Validate date format
        try:
            datetime.datetime.fromisoformat(start_date)
            datetime.datetime.fromisoformat(end_date)
        except ValueError:
            return json.dumps({
                "status": "error",
                "message": "Invalid date format. Use YYYY-MM-DD format."
            })
        
        # Validate that start_date is before end_date
        if start_date >= end_date:
            return json.dumps({
                "status": "error", 
                "message": "start_date must be before end_date"
            })
        
        # Test Odoo connection first
        models, uid = get_odoo_connection()
        
        # Verify user exists
        user_check = odoo_search(
            model='res.users',
            domain=[['id', '=', user_id]],
            fields=['name'],
            limit=1
        )
        user_response = json.loads(user_check)
        if not (user_response.get('status') == 'success' and user_response.get('records')):
            return json.dumps({
                "status": "error",
                "message": f"User with ID {user_id} not found"
            })
        
        user_name = user_response['records'][0]['name']
        
        # Collect all report data
        report_data = {
            "user_info": {
                "user_id": user_id,
                "user_name": user_name,
                "start_date": start_date,
                "end_date": end_date
            },
            "activities_data": collect_activities_data(start_date, end_date, user_id),
            "tasks_data": collect_tasks_data(start_date, end_date, user_id),
            "projects_data": collect_projects_data(start_date, end_date, user_id)
        }
        
        # Create task with formatted report
        task_id = create_activity_report_task(report_data, project_id, task_column_id)
        
        return json.dumps({
            "status": "success",
            "message": f"Activity report generated successfully for {user_name}",
            "period": f"{start_date} to {end_date}",
            "task_id": task_id,
            "task_name": f"Rapport d'activité - {user_name} ({start_date} au {end_date})",
            "report_data": report_data,
            "timestamp": datetime.datetime.now().isoformat()
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Error generating activity report: {str(e)}"
        })

def collect_activities_data(start_date: str, end_date: str, user_id: int):
    """Collect all activities data for the report"""
    try:
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Nombres (comme avant)
        activites_realisees_count = get_activity_count([
            ['active', '=', False],
            ['state', '=', 'done'],
            ['date_done', '>=', start_date],
            ['date_done', '<=', end_date], 
            ['user_id', '=', user_id]
        ])
        
        activites_retard = get_activity_count([
            ['active', '=', True],
            ['state', '!=', 'done'],
            ['date_deadline', '<', today],
            ['user_id', '=', user_id]
        ])
        
        activites_delais = get_activity_count([
            ['active', '=', True],
            ['state', '!=', 'done'],
            ['date_deadline', '>=', today],
            ['user_id', '=', user_id]
        ])
        
        activites_cours_total = get_activity_count([
            ['active', '=', True],
            ['state', '!=', 'done'],
            ['user_id', '=', user_id]
        ])
        
        # Listes détaillées (nouveau)
        activites_realisees_details = get_completed_activities_details(start_date, end_date, user_id)
        
        return {
            "activites_realisees": activites_realisees_count,
            "activites_retard": activites_retard,
            "activites_delais": activites_delais,
            "activites_cours_total": activites_cours_total,
            "activites_realisees_details": activites_realisees_details
        }
        
    except Exception as e:
        raise Exception(f"Error collecting activities data: {str(e)}")

def collect_tasks_data(start_date: str, end_date: str, user_id: int):
    """Collect all tasks data for the report"""
    try:
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Nombres (comme avant)
        taches_realisees_count = get_task_count([
            ['user_ids', 'in', [user_id]],
            ['state', '=', '1_done'],
            ['date_last_stage_update', '>=', start_date],
            ['date_last_stage_update', '<=', end_date]
        ])
        
        taches_retard = get_task_count([
            ['user_ids', 'in', [user_id]],
            ['state', '=', '01_in_progress'],
            ['date_deadline', '!=', False],
            ['date_deadline', '<', today]
        ])
        
        taches_delais = get_task_count([
            ['user_ids', 'in', [user_id]],
            ['state', '=', '01_in_progress'],
            ['date_deadline', '!=', False],
            ['date_deadline', '>=', today]
        ])
        
        taches_sans_delais = get_task_count([
            ['user_ids', 'in', [user_id]],
            ['state', '=', '01_in_progress'],
            ['date_deadline', '=', False]
        ])
        
        taches_cours_total = get_task_count([
            ['user_ids', 'in', [user_id]],
            ['state', '=', '01_in_progress']
        ])
        
        # Listes détaillées (nouveau)
        taches_realisees_details = get_completed_tasks_details(start_date, end_date, user_id)
        
        return {
            "taches_realisees": taches_realisees_count,
            "taches_retard": taches_retard,
            "taches_delais": taches_delais,
            "taches_sans_delais": taches_sans_delais,
            "taches_cours_total": taches_cours_total,
            "taches_realisees_details": taches_realisees_details
        }
        
    except Exception as e:
        raise Exception(f"Error collecting tasks data: {str(e)}")

def collect_projects_data(start_date: str, end_date: str, user_id: int):
    """Collect all projects data for the report"""
    try:
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Nombres (comme avant)
        projets_realises_count = get_completed_projects_count(start_date, end_date, user_id)
        
        projets_retard = get_project_count([
            '|',
            ['user_id', '=', user_id],
            ['favorite_user_ids', 'in', [user_id]],
            ['last_update_status', '!=', 'done'],
            ['date', '!=', False],
            ['date', '<', today]
        ])
        
        projets_delais = get_project_count([
            '|',
            ['user_id', '=', user_id],
            ['favorite_user_ids', 'in', [user_id]],
            ['last_update_status', '!=', 'done'],
            ['date', '!=', False],
            ['date', '>=', today]
        ])
        
        projets_sans_dates = get_project_count([
            '|',
            ['user_id', '=', user_id],
            ['favorite_user_ids', 'in', [user_id]],
            ['last_update_status', '!=', 'done'],
            ['date', '=', False]
        ])
        
        projets_cours_total = get_project_count([
            '|',
            ['user_id', '=', user_id],
            ['favorite_user_ids', 'in', [user_id]],
            ['last_update_status', '!=', 'done']
        ])
        
        # Listes détaillées (nouveau)
        projets_realises_details = get_completed_projects_details(start_date, end_date, user_id)
        
        return {
            "projets_realises": projets_realises_count,
            "projets_retard": projets_retard,
            "projets_delais": projets_delais,
            "projets_sans_dates": projets_sans_dates,
            "projets_cours_total": projets_cours_total,
            "projets_realises_details": projets_realises_details
        }
        
    except Exception as e:
        raise Exception(f"Error collecting projects data: {str(e)}")

def get_completed_activities_details(start_date: str, end_date: str, user_id: int):
    """Get detailed list of completed activities with links"""
    try:
        result = odoo_search(
            model='mail.activity',
            domain=[
                ['active', '=', False],
                ['state', '=', 'done'],
                ['date_done', '>=', start_date],
                ['date_done', '<=', end_date], 
                ['user_id', '=', user_id]
            ],
            fields=['id', 'summary', 'date_done', 'res_model', 'res_id'],
            limit=50
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            activities = []
            for activity in response.get('records', []):
                activity_url = f"{ODOO_URL}/web#id={activity['id']}&model=mail.activity&view_type=form"
                activities.append({
                    'name': activity.get('summary', 'Activité sans nom'),
                    'url': activity_url,
                    'date': activity.get('date_done', '')
                })
            return activities
        return []
        
    except Exception as e:
        raise Exception(f"Error getting completed activities details: {str(e)}")

def get_completed_tasks_details(start_date: str, end_date: str, user_id: int):
    """Get detailed list of completed tasks with links"""
    try:
        result = odoo_search(
            model='project.task',
            domain=[
                ['user_ids', 'in', [user_id]],
                ['state', '=', '1_done'],
                ['date_last_stage_update', '>=', start_date],
                ['date_last_stage_update', '<=', end_date]
            ],
            fields=['id', 'name', 'date_last_stage_update', 'project_id'],
            limit=50
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            tasks = []
            for task in response.get('records', []):
                task_url = f"{ODOO_URL}/web#id={task['id']}&model=project.task&view_type=form"
                tasks.append({
                    'name': task.get('name', 'Tâche sans nom'),
                    'url': task_url,
                    'date': task.get('date_last_stage_update', ''),
                    'project': task.get('project_id', [False, 'N/A'])[1] if task.get('project_id') else 'N/A'
                })
            return tasks
        return []
        
    except Exception as e:
        raise Exception(f"Error getting completed tasks details: {str(e)}")

def get_completed_projects_details(start_date: str, end_date: str, user_id: int):
    """Get detailed list of completed projects with links"""
    try:
        # Étape 1: Chercher les project.update avec status="done" dans la période
        updates_result = odoo_search(
            model='project.update',
            domain=[
                ['status', '=', 'done'],
                ['date', '>=', start_date], 
                ['date', '<=', end_date]
            ],
            fields=['project_id', 'date'],
            limit=50
        )
        
        updates_response = json.loads(updates_result)
        if updates_response.get('status') != 'success':
            return []
        
        # Récupérer les IDs des projets avec leur date de completion
        project_updates = {}
        for update in updates_response.get('records', []):
            if update.get('project_id'):
                project_id = update['project_id'][0]
                project_updates[project_id] = update.get('date', '')
        
        if not project_updates:
            return []
        
        # Étape 2: Récupérer les détails des projets où l'utilisateur participe
        projects_result = odoo_search(
            model='project.project',
            domain=[
                ['id', 'in', list(project_updates.keys())],
                '|',
                ['user_id', '=', user_id],
                ['favorite_user_ids', 'in', [user_id]]
            ],
            fields=['id', 'name'],
            limit=50
        )
        
        projects_response = json.loads(projects_result)
        if projects_response.get('status') == 'success':
            projects = []
            for project in projects_response.get('records', []):
                project_url = f"{ODOO_URL}/web#id={project['id']}&model=project.project&view_type=kanban"
                projects.append({
                    'name': project.get('name', 'Projet sans nom'),
                    'url': project_url,
                    'date': project_updates.get(project['id'], '')
                })
            return projects
        return []
        
    except Exception as e:
        raise Exception(f"Error getting completed projects details: {str(e)}")

def get_activity_count(domain):
    """Get count of mail.activity with given domain"""
    try:
        result = odoo_search(
            model='mail.activity',
            domain=domain,
            fields=['id']
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('returned_count', 0)
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error getting activity count: {str(e)}")

def get_task_count(domain):
    """Get count of project.task with given domain"""
    try:
        result = odoo_search(
            model='project.task',
            domain=domain,
            fields=['id']
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('returned_count', 0)
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error getting task count: {str(e)}")

def get_project_count(domain):
    """Get count of project.project with given domain"""
    try:
        result = odoo_search(
            model='project.project',
            domain=domain,
            fields=['id']
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            return response.get('returned_count', 0)
        else:
            raise Exception(f"Search failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error getting project count: {str(e)}")

def get_completed_projects_count(start_date: str, end_date: str, user_id: int):
    """Get count of projects completed in period (complex logic with project.update)"""
    try:
        # Étape 1: Chercher les project.update avec status="done" dans la période
        updates_result = odoo_search(
            model='project.update',
            domain=[
                ['status', '=', 'done'],
                ['date', '>=', start_date], 
                ['date', '<=', end_date]
            ],
            fields=['project_id']
        )
        
        updates_response = json.loads(updates_result)
        if updates_response.get('status') != 'success':
            raise Exception(f"Updates search failed: {updates_response.get('error', 'Unknown error')}")
        
        # Récupérer les IDs des projets
        project_ids = []
        for update in updates_response.get('records', []):
            if update.get('project_id'):
                project_ids.append(update['project_id'][0])
        
        if not project_ids:
            return 0
        
        # Étape 2: Vérifier que l'utilisateur participe à ces projets
        completed_projects_result = odoo_search(
            model='project.project',
            domain=[
                ['id', 'in', project_ids],
                '|',
                ['user_id', '=', user_id],
                ['favorite_user_ids', 'in', [user_id]]
            ],
            fields=['id']
        )
        
        completed_response = json.loads(completed_projects_result)
        if completed_response.get('status') == 'success':
            return completed_response.get('returned_count', 0)
        else:
            raise Exception(f"Projects search failed: {completed_response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error getting completed projects count: {str(e)}")

def generate_activity_report_html_table(report_data):
    """Generate HTML table for activity report with detailed lists"""
    try:
        user_info = report_data.get('user_info', {})
        activities_data = report_data.get('activities_data', {})
        tasks_data = report_data.get('tasks_data', {})
        projects_data = report_data.get('projects_data', {})
        
        html = f"""
        <div class="container">
            <h2>Rapport d'activité - {user_info.get('user_name', 'N/A')}</h2>
            <p><strong>Période:</strong> {user_info.get('start_date', 'N/A')} au {user_info.get('end_date', 'N/A')}</p>
            
            <table class="table table-bordered table-striped" style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <thead style="background-color: #f8f9fa;">
                    <tr>
                        <th style="border: 1px solid #dee2e6; padding: 12px; text-align: left; font-weight: bold;">Métrique</th>
                        <th style="border: 1px solid #dee2e6; padding: 12px; text-align: right; font-weight: bold;">Valeur</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        # Section Activités
        html += '<tr style="background-color: #e9ecef; font-weight: bold;"><td colspan="2" style="border: 1px solid #dee2e6; padding: 10px;">ACTIVITÉS</td></tr>'
        
        # Nombre d'activités réalisées
        html += f"""
                <tr>
                    <td style="border: 1px solid #dee2e6; padding: 10px;">Nombre d'activités réalisées dans la période donnée</td>
                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{activities_data.get('activites_realisees', 0)}</td>
                </tr>
        """
        
        # Liste des activités réalisées
        activites_details = activities_data.get('activites_realisees_details', [])
        activites_list = ""
        if activites_details:
            activites_list = "<br>".join([f"• <a href='{act['url']}'>{act['name']}</a> ({act['date']})" for act in activites_details])
        else:
            activites_list = "Aucune activité réalisée"
            
        html += f"""
                <tr>
                    <td style="border: 1px solid #dee2e6; padding: 10px;">Activités réalisées dans la période donnée</td>
                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: left; font-size: 0.9em;">{activites_list}</td>
                </tr>
        """
        
        # Autres métriques d'activités
        activities_labels = {
            "activites_retard": "Nombre d'activités en retard",
            "activites_delais": "Nombre d'activités dans les délais", 
            "activites_cours_total": "Nombre total d'activités en cours"
        }
        
        for key, label in activities_labels.items():
            value = activities_data.get(key, 0)
            html += f"""
                    <tr>
                        <td style="border: 1px solid #dee2e6; padding: 10px;">{label}</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{value}</td>
                    </tr>
            """
        
        # Section Tâches
        html += '<tr style="background-color: #e9ecef; font-weight: bold;"><td colspan="2" style="border: 1px solid #dee2e6; padding: 10px;">TÂCHES</td></tr>'
        
        # Nombre de tâches réalisées
        html += f"""
                <tr>
                    <td style="border: 1px solid #dee2e6; padding: 10px;">Nombre de tâches réalisées dans la période donnée</td>
                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{tasks_data.get('taches_realisees', 0)}</td>
                </tr>
        """
        
        # Liste des tâches réalisées
        taches_details = tasks_data.get('taches_realisees_details', [])
        taches_list = ""
        if taches_details:
            taches_list = "<br>".join([f"• <a href='{task['url']}'>{task['name']}</a> - {task['project']} ({task['date']})" for task in taches_details])
        else:
            taches_list = "Aucune tâche réalisée"
            
        html += f"""
                <tr>
                    <td style="border: 1px solid #dee2e6; padding: 10px;">Tâches réalisées dans la période donnée</td>
                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: left; font-size: 0.9em;">{taches_list}</td>
                </tr>
        """
        
        # Autres métriques de tâches
        tasks_labels = {
            "taches_retard": "Nombre de tâches en retard",
            "taches_delais": "Nombre de tâches dans les délais",
            "taches_sans_delais": "Nombre de tâches sans délais",
            "taches_cours_total": "Nombre total de tâches en cours"
        }
        
        for key, label in tasks_labels.items():
            value = tasks_data.get(key, 0)
            html += f"""
                    <tr>
                        <td style="border: 1px solid #dee2e6; padding: 10px;">{label}</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{value}</td>
                    </tr>
            """
        
        # Section Projets
        html += '<tr style="background-color: #e9ecef; font-weight: bold;"><td colspan="2" style="border: 1px solid #dee2e6; padding: 10px;">PROJETS</td></tr>'
        
        # Nombre de projets réalisés
        html += f"""
                <tr>
                    <td style="border: 1px solid #dee2e6; padding: 10px;">Nombre de projets réalisés dans la période donnée</td>
                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{projects_data.get('projets_realises', 0)}</td>
                </tr>
        """
        
        # Liste des projets réalisés
        projets_details = projects_data.get('projets_realises_details', [])
        projets_list = ""
        if projets_details:
            projets_list = "<br>".join([f"• <a href='{proj['url']}'>{proj['name']}</a> ({proj['date']})" for proj in projets_details])
        else:
            projets_list = "Aucun projet réalisé"
            
        html += f"""
                <tr>
                    <td style="border: 1px solid #dee2e6; padding: 10px;">Projets réalisés dans la période donnée</td>
                    <td style="border: 1px solid #dee2e6; padding: 10px; text-align: left; font-size: 0.9em;">{projets_list}</td>
                </tr>
        """
        
        # Autres métriques de projets
        projects_labels = {
            "projets_retard": "Nombre de projets en retard",
            "projets_delais": "Nombre de projets dans les délais",
            "projets_sans_dates": "Nombre de projets sans dates",
            "projets_cours_total": "Nombre total de projets en cours"
        }
        
        for key, label in projects_labels.items():
            value = projects_data.get(key, 0)
            html += f"""
                    <tr>
                        <td style="border: 1px solid #dee2e6; padding: 10px;">{label}</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">{value}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
        
        return html
        
    except Exception as e:
        raise Exception(f"Error generating HTML table: {str(e)}")

def create_activity_report_task(report_data, project_id, task_column_id):
    """Create an Odoo task with the activity report"""
    try:
        user_info = report_data.get('user_info', {})
        user_name = user_info.get('user_name', 'N/A')
        start_date = user_info.get('start_date', 'N/A')
        end_date = user_info.get('end_date', 'N/A')
        
        # Generate task title
        task_name = f"Rapport d'activité - {user_name} ({start_date} au {end_date})"
        
        # Generate HTML table
        html_description = generate_activity_report_html_table(report_data)
        
        # Create task using odoo_execute
        result = odoo_execute(
            model='project.task',
            method='create',
            args=[{
                'name': task_name,
                'project_id': project_id,
                'stage_id': task_column_id,
                'description': html_description,
                'user_ids': [(4, user_info.get('user_id'))]  # Assign to the user
            }]
        )
        
        response = json.loads(result)
        if response.get('status') == 'success':
            task_id = response.get('result')
            return task_id
        else:
            raise Exception(f"Task creation failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise Exception(f"Error creating activity report task: {str(e)}")