# Odoo MCP Server

Serveur MCP (Model Context Protocol) pour l'intégration Odoo avec Claude.

## Vue d'ensemble

Ce serveur MCP fournit une interface standardisée pour interagir avec les systèmes Odoo via Claude Web. Il implémente les outils essentiels pour la découverte de modèles, la recherche de données, et les opérations CRUD.

## Installation rapide

1. **Cloner le repository**
   ```bash
   git clone https://github.com/Alcides-Pepin/odoo-claude-integration.git
   cd odoo-claude-integration
   ```

2. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configuration**
   ```bash
   # Créer un fichier .env avec vos paramètres Odoo
   ODOO_URL=https://your-odoo-instance.com
   ODOO_DB=your_database_name
   ODOO_USER=your_username
   ODOO_PASSWORD=your_password
   ```

4. **Lancer le serveur**
   ```bash
   python odoo_mcp.py
   ```

## Outils disponibles

- **`ping`** - Test de connectivité du serveur MCP
- **`odoo_health_check`** - Vérification complète de la santé Odoo
- **`odoo_discover_models`** - Découverte des modèles avec recherche
- **`odoo_get_model_fields`** - Information détaillée sur les champs d'un modèle
- **`odoo_search`** - Recherche avancée avec pagination et filtres
- **`odoo_execute`** - Exécuteur générique pour toutes les opérations CRUD

## Documentation

- [Installation et Configuration](docs/installation.md)
- [Guide d'utilisation](docs/usage.md)
- [Référence des outils](docs/tools-reference.md)
- [Déploiement](docs/deployment.md)

## Support

Pour signaler des problèmes ou demander des fonctionnalités, créez une issue sur le repository GitHub.