"""
Odoo client module.

Provides connection management and XML-RPC communication functions for Odoo.
"""

import xmlrpc.client
import socket
from config import ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD, TIMEOUT


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
