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

# Configuration de l'API OpenAI
st.sidebar.header("⚙️ Configuration")
api_key = st.sidebar.text_input("Clé API OpenAI", type="password", help="Votre clé API OpenAI pour GPT-4o mini")

if api_key:
    client = OpenAI(api_key=api_key)
    st.sidebar.success("✅ API configurée")
else:
    st.sidebar.warning("⚠️ Veuillez entrer votre clé API OpenAI")
    client = None

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

def get_google_suggestions_multilevel(keyword, lang='fr', level1_count=10, level2_count=5, enable_level2=True):
    """
    Récupère les suggestions Google à plusieurs niveaux
    - Niveau 0: mot-clé de base
    - Niveau 1: suggestions directes du mot-clé (2-15)
    - Niveau 2: suggestions des suggestions de niveau 1 (2-15)
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
        for suggestion_data in all_suggestions.copy():  # Copie pour éviter la modification pendant l'itération
            if suggestion_data['Niveau'] == 1:  # Traiter uniquement les suggestions de niveau 1
                level2_suggestions = get_google_suggestions(suggestion_data['Suggestion Google'], lang, level2_count)
                
                for l2_suggestion in level2_suggestions:
                    normalized = l2_suggestion.lower().strip()
                    if normalized not in processed_suggestions:
                        all_suggestions.append({
                            'Mot-clé': keyword,
                            'Niveau': 2,
                            'Suggestion Google': l2_suggestion,
                            'Parent': suggestion_data['Suggestion Google']
                        })
                        processed_suggestions.add(normalized)
                
                time.sleep(0.3)  # Délai entre les requêtes pour éviter le rate limiting
    
    return all_suggestions

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
    
    # Configuration améliorée
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        level1_count = st.slider(
            "Suggestions niveau 1", 
            min_value=2, 
            max_value=15, 
            value=10,
            help="Nombre de suggestions Google directes pour chaque mot-clé"
        )
    with col2:
        enable_level2 = st.checkbox(
            "Activer niveau 2",
            value=False,  # Changé de True à False
            help="Rechercher des suggestions à partir des suggestions de niveau 1"
        )
        level2_count = st.slider(
            "Suggestions niveau 2", 
            min_value=0,  # Changé de 2 à 0
            max_value=15, 
            value=10,  # Changé de 5 à 10
            disabled=not enable_level2,
            help="Nombre de suggestions pour chaque suggestion de niveau 1"
        )
    with col3:
        generate_questions = st.checkbox(
            "Générer questions conversationnelles",
            value=True,
            help="Générer des questions conversationnelles à partir des suggestions"
        )
        if generate_questions:
            final_questions_count = st.slider(
                "Nombre de questions finales",
                min_value=5,
                max_value=100,
                value=20,
                help="Nombre de questions conversationnelles à conserver après consolidation"
            )
    with col4:
        lang = st.selectbox("Langue", ["fr", "en", "es", "de", "it"], index=0)
    
    # Boutons d'action
    col_analyze, col_clear = st.columns([4, 1])
    with col_analyze:
        if keywords_input and api_key:
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
                            enable_level2
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
                        
                        st.info(f"✅ {len(all_suggestions)} suggestions collectées - Niveau 0: {level_counts.get(0, 0)}, Niveau 1: {level_counts.get(1, 0)}, Niveau 2: {level_counts.get(2, 0)}")
                        
                        final_consolidated_data = []
                        all_questions_data = []
                        
                        if generate_questions:
                            # Étape 2: Génération des questions conversationnelles
                            status_text.text("⏳ Étape 2/3: Génération des questions conversationnelles...")
                            
                            processed = 0
                            total_items = len(all_suggestions)
                            
                            for item in all_suggestions:
                                keyword = item['Mot-clé']
                                suggestion = item['Suggestion Google']
                                niveau = item['Niveau']
                                parent = item['Parent']
                                
                                prompt = f"""
                                Basé sur le mot-clé "{keyword}" et la suggestion Google "{suggestion}" (niveau {niveau}), 
                                génère EXACTEMENT 5 questions conversationnelles SEO pertinentes au format question.
                                
                                Les questions doivent :
                                - Être naturelles et conversationnelles
                                - Optimisées pour la recherche vocale
                                - Pertinentes pour l'intention de recherche
                                - Se terminer par un point d'interrogation
                                - Être variées dans leur formulation
                                
                                Présente-les sous forme de liste numérotée de 1 à 5.
                                """
                                
                                response = call_gpt4o_mini(prompt)
                                if response:
                                    questions = extract_questions_from_response(response)
                                    for question in questions[:5]:
                                        all_questions_data.append({
                                            'Mot-clé': keyword,
                                            'Suggestion Google': suggestion,
                                            'Question Conversationnelle': question,
                                            'Niveau': niveau,
                                            'Parent': parent
                                        })
                                
                                processed += 1
                                progress_bar.progress(40 + (processed * 40 // total_items))
                                time.sleep(0.5)  # Délai réduit
                                
                                # Affichage du progrès en temps réel
                                current_questions = len(all_questions_data)
                                status_text.text(f"⏳ Étape 2/3: {current_questions} questions générées...")
                            
                            if not all_questions_data:
                                st.error("❌ Aucune question générée")
                            else:
                                st.info(f"✅ {len(all_questions_data)} questions générées au total")
                                
                                # Étape 3: Consolidation et déduplication
                                status_text.text("⏳ Étape 3/3: Consolidation et déduplication...")
                                progress_bar.progress(90)
                                
                                final_consolidated_data = consolidate_and_deduplicate(
                                    all_questions_data, 
                                    final_questions_count
                                )
                        
                        progress_bar.progress(100)
                        status_text.text("✅ Analyse terminée !")
                        
                        # Sauvegarder les résultats dans le session state
                        st.session_state.analysis_results = {
                            'all_suggestions': all_suggestions,
                            'all_questions_data': all_questions_data,
                            'final_consolidated_data': final_consolidated_data,
                            'level_counts': level_counts
                        }
                        
                        st.session_state.analysis_metadata = {
                            'keywords': keywords,
                            'level1_count': level1_count,
                            'level2_count': level2_count,
                            'enable_level2': enable_level2,
                            'generate_questions': generate_questions,
                            'final_questions_count': final_questions_count if generate_questions else 0,
                            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        # Nettoyer les éléments temporaires
                        progress_bar.empty()
                        status_text.empty()
        elif not api_key:
            st.warning("⚠️ Veuillez configurer votre clé API OpenAI dans la barre latérale pour commencer l'analyse.")
    
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
                st.metric("Questions générées", len(results['all_questions_data']))
            with col4:
                st.metric("Questions finales", len(results['final_consolidated_data']))
            with col5:
                consolidation_rate = (len(results['all_questions_data']) - len(results['final_consolidated_data'])) / len(results['all_questions_data']) * 100 if results['all_questions_data'] else 0
                st.metric("Taux consolidation", f"{consolidation_rate:.0f}%")
            
            # Tableau des résultats avec questions
            st.markdown("### 📋 Questions conversationnelles (par pertinence)")
            df_results = pd.DataFrame(results['final_consolidated_data'])
            df_display = df_results[['Requêtes Conversationnelles', 'Suggestion', 'Mot-clé']].copy()
            st.dataframe(df_display, use_container_width=True)
        else:
            # Métriques sans questions
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Mots-clés analysés", len(metadata['keywords']))
            with col2:
                st.metric("Suggestions collectées", len(results['all_suggestions']))
            with col3:
                st.metric("Niveaux activés", "2" if metadata['enable_level2'] else "1")
        
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
        
        # Statistiques détaillées
        with st.expander("📊 Statistiques détaillées"):
            if metadata['generate_questions']:
                st.markdown(f"**Questions éliminées:** {len(results['all_questions_data']) - len(results['final_consolidated_data'])}")
                st.markdown(f"**Questions conservées:** {len(results['final_consolidated_data'])}")
            
            st.markdown("**Répartition des suggestions par niveau:**")
            for level, count in results['level_counts'].items():
                st.markdown(f"- Niveau {level}: {count} suggestions")
            
            # Répartition par mot-clé
            keyword_counts = suggestions_df['Mot-clé'].value_counts()
            st.markdown("**Répartition par mot-clé:**")
            for keyword, count in keyword_counts.items():
                st.markdown(f"- {keyword}: {count} suggestions")
        
        # Export des résultats
        st.markdown("### 📤 Export des résultats")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if metadata['generate_questions'] and len(results['final_consolidated_data']) > 0:
                # Export Excel des questions
                excel_file = create_excel_file(df_display)
                st.download_button(
                    label="📊 Télécharger Questions (Excel)",
                    data=excel_file,
                    file_name="questions_conversationnelles_multiniveaux.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_questions_excel"
                )
            
            # Export Excel des suggestions
            suggestions_excel = create_excel_file(suggestions_display)
            st.download_button(
                label="🔍 Télécharger Suggestions (Excel)",
                data=suggestions_excel,
                file_name="suggestions_google_multiniveaux.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_suggestions_excel"
            )
        
        with col2:
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
            st.download_button(
                label="📋 Télécharger Données (JSON)",
                data=json_data,
                file_name="analyse_complete_multiniveaux.json",
                mime="application/json",
                key="download_json"
            )

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
