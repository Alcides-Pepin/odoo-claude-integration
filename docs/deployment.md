# Déploiement

## Déploiement sur Railway

Railway est la plateforme recommandée pour déployer le serveur MCP Odoo.

### 1. Préparer le repository

Votre repository doit contenir :
- `odoo_mcp.py` - Le serveur principal
- `requirements.txt` - Les dépendances
- Variables d'environnement configurées

### 2. Déploiement sur Railway

1. **Se connecter à Railway :**
   - Aller sur [railway.app](https://railway.app)
   - Se connecter avec GitHub

2. **Créer un nouveau projet :**
   - Cliquer sur "New Project"
   - Sélectionner "Deploy from GitHub repo"
   - Choisir votre repository

3. **Configuration des variables d'environnement :**
   Dans l'onglet "Variables" de votre projet Railway :
   ```
   ODOO_URL=https://your-odoo-instance.com
   ODOO_DB=your_database_name
   ODOO_USER=your_username
   ODOO_PASSWORD=your_password
   ```

4. **Configuration du déploiement :**
   Railway détecte automatiquement Python et utilise :
   - **Build Command :** `pip install -r requirements.txt`
   - **Start Command :** `python odoo_mcp.py`
   - **Port :** Automatiquement défini via `$PORT`

### 3. Vérification du déploiement

1. **URL du service :**
   Railway génère automatiquement une URL : `https://your-app.up.railway.app`

2. **URL MCP pour Claude :**
   `https://your-app.up.railway.app/sse`

3. **Test de connectivité :**
   ```bash
   curl https://your-app.up.railway.app/sse
   ```

## Déploiement sur Render

### 1. Créer un Web Service

1. Se connecter à [render.com](https://render.com)
2. Cliquer sur "New" → "Web Service"
3. Connecter votre repository GitHub

### 2. Configuration

- **Environment :** Python 3
- **Build Command :** `pip install -r requirements.txt`
- **Start Command :** `python odoo_mcp.py`

### 3. Variables d'environnement

Ajouter dans l'onglet "Environment" :
```
ODOO_URL=https://your-odoo-instance.com
ODOO_DB=your_database_name
ODOO_USER=your_username
ODOO_PASSWORD=your_password
```

## Configuration dans Claude Web

Une fois déployé, configurer dans Claude Web :

1. **Ouvrir Claude Web**
2. **Settings → Model Context Protocol**
3. **Ajouter un serveur :**
   - **Nom :** Odoo MCP Server
   - **URL :** `https://your-app.up.railway.app/sse`
   - **Type :** SSE

## Déploiement local (développement)

### Avec Docker (optionnel)

Créer un `Dockerfile` :

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["python", "odoo_mcp.py"]
```

Construire et lancer :
```bash
docker build -t odoo-mcp .
docker run -p 8001:8001 --env-file .env odoo-mcp
```

### Avec systemd (Linux)

Créer `/etc/systemd/system/odoo-mcp.service` :

```ini
[Unit]
Description=Odoo MCP Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/your/project
Environment=PATH=/path/to/your/venv/bin
EnvironmentFile=/path/to/your/.env
ExecStart=/path/to/your/venv/bin/python odoo_mcp.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Activer le service :
```bash
sudo systemctl enable odoo-mcp
sudo systemctl start odoo-mcp
```

## Monitoring et maintenance

### Logs sur Railway
- Aller dans votre projet → Onglet "Deployments"
- Cliquer sur un déploiement pour voir les logs

### Health check
Utiliser l'outil `ping` dans Claude pour vérifier le statut :
```
Peux-tu vérifier que le serveur MCP fonctionne ?
```

### Redémarrage
Sur Railway, pousser un nouveau commit déclenche automatiquement un redéploiement.

## Sécurité

### Variables d'environnement
- ❌ **Jamais** commiter les credentials dans le code
- ✅ Utiliser les variables d'environnement de la plateforme
- ✅ Utiliser des mots de passe forts pour Odoo

### Accès réseau
- Le serveur MCP doit pouvoir accéder à votre instance Odoo
- Si Odoo est derrière un firewall, autoriser les IPs de Railway/Render

### Utilisateur Odoo
- Créer un utilisateur dédié pour l'API XML-RPC
- Donner uniquement les permissions nécessaires
- Éviter d'utiliser l'utilisateur administrateur

## Résolution de problèmes

### Erreur de démarrage
1. Vérifier les logs de déploiement
2. Vérifier que toutes les variables d'environnement sont définies
3. Tester la connexion Odoo en local

### Timeout de connexion
1. Vérifier l'URL Odoo
2. Tester l'accès depuis l'extérieur : `curl https://your-odoo.com/web/login`
3. Vérifier les paramètres firewall

### Erreurs d'authentification
1. Tester les credentials dans l'interface web Odoo
2. Vérifier que l'utilisateur a les droits XML-RPC
3. Vérifier le nom de la base de données