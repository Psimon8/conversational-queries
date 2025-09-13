# 🔍 Optimiseur de Requêtes Conversationnelles SEO

Une application Streamlit qui utilise l'IA et les suggestions Google pour identifier et optimiser les meilleures requêtes conversationnelles pour vos mots-clés SEO.

## 🚀 Fonctionnalités

- **Analyse basée sur les suggestions Google** pour des données de recherche réelles
- **Génération automatique de questions conversationnelles** via GPT-4o mini
- **Consolidation intelligente** avec déduplication et scoring de pertinence
- **Configuration flexible** du nombre de suggestions et questions finales
- **Export professionnel** en Excel formaté et JSON avec métadonnées
- **Interface utilisateur intuitive** avec visualisations interactives

## 🛠️ Installation

1. Clonez le repository :
```bash
git clone <repository-url>
cd conversational-queries
```

2. Installez les dépendances :
```bash
pip install -r requirements.txt
```

3. Lancez l'application :
```bash
streamlit run app.py
```

## 🎯 Utilisation

1. **Configurez votre clé API OpenAI** dans la barre latérale
2. **Entrez vos mots-clés** (un par ligne) dans la zone de texte
3. **Ajustez les paramètres** : nombre de suggestions Google et questions finales
4. **Lancez l'analyse** et obtenez vos requêtes conversationnelles optimisées
5. **Exportez les résultats** en Excel ou JSON pour votre stratégie SEO

## 🔄 Processus d'analyse en 4 étapes

### Étape 1 : Collecte des suggestions Google
- Récupération automatique des suggestions pour chaque mot-clé
- Données de recherche réelles et actuelles

### Étape 2 : Génération de questions conversationnelles
- 10 questions par suggestion Google via GPT-4o mini
- Optimisées pour la recherche vocale et conversationnelle

### Étape 3 : Consolidation intelligente
- Déduplication avec détection des similitudes
- Scoring de pertinence basé sur les occurrences

### Étape 4 : Export optimisé
- Tri par pertinence décroissante
- Format professionnel Excel et JSON

## 📊 Format d'export

Les résultats sont organisés en 3 colonnes principales :
- **Colonne A** : Requêtes Conversationnelles
- **Colonne B** : Suggestion Google associée
- **Colonne C** : Mot-clé d'origine

## 🔧 Configuration requise

- Python 3.7+
- Clé API OpenAI (GPT-4o mini)
- Connexion internet stable pour les suggestions Google

## 📈 Avantages SEO

- **Recherche vocale** : Questions naturelles et conversationnelles
- **Données réelles** : Basé sur les suggestions Google actuelles
- **Optimisation ciblée** : Questions liées aux intentions de recherche
- **Contenu FAQ** : Prêt pour l'intégration dans vos pages
- **Long tail** : Capture des requêtes spécifiques et moins concurrentielles

## 🎯 Cas d'usage

- **E-commerce** : Questions produits et comparaisons
- **Services locaux** : Requêtes géolocalisées
- **Formation** : Questions pédagogiques et explicatives
- **Santé** : Questions symptômes et traitements
- **Voyage** : Questions destinations et planification
- **Finance** : Questions conseils et comparatifs