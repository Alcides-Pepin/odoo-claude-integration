# Référence des outils MCP

## Vue d'ensemble

Le serveur MCP Odoo fournit 6 outils principaux pour interagir avec votre système Odoo.

## 1. ping

**Description :** Test de connectivité du serveur MCP.

**Paramètres :** Aucun

**Utilisation :**
```json
{
  "tool": "ping"
}
```

**Réponse :**
```json
{
  "status": "ok",
  "message": "Oui le serveur marche",
  "timestamp": "2025-01-27T10:30:00",
  "server": "Odoo MCP Server"
}
```

---

## 2. odoo_health_check

**Description :** Vérification complète de la santé de la connexion Odoo.

**Paramètres :** Aucun

**Tests effectués :**
- Test de connexion au serveur
- Test d'authentification
- Test d'accès à la base de données
- Test de performance

**Utilisation :**
```json
{
  "tool": "odoo_health_check"
}
```

**Réponse :**
```json
{
  "status": "success|warning|error",
  "report": "Rapport détaillé avec symboles ✓/✗/⚠",
  "timestamp": "2025-01-27T10:30:00"
}
```

---

## 3. odoo_discover_models

**Description :** Découverte des modèles Odoo disponibles avec recherche optionnelle.

**Paramètres :**
- `search_term` (string, optionnel) : Terme de recherche pour filtrer les modèles

**Utilisation :**
```json
{
  "tool": "odoo_discover_models",
  "parameters": {
    "search_term": "partner"
  }
}
```

**Réponse :**
```json
{
  "status": "success",
  "total_found": 5,
  "search_term": "partner",
  "models": [
    {
      "model": "res.partner",
      "name": "Contact",
      "description": "Partners (customers, suppliers, etc.)"
    }
  ]
}
```

---

## 4. odoo_get_model_fields

**Description :** Obtient les informations détaillées sur tous les champs d'un modèle.

**Paramètres :**
- `model_name` (string, requis) : Nom technique du modèle (ex: 'res.partner')

**Utilisation :**
```json
{
  "tool": "odoo_get_model_fields",
  "parameters": {
    "model_name": "res.partner"
  }
}
```

**Réponse :**
```json
{
  "status": "success",
  "model": "res.partner",
  "total_fields": 25,
  "fields": [
    {
      "name": "name",
      "label": "Name",
      "type": "char",
      "required": true,
      "readonly": false
    },
    {
      "name": "parent_id",
      "label": "Parent Company",
      "type": "many2one",
      "required": false,
      "readonly": false,
      "relation": "res.partner"
    }
  ]
}
```

---

## 5. odoo_search

**Description :** Recherche et récupération d'enregistrements avec filtrage avancé et pagination.

**Paramètres :**
- `model` (string, requis) : Modèle à interroger
- `domain` (list, optionnel) : Filtre de domaine Odoo
- `fields` (list, optionnel) : Liste des champs à retourner
- `limit` (int, optionnel) : Nombre max d'enregistrements (défaut: 10, max: 100)
- `offset` (int, optionnel) : Nombre d'enregistrements à ignorer (pagination)
- `order` (string, optionnel) : Ordre de tri (ex: 'name desc, id')

**Utilisation :**
```json
{
  "tool": "odoo_search",
  "parameters": {
    "model": "res.partner",
    "domain": [["is_company", "=", true]],
    "fields": ["name", "email", "phone"],
    "limit": 5,
    "order": "name"
  }
}
```

**Réponse :**
```json
{
  "status": "success",
  "model": "res.partner",
  "total_count": 150,
  "returned_count": 5,
  "offset": 0,
  "limit": 5,
  "domain": [["is_company", "=", true]],
  "has_more": true,
  "next_offset": 5,
  "records": [
    {
      "id": 1,
      "name": "My Company",
      "email": "contact@mycompany.com",
      "phone": "+1234567890"
    }
  ]
}
```

---

## 6. odoo_execute

**Description :** Exécuteur générique pour toutes les méthodes Odoo (CRUD et autres).

**Paramètres :**
- `model` (string, requis) : Nom du modèle Odoo
- `method` (string, requis) : Méthode à exécuter
- `args` (list, optionnel) : Arguments positionnels
- `kwargs` (dict, optionnel) : Arguments nommés

**Sécurité :** Certaines opérations dangereuses sont bloquées par la blacklist de sécurité.

### Opérations CRUD courantes

#### CREATE
```json
{
  "tool": "odoo_execute",
  "parameters": {
    "model": "res.partner",
    "method": "create",
    "args": [{"name": "New Partner", "email": "new@partner.com"}]
  }
}
```

#### READ
```json
{
  "tool": "odoo_execute",
  "parameters": {
    "model": "res.partner",
    "method": "read",
    "args": [[1], ["name", "email"]]
  }
}
```

#### UPDATE (WRITE)
```json
{
  "tool": "odoo_execute",
  "parameters": {
    "model": "res.partner",
    "method": "write",
    "args": [[1], {"phone": "+1234567890"}]
  }
}
```

#### DELETE (UNLINK)
```json
{
  "tool": "odoo_execute",
  "parameters": {
    "model": "res.partner",
    "method": "unlink",
    "args": [[1]]
  }
}
```

#### SEARCH_COUNT
```json
{
  "tool": "odoo_execute",
  "parameters": {
    "model": "res.partner",
    "method": "search_count",
    "args": [[["is_company", "=", true]]]
  }
}
```

**Réponse générique :**
```json
{
  "status": "success",
  "model": "res.partner",
  "method": "create",
  "result": 123,
  "timestamp": "2025-01-27T10:30:00"
}
```

## Gestion d'erreurs

Tous les outils retournent des erreurs dans le même format :

```json
{
  "error": "Description de l'erreur détaillée"
}
```

## Blacklist de sécurité

Certaines opérations sont interdites pour des raisons de sécurité :

- `('res.users', 'unlink')` - Suppression d'utilisateurs
- `('ir.model', 'unlink')` - Suppression de modèles
- `('ir.model.fields', 'unlink')` - Suppression de champs
- `('ir.module.module', 'button_immediate_uninstall')` - Désinstallation de modules

## Types de champs Odoo courants

| Type | Description | Exemple |
|------|-------------|---------|
| `char` | Texte court | Nom, email |
| `text` | Texte long | Description, notes |
| `integer` | Nombre entier | Quantité, âge |
| `float` | Nombre décimal | Prix, pourcentage |
| `boolean` | Vrai/Faux | Actif, archivé |
| `date` | Date | Date de naissance |
| `datetime` | Date et heure | Date de création |
| `many2one` | Relation vers un enregistrement | Client, produit |
| `one2many` | Relation vers plusieurs enregistrements | Lignes de commande |
| `many2many` | Relation plusieurs vers plusieurs | Tags, catégories |
| `selection` | Liste de choix | État, priorité |