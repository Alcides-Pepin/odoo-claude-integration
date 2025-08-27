# Guide d'utilisation

## Vue d'ensemble

Le serveur MCP Odoo fournit une interface standardisée pour interagir avec votre système Odoo via Claude. Une fois configuré, vous pouvez utiliser les outils directement dans Claude Web.

## Utilisation dans Claude Web

### Test de connectivité

Commencez toujours par tester la connectivité :

```
Peux-tu utiliser l'outil ping pour vérifier que le serveur MCP fonctionne ?
```

### Vérification de la santé Odoo

```
Lance un health check d'Odoo pour vérifier que tout fonctionne correctement.
```

## Exemples d'utilisation

### 1. Découverte de modèles

```
Trouve tous les modèles Odoo liés aux ventes.
```

```
Découvre les modèles contenant le mot "partner".
```

### 2. Information sur les champs

```
Montre-moi tous les champs du modèle res.partner.
```

```
Quels sont les champs disponibles pour le modèle sale.order ?
```

### 3. Recherche de données

```
Trouve les 10 premiers partenaires dans Odoo.
```

```
Recherche tous les clients dont le nom contient "john".
```

```
Montre-moi les commandes de vente créées aujourd'hui.
```

### 4. Opérations CRUD avec odoo_execute

#### Créer un enregistrement
```
Crée un nouveau partenaire avec le nom "Test Company" et l'email "test@company.com".
```

#### Lire des enregistrements
```
Lis les informations du partenaire avec l'ID 1.
```

#### Mettre à jour un enregistrement
```
Mets à jour le partenaire ID 1 pour changer son téléphone à "123-456-7890".
```

#### Compter des enregistrements
```
Compte combien de partenaires sont des clients.
```

## Filtres et domaines Odoo

### Syntaxe des domaines

Les domaines Odoo utilisent une syntaxe spécifique :

- **Égalité :** `[['field', '=', 'value']]`
- **Contient :** `[['field', 'ilike', '%value%']]`
- **Comparaisons :** `[['field', '>', 100]]`
- **ET logique :** `[['field1', '=', 'value1'], ['field2', '>', 10]]`
- **OU logique :** `['|', ['field1', '=', 'value1'], ['field2', '=', 'value2']]`

### Exemples de recherches avancées

```
Trouve tous les partenaires qui sont des clients ET des fournisseurs.
```

```
Recherche les factures dont le montant est supérieur à 1000€.
```

```
Montre les commandes de vente en état "draft" ou "sent".
```

## Pagination

Pour les grandes quantités de données :

```
Montre les 50 premiers partenaires, triés par nom.
```

```
Montre la page suivante des résultats (offset 50).
```

## Bonnes pratiques

### 1. Commencer par la découverte
Avant de travailler avec un modèle, découvrez ses champs :
```
Montre-moi les champs du modèle [nom_du_modèle].
```

### 2. Tester avec de petites limites
Commencez avec `limit=5` ou `limit=10` pour tester vos requêtes.

### 3. Utiliser des filtres appropriés
Évitez de récupérer tous les enregistrements sans filtre sur de gros modèles.

### 4. Vérifier les permissions
Si une opération échoue, vérifiez que votre utilisateur Odoo a les droits nécessaires.

## Exemples de workflow complet

### Workflow : Gestion des prospects

1. **Découvrir le modèle :**
   ```
   Trouve les modèles liés aux prospects ou CRM.
   ```

2. **Analyser les champs :**
   ```
   Quels champs sont disponibles pour crm.lead ?
   ```

3. **Rechercher des prospects :**
   ```
   Trouve tous les prospects en statut "nouveau".
   ```

4. **Créer un nouveau prospect :**
   ```
   Crée un nouveau prospect avec les informations suivantes...
   ```

### Workflow : Analyse des ventes

1. **Rechercher les commandes :**
   ```
   Trouve toutes les commandes de vente de ce mois.
   ```

2. **Analyser les montants :**
   ```
   Calcule le total des ventes de cette semaine.
   ```

3. **Identifier les top clients :**
   ```
   Quels sont les clients avec le plus de commandes ?
   ```