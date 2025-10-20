"""
Configuration module for Odoo MCP Server.

Contains all constants, environment variables, and configuration mappings.
"""

import os

# Server configuration
PORT = int(os.environ.get("PORT", 8001))

# Odoo connection configuration
ODOO_URL = os.getenv('ODOO_URL')
ODOO_DB = os.getenv('ODOO_DB')
ODOO_USER = os.getenv('ODOO_USER')
ODOO_PASSWORD = os.getenv('ODOO_PASSWORD')

# Anthropic API configuration
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

# Connection timeout in seconds
TIMEOUT = 30

# Security blacklist - operations that should never be allowed
SECURITY_BLACKLIST = {
    ('res.users', 'unlink'),  # Never delete users
    ('ir.model', 'unlink'),   # Never delete models
    ('ir.model.fields', 'unlink'),  # Never delete fields
    ('ir.module.module', 'button_immediate_uninstall'),  # Never uninstall modules
}

# Mapping des subtypes mail.message vers actions francaises
# Ce mapping permet de traduire les subtypes Odoo en actions comprehensibles
SUBTYPE_MAPPING = {
    # Generiques
    1: "Discussion",
    2: "Note interne",
    3: "Activite planifiee",
    4: "Invitation evenement",

    # Taches projet
    8: "Tache creee",
    9: "Changement d'etape",
    10: "Tache en cours",
    14: "Tache terminee",
    15: "Tache en attente",

    # CRM
    42: "Opportunite creee",
    43: "Changement d'etape",
    44: "Opportunite gagnee",
    45: "Opportunite perdue",

    # Factures
    5: "Facture validee",
    6: "Facture payee",
    7: "Facture creee",
}

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
