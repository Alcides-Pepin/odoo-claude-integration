# Spécifications Minimales pour Serveur MCP

## Vue d'ensemble
Ce document détaille les spécifications minimales pour créer un serveur MCP (Model Context Protocol) fonctionnel avec FastMCP et compatible avec Claude Web.

## Structure de base minimale

### Imports requis
```python
import json
import datetime
import os
from mcp.server.fastmcp import FastMCP
```

### Configuration du serveur
```python
# Port depuis variable d'environnement (Railway/Render)
PORT = int(os.environ.get("PORT", 8001))

# Initialisation du serveur FastMCP
mcp = FastMCP("nom-serveur", host="0.0.0.0", port=PORT)
```

### Point d'entrée
```python
if __name__ == "__main__":
    # Lancement avec transport SSE
    mcp.run(transport="sse")
```

## Outils (Tools)

### Déclaration d'un outil
```python
@mcp.tool()
def nom_fonction(parametre: type) -> str:
    """
    Description de l'outil.
    
    Args:
        parametre: Description du paramètre
    
    Returns:
        Description du retour (toujours JSON string)
    """
    try:
        # Logique de l'outil
        response = {
            "status": "success",
            "data": "résultat",
            "timestamp": datetime.datetime.now().isoformat()
        }
        return json.dumps(response, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Erreur: {str(e)}"})
```

### Règles importantes
- **Retour obligatoire** : Toujours retourner une string JSON
- **Gestion d'erreurs** : Encapsuler dans try/except
- **Documentation** : Docstring complète obligatoire
- **Types** : Annoter les paramètres et retours

## Exemple minimal complet

```python
import json
import datetime
import os
from mcp.server.fastmcp import FastMCP

# Configuration
PORT = int(os.environ.get("PORT", 8001))
mcp = FastMCP("mon-serveur-mcp", host="0.0.0.0", port=PORT)

@mcp.tool()
def ping() -> str:
    """
    Test de connectivité du serveur MCP.
    
    Returns:
        JSON string confirmant le fonctionnement
    """
    try:
        response = {
            "status": "ok",
            "message": "Serveur MCP opérationnel",
            "timestamp": datetime.datetime.now().isoformat()
        }
        return json.dumps(response, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Erreur: {str(e)}"})

if __name__ == "__main__":
    mcp.run(transport="sse")
```

## Dépendances minimales

### requirements.txt
```
annotated-types==0.7.0
anyio==4.9.0
certifi==2025.4.26
charset-normalizer==3.4.2
click==8.2.1
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
httpx-sse==0.4.0
idna==3.10
mcp==1.9.3
pydantic==2.11.5
pydantic-core==2.33.2
pydantic-settings==2.9.1
python-dotenv==1.1.0
python-multipart==0.0.20
sniffio==1.3.1
sse-starlette==2.3.6
starlette==0.47.0
typing-extensions==4.14.0
typing-inspection==0.4.1
urllib3==2.4.0
uvicorn==0.34.3
```

## Déploiement

### Railway/Render
- **Commande de démarrage** : `python nom_fichier.py`
- **Port** : Automatiquement défini via `PORT` env variable
- **Host** : Obligatoirement `"0.0.0.0"`
- **Transport** : Toujours `"sse"` pour Claude Web

### Configuration Claude Web
- **URL** : `https://votre-app.up.railway.app/sse`
- **Type de transport** : SSE (Server-Sent Events)

## Bonnes pratiques

### Structure des réponses
```python
# Succès
{
    "status": "success",
    "data": {...},
    "timestamp": "2025-01-27T10:30:00"
}

# Erreur
{
    "error": "Description de l'erreur",
    "timestamp": "2025-01-27T10:30:00"
}
```

### Nommage
- **Serveur** : `kebab-case` (ex: `"mon-serveur-mcp"`)
- **Fonctions** : `snake_case` (ex: `ma_fonction`)
- **Variables** : `snake_case`

### Éviter
- ❌ Outils trop complexes (peuvent casser la détection)
- ❌ Trop d'éléments simultanés (tools + resources + prompts)
- ❌ Dépendances externes non nécessaires
- ❌ Retours non-JSON
- ❌ Exceptions non gérées

## Extension du template

Pour ajouter des outils, copier le pattern :

```python
@mcp.tool()
def nouvel_outil(param: str) -> str:
    """Description complète."""
    try:
        # Logique
        return json.dumps({"result": "success"})
    except Exception as e:
        return json.dumps({"error": str(e)})
```

## Tests de validation

1. **Connectivité** : Outil `ping()` obligatoire
2. **Déploiement** : Tester sur Railway/Render  
3. **Claude Web** : Vérifier apparition des outils
4. **Fonctionnalité** : Tester chaque outil individuellement

---

*Ce template a été validé et testé avec Claude Web. Respecter ces spécifications garantit un serveur MCP fonctionnel.*