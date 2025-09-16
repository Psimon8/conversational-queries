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

if api_key:
    client = OpenAI(api_key=api_key)
    st.sidebar.success("✅ API configurée")
else:
    st.sidebar.warning("⚠️ Veuillez entrer votre clé API OpenAI")
    client = None

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

# Export des résultats dans la sidebar
if 'analysis_results' in st.session_state and st.session_state.analysis_results is not None:
    results = st.session_state.analysis_results
    metadata = st.session_state.analysis_metadata
    
    st.sidebar.header("📤 Export des résultats")
    
    if metadata['generate_questions'] and len(results['final_consolidated_data']) > 0:
        # Export Excel des questions avec thèmes
        excel_df = pd.DataFrame(results['final_consolidated_data'])
        excel_display = excel_df[['Question Conversationnelle', 'Mot-clé', 'Thème', 'Intention', 'Score_Importance']].copy()
        excel_display.columns = ['Questions Conversationnelles', 'Mot-clé', 'Thème', 'Intention', 'Importance']
        
        excel_file = create_excel_file(excel_display)
        st.sidebar.download_button(
            label="📊 Questions (Excel)",
            data=excel_file,
            file_name="questions_conversationnelles_themes.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_questions_themes_excel",
            use_container_width=True
        )
    
    # Export Excel des suggestions
    if len(results['all_suggestions']) > 0:
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
    
    # Export JSON complet
    export_json = {
        "metadata": {
            **metadata,
            "total_suggestions": len(results['all_suggestions']),
            "level_distribution": results['level_counts']
        },
        "suggestions": results['all_suggestions'],
        "questions": results['final_consolidated_data'] if metadata['generate_questions'] else []
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

# Fonctions utilitaires communes
def call_gpt4o_mini(prompt, max_retries=3):
    """Appel à l'API GPT-4o mini avec gestion d'erreurs"""
    if not client:
        st.error("❌ Clé API manquante")
        return None
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un expert SEO spécialisé dans l'analyse des requêtes conversationnelles et l'optimisation pour les moteurs de recherche."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=1500,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            else:
                st.error(f"❌ Erreur API après {max_retries} tentatives: {str(e)}")
                return None

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

def extract_questions_from_response(response_text):
    """Extrait les questions d'une réponse de GPT"""
    if not response_text:
        return []
    
    patterns = [
        r'^\d+\.?\s*["\']?([^"\']+\?)["\']?',  # Format numéroté avec ?
        r'^-\s*["\']?([^"\']+\?)["\']?',       # Format avec tirets avec ?
        r'^•\s*["\']?([^"\']+\?)["\']?'        # Format avec puces avec ?
    ]
    
    questions = []
    lines = response_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or not line.endswith('?'):
            continue
            
        for pattern in patterns:
            match = re.match(pattern, line, re.MULTILINE)
            if match:
                question = match.group(1).strip()
                if len(question) > 10:
                    questions.append(question)
                break
        else:
            # Si aucun pattern ne correspond mais que la ligne se termine par ?
            if line.endswith('?') and len(line) > 10:
                questions.append(line)
    
    return questions

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
        worksheet.column_dimensions['B'].width = 40  # Suggestions
        worksheet.column_dimensions['C'].width = 25  # Mots-clés
        
        # Formatage de l'en-tête
        from openpyxl.styles import Font, PatternFill
        header_font = Font(bold=True)
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        
        for cell in worksheet[1]:
            cell.font = header_font
            cell.fill = header_fill
    
    output.seek(0)
    return output

def get_google_suggestions_multilevel(keyword, lang='fr', level1_count=10, level2_count=5, level3_count=0, enable_level2=True, enable_level3=False):
    """
    Récupère les suggestions Google à plusieurs niveaux
    - Niveau 0: mot-clé de base
    - Niveau 1: suggestions directes du mot-clé (2-15)
    - Niveau 2: suggestions des suggestions de niveau 1 (0-15)
    - Niveau 3: suggestions des suggestions de niveau 2 (0-15)
    """
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
    1. Sont adaptées à la catégorie "{category}" et l'intention "{intent}"
    2. Intègrent naturellement le contexte de la suggestion
    3. Sont formulées comme des questions que les utilisateurs poseraient vraiment
    4. Sont optimisées pour la recherche vocale
    5. Se terminent par un point d'interrogation
    6. Sont de longueur appropriée (ni trop courtes, ni trop longues)
    
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
            value=10,
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
            # Vérifier la clé API seulement si la génération de questions est activée
            if generate_questions and not api_key:
                st.warning("⚠️ Veuillez configurer votre clé API OpenAI dans la barre latérale pour générer les questions conversationnelles.")
            elif keywords_input:
                keywords = [kw.strip() for kw in keywords_input.split('\n') if kw.strip()]
                
                if st.button("🚀 Analyser les suggestions", type="primary"):
                    if not keywords:
                        st.error("❌ Veuillez entrer au moins un mot-clé")
                    else:
                        # Réinitialiser les résultats précédents
                        st.session_state.analysis_results = None
                        st.session_state.analysis_metadata = None
                        
                        # Progress tracking
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # Déterminer les niveaux activés
                        enable_level2 = level2_count > 0
                        enable_level3 = level3_count > 0 and enable_level2
                        
                        # Étape 1: Collecte des suggestions multi-niveaux
                        total_steps = 3 if generate_questions else 2
                        status_text.text("⏳ Étape 1/{}: Collecte des suggestions Google multi-niveaux...".format(total_steps))
                        
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
                            
                            progress_bar.progress((i + 1) * 40 // len(keywords))
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
                            
                            final_consolidated_data = []
                            all_questions_data = []
                            
                            if generate_questions:
                                # Étape 2: Analyse des thèmes récurrents
                                status_text.text("⏳ Étape 2/4: Analyse des thèmes récurrents dans les suggestions...")
                                progress_bar.progress(50)
                                
                                # Analyser les thèmes pour chaque mot-clé
                                all_themes = {}
                                for keyword in keywords:
                                    keyword_suggestions = [s for s in all_suggestions if s['Mot-clé'] == keyword]
                                    themes = analyze_suggestions_themes(keyword_suggestions, keyword)
                                    all_themes[keyword] = themes
                                    time.sleep(1)  # Délai pour éviter le rate limiting
                                
                                # Étape 3: Génération intelligente des questions
                                status_text.text("⏳ Étape 3/4: Génération des questions conversationnelles par thème...")
                                progress_bar.progress(70)
                                
                                all_questions_data = []
                                questions_per_keyword = final_questions_count // len(keywords)
                                remaining_questions = final_questions_count
                                
                                for i, keyword in enumerate(keywords):
                                    # Calculer le nombre de questions pour ce mot-clé
                                    if i == len(keywords) - 1:  # Dernier mot-clé
                                        keyword_questions = remaining_questions
                                    else:
                                        keyword_questions = min(questions_per_keyword, remaining_questions)
                                    
                                    if keyword_questions > 0:
                                        themes = all_themes.get(keyword, [])
                                        if themes:
                                            keyword_questions_list = generate_questions_from_themes(
                                                keyword, 
                                                themes, 
                                                keyword_questions
                                            )
                                            
                                            for q in keyword_questions_list:
                                                q['Mot-clé'] = keyword
                                                all_questions_data.append(q)
                                            
                                            remaining_questions -= len(keyword_questions_list)
                                        else:
                                            st.warning(f"Aucun thème identifié pour '{keyword}'")
                                    
                                    time.sleep(0.5)  # Délai entre les mots-clés
                                
                                if not all_questions_data:
                                    st.error("❌ Aucune question générée")
                                else:
                                    st.info(f"✅ {len(all_questions_data)} questions conversationnelles générées à partir des thèmes")
                                    
                                    # Étape 4: Finalisation
                                    status_text.text("⏳ Étape 4/4: Finalisation...")
                                    progress_bar.progress(90)
                                    
                                    # Trier par score d'importance et limiter au nombre demandé
                                    sorted_questions = sorted(
                                        all_questions_data,
                                        key=lambda x: x.get('Score_Importance', 0),
                                        reverse=True
                                    )
                                    
                                    final_consolidated_data = sorted_questions[:final_questions_count]
                                    
                                    # Sauvegarder les thèmes pour l'affichage
                                    st.session_state.themes_analysis = all_themes

                            progress_bar.progress(100)
                            status_text.text("✅ Analyse terminée !")
                            
                            # Sauvegarder les résultats dans le session state
                            st.session_state.analysis_results = {
                                'all_suggestions': all_suggestions,
                                'all_questions_data': all_questions_data if generate_questions else [],
                                'final_consolidated_data': final_consolidated_data if generate_questions else [],
                                'level_counts': level_counts,
                                'themes_analysis': all_themes if generate_questions else {}
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
                                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
                            }
                            
                            # Nettoyer les éléments temporaires
                            progress_bar.empty()
                            status_text.empty()
    
    with col_clear:
        if st.button("🗑️ Effacer", help="Effacer les résultats actuels"):
            st.session_state.analysis_results = None
            st.session_state.analysis_metadata = None
            st.rerun()
    
    # Affichage des résultats sauvegardés
    if st.session_state.analysis_results is not None:
        results = st.session_state.analysis_results
        metadata = st.session_state.analysis_metadata
        
        st.markdown("## 📊 Résultats de l'analyse")
        
        if metadata['generate_questions']:
            # Métriques avec questions
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Mots-clés analysés", len(metadata['keywords']))
            with col2:
                st.metric("Suggestions collectées", len(results['all_suggestions']))
            with col3:
                total_themes = sum(len(themes) for themes in results.get('themes_analysis', {}).values())
                st.metric("Thèmes identifiés", total_themes)
            with col4:
                st.metric("Questions générées", len(results['final_consolidated_data']))
            with col5:
                avg_importance = sum(q.get('Score_Importance', 0) for q in results['final_consolidated_data']) / len(results['final_consolidated_data']) if results['final_consolidated_data'] else 0
                st.metric("Importance moyenne", f"{avg_importance:.1f}/5")
        else:
            # Métriques sans questions
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Mots-clés analysés", len(metadata['keywords']))
            with col2:
                st.metric("Suggestions collectées", len(results['all_suggestions']))
            with col3:
                max_level = 3 if metadata['enable_level3'] else (2 if metadata['enable_level2'] else 1)
                st.metric("Niveaux activés", str(max_level))
        
        # Tableau des suggestions par niveau
        st.markdown("### 🔍 Suggestions collectées par niveau")
        
        # Créer un DataFrame pour les suggestions
        suggestions_df = pd.DataFrame(results['all_suggestions'])
        suggestions_display = suggestions_df[['Mot-clé', 'Suggestion Google', 'Niveau', 'Parent']].copy()
        
        # Filtres par niveau
        available_levels = suggestions_df['Niveau'].unique().tolist()
        nivel_filter = st.multiselect(
            "Filtrer par niveau",
            options=available_levels,
            default=available_levels,
            format_func=lambda x: f"Niveau {x}"
        )
        
        if nivel_filter:
            filtered_suggestions = suggestions_display[suggestions_display['Niveau'].isin(nivel_filter)]
            st.dataframe(filtered_suggestions, use_container_width=True)
        
        # Tableau des questions conversationnelles (déplacé après les suggestions)
        if metadata['generate_questions'] and len(results['final_consolidated_data']) > 0:
            st.markdown("### 📋 Questions conversationnelles basées sur les thèmes")
            df_results = pd.DataFrame(results['final_consolidated_data'])
            df_display = df_results[['Question Conversationnelle', 'Thème', 'Intention', 'Score_Importance', 'Mot-clé']].copy()
            df_display.columns = ['Questions Conversationnelles', 'Thème', 'Intention', 'Importance', 'Mot-clé']
            st.dataframe(df_display, use_container_width=True)
            
            # Analyse des thèmes
            with st.expander("📊 Analyse détaillée des thèmes"):
                themes_analysis = results.get('themes_analysis', {})
                
                for keyword, themes in themes_analysis.items():
                    if themes:
                        st.markdown(f"**Thèmes pour '{keyword}' :**")
                        themes_df = pd.DataFrame(themes)
                        if not themes_df.empty:
                            display_themes = themes_df[['nom', 'importance', 'intention', 'concepts']].copy()
                            display_themes.columns = ['Thème', 'Importance', 'Intention', 'Concepts']
                            st.dataframe(display_themes, use_container_width=True)
                            st.markdown("---")
            
            # Statistiques par thème et intention
            with st.expander("📈 Répartition des questions"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Répartition par thème:**")
                    theme_counts = df_results['Thème'].value_counts()
                    for theme, count in theme_counts.items():
                        st.markdown(f"- {theme}: {count} questions")
                
                with col2:
                    st.markdown("**Répartition par intention:**")
                    intent_counts = df_results['Intention'].value_counts()
                    for intent, count in intent_counts.items():
                        st.markdown(f"- {intent}: {count} questions")
        
        # Statistiques détaillées
        with st.expander("📊 Statistiques détaillées"):
            if metadata['generate_questions']:
                st.markdown(f"**Questions générées:** {len(results['final_consolidated_data'])}")
                total_themes = sum(len(themes) for themes in results.get('themes_analysis', {}).values())
                st.markdown(f"**Thèmes identifiés:** {total_themes}")
            
            st.markdown("**Répartition des suggestions par niveau:**")
            for level, count in results['level_counts'].items():
                st.markdown(f"- Niveau {level}: {count} suggestions")
            
            # Répartition par mot-clé
            keyword_counts = suggestions_df['Mot-clé'].value_counts()
            st.markdown("**Répartition par mot-clé:**")
            for keyword, count in keyword_counts.items():
                st.markdown(f"- {keyword}: {count} suggestions")

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
    - **Génération intelligente** de 10 questions par suggestion
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
