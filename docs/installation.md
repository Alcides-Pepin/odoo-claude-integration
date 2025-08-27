# Installation et Configuration

## Prérequis

- Python 3.8 ou supérieur
- Accès à une instance Odoo fonctionnelle
- Connexion internet pour l'installation des dépendances

## Installation locale

### 1. Cloner le repository

```bash
git clone https://github.com/Alcides-Pepin/odoo-claude-integration.git
cd odoo-claude-integration
```

### 2. Créer un environnement virtuel (recommandé)

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# ou
venv\Scripts\activate     # Windows
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Configuration

Créer un fichier `.env` à la racine du projet :

```env
# Configuration Odoo
ODOO_URL=https://your-odoo-instance.com
ODOO_DB=your_database_name
ODOO_USER=your_username
ODOO_PASSWORD=your_password

# Configuration serveur (optionnel)
PORT=8001
```

### 5. Test de l'installation

```bash
python odoo_mcp.py
```

Le serveur démarre sur `http://localhost:8001` par défaut.

## Configuration pour Claude Web

1. **Ouvrir Claude Web**
2. **Aller dans Settings > Model Context Protocol**
3. **Ajouter un nouveau serveur :**
   - **Nom :** Odoo MCP Server
   - **URL :** `http://localhost:8001/sse`
   - **Type :** SSE (Server-Sent Events)

## Variables d'environnement

| Variable | Description | Requis | Défaut |
|----------|-------------|---------|---------|
| `ODOO_URL` | URL de votre instance Odoo | ✅ | - |
| `ODOO_DB` | Nom de la base de données | ✅ | - |
| `ODOO_USER` | Nom d'utilisateur Odoo | ✅ | - |
| `ODOO_PASSWORD` | Mot de passe Odoo | ✅ | - |
| `PORT` | Port du serveur MCP | ❌ | 8001 |

## Résolution de problèmes

### Erreur de connexion à Odoo

- Vérifiez que l'URL Odoo est correcte
- Testez les credentials dans l'interface web Odoo
- Vérifiez que l'utilisateur a les droits d'accès XML-RPC

### Erreur "Module not found"

```bash
pip install --upgrade -r requirements.txt
```

### Port déjà utilisé

Changez le port dans le fichier `.env` :
```env
PORT=8002
```