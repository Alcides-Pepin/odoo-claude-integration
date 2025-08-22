#!/usr/bin/env python3
"""
Odoo MCP Server - Generic Tools for Odoo Integration

This server provides generic tools to interact with any Odoo instance via XML-RPC.
It enables discovery, exploration, and manipulation of Odoo data through Claude AI.
"""
import os
import sys
import xmlrpc.client
import json
import socket
import time
import logging
import hashlib
import base64
import secrets
from typing import Any, List, Dict, Optional
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
ODOO_URL = os.getenv('ODOO_URL')
ODOO_DB = os.getenv('ODOO_DB')
ODOO_USER = os.getenv('ODOO_USER')
ODOO_PASSWORD = os.getenv('ODOO_PASSWORD')

# Validate required environment variables
required_vars = ['ODOO_URL', 'ODOO_DB', 'ODOO_USER', 'ODOO_PASSWORD']
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    logger.error(f"Missing required environment variables: {missing_vars}")
    logger.error("Please ensure all required variables are set in your .env file or environment")
    sys.exit(1)

# Security blacklist - operations that should never be allowed
SECURITY_BLACKLIST = {
    ('res.users', 'unlink'),  # Never delete users
    ('ir.model', 'unlink'),   # Never delete models
    ('ir.model.fields', 'unlink'),  # Never delete fields
    ('ir.module.module', 'button_immediate_uninstall'),  # Never uninstall modules
}

# Timeout for XML-RPC calls (in seconds)
TIMEOUT = 30

# Railway port configuration
PORT = int(os.getenv('PORT', 8000))

# OAuth configuration
BASE_URL = f"https://{os.getenv('RAILWAY_STATIC_URL', 'claude-odoo.up.railway.app')}"

# Global storage for OAuth 2.1 implementation
REGISTERED_CLIENTS = {}
AUTH_CODES = {}

# Initialize MCP server
mcp = FastMCP("Odoo MCP Server")

# Initialize FastAPI app for HTTP endpoints
app = FastAPI(title="Odoo MCP Server", description="Production-ready MCP server for Odoo integration")

# Add CORS middleware for Claude.ai
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://claude.ai"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Get SSE app from FastMCP for Claude Web
sse_app = mcp.sse_app()

def create_server_proxy(url):
    """Create ServerProxy with timeout"""
    transport = xmlrpc.client.Transport()
    transport.timeout = TIMEOUT
    return xmlrpc.client.ServerProxy(url, transport=transport)

def get_odoo_connection():
    """Establish connection to Odoo with better error handling"""
    logger.info("Connecting to Odoo...")
    try:
        common = create_server_proxy(f'{ODOO_URL}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
        if not uid:
            raise Exception("Authentication failed - check username/password")
        models = create_server_proxy(f'{ODOO_URL}/xmlrpc/2/object')
        logger.info(f"Connected with UID: {uid}")
        return models, uid
    except socket.timeout:
        logger.error(f"Connection timeout after {TIMEOUT} seconds")
        raise Exception(f"Connection timeout after {TIMEOUT} seconds - Odoo server may be down")
    except socket.error as e:
        logger.error(f"Network error: {str(e)}")
        raise Exception(f"Network error: {str(e)} - Cannot reach Odoo at {ODOO_URL}")
    except xmlrpc.client.Fault as fault:
        logger.error(f"Odoo XML-RPC error: {fault.faultString}")
        raise Exception(f"Odoo XML-RPC error: {fault.faultString}")
    except Exception as e:
        logger.error(f"Connection error: {e}")
        raise

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
        Health check report with test results
    """
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
        return result
    except Exception as e:
        result += f"✗ FAILED - {str(e)}\n"
        return result
    
    # Test 2: Authentication
    try:
        result += "2. Authentication Test: "
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
        if uid:
            result += f"✓ OK (UID: {uid})\n"
        else:
            result += "✗ FAILED - Invalid credentials\n"
            return result
    except Exception as e:
        result += f"✗ FAILED - {str(e)}\n"
        return result
    
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
        return result
    
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
    elif "⚠" in result:
        result += "⚠️ System operational with warnings"
    else:
        result += "✅ All systems operational"
    
    return result

@mcp.tool()
def odoo_discover_models(search_term: str = "") -> str:
    """
    Discover available Odoo models by searching in model registry.
    
    Args:
        search_term: Optional search term to filter models by name or description
        
    Returns:
        List of matching models with their names and descriptions
        
    Example:
        odoo_discover_models("partner") -> Returns models related to partners
        odoo_discover_models() -> Returns all available models (up to 50)
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
            return f"No models found matching '{search_term}'"
        
        result = f"Found {len(ir_models)} models"
        if search_term:
            result += f" matching '{search_term}'"
        result += ":\n\n"
        
        for model in ir_models:
            result += f"Model: {model['model']}\n"
            result += f"  Name: {model['name']}\n"
            if model.get('info'):
                result += f"  Description: {model['info']}\n"
            result += "\n"
        
        return result
    except socket.timeout:
        return f"Error: Operation timeout after {TIMEOUT} seconds. Odoo server may be overloaded."
    except socket.error as e:
        return f"Network error: Cannot reach Odoo server - {str(e)}"
    except xmlrpc.client.Fault as fault:
        if "psycopg2" in fault.faultString or "PostgreSQL" in fault.faultString:
            return f"Database error: {fault.faultString.split('\\n')[0]}"
        return f"Odoo error: {fault.faultString}"
    except Exception as e:
        return f"Error discovering models: {str(e)}"

@mcp.tool()
def odoo_get_model_fields(model_name: str) -> str:
    """
    Get detailed information about all fields of a specific Odoo model.
    
    Args:
        model_name: The technical name of the model (e.g., 'res.partner')
        
    Returns:
        Detailed field information including types, relations, and constraints
        
    Example:
        odoo_get_model_fields("res.partner") -> Returns all partner fields
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
            return f"Model '{model_name}' not found"
        
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
            return f"No fields found for model '{model_name}'"
        
        result = f"Model: {model_name}\n"
        result += f"Total fields: {len(fields)}\n\n"
        
        for field in fields:
            result += f"Field: {field['name']}\n"
            result += f"  Label: {field.get('field_description', 'N/A')}\n"
            result += f"  Type: {field['ttype']}\n"
            result += f"  Required: {'Yes' if field.get('required') else 'No'}\n"
            result += f"  Readonly: {'Yes' if field.get('readonly') else 'No'}\n"
            
            if field.get('relation'):
                result += f"  Relation: {field['relation']}\n"
                if field.get('relation_field'):
                    result += f"  Relation Field: {field['relation_field']}\n"
            
            if field.get('help'):
                result += f"  Help: {field['help']}\n"
            
            result += "\n"
        
        return result
    except socket.timeout:
        return f"Error: Operation timeout after {TIMEOUT} seconds. Odoo server may be overloaded."
    except socket.error as e:
        return f"Network error: Cannot reach Odoo server - {str(e)}"
    except xmlrpc.client.Fault as fault:
        if "psycopg2" in fault.faultString or "PostgreSQL" in fault.faultString:
            return f"Database error: {fault.faultString.split('\\n')[0]}"
        return f"Odoo error: {fault.faultString}"
    except Exception as e:
        return f"Error getting model fields: {str(e)}"

@mcp.tool()
def odoo_execute(model: str, method: str, args: Optional[List[Any]] = None, 
                kwargs: Optional[Dict[str, Any]] = None) -> str:
    """
    Execute any method on an Odoo model. This is a powerful generic wrapper.
    
    Args:
        model: The Odoo model name (e.g., 'res.partner')
        method: The method to execute (e.g., 'create', 'write', 'search')
        args: List of positional arguments for the method
        kwargs: Dictionary of keyword arguments for the method
    
    Returns:
        String representation of the result
        
    Examples:
        odoo_execute("res.partner", "create", [{"name": "John Doe"}])
        odoo_execute("res.partner", "search", [[("name", "ilike", "john")]])
        odoo_execute("res.partner", "fields_get", [], {"attributes": ["string", "type"]})
    """
    try:
        # Security check
        if (model, method) in SECURITY_BLACKLIST:
            return f"Error: Operation '{method}' on model '{model}' is not allowed for security reasons"
        
        # Validate dangerous operations
        if method in ['unlink', 'button_immediate_uninstall'] and model not in ['sale.order', 'purchase.order', 'stock.picking']:
            return f"Error: Method '{method}' is restricted. Please use with caution."
        
        models, uid = get_odoo_connection()
        
        # Default args and kwargs if not provided
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        
        # Log the operation for security audit
        logger.info(f"Executing: {model}.{method}")
        logger.debug(f"Args: {args}, Kwargs: {kwargs}")
        
        try:
            result = models.execute_kw(
                ODOO_DB, uid, ODOO_PASSWORD,
                model, method,
                args,
                kwargs
            )
            
            # Format the result nicely
            if isinstance(result, list) and result and isinstance(result[0], dict):
                # It's a list of records
                return f"Result ({len(result)} records):\n" + json.dumps(result, indent=2)
            elif isinstance(result, dict):
                # It's a single record
                return f"Result:\n{json.dumps(result, indent=2)}"
            elif isinstance(result, (int, float)):
                # It's an ID or count
                return f"Result: {result}"
            elif isinstance(result, bool):
                return f"Result: {'Success' if result else 'Failed'}"
            else:
                # Other types
                return f"Result: {str(result)}"
                
        except xmlrpc.client.Fault as fault:
            error_msg = fault.faultString
            if "psycopg2" in error_msg or "PostgreSQL" in error_msg:
                if "does not exist" in error_msg:
                    return f"Database error: Model or field not found. Check if '{model}' is installed."
                elif "permission denied" in error_msg:
                    return f"Database error: Access denied to model '{model}'."
                else:
                    return f"Database error: {error_msg.split('\\n')[0]}"
            return f"Odoo Error: {error_msg}"
            
    except socket.timeout:
        return f"Error: Operation timeout after {TIMEOUT} seconds. Try simpler operation."
    except socket.error as e:
        return f"Network error: Cannot reach Odoo server - {str(e)}"
    except Exception as e:
        return f"Error executing method: {str(e)}"

@mcp.tool()
def odoo_search(model: str, domain: Optional[List[Any]] = None, 
               fields: Optional[List[str]] = None, limit: int = 10,
               offset: int = 0, order: Optional[str] = None) -> str:
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
        Formatted string with search results and pagination info
        
    Examples:
        odoo_search("res.partner", [["is_company", "=", True]], ["name", "email"])
        odoo_search("sale.order", [["state", "=", "sale"]], limit=5)
        odoo_search("product.product", [["name", "ilike", "laptop"]], order="list_price desc")
    """
    try:
        models, uid = get_odoo_connection()
        
        # Validate and set defaults
        if domain is None:
            domain = []
        if limit > 100:
            limit = 100  # Cap at 100 for performance
        
        # First, let's check if the model exists
        model_exists = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'ir.model', 'search_count',
            [[('model', '=', model)]]
        )
        
        if not model_exists:
            return f"Error: Model '{model}' not found"
        
        # Prepare search parameters
        search_params = {
            'limit': limit,
            'offset': offset
        }
        
        if fields:
            search_params['fields'] = fields
        
        if order:
            search_params['order'] = order
        
        try:
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
            
            if not records:
                return f"No records found in '{model}' matching the criteria"
            
            # Format results
            result = f"Model: {model}\n"
            result += f"Found: {len(records)} records (Total: {total_count})\n"
            if domain:
                result += f"Filter: {domain}\n"
            result += "\n"
            
            # Display records
            for i, record in enumerate(records, 1):
                result += f"Record {i} (ID: {record.get('id', 'N/A')}):\n"
                for field, value in record.items():
                    if field != 'id':
                        # Handle special field types
                        if isinstance(value, list) and len(value) == 2 and isinstance(value[0], int):
                            # Many2one field
                            result += f"  {field}: {value[1]} (ID: {value[0]})\n"
                        elif isinstance(value, list):
                            # One2many or Many2many
                            result += f"  {field}: {len(value)} items\n"
                        else:
                            result += f"  {field}: {value}\n"
                result += "\n"
            
            # Add pagination info if needed
            if total_count > limit + offset:
                result += f"Showing records {offset + 1}-{offset + len(records)} of {total_count}\n"
                result += f"Use offset={offset + limit} to see next page\n"
            
            return result
            
        except xmlrpc.client.Fault as fault:
            error_msg = fault.faultString
            # Handle common PostgreSQL errors
            if "psycopg2" in error_msg or "PostgreSQL" in error_msg:
                if "does not exist" in error_msg:
                    return f"Database error: Table or column not found. The model '{model}' may not be properly installed."
                elif "permission denied" in error_msg:
                    return f"Database error: Permission denied. Check user access rights for model '{model}'."
                elif "syntax error" in error_msg:
                    return f"Database error: Invalid query syntax. Check your domain filter: {domain}"
                else:
                    return f"Database error: {error_msg.split('\\n')[0]}"
            return f"Odoo Error: {error_msg}"
            
    except socket.timeout:
        return f"Error: Search timeout after {TIMEOUT} seconds. Try with smaller limit or simpler query."
    except socket.error as e:
        return f"Network error: Cannot reach Odoo server - {str(e)}"
    except Exception as e:
        return f"Error searching: {str(e)}"

# FastAPI HTTP endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint for Railway monitoring"""
    try:
        # Quick connection test
        models, uid = get_odoo_connection()
        return JSONResponse({
            "status": "healthy",
            "service": "Odoo MCP Server",
            "odoo_connection": "ok",
            "odoo_url": ODOO_URL,
            "port": PORT
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse({
            "status": "unhealthy",
            "service": "Odoo MCP Server",
            "error": str(e),
            "port": PORT
        }, status_code=503)

@app.get("/")
async def root():
    """Root endpoint with server information"""
    return JSONResponse({
        "message": "Odoo MCP Server running",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "mcp": "Uses MCP protocol for Claude integration"
        },
        "tools": [
            "odoo_health_check",
            "odoo_discover_models",
            "odoo_get_model_fields",
            "odoo_execute",
            "odoo_search"
        ]
    })

@app.get("/status")
async def server_status():
    """Detailed server status"""
    return JSONResponse({
        "service": "Odoo MCP Server",
        "port": PORT,
        "odoo_url": ODOO_URL,
        "odoo_database": ODOO_DB,
        "odoo_user": ODOO_USER,
        "timeout": TIMEOUT,
        "environment": "production" if os.getenv('PORT') else "development"
    })

def run_mcp_server():
    """Run MCP server in a separate thread"""
    try:
        logger.info("Starting MCP server thread...")
        mcp.run()
    except Exception as e:
        logger.error(f"MCP server error: {e}")

# OAuth 2.1 endpoints for Claude Web integration - MCP Spec 2025-03-26 compliant

@app.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    """OAuth 2.1 discovery endpoint required by MCP specification"""
    return {
        "issuer": BASE_URL,
        "authorization_endpoint": f"{BASE_URL}/authorize",
        "token_endpoint": f"{BASE_URL}/token",
        "registration_endpoint": f"{BASE_URL}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["claudeai"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "none"]
    }

@app.post("/register")
async def dynamic_client_registration(request: Request):
    """Dynamic Client Registration per RFC 7591"""
    try:
        data = await request.json()
        logger.info(f"Dynamic client registration: {data}")
        
        # Generate client credentials
        client_id = f"client_{secrets.token_urlsafe(16)}"
        client_secret = secrets.token_urlsafe(32)
        
        # Store client
        REGISTERED_CLIENTS[client_id] = {
            "client_secret": client_secret,
            "redirect_uris": data.get("redirect_uris", []),
            "client_name": data.get("client_name", "Unknown"),
            "created_at": time.time()
        }
        
        response = {
            "client_id": client_id,
            "client_secret": client_secret,
            "client_id_issued_at": int(time.time()),
            "client_secret_expires_at": 0  # Never expires
        }
        
        logger.info(f"Registered client: {client_id}")
        return response
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return JSONResponse(
            {"error": "invalid_request", "error_description": str(e)},
            status_code=400
        )

@app.get("/authorize")
async def authorize(
    response_type: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str,
    state: str,
    scope: str
):
    """OAuth 2.1 Authorization endpoint with PKCE - MCP Spec 2025-03-26 compliant"""
    logger.info(f"Authorization request: client_id={client_id}, scope={scope}")
    logger.info(f"PKCE challenge: {code_challenge[:20]}... method: {code_challenge_method}")
    
    # Validate parameters
    if response_type != "code":
        logger.error(f"Unsupported response_type: {response_type}")
        raise HTTPException(status_code=400, detail="Unsupported response_type")
    
    if code_challenge_method != "S256":
        logger.error(f"Unsupported code_challenge_method: {code_challenge_method}")
        raise HTTPException(status_code=400, detail="Unsupported code_challenge_method")
    
    # Validate client exists (if registered dynamically)
    if client_id in REGISTERED_CLIENTS:
        client_info = REGISTERED_CLIENTS[client_id]
        if redirect_uri not in client_info["redirect_uris"]:
            logger.error(f"Invalid redirect_uri for registered client: {redirect_uri}")
            raise HTTPException(status_code=400, detail="Invalid redirect_uri")
        logger.info(f"Using registered client: {client_id}")
    else:
        # Allow unregistered clients for MCP compatibility (Claude may not register)
        logger.info(f"Using unregistered client: {client_id}")
    
    # Nettoyer redirect_uri avant stockage (enlever ; à la fin si présent)
    if redirect_uri and redirect_uri.endswith(';'):
        logger.info(f"Cleaning redirect_uri in /authorize: removing trailing ';' from {redirect_uri}")
        redirect_uri = redirect_uri[:-1]
    
    # Generate authorization code
    auth_code = f"auth_code_{secrets.token_urlsafe(32)}"
    
    # Store code with PKCE challenge and cleaned redirect_uri
    AUTH_CODES[auth_code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,  # Maintenant nettoyé
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "scope": scope,
        "created_at": time.time()
    }
    
    logger.info(f"Generated auth code: {auth_code[:20]}...")
    
    # Redirect to client with authorization code
    final_url = f"{redirect_uri}?code={auth_code}&state={state}"
    logger.info(f"Redirecting to: {final_url}")
    
    return RedirectResponse(url=final_url, status_code=302)


@app.post("/token")
async def token_exchange(request: Request):
    """OAuth 2.1 Token exchange with PKCE validation - MCP Spec 2025-03-26 compliant"""
    logger.info("=== TOKEN EXCHANGE REQUEST ===")
    
    try:
        logger.info("1. Parsing form data...")
        form_data = await request.form()
        logger.info(f"Form data parsed successfully: {dict(form_data)}")
        
        logger.info("2. Extracting parameters...")
        grant_type = form_data.get("grant_type")
        code = form_data.get("code")
        client_id = form_data.get("client_id")
        code_verifier = form_data.get("code_verifier")
        redirect_uri = form_data.get("redirect_uri")
        
        # Nettoyer redirect_uri (enlever ; à la fin si présent)
        if redirect_uri and redirect_uri.endswith(';'):
            logger.info(f"Cleaning redirect_uri: removing trailing ';' from {redirect_uri}")
            redirect_uri = redirect_uri[:-1]
        
        logger.info(f"Parameters extracted: grant_type={grant_type}, code={code}, client_id={client_id}")
        logger.info(f"code_verifier: {code_verifier[:20] if code_verifier else None}...")
        logger.info(f"redirect_uri: {redirect_uri}")
        
        logger.info("3. Validating grant type...")
        logger.info(f"Grant type value: '{grant_type}'")
        logger.info(f"Comparing with 'authorization_code'")
        
        if grant_type != "authorization_code":
            logger.error(f"Invalid grant type: {grant_type}")
            raise HTTPException(status_code=400, detail="Unsupported grant_type")
        
        logger.info("Grant type validation passed")
        
        logger.info("4. Validating auth code...")
        logger.info(f"Looking for code: '{code}'")
        logger.info(f"AUTH_CODES keys: {list(AUTH_CODES.keys())}")
        logger.info(f"Code is None: {code is None}")
        logger.info(f"Code is empty: {code == ''}")
        
        if not code:
            logger.error("Code is missing or empty")
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Missing authorization code"},
                status_code=400
            )
        
        if code not in AUTH_CODES:
            logger.error(f"Code not found in AUTH_CODES: {code}")
            logger.error(f"Available codes: {list(AUTH_CODES.keys())}")
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Invalid authorization code"},
                status_code=400
            )
        
        logger.info("5. Code found, getting auth data...")
        auth_data = AUTH_CODES[code]
        logger.info(f"Auth data retrieved: {auth_data}")
        logger.info(f"Auth data type: {type(auth_data)}")
        
        logger.info("5a. Validating client ID...")
        logger.info(f"Stored client_id: '{auth_data['client_id']}'")
        logger.info(f"Received client_id: '{client_id}'")
        logger.info(f"Client IDs match: {auth_data['client_id'] == client_id}")
        
        if auth_data["client_id"] != client_id:
            logger.error(f"Client ID mismatch: '{auth_data['client_id']}' != '{client_id}'")
            return JSONResponse(
                {"error": "invalid_client", "error_description": "Client ID mismatch"},
                status_code=400
            )
        
        logger.info("Client ID validation passed")
        
        logger.info("6. Validating redirect URI...")
        logger.info(f"Stored redirect_uri: '{auth_data['redirect_uri']}'")
        logger.info(f"Received redirect_uri: '{redirect_uri}'")
        logger.info(f"Redirect URIs match: {auth_data['redirect_uri'] == redirect_uri}")
        
        if auth_data["redirect_uri"] != redirect_uri:
            logger.error(f"Redirect URI mismatch: '{auth_data['redirect_uri']}' != '{redirect_uri}'")
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Redirect URI mismatch"},
                status_code=400
            )
        
        logger.info("Redirect URI validation passed")
        
        logger.info("7. Validating PKCE code_verifier...")
        if not code_verifier:
            logger.error("Missing code_verifier")
            return JSONResponse(
                {"error": "invalid_request", "error_description": "Missing code_verifier"},
                status_code=400
            )
        
        logger.info("8. Computing PKCE challenge...")
        expected_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip('=')
        
        logger.info("9. Verifying PKCE challenge...")
        if expected_challenge != auth_data["code_challenge"]:
            logger.error("PKCE validation failed")
            logger.error(f"Expected: {expected_challenge}")
            logger.error(f"Received: {auth_data['code_challenge']}")
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Invalid code_verifier"},
                status_code=400
            )
        
        logger.info("10. PKCE validation successful, generating token...")
        access_token = f"mcp_access_token_{secrets.token_urlsafe(32)}"
        
        logger.info("11. Cleaning up auth code...")
        del AUTH_CODES[code]
        
        logger.info("12. Building response...")
        response = {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": auth_data["scope"]
        }
        
        logger.info(f"=== TOKEN SUCCESS: {access_token[:20]}... ===")
        return response
        
    except HTTPException as he:
        logger.error(f"=== TOKEN HTTP ERROR: {he.detail} ===")
        raise
    except Exception as e:
        logger.error(f"=== TOKEN ERROR: {e} ===")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(
            {"error": "invalid_request", "error_description": str(e)},
            status_code=400
        )

# SSE endpoint with MCP OAuth 2.1 support - GET only (FastMCP uses GET for SSE)
@app.get("/sse")
async def sse_get(request: Request):
    """GET SSE endpoint - requires MCP access token"""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer mcp_access_token_"):
        logger.info("GET /sse - No valid token, returning 401")
        return JSONResponse(
            {"error": "unauthorized"}, 
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = auth.split(" ", 1)[1]
    logger.info(f"GET /sse - Valid token found ({token[:20]}...), forwarding to SSE")
    return await sse_app(request.scope, request.receive, request._send)

@app.head("/sse")
async def sse_head(request: Request):
    """HEAD SSE endpoint - requires MCP access token"""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer mcp_access_token_"):
        logger.info("HEAD /sse - No valid token, returning 401")
        return JSONResponse(
            {"error": "unauthorized"}, 
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = auth.split(" ", 1)[1]
    logger.info(f"HEAD /sse - Valid token found ({token[:20]}...), returning 200")
    return Response(status_code=200)

# Note: Cleanup automatique supprimé pour éviter les conflits ASGI
# Les codes expireront naturellement lors du redémarrage du serveur

# Mount SSE app commented out to avoid conflicts with explicit endpoints
# app.mount("", sse_app)

if __name__ == "__main__":
    logger.info("Starting Odoo MCP Server...")
    logger.info(f"Configuration:")
    logger.info(f"  - Port: {PORT}")
    logger.info(f"  - Odoo URL: {ODOO_URL}")
    logger.info(f"  - Database: {ODOO_DB}")
    logger.info(f"  - User: {ODOO_USER}")
    logger.info(f"  - Timeout: {TIMEOUT}s")
    logger.info(f"\nAvailable tools:")
    logger.info(f"  - odoo_health_check: Check system health")
    logger.info(f"  - odoo_discover_models: Find available models")
    logger.info(f"  - odoo_get_model_fields: Get model field details")
    logger.info(f"  - odoo_execute: Execute any model method")
    logger.info(f"  - odoo_search: Search records with filters")
    logger.info(f"\nStarting hybrid server (FastAPI + MCP)...")
    
    try:
        # Start FastAPI server with SSE support for Claude Web
        logger.info(f"Starting hybrid server on port {PORT}")
        logger.info(f"SSE endpoint available at: /messages")
        uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)