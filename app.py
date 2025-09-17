import streamlit as st
from openai import OpenAI
import pandas as pd
import json
import time
from collections import Counter
import re
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from io import BytesIO

# Import du module de génération de questions
from question_generator import QuestionGenerator

# Import du module DataForSEO
from dataforseo_client import DataForSEOClient

# Configuration de la page Streamlit
st.set_page_config(
    page_title="SEO Conversational Queries Optimizer",
    page_icon="🔍",
    layout="wide"
)

# Initialisation du session state
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'analysis_metadata' not in st.session_state:
    st.session_state.analysis_metadata = None

# Titre principal
st.title("🔍 Optimiseur de Requêtes Conversationnelles SEO")
st.subheader("Analyse basée sur les suggestions Google pour l'optimisation SEO")

# Configuration dans la sidebar
st.sidebar.header("⚙️ Configuration")
api_key = st.sidebar.text_input("Clé API OpenAI", type="password", help="Votre clé API OpenAI pour GPT-4o mini")

# Configuration DataForSEO
st.sidebar.header("📊 DataForSEO (optionnel)")
enable_dataforseo = st.sidebar.checkbox(
    "Enrichir avec DataForSEO",
    value=False,
    help="Ajouter les volumes de recherche et suggestions Ads"
)

dataforseo_client = DataForSEOClient()

if enable_dataforseo:
    dataforseo_login = st.sidebar.text_input("Login DataForSEO", type="default")
    dataforseo_password = st.sidebar.text_input("Mot de passe DataForSEO", type="password")
    
    # Sélecteurs géographiques
    col_lang, col_country = st.sidebar.columns(2)
    with col_lang:
        dataforseo_language = st.selectbox(
            "Langue DataForSEO",
            options=['fr', 'en', 'es', 'de', 'it'],
            index=0,
            help="Langue pour les données DataForSEO"
        )
    
    with col_country:
        dataforseo_location = st.selectbox(
            "Pays cible",
            options=['fr', 'en-us', 'en-gb', 'es', 'de', 'it', 'ca', 'au'],
            index=0,
            help="Pays pour la géolocalisation des volumes"
        )
    
    min_search_volume = st.sidebar.slider(
        "Volume de recherche minimum",
        min_value=0,
        max_value=1000,
        value=10,
        help="Volume mensuel minimum pour conserver un mot-clé"
    )
    
    if dataforseo_login and dataforseo_password:
        dataforseo_client.set_credentials(dataforseo_login, dataforseo_password)
        
        # Test des credentials
        if st.sidebar.button("🔍 Tester les credentials"):
            is_valid, message = dataforseo_client.test_credentials()
            if is_valid:
                st.sidebar.success(message)
            else:
                st.sidebar.error(message)
        
        st.sidebar.success("✅ DataForSEO configuré")
    else:
        st.sidebar.warning("⚠️ Credentials DataForSEO requis")

# Options de génération dans la sidebar
st.sidebar.header("🎯 Options d'analyse")
generate_questions = st.sidebar.checkbox(
    "Générer questions conversationnelles",
    value=True,
    help="Générer des questions conversationnelles à partir des suggestions"
)

if generate_questions:
    final_questions_count = st.sidebar.slider(
        "Nombre de questions finales",
        min_value=5,
        max_value=100,
        value=20,
        help="Nombre de questions conversationnelles à conserver après consolidation"
    )

lang = st.sidebar.selectbox(
    "Langue", 
    ["fr", "en", "es", "de", "it"], 
    index=0,
    help="Langue pour les suggestions Google"
)

# Ajouter les liens sociaux en bas de la sidebar
st.sidebar.markdown(
    """
    <div style="position: fixed; bottom: 10px; left: 20px;">
        <a href="https://github.com/Psimon8" target="_blank" style="text-decoration: none;">
            <img src="https://github.githubassets.com/assets/pinned-octocat-093da3e6fa40.svg" 
                 alt="GitHub Simon le Coz" style="width:20px; vertical-align: middle; margin-right: 5px;">
            <span style="color: white; font-size: 14px;"></span>
        </a>    
        <a href="https://www.linkedin.com/in/simon-le-coz/" target="_blank" style="text-decoration: none;">
            <img src="https://static.licdn.com/aero-v1/sc/h/8s162nmbcnfkg7a0k8nq9wwqo" 
                 alt="LinkedIn Simon Le Coz" style="width:20px; vertical-align: middle; margin-right: 5px;">
            <span style="color: white; font-size: 14px;"></span>
        </a>
        <a href="https://twitter.com/lekoz_simon" target="_blank" style="text-decoration: none;">
            <img src="https://abs.twimg.com/favicons/twitter.3.ico" 
                 alt="Twitter Simon Le Coz" style="width:20px; vertical-align: middle; margin-right: 5px;">
            <span style="color: white; font-size: 14px;">@lekoz_simon</span>
        </a>
    </div>
    """,
    unsafe_allow_html=True
)

# Fonctions utilitaires pour les suggestions Google
def get_google_suggestions(keyword, lang='fr', max_suggestions=10):
    """Récupère les suggestions Google pour un mot-clé"""
    url = "https://suggestqueries.google.com/complete/search"
    params = {
        "q": keyword,
        "gl": lang,
        "client": "chrome",
        "_": str(int(time.time() * 1000))
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        suggestions = response.json()[1][:max_suggestions]
        return suggestions
    except Exception as e:
        st.error(f"❌ Erreur lors de la récupération des suggestions pour '{keyword}': {str(e)}")
        return []

def get_google_suggestions_multilevel(keyword, lang='fr', level1_count=10, level2_count=5, level3_count=0, enable_level2=True, enable_level3=False):
    """Récupère les suggestions Google à plusieurs niveaux"""
    all_suggestions = []
    processed_suggestions = set()  # Pour éviter les doublons
    
    # Ajouter le mot-clé de base (niveau 0)
    all_suggestions.append({
        'Mot-clé': keyword,
        'Niveau': 0,
        'Suggestion Google': keyword,
        'Parent': None
    })
    processed_suggestions.add(keyword.lower().strip())
    
    # Niveau 1: Suggestions directes du mot-clé
    level1_suggestions = get_google_suggestions(keyword, lang, level1_count)
    
    for suggestion in level1_suggestions:
        normalized = suggestion.lower().strip()
        if normalized not in processed_suggestions:
            all_suggestions.append({
                'Mot-clé': keyword,
                'Niveau': 1,
                'Suggestion Google': suggestion,
                'Parent': keyword
            })
            processed_suggestions.add(normalized)
    
    # Niveau 2: Suggestions des suggestions (si activé)
    if enable_level2:
        level2_parents = []
        for suggestion_data in all_suggestions.copy():  # Copie pour éviter la modification pendant l'itération
            if suggestion_data['Niveau'] == 1:  # Traiter uniquement les suggestions de niveau 1
                level2_suggestions = get_google_suggestions(suggestion_data['Suggestion Google'], lang, level2_count)
                
                for l2_suggestion in level2_suggestions:
                    normalized = l2_suggestion.lower().strip()
                    if normalized not in processed_suggestions:
                        new_suggestion = {
                            'Mot-clé': keyword,
                            'Niveau': 2,
                            'Suggestion Google': l2_suggestion,
                            'Parent': suggestion_data['Suggestion Google']
                        }
                        all_suggestions.append(new_suggestion)
                        level2_parents.append(new_suggestion)
                        processed_suggestions.add(normalized)
                
                time.sleep(0.3)  # Délai entre les requêtes pour éviter le rate limiting
        
        # Niveau 3: Suggestions des suggestions de niveau 2 (si activé)
        if enable_level3:
            for suggestion_data in level2_parents:  # Traiter uniquement les suggestions de niveau 2
                level3_suggestions = get_google_suggestions(suggestion_data['Suggestion Google'], lang, level3_count)
                
                for l3_suggestion in level3_suggestions:
                    normalized = l3_suggestion.lower().strip()
                    if normalized not in processed_suggestions:
                        all_suggestions.append({
                            'Mot-clé': keyword,
                            'Niveau': 3,
                            'Suggestion Google': l3_suggestion,
                            'Parent': suggestion_data['Suggestion Google']
                        })
                        processed_suggestions.add(normalized)
                
                time.sleep(0.3)  # Délai entre les requêtes pour éviter le rate limiting
    
    return all_suggestions

def consolidate_and_deduplicate(questions_data, target_count):
    """Consolide et déduplique les questions en gardant les plus pertinentes"""
    if not questions_data:
        return []
    
    # Créer un dictionnaire pour comptabiliser les occurrences et garder les métadonnées
    question_stats = {}
    
    for item in questions_data:
        question = item['Question Conversationnelle'].strip()
        # Normalisation pour détecter les similitudes
        normalized = re.sub(r'[^\w\s]', '', question.lower()).strip()
        
        if normalized not in question_stats:
            question_stats[normalized] = {
                'original_question': question,
                'count': 1,
                'suggestions': [item['Suggestion Google']],
                'keywords': [item['Mot-clé']],
                'first_occurrence': item
            }
        else:
            question_stats[normalized]['count'] += 1
            if item['Suggestion Google'] not in question_stats[normalized]['suggestions']:
                question_stats[normalized]['suggestions'].append(item['Suggestion Google'])
            if item['Mot-clé'] not in question_stats[normalized]['keywords']:
                question_stats[normalized]['keywords'].append(item['Mot-clé'])
    
    # Trier par nombre d'occurrences (pertinence) et prendre les meilleures
    sorted_questions = sorted(
        question_stats.values(),
        key=lambda x: (x['count'], len(x['keywords'])),
        reverse=True
    )
    
    # Prendre le nombre demandé de questions
    final_questions = []
    for i, q_data in enumerate(sorted_questions[:target_count]):
        final_questions.append({
            'Requêtes Conversationnelles': q_data['original_question'],
            'Suggestion': q_data['suggestions'][0],  # Première suggestion associée
            'Mot-clé': q_data['keywords'][0],  # Premier mot-clé associé
            'Score_Pertinence': q_data['count'],
            'Nb_Keywords': len(q_data['keywords']),
            'Nb_Suggestions': len(q_data['suggestions'])
        })
    
    return final_questions

def create_excel_file(df):
    """Crée un fichier Excel avec formatage"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Questions_Conversationnelles')
        
        # Accéder au workbook et worksheet pour le formatage
        workbook = writer.book
        worksheet = writer.sheets['Questions_Conversationnelles']
        
        # Ajuster la largeur des colonnes
        worksheet.column_dimensions['A'].width = 60  # Questions
        worksheet.column_dimensions['B'].width = 50  # Suggestions Google
        worksheet.column_dimensions['C'].width = 25  # Mots-clés
        worksheet.column_dimensions['D'].width = 25  # Thème
        worksheet.column_dimensions['E'].width = 20  # Intention
        worksheet.column_dimensions['F'].width = 15  # Importance
        
        # Formatage de l'en-tête
        from openpyxl.styles import Font, PatternFill
        header_font = Font(bold=True)
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        
        for cell in worksheet[1]:
            cell.font = header_font
            cell.fill = header_fill
    
    output.seek(0)
    return output

# Export des résultats dans la sidebar (après la définition des fonctions)
if 'analysis_results' in st.session_state and st.session_state.analysis_results is not None:
    results = st.session_state.analysis_results
    metadata = st.session_state.analysis_metadata
    
    st.sidebar.header("📤 Export des résultats")
    
    # Vérifier que les questions ont été générées avant d'afficher les exports
    if (metadata['generate_questions'] and 
        results.get('stage') == 'questions_generated' and 
        results.get('final_consolidated_data') and 
        len(results['final_consolidated_data']) > 0):
        
        # Export Excel des questions avec thèmes et suggestions
        excel_df = pd.DataFrame(results['final_consolidated_data'])
        excel_display = excel_df[['Question Conversationnelle', 'Suggestion Google', 'Mot-clé', 'Thème', 'Intention', 'Score_Importance']].copy()
        excel_display.columns = ['Questions Conversationnelles', 'Suggestion Google', 'Mot-clé', 'Thème', 'Intention', 'Importance']
        
        excel_file = create_excel_file(excel_display)
        st.sidebar.download_button(
            label="📊 Questions (Excel)",
            data=excel_file,
            file_name="questions_conversationnelles_themes.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_questions_themes_excel",
            use_container_width=True
        )
    
    # Export Excel des suggestions (toujours disponible après analyse)
    if results.get('all_suggestions') and len(results['all_suggestions']) > 0:
        suggestions_df = pd.DataFrame(results['all_suggestions'])
        suggestions_display = suggestions_df[['Mot-clé', 'Suggestion Google', 'Niveau', 'Parent']].copy()
        suggestions_excel = create_excel_file(suggestions_display)
        st.sidebar.download_button(
            label="🔍 Suggestions (Excel)",
            data=suggestions_excel,
            file_name="suggestions_google_multiniveaux.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_suggestions_excel",
            use_container_width=True
        )
    
    # Export JSON complet (adapté selon l'étape)
    if results.get('all_suggestions'):
        export_json = {
            "metadata": {
                **metadata,
                "total_suggestions": len(results.get('all_suggestions', [])),
                "level_distribution": results.get('level_counts', {}),
                "stage": results.get('stage', 'unknown')
            },
            "suggestions": results.get('all_suggestions', []),
            "themes_analysis": results.get('themes_analysis', {}),
            "questions": results.get('final_consolidated_data', []) if metadata.get('generate_questions') and results.get('stage') == 'questions_generated' else []
        }
        
        json_data = json.dumps(export_json, ensure_ascii=False, indent=2)
        st.sidebar.download_button(
            label="📋 Données (JSON)",
            data=json_data,
            file_name="analyse_complete_multiniveaux.json",
            mime="application/json",
            key="download_json",
            use_container_width=True
        )
    
    # Afficher l'état actuel dans la sidebar
    if results.get('stage') == 'themes_analyzed' and metadata.get('generate_questions'):
        st.sidebar.info("📋 Sélectionnez vos thèmes pour générer les questions")
    elif results.get('stage') == 'questions_generated':
        st.sidebar.success("✅ Questions générées - Exports disponibles")
    elif results.get('all_suggestions'):
        st.sidebar.success("✅ Suggestions collectées - Export disponible")

def analyze_suggestion_relevance(keyword, suggestion, level):
    """Analyse la pertinence d'une suggestion par rapport au mot-clé principal"""
    if not client:
        return {"category": "unknown", "relevance_score": 0, "intent": "unknown"}
    
    prompt = f"""
    Analyse la suggestion Google "{suggestion}" (niveau {level}) par rapport au mot-clé principal "{keyword}".
    
    Évalue selon ces critères :
    1. PERTINENCE (0-10) : À quel point la suggestion est-elle liée au mot-clé principal ?
    2. CATÉGORIE : Classe la suggestion dans une de ces catégories :
       - "core" : Directement lié au mot-clé principal
       - "related" : Lié mais avec une nuance différente
       - "complementary" : Complémentaire ou service associé
       - "geographic" : Variation géographique
       - "temporal" : Variation temporelle (horaires, saisons...)
       - "competitive" : Comparaison ou alternative
       - "informational" : Recherche d'information
       - "transactional" : Intention d'achat/réservation
       - "navigational" : Recherche d'un lieu/site spécifique
    
    3. INTENTION : Détermine l'intention de recherche :
       - "informational" : Cherche de l'information
       - "navigational" : Cherche à aller quelque part
       - "transactional" : Veut acheter/réserver
       - "local" : Recherche locale
    
    Réponds UNIQUEMENT au format JSON :
    {{"relevance_score": X, "category": "xxx", "intent": "xxx", "justification": "courte explication"}}
    """
    
    try:
        response = call_gpt4o_mini(prompt)
        if response:
            # Nettoyer la réponse pour extraire le JSON
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:-3]
            elif response_clean.startswith('```'):
                response_clean = response_clean[3:-3]
            
            return json.loads(response_clean)
    except Exception as e:
        st.warning(f"Erreur analyse suggestion '{suggestion}': {str(e)}")
    
    # Fallback basique si l'analyse GPT échoue
    return {
        "relevance_score": 5, 
        "category": "related", 
        "intent": "informational",
        "justification": "Analyse automatique indisponible"
    }

def generate_contextual_questions(keyword, suggestion, analysis_data, num_questions=3):
    """Génère des questions conversationnelles contextuelles basées sur l'analyse"""
    if not client:
        return []
    
    category = analysis_data.get('category', 'related')
    intent = analysis_data.get('intent', 'informational')
    relevance = analysis_data.get('relevance_score', 5)
    
    # Adapter le prompt selon la catégorie et l'intention
    context_prompts = {
        "core": "questions directement liées au cœur du sujet",
        "related": "questions sur les aspects connexes",
        "complementary": "questions sur les services/produits complémentaires",
        "geographic": "questions géolocalisées",
        "temporal": "questions temporelles (quand, horaires, saisons)",
        "competitive": "questions de comparaison",
        "informational": "questions d'information pratique",
        "transactional": "questions d'achat/réservation",
        "navigational": "questions de localisation/accès"
    }
    
    intent_focus = {
        "informational": "Concentre-toi sur des questions 'comment', 'pourquoi', 'qu'est-ce que'",
        "navigational": "Concentre-toi sur des questions 'où', 'comment accéder', 'comment trouver'",
        "transactional": "Concentre-toi sur des questions 'combien', 'comment acheter/réserver', 'quelles options'",
        "local": "Concentre-toi sur des questions géolocalisées 'près de moi', 'dans ma région'"
    }
    
    prompt = f"""
    Mot-clé principal : "{keyword}"
    Suggestion analysée : "{suggestion}"
    Catégorie : {category} ({context_prompts.get(category, 'questions générales')})
    Intention : {intent} ({intent_focus.get(intent, 'questions générales')})
    Score de pertinence : {relevance}/10
    
    Génère EXACTEMENT {num_questions} questions conversationnelles SEO optimisées qui :
    Sont adaptées à la catégorie "{category}" et l'intention "{intent}"
    Intègrent naturellement le contexte de la suggestion
    Sont formulées comme des questions que les utilisateurs poseraient vraiment
    Sont optimisées pour la recherche vocale
    Se terminent par un point d'interrogation
    Sont de longueur appropriée (ni trop courtes, ni trop longues)
    
    Exemples de formulations selon l'intention :
    - Informational : "Comment...", "Pourquoi...", "Qu'est-ce que..."
    - Transactional : "Combien coûte...", "Où acheter...", "Comment réserver..."
    - Local : "Où trouver... près de moi", "Quel est le meilleur... dans ma ville"
    
    Présente les questions sous forme de liste numérotée de 1 à {num_questions}.
    """
    
    response = call_gpt4o_mini(prompt)
    if response:
        return extract_questions_from_response(response)
    return []

def smart_question_generation(all_suggestions_with_analysis, target_questions):
    """Génère intelligemment les questions en fonction de l'analyse des suggestions"""
    if not all_suggestions_with_analysis:
        return []
    
    # Trier les suggestions par pertinence décroissante
    sorted_suggestions = sorted(
        all_suggestions_with_analysis, 
        key=lambda x: x.get('analysis', {}).get('relevance_score', 0), 
        reverse=True
    )
    
    # Grouper par catégorie et intention pour équilibrer
    categories = {}
    for suggestion in sorted_suggestions:
        analysis = suggestion.get('analysis', {})
        category = analysis.get('category', 'unknown')
        
        if category not in categories:
            categories[category] = []
        categories[category].append(suggestion)
    
    # Calculer la distribution des questions par catégorie
    total_suggestions = len(sorted_suggestions)
    questions_per_suggestion = max(1, target_questions // total_suggestions)
    
    all_generated_questions = []
    questions_generated = 0
    
    # Prioriser les catégories les plus pertinentes
    priority_categories = ['core', 'transactional', 'informational', 'related', 'complementary']
    
    for category in priority_categories:
        if category in categories and questions_generated < target_questions:
            category_suggestions = categories[category][:3]  # Max 3 suggestions par catégorie
            
            for suggestion_data in category_suggestions:
                if questions_generated >= target_questions:
                    break
                
                # Calculer le nombre de questions pour cette suggestion
                remaining_questions = target_questions - questions_generated
                analysis = suggestion_data.get('analysis', {})
                relevance = analysis.get('relevance_score', 5)
                
                # Plus la suggestion est pertinente, plus on génère de questions
                if relevance >= 8:
                    num_questions = min(5, remaining_questions)
                elif relevance >= 6:
                    num_questions = min(3, remaining_questions)
                else:
                    num_questions = min(2, remaining_questions)
                
                if num_questions > 0:
                    questions = generate_contextual_questions(
                        suggestion_data['Mot-clé'],
                        suggestion_data['Suggestion Google'],
                        analysis,
                        num_questions
                    )
                    
                    for question in questions:
                        if questions_generated < target_questions:
                            all_generated_questions.append({
                                'Mot-clé': suggestion_data['Mot-clé'],
                                'Suggestion Google': suggestion_data['Suggestion Google'],
                                'Question Conversationnelle': question,
                                'Niveau': suggestion_data['Niveau'],
                                'Parent': suggestion_data['Parent'],
                                'Catégorie': category,
                                'Intention': analysis.get('intent', 'unknown'),
                                'Score_Pertinence': relevance
                            })
                            questions_generated += 1
    
    # Compléter avec les catégories restantes si nécessaire
    for category, suggestions in categories.items():
        if category not in priority_categories and questions_generated < target_questions:
            for suggestion_data in suggestions:
                if questions_generated >= target_questions:
                    break
                
                remaining_questions = target_questions - questions_generated
                questions = generate_contextual_questions(
                    suggestion_data['Mot-clé'],
                    suggestion_data['Suggestion Google'],
                    suggestion_data.get('analysis', {}),
                    min(2, remaining_questions)
                )
                
                for question in questions:
                    if questions_generated < target_questions:
                        analysis = suggestion_data.get('analysis', {})
                        all_generated_questions.append({
                            'Mot-clé': suggestion_data['Mot-clé'],
                            'Suggestion Google': suggestion_data['Suggestion Google'],
                            'Question Conversationnelle': question,
                            'Niveau': suggestion_data['Niveau'],
                            'Parent': suggestion_data['Parent'],
                            'Catégorie': category,
                            'Intention': analysis.get('intent', 'unknown'),
                            'Score_Pertinence': analysis.get('relevance_score', 5)
                        })
                        questions_generated += 1
    
    return all_generated_questions

def analyze_suggestions_themes(all_suggestions, keyword):
    """Analyse les suggestions pour identifier les thèmes récurrents"""
    if not client or not all_suggestions:
        return []
    
    # Créer une liste des suggestions sans doublons pour analyse
    suggestions_text = []
    for item in all_suggestions:
        if item['Niveau'] > 0:  # Exclure le mot-clé de base
            suggestions_text.append(item['Suggestion Google'])
    
    # Limiter à 50 suggestions max pour l'analyse
    suggestions_sample = list(set(suggestions_text))[:50]
    
    if not suggestions_sample:
        return []
    
    prompt = f"""
    Analyse ces suggestions Google pour le mot-clé principal "{keyword}" et identifie les thèmes récurrents :
    
    Suggestions à analyser :
    {chr(10).join([f"- {s}" for s in suggestions_sample])}
    
    Identifie les 5-10 THÈMES PRINCIPAUX qui ressortent de ces suggestions.
    Pour chaque thème, indique :
    1. Le nom du thème
    2. Les mots-clés/concepts récurrents
    3. L'intention de recherche dominante
    4. Le niveau d'importance (1-5)
    
    Réponds UNIQUEMENT au format JSON :
    {{
        "themes": [
            {{
                "nom": "nom_du_theme",
                "concepts": ["concept1", "concept2"],
                "intention": "informational",
                "importance": 4,
                "exemples_suggestions": ["suggestion1", "suggestion2"]
            }}
        ]
    }}
    """
    
    try:
        response = call_gpt4o_mini(prompt)
        if response:
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:-3]
            elif response_clean.startswith('```'):
                response_clean = response_clean[3:-3]
            
            parsed = json.loads(response_clean)
            return parsed.get('themes', [])
    except Exception as e:
        st.warning(f"Erreur analyse thèmes pour '{keyword}': {str(e)}")
        return []

def generate_questions_from_themes(keyword, themes, target_count):
    """Génère des questions conversationnelles basées sur les thèmes identifiés"""
    if not client or not themes or target_count <= 0:
        return []
    
    # Trier les thèmes par importance
    sorted_themes = sorted(themes, key=lambda x: x.get('importance', 0), reverse=True)
    
    # Calculer la répartition des questions par thème
    questions_per_theme = max(1, target_count // len(sorted_themes))
    remaining_questions = target_count
    
    all_questions = []
    
    for i, theme in enumerate(sorted_themes):
        if remaining_questions <= 0:
            break
        
        # Calculer le nombre de questions pour ce thème
        if i == len(sorted_themes) - 1:  # Dernier thème
            theme_questions = remaining_questions
        else:
            theme_questions = min(questions_per_theme, remaining_questions)
        
        if theme_questions > 0:
            theme_name = theme.get('nom', 'theme')
            concepts = ', '.join(theme.get('concepts', []))
            intention = theme.get('intention', 'informational')
            exemples = ', '.join(theme.get('exemples_suggestions', [])[:3])
            
            prompt = f"""
            Génère EXACTEMENT {theme_questions} questions conversationnelles SEO pour :
            
            Mot-clé principal : "{keyword}"
            Thème : "{theme_name}"
            Concepts clés : {concepts}
            Intention : {intention}
            Exemples de suggestions : {exemples}
            
            Les questions doivent :
            1. Être naturelles et conversationnelles
            2. Intégrer le thème "{theme_name}" de manière naturelle
            3. Correspondre à l'intention "{intention}"
            4. Être optimisées pour la recherche vocale
            5. Se terminer par un point d'interrogation
            6. Être variées et complémentaires
            
            Formulations selon l'intention :
            - Informational : "Comment...", "Pourquoi...", "Qu'est-ce que...", "Quels sont..."
            - Transactional : "Combien coûte...", "Où acheter...", "Comment réserver...", "Quel prix..."
            - Navigational : "Où trouver...", "Comment accéder...", "Quelle adresse..."
            - Local : "... près de moi", "... dans ma ville", "... dans ma région"
            
            Présente les questions sous forme de liste numérotée de 1 à {theme_questions}.
            """
            
            response = call_gpt4o_mini(prompt)
            if response:
                theme_questions_list = extract_questions_from_response(response)
                for question in theme_questions_list[:theme_questions]:
                    all_questions.append({
                        'Question Conversationnelle': question,
                        'Thème': theme_name,
                        'Intention': intention,
                        'Concepts': concepts,
                        'Score_Importance': theme.get('importance', 3)
                    })
                    remaining_questions -= 1
    
    return all_questions

# Création des onglets
tab1, tab2 = st.tabs(["🔍 Analyseur de Requêtes", "📖 Instructions"])

# TAB 1: Analyseur principal
with tab1:
    # Interface principale - Analyse par Suggestions Google
    st.markdown("### 🔍 Analyse basée sur les suggestions Google multi-niveaux")
    
    # Input pour les mots-clés
    keywords_input = st.text_area(
        "🎯 Entrez vos mots-clés (un par ligne)",
        placeholder="restaurant paris\nhôtel luxe\nvoyage écologique",
        help="Entrez un ou plusieurs mots-clés, un par ligne"
    )
    
    # Configuration des niveaux de suggestions
    st.markdown("#### 📊 Configuration des niveaux de suggestions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        level1_count = st.slider(
            "Suggestions niveau 1", 
            min_value=2, 
            max_value=15, 
            value=10,
            help="Nombre de suggestions Google directes pour chaque mot-clé"
        )
    
    with col2:
        level2_count = st.slider(
            "Suggestions niveau 2", 
            min_value=0,
            max_value=15, 
            value=0,
            help="Nombre de suggestions pour chaque suggestion de niveau 1 (0 = désactivé)"
        )
    
    with col3:
        level3_count = st.slider(
            "Suggestions niveau 3", 
            min_value=0,
            max_value=15, 
            value=0,
            help="Nombre de suggestions pour chaque suggestion de niveau 2 (0 = désactivé)"
        )
    
    # Boutons d'action
    col_analyze, col_clear = st.columns([4, 1])
    with col_analyze:
        if keywords_input:
            if generate_questions and not api_key:
                st.warning("⚠️ Veuillez configurer votre clé API OpenAI dans la barre latérale pour générer les questions conversationnelles.")
            elif keywords_input:
                keywords = [kw.strip() for kw in keywords_input.split('\n') if kw.strip()]
                
                # Étape 1: Analyse des suggestions et thèmes
                if st.button("🚀 Analyser les suggestions", type="primary"):
                    if not keywords:
                        st.error("❌ Veuillez entrer au moins un mot-clé")
                    else:
                        # Réinitialiser les résultats précédents
                        st.session_state.analysis_results = None
                        st.session_state.analysis_metadata = None
                        st.session_state.themes_selection = None
                        
                        try:
                            # Progress tracking
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            # Déterminer les niveaux activés
                            enable_level2 = level2_count > 0
                            enable_level3 = level3_count > 0 and enable_level2
                            
                            # Étape 1: Collecte des suggestions multi-niveaux
                            status_text.text("⏳ Étape 1/5: Collecte des suggestions Google multi-niveaux...")
                            
                            all_suggestions = []
                            
                            for i, keyword in enumerate(keywords):
                                keyword_suggestions = get_google_suggestions_multilevel(
                                    keyword, 
                                    lang, 
                                    level1_count, 
                                    level2_count, 
                                    level3_count,
                                    enable_level2,
                                    enable_level3
                                )
                                all_suggestions.extend(keyword_suggestions)
                                
                                progress_bar.progress((i + 1) * 15 // len(keywords))
                                status_text.text(f"⏳ Collecte en cours... {len(all_suggestions)} suggestions trouvées")
                            
                            if not all_suggestions:
                                st.error("❌ Aucune suggestion trouvée")
                            else:
                                # Affichage des statistiques de collecte
                                level_counts = {}
                                for suggestion in all_suggestions:
                                    level = suggestion['Niveau']
                                    level_counts[level] = level_counts.get(level, 0) + 1
                                
                                st.info(f"✅ {len(all_suggestions)} suggestions collectées - Niveau 0: {level_counts.get(0, 0)}, Niveau 1: {level_counts.get(1, 0)}, Niveau 2: {level_counts.get(2, 0)}, Niveau 3: {level_counts.get(3, 0)}")
                                
                                # Nouvelles étapes DataForSEO
                                enriched_data = {}
                                all_enriched_keywords = []
                                
                                if enable_dataforseo and dataforseo_login and dataforseo_password:
                                    # Étape 2: Enrichissement DataForSEO
                                    status_text.text("⏳ Étape 2/5: Enrichissement avec DataForSEO...")
                                    progress_bar.progress(30)
                                    
                                    # Extraire tous les mots-clés et suggestions
                                    initial_keywords = keywords
                                    suggestion_texts = [s['Suggestion Google'] for s in all_suggestions if s['Niveau'] > 0]
                                    
                                    enriched_data = dataforseo_client.process_keywords_complete(
                                        initial_keywords,
                                        suggestion_texts,
                                        dataforseo_language,
                                        dataforseo_location,
                                        min_search_volume
                                    )
                                    
                                    all_enriched_keywords = enriched_data.get('enriched_keywords', [])
                                    
                                    st.success(f"✅ {enriched_data.get('total_keywords', 0)} mots-clés enrichis, {enriched_data.get('keywords_with_volume', 0)} avec volume ≥ {min_search_volume}")
                                    progress_bar.progress(50)
                                else:
                                    # Pas d'enrichissement DataForSEO, utiliser les suggestions Google uniquement
                                    all_enriched_keywords = [
                                        {
                                            'keyword': s['Suggestion Google'],
                                            'search_volume': 0,
                                            'cpc': 0,
                                            'competition': 0,
                                            'competition_level': 'UNKNOWN',
                                            'type': 'original',
                                            'source': 'google_suggest'
                                        }
                                        for s in all_suggestions
                                    ]
                                    progress_bar.progress(50)
                                
                                all_themes = {}
                                
                                if generate_questions:
                                    # Étape 3: Analyse des thèmes récurrents sur TOUS les mots-clés enrichis
                                    status_text.text("⏳ Étape 3/5: Analyse des thèmes sur tous les mots-clés...")
                                    progress_bar.progress(60)
                                    
                                    # Grouper les mots-clés enrichis par mot-clé principal d'origine
                                    keywords_by_origin = {}
                                    for keyword in keywords:
                                        # Trouver tous les mots-clés enrichis liés à ce mot-clé principal
                                        related_keywords = []
                                        
                                        # Ajouter le mot-clé principal
                                        for enriched in all_enriched_keywords:
                                            if enriched['keyword'].lower() == keyword.lower():
                                                related_keywords.append(enriched)
                                                break
                                        
                                        # Ajouter les suggestions Google liées
                                        for suggestion in all_suggestions:
                                            if suggestion['Mot-clé'] == keyword and suggestion['Niveau'] > 0:
                                                for enriched in all_enriched_keywords:
                                                    if enriched['keyword'].lower() == suggestion['Suggestion Google'].lower():
                                                        related_keywords.append(enriched)
                                                        break
                                        
                                        # Ajouter les suggestions Ads si disponibles
                                        if enable_dataforseo and 'ads_suggestions' in enriched_data:
                                            for ads_suggestion in enriched_data['ads_suggestions']:
                                                # Associer les suggestions Ads aux mots-clés principaux
                                                if any(kw.lower() in ads_suggestion.get('source_keyword', '').lower() or 
                                                      ads_suggestion.get('source_keyword', '').lower() in kw.lower() 
                                                      for kw in [keyword]):
                                                    related_keywords.append(ads_suggestion)
                                        
                                        keywords_by_origin[keyword] = related_keywords
                                    
                                    # Analyser les thèmes pour chaque groupe de mots-clés enrichis
                                    for i, (keyword, enriched_keywords_group) in enumerate(keywords_by_origin.items()):
                                        if enriched_keywords_group:
                                            # Créer des suggestions fictives pour l'analyse des thèmes
                                            fake_suggestions = [
                                                {
                                                    'Mot-clé': keyword,
                                                    'Niveau': 1,
                                                    'Suggestion Google': enriched_kw['keyword'],
                                                    'Parent': keyword,
                                                    'Search_Volume': enriched_kw.get('search_volume', 0),
                                                    'CPC': enriched_kw.get('cpc', 0),
                                                    'Competition': enriched_kw.get('competition_level', 'UNKNOWN')
                                                }
                                                for enriched_kw in enriched_keywords_group
                                                if enriched_kw['keyword'] != keyword  # Exclure le mot-clé principal
                                            ]
                                            
                                            if fake_suggestions:  # Vérifier qu'il y a des suggestions à analyser
                                                themes = question_generator.analyze_suggestions_themes(fake_suggestions, keyword, lang)
                                                all_themes[keyword] = themes
                                        
                                        progress_bar.progress(60 + (i + 1) * 20 // len(keywords_by_origin))
                                        time.sleep(0.5)
                                    
                                    progress_bar.progress(85)
                                    status_text.text("⏳ Étape 4/5: Finalisation de l'analyse...")
                                
                                progress_bar.progress(100)
                                status_text.text("✅ Analyse des thèmes terminée !")
                                
                                # Sauvegarder les résultats intermédiaires
                                st.session_state.analysis_results = {
                                    'all_suggestions': all_suggestions,
                                    'level_counts': level_counts,
                                    'themes_analysis': all_themes if generate_questions else {},
                                    'enriched_keywords': all_enriched_keywords,
                                    'dataforseo_data': enriched_data,
                                    'stage': 'themes_analyzed'
                                }
                                
                                st.session_state.analysis_metadata = {
                                    'keywords': keywords,
                                    'level1_count': level1_count,
                                    'level2_count': level2_count,
                                    'level3_count': level3_count,
                                    'enable_level2': enable_level2,
                                    'enable_level3': enable_level3,
                                    'generate_questions': generate_questions,
                                    'final_questions_count': final_questions_count if generate_questions else 0,
                                    'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                                    'language': lang,
                                    'enable_dataforseo': enable_dataforseo,
                                    'dataforseo_language': dataforseo_language if enable_dataforseo else None,
                                    'dataforseo_location': dataforseo_location if enable_dataforseo else None,
                                    'min_search_volume': min_search_volume if enable_dataforseo else 0
                                }
                                
                                # Nettoyer les éléments temporaires
                                progress_bar.empty()
                                status_text.empty()
                                
                                # Forcer le rechargement pour afficher l'interface de sélection
                                st.rerun()
                        
                        except Exception as e:
                            st.error(f"❌ Erreur lors de l'analyse: {str(e)}")
                            # Debug info
                            import traceback
                            st.error(f"Détails de l'erreur: {traceback.format_exc()}")

    with col_clear:
        if st.button("🗑️ Effacer", help="Effacer les résultats actuels"):
            st.session_state.analysis_results = None
            st.session_state.analysis_metadata = None
            st.session_state.themes_selection = None
            st.rerun()
    
    # Interface de sélection des thèmes (avec données enrichies)
    if (st.session_state.get('analysis_results') is not None and 
        st.session_state.analysis_results.get('stage') == 'themes_analyzed' and
        st.session_state.analysis_metadata['generate_questions']):
        
        st.markdown("---")
        st.markdown("## 🎨 Sélection des thèmes pour la génération de questions")
        
        # Afficher les statistiques d'enrichissement DataForSEO si disponible
        if st.session_state.analysis_metadata.get('enable_dataforseo'):
            dataforseo_data = st.session_state.analysis_results.get('dataforseo_data', {})
            if dataforseo_data:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Mots-clés totaux", dataforseo_data.get('total_keywords', 0))
                with col2:
                    st.metric("Avec volume > 0", dataforseo_data.get('keywords_with_volume', 0))
                with col3:
                    st.metric("Suggestions Ads", len(dataforseo_data.get('ads_suggestions', [])))
                with col4:
                    avg_volume = sum(k.get('search_volume', 0) for k in st.session_state.analysis_results.get('enriched_keywords', [])) / max(len(st.session_state.analysis_results.get('enriched_keywords', [])), 1)
                    st.metric("Volume moyen", f"{avg_volume:.0f}")
        
        # Créer une interface de sélection pour chaque mot-clé
        selected_themes_by_keyword = {}
        themes_analysis = st.session_state.analysis_results.get('themes_analysis', {})
        
        if themes_analysis:
            for keyword, themes in themes_analysis.items():
                if themes:
                    st.markdown(f"### 🎯 Thèmes identifiés pour '{keyword}'")
                    
                    # Créer des colonnes pour l'affichage des thèmes
                    themes_per_row = 2
                    for i in range(0, len(themes), themes_per_row):
                        cols = st.columns(themes_per_row)
                        
                        for j, theme in enumerate(themes[i:i+themes_per_row]):
                            with cols[j]:
                                theme_name = theme.get('nom', f'Thème {i+j+1}')
                                theme_importance = theme.get('importance', 3)
                                theme_intention = theme.get('intention', 'informational')
                                concepts = theme.get('concepts', [])
                                exemples = theme.get('exemples_suggestions', [])
                                
                                # Checkbox pour sélectionner le thème (sélectionné par défaut)
                                theme_key = f"{keyword}_{theme_name}_{i+j}"
                                is_selected = st.checkbox(
                                    f"**{theme_name}**",
                                    value=True,  # Sélectionné par défaut
                                    key=theme_key,
                                    help=f"Importance: {theme_importance}/5 | Intention: {theme_intention}"
                                )
                                
                                if is_selected:
                                    if keyword not in selected_themes_by_keyword:
                                        selected_themes_by_keyword[keyword] = []
                                    selected_themes_by_keyword[keyword].append(theme)
                                
                                # Afficher les détails du thème
                                with st.expander(f"Détails du thème '{theme_name}'"):
                                    st.write(f"**Importance:** {theme_importance}/5")
                                    st.write(f"**Intention:** {theme_intention}")
                                    if concepts:
                                        st.write(f"**Concepts:** {', '.join(concepts[:5])}")
                                    if exemples:
                                        st.write(f"**Exemples de suggestions:** {', '.join(exemples[:3])}")
        
        # Bouton pour générer les questions avec les thèmes sélectionnés
        st.markdown("---")
        col_generate, col_info = st.columns([3, 2])
        
        with col_generate:
            total_selected_themes = sum(len(themes) for themes in selected_themes_by_keyword.values())
            
            if total_selected_themes > 0:
                if st.button("✨ Générer les questions avec les thèmes sélectionnés", type="primary"):
                    # Lancer la génération avec les thèmes sélectionnés
                    try:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        status_text.text("⏳ Génération des questions conversationnelles...")
                        
                        metadata = st.session_state.analysis_metadata
                        final_questions_count = metadata.get('final_questions_count', 20)
                        lang = metadata.get('language', 'fr')
                        
                        all_questions_data = []
                        questions_per_keyword = final_questions_count // len(selected_themes_by_keyword) if selected_themes_by_keyword else final_questions_count
                        remaining_questions = final_questions_count
                        
                        keyword_list = list(selected_themes_by_keyword.keys())
                        
                        for i, (keyword, selected_themes) in enumerate(selected_themes_by_keyword.items()):
                            if remaining_questions <= 0:
                                break
                            
                            # Calculer le nombre de questions pour ce mot-clé
                            if i == len(keyword_list) - 1:  # Dernier mot-clé
                                keyword_questions = remaining_questions
                            else:
                                keyword_questions = min(questions_per_keyword, remaining_questions)
                            
                            if keyword_questions > 0 and selected_themes:
                                keyword_questions_list = question_generator.generate_questions_from_themes(
                                    keyword, 
                                    selected_themes, 
                                    keyword_questions,
                                    lang
                                )
                                
                                for q in keyword_questions_list:
                                    q['Mot-clé'] = keyword
                                    # Ajouter une suggestion Google représentative du thème
                                    theme_name = q.get('Thème', '')
                                    # Trouver une suggestion représentative du thème dans les suggestions collectées
                                    representative_suggestion = keyword  # Fallback
                                    if theme_name and selected_themes:
                                        for theme in selected_themes:
                                            if theme.get('nom') == theme_name:
                                                exemples_suggestions = theme.get('exemples_suggestions', [])
                                                if exemples_suggestions:
                                                    representative_suggestion = exemples_suggestions[0]
                                                break
                                    q['Suggestion Google'] = representative_suggestion
                                    all_questions_data.append(q)
                                
                                remaining_questions -= len(keyword_questions_list)
                            
                            progress_bar.progress((i + 1) / len(keyword_list))
                            time.sleep(0.5)
                        
                        if all_questions_data:
                            # Trier par score d'importance et limiter au nombre demandé
                            sorted_questions = sorted(
                                all_questions_data,
                                key=lambda x: x.get('Score_Importance', 0),
                                reverse=True
                            )
                            
                            final_consolidated_data = sorted_questions[:final_questions_count]
                            
                            # Mettre à jour les résultats
                            st.session_state.analysis_results.update({
                                'all_questions_data': all_questions_data,
                                'final_consolidated_data': final_consolidated_data,
                                'selected_themes_by_keyword': selected_themes_by_keyword,
                                'stage': 'questions_generated'
                            })
                            
                            progress_bar.progress(1.0)
                            status_text.text(f"✅ {len(final_consolidated_data)} questions générées avec succès !")
                            
                            time.sleep(1)
                            progress_bar.empty()
                            status_text.empty()
                            
                            st.success(f"🎉 {len(final_consolidated_data)} questions conversationnelles générées à partir de {total_selected_themes} thèmes sélectionnés !")
                            
                            # Forcer le rechargement pour afficher les résultats
                            st.rerun()
                        else:
                            st.error("❌ Aucune question générée")
                            
                    except Exception as e:
                        st.error(f"❌ Erreur lors de la génération: {str(e)}")
                        import traceback
                        st.error(f"Détails de l'erreur: {traceback.format_exc()}")
            else:
                st.warning("⚠️ Veuillez sélectionner au moins un thème pour générer les questions.")
        
        with col_info:
            total_themes_available = sum(len(themes) for themes in themes_analysis.values())
            st.info(f"📊 **{total_selected_themes}** thèmes sélectionnés sur {total_themes_available}")
            if total_selected_themes > 0:
                final_questions_count = st.session_state.analysis_metadata.get('final_questions_count', 20)
                estimated_questions = min(final_questions_count, total_selected_themes * 3)
                st.info(f"🎯 Environ **{estimated_questions}** questions seront générées")
        
        if not themes_analysis:
            st.warning("⚠️ Aucun thème identifié. Relancez l'analyse avec d'autres mots-clés.")

# TAB 2: Instructions d'utilisation
with tab2:
    st.markdown("""
    # 📖 Instructions d'utilisation
    
    ## 🔍 Processus d'analyse en 4 étapes
    
    ### 1. **Configuration**
    Entrez votre clé API OpenAI dans la barre latérale
    
    ### 2. **Saisie des mots-clés** 
    Entrez vos mots-clés (un par ligne) dans la zone de texte
    
    ### 3. **Paramétrage**
    Ajustez le nombre de suggestions et questions finales selon vos besoins
    
    ### 4. **Analyse**
    Lancez l'analyse et obtenez vos questions conversationnelles optimisées
    
    ---
    
    ## ⚙️ Fonctionnalités principales
    
    - **Collecte automatique** des suggestions Google réelles
    - **Génération intelligente** de questions par thème
    - **Consolidation avancée** avec déduplication et scoring
    - **Export professionnel** en Excel et JSON
    
    ---
    
    ## 🎯 Exemples de mots-clés
    
    ```
    restaurant paris
    formation développement web
    voyage écologique
    coaching personnel
    e-commerce bio
    hôtel spa luxe
    assurance auto jeune
    formation marketing digital
    ```
    
    ---
    
    ## 📊 Résultats obtenus
    
    - ✅ Questions conversationnelles optimisées SEO
    - ✅ Triées par pertinence décroissante
    - ✅ Prêtes pour l'intégration dans votre contenu
    - ✅ Format Excel professionnel avec colonnes organisées
    - ✅ Métadonnées complètes en JSON
    
    ---
    
    ## 🚀 Conseils d'optimisation
    
    ### Pour de meilleurs résultats :
    
    - **Utilisez des mots-clés spécifiques** plutôt que génériques
    - **Variez les intentions** (informationnelle, transactionnelle, navigationnelle)
    - **Adaptez la langue** selon votre audience cible
    - **Ajustez le nombre de suggestions** selon la profondeur d'analyse souhaitée
    
    ### Paramètres recommandés :
    
    - **Débutant** : 5 suggestions, 10 questions finales
    - **Intermédiaire** : 10 suggestions, 15 questions finales  
    - **Expert** : 15 suggestions, 25-50 questions finales
    
    ---
    
    ## 📈 Applications SEO
    
    ### Utilisez vos questions pour :
    
    - **FAQ** : Intégrer dans vos pages FAQ
    - **Blog** : Créer des articles basés sur les questions
    - **Featured Snippets** : Optimiser pour les extraits enrichis
    - **Recherche vocale** : Adapter votre contenu aux assistants vocaux
    - **Long tail** : Capturer le trafic des requêtes spécifiques
    
    ---
    
    ## 🔧 Support technique
    
    En cas de problème :
    1. Vérifiez votre clé API OpenAI
    2. Assurez-vous d'avoir une connexion internet stable
    3. Réduisez le nombre de mots-clés si l'analyse est trop lente
    4. Contactez le support si les suggestions Google ne se chargent pas
    """)

# Footer
st.markdown("---")
st.markdown("*Outil d'optimisation SEO pour requêtes conversationnelles | Powered by GPT-4o mini & Streamlit*")