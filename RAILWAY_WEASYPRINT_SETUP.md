# Configuration Railway pour WeasyPrint

## 🎯 Objectif

Déployer l'application Python avec WeasyPrint sur Railway. WeasyPrint nécessite des bibliothèques système (Cairo, Pango, GObject) qui doivent être installées via Nixpacks.

---

## ⚠️ Note importante sur Nixpacks

**Nixpacks est en mode maintenance** depuis que Railway a introduit Railpack. Cependant, les applications existantes continuent de fonctionner avec Nixpacks, et c'est la méthode la plus simple pour notre cas d'usage.

---

## 📋 Méthodes de configuration

Railway supporte **2 méthodes** pour ajouter les dépendances système nécessaires à WeasyPrint. Choisis celle qui te convient le mieux.

---

## 🚀 Méthode 1 : Variable d'environnement (LA PLUS SIMPLE)

### Étape 1 : Aller dans les paramètres du service sur Railway

1. Va sur [railway.app](https://railway.app)
2. Sélectionne ton projet
3. Clique sur ton service (ex: `web` ou `serveur_mcp_claude`)
4. Clique sur l'onglet **"Variables"**

### Étape 2 : Ajouter la variable d'environnement

Clique sur **"New Variable"** et ajoute :

**Nom de la variable :**
```
NIXPACKS_PKGS
```

**Valeur :**
```
cairo pango gobject-introspection glib libffi pkg-config gdk-pixbuf
```

### Étape 3 : Redéployer

1. Railway va automatiquement redéployer l'application
2. Ou force un redéploiement en cliquant sur **"Deploy"** → **"Redeploy"**

### Étape 4 : Vérifier les logs

Dans l'onglet **"Deployments"**, vérifie les logs de build. Tu devrais voir :
```
====== Installing Nix packages ======
cairo
pango
gobject-introspection
glib
libffi
pkg-config
gdk-pixbuf
```

---

## 🔧 Méthode 2 : Fichier nixpacks.toml (PLUS PROPRE)

### Étape 1 : Créer le fichier nixpacks.toml

À la racine de ton projet, crée un fichier `nixpacks.toml` :

```toml
# nixpacks.toml - Configuration Railway pour WeasyPrint

[phases.setup]
# Note: "..." est important - il étend les packages au lieu de les remplacer
nixPkgs = [
    "...",
    "cairo",
    "pango",
    "gobject-introspection",
    "glib",
    "libffi",
    "pkg-config",
    "gdk-pixbuf",
    "fontconfig",
    "freetype"
]
```

**Explication des packages :**
- `cairo` : Moteur de rendu graphique 2D
- `pango` : Moteur de layout de texte
- `gobject-introspection` : Introspection pour bibliothèques GObject
- `glib` : Bibliothèque utilitaire C de base
- `libffi` : Foreign Function Interface
- `pkg-config` : Outil pour interroger les bibliothèques installées
- `gdk-pixbuf` : Manipulation d'images
- `fontconfig` : Configuration des polices
- `freetype` : Moteur de rendu de polices

### Étape 2 : Commit et push

```bash
git add nixpacks.toml
git commit -m "feat: Add nixpacks config for WeasyPrint system dependencies"
git push origin feature/pdf-activity-report
```

### Étape 3 : Railway détectera automatiquement le fichier

Railway lit automatiquement `nixpacks.toml` s'il existe à la racine du projet.

---

## 🧪 Tester le déploiement

### Option A : Via l'endpoint HTTP

Une fois déployé, teste avec curl :

```bash
curl https://ton-app.up.railway.app/test_pdf_attachment
```

### Option B : Via Claude Web (MCP tool)

Dans Claude Web, utilise l'outil MCP `test_pdf_attachment` avec :
- `project_id`: 151
- `task_column_id`: 726

### Résultat attendu

```json
{
  "status": "success",
  "message": "PDF generation and attachment test completed successfully!",
  "task_id": 12345,
  "task_url": "https://your-odoo.com/web#id=12345...",
  "attachment_id": 67890,
  "attachment_filename": "test_pdf_20250124_143022.pdf",
  "pdf_size_bytes": 8432,
  "tests_passed": [
    "WeasyPrint PDF generation",
    "HTML to PDF conversion with CSS styling",
    "ir.attachment creation via XML-RPC",
    "PDF attachment to project.task"
  ]
}
```

**Vérifie dans Odoo :**
- Tâche créée avec le nom `[TEST PDF] 2025-...`
- PDF attaché dans les fichiers joints
- PDF téléchargeable avec contenu "Hello World" formaté

---

## 🐛 Troubleshooting

### Erreur : "cannot load library 'gobject-2.0-0'"

**Cause :** Les dépendances système ne sont pas installées.

**Solution :**
1. Vérifie que `NIXPACKS_PKGS` est bien configuré (Méthode 1)
2. OU que `nixpacks.toml` existe et est bien formaté (Méthode 2)
3. Force un redéploiement complet

### Erreur : "Nixpacks was unable to generate a build plan"

**Cause :** Fichier `nixpacks.toml` mal formaté ou problème de détection Python.

**Solution :**
1. Vérifie la syntaxe TOML (pas de fautes de frappe)
2. Assure-toi que `requirements.txt` existe
3. Essaie la Méthode 1 (variable d'environnement) en attendant

### Les logs de build ne montrent pas l'installation des packages

**Cause :** Railway n'a pas détecté la configuration.

**Solution :**
1. Vérifie que le fichier `nixpacks.toml` est **à la racine** du projet
2. Force un redéploiement complet (pas juste un restart)
3. Vérifie que la variable d'environnement est bien enregistrée

### Le PDF est généré mais mal formaté

**Cause :** Problème de polices ou de rendu CSS.

**Solution :**
1. Ajoute `fontconfig` et `freetype` aux nixPkgs si pas déjà fait
2. Simplifie le CSS (évite les propriétés CSS3 avancées)
3. Teste localement avec les mêmes polices

---

## 📚 Ressources

- [Railway Nixpacks Documentation](https://docs.railway.com/reference/nixpacks)
- [Nixpacks Configuration File Reference](https://nixpacks.com/docs/configuration/file)
- [WeasyPrint Installation Guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html)
- [Nix Package Search](https://search.nixos.org/packages)
- [Railway Help Station - WeasyPrint Issues](https://station.railway.com/questions/error-installing-weasy-print-a30df387)

---

## 🎉 Prochaines étapes après validation

Une fois que `/test_pdf_attachment` fonctionne en production :

1. ✅ Valider que WeasyPrint et ir.attachment fonctionnent
2. 🚀 Implémenter la génération PDF pour les rapports d'activité
3. 📝 Séparer le tableau récapitulatif (HTML) de la timeline exhaustive (PDF)
4. 🔄 Merger la branche `feature/pdf-activity-report` dans `main`

---

## 💡 Recommandation finale

**Commence par la Méthode 1 (variable d'environnement)** car :
- ✅ Plus rapide à tester
- ✅ Pas besoin de commit/push
- ✅ Tu peux modifier la liste de packages facilement
- ✅ Si ça marche, tu pourras toujours créer le `nixpacks.toml` après

**Passe à la Méthode 2** uniquement si :
- Tu veux versionner la configuration
- Tu veux partager la config avec d'autres environnements
- La Méthode 1 fonctionne et tu veux la rendre permanente
