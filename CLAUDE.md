# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an Odoo MCP Server that provides a standardized interface for interacting with Odoo systems via Claude Web. The server implements essential tools for model discovery, data search, and CRUD operations through the Model Context Protocol (MCP).

## Development Commands

### Running the Server
```bash
# Local development
python odoo_mcp.py

# With environment variables
ODOO_URL=https://your-instance.com ODOO_DB=db_name python odoo_mcp.py
```

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file with required variables:
# ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD
```

### Testing the Server
- Test connectivity: Use the `ping` tool in Claude Web
- Test Odoo connection: Use the `odoo_health_check` tool
- Verify deployment: URL should be `https://your-app.up.railway.app/sse` for Claude Web

## Architecture

### Core Components

**Main Server (`odoo_mcp.py`):**
- FastMCP server instance with SSE transport
- 6 MCP tools for Odoo interaction
- Security blacklist for dangerous operations
- Timeout and error handling for XML-RPC calls

**Connection Management:**
- `get_odoo_connection()`: Establishes authenticated connection to Odoo via XML-RPC
- `create_server_proxy()`: Creates XML-RPC proxy with timeout configuration
- Environment-based configuration with required variables

**Security Layer:**
- `SECURITY_BLACKLIST`: Prevents dangerous operations (user deletion, model deletion, etc.)
- Input validation and model existence checks
- Error handling prevents information leakage

### Tool Architecture

All tools follow the same pattern:
1. Parameter validation and type checking
2. Odoo connection establishment via `get_odoo_connection()`
3. Business logic execution with XML-RPC calls
4. Structured JSON response with consistent error handling

**Tool Categories:**
- **System Tools:** `ping`, `odoo_health_check`
- **Discovery Tools:** `odoo_discover_models`, `odoo_get_model_fields`  
- **Data Tools:** `odoo_search`, `odoo_execute`

### Response Format Standards

All tools return JSON strings with consistent structure:
```python
# Success response
{
    "status": "success",
    "data": {...},
    "timestamp": "ISO-8601"
}

# Error response  
{
    "error": "Detailed error message"
}
```

## MCP Development Standards

### Tool Implementation Requirements
- **Return Type:** All tools must return `str` (JSON string)
- **Error Handling:** Wrap all logic in try/except blocks
- **Documentation:** Complete docstrings with Args/Returns sections
- **Type Hints:** Full type annotation for parameters and return values

### Security Considerations
- Never expose Odoo credentials in responses
- Validate model names before XML-RPC calls
- Implement operation blacklist for destructive actions
- Use timeouts to prevent hanging connections

### Deployment Configuration
- **Transport:** Always use "sse" for Claude Web compatibility
- **Host:** Must be "0.0.0.0" for cloud deployment
- **Port:** Use environment variable `PORT` (default: 8001)
- **Environment Variables:** ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD are required

## Extending the Server

When adding new tools, follow this template:

```python
@mcp.tool()
def new_tool_name(param: str, optional_param: int = 10) -> str:
    """
    Description of what this tool does.
    
    Args:
        param: Description of required parameter
        optional_param: Description of optional parameter
    
    Returns:
        JSON string with tool results
    """
    try:
        models, uid = get_odoo_connection()
        
        # Tool logic here
        result = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'model.name', 'method',
            [args], {kwargs}
        )
        
        return json.dumps({
            "status": "success", 
            "data": result,
            "timestamp": datetime.datetime.now().isoformat()
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Error: {str(e)}"})
```

## Available Tools Reference

1. **`ping`** - Server connectivity test
2. **`odoo_health_check`** - Comprehensive Odoo health verification  
3. **`odoo_discover_models`** - Model discovery with search capability
4. **`odoo_get_model_fields`** - Field information for any model
5. **`odoo_search`** - Advanced record search with pagination
6. **`odoo_execute`** - Generic method executor for CRUD operations

## Odoo Domain Filter Examples

```python
# Equality
[['field', '=', 'value']]

# Contains (case-insensitive)  
[['field', 'ilike', '%search%']]

# Comparisons
[['field', '>', 100]]

# AND logic (implicit)
[['field1', '=', 'value1'], ['field2', '>', 10]]

# OR logic
['|', ['field1', '=', 'value1'], ['field2', '=', 'value2']]

# Complex combinations
['&', ['state', '=', 'draft'], '|', ['amount_total', '>', 1000], ['priority', '=', 'high']]
```