"""
Data tools module.

Contains MCP tools for searching and executing operations on Odoo data.
"""

import json
import datetime
from typing import List, Any, Dict, Optional
from config import ODOO_DB, ODOO_PASSWORD, SECURITY_BLACKLIST
from services.odoo_client import get_odoo_connection


# The mcp instance will be injected by the main module
mcp = None


def init_mcp(mcp_instance):
    """Initialize the mcp instance for this module"""
    global mcp
    mcp = mcp_instance
    
    # Register all tools
    mcp.tool()(odoo_search)
    mcp.tool()(odoo_execute)


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
        limit: Maximum number of records to return (default: 10, max: 100000)
        offset: Number of records to skip (for pagination)
        order: Sort order (e.g., 'name desc, id')

    Returns:
        JSON string with search results
    """
    try:
        print(f"[🔥 RESTORED d2c0a1d] odoo_search called with model={model}, domain={domain}")

        models, uid = get_odoo_connection()

        # Validate and set defaults
        if domain is None:
            domain = []
        if limit > 100000:
            limit = 100000  # Cap at 100,000 for performance

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
