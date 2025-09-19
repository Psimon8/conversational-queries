import streamlit as st
from openai import OpenAI
import pandas as pd
import time

# Imports des modules refactorisés
from utils.ui_components import setup_page_config, render_header, render_social_links
from utils.config_manager import ConfigManager
from utils.export_manager import ExportManager
from utils.workflow_manager import WorkflowManager
from utils.results_manager import ResultsManager
from utils.keyword_utils import normalize_keyword, deduplicate_keywords_with_origins
from services.dataforseo_service import DataForSEOService
from question_generator import QuestionGenerator
from google_suggestions import GoogleSuggestionsClient

def main():
    """Fonction principale de l'application"""
    
    # Configuration de la page
    setup_page_config()
    
    # Initialisation du session state
    initialize_session_state()
    
    # Interface utilisateur
    render_header()
    
    # Gestionnaire de configuration
    config_manager = ConfigManager()
    
    # Configuration centralisée des credentials
    api_key, enable_dataforseo, dataforseo_config = config_manager.render_credentials_section()
    
    # Configuration des options d'analyse
    analysis_options = config_manager.render_analysis_options()
    
    # Initialisation des clients
    client = OpenAI(api_key=api_key) if api_key else None
    question_generator = QuestionGenerator(client)
    google_client = GoogleSuggestionsClient()
    dataforseo_service = DataForSEOService(dataforseo_config) if enable_dataforseo else None
    
    # Gestionnaire d'export
    if st.session_state.analysis_results:
        export_manager = ExportManager(
            st.session_state.analysis_results, 
            st.session_state.analysis_metadata
        )
        export_manager.render_export_section()
    
    render_social_links()
    
    # Interface principale
    render_main_interface(
        config_manager, 
        google_client, 
        question_generator,
        dataforseo_service,
        api_key, 
        analysis_options
    )

def initialize_session_state():
    """Initialisation du session state"""
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    if 'analysis_metadata' not in st.session_state:
        st.session_state.analysis_metadata = None

def render_main_interface(config_manager, google_client, question_generator, 
                         dataforseo_service, api_key, analysis_options):
    """Interface principale d'analyse"""
    
    # Création des onglets
    tab1, tab2 = st.tabs(["🔍 Analyseur de Requêtes", "📖 Instructions"])
    
    with tab1:
        render_analysis_tab(
            config_manager, google_client, question_generator,
            dataforseo_service, api_key, analysis_options
        )
    
    with tab2:
        render_instructions_tab()

def render_analysis_tab(config_manager, google_client, question_generator,
                       dataforseo_service, api_key, analysis_options):
    """Onglet d'analyse principal"""
    
    st.markdown("### 🔍 Analyse basée sur les suggestions Google")
    
    # Input des mots-clés
    keywords_input = st.text_area(
        "🎯 Entrez vos mots-clés (un par ligne)",
        placeholder="restaurant paris\nhôtel luxe\nvoyage écologique",
        help="Un mot-clé par ligne"
    )
    
    # Configuration des niveaux
    levels_config = config_manager.render_suggestion_levels()
    
    # Estimation des coûts DataForSEO si configuré
    if dataforseo_service and dataforseo_service.is_configured():
        render_cost_estimation(keywords_input, levels_config, dataforseo_service)
    
    # Boutons d'action
    col_analyze, col_clear = st.columns([4, 1])
    
    with col_analyze:
        if keywords_input and st.button("🚀 Analyser les suggestions", type="primary"):
            run_analysis(
                keywords_input, levels_config, google_client, question_generator,
                dataforseo_service, api_key, analysis_options
            )
    
    with col_clear:
        if st.button("🗑️ Effacer", help="Effacer les résultats"):
            clear_results()
    
    # Affichage des résultats
    render_results_section(question_generator, analysis_options)

def render_cost_estimation(keywords_input, levels_config, dataforseo_service):
    """Afficher l'estimation des coûts DataForSEO"""
    if not keywords_input:
        return
    
    keywords = [kw.strip() for kw in keywords_input.split('\n') if kw.strip()]
    estimated_suggestions = len(keywords) * (
        levels_config['level1_count'] + 
        (levels_config['level2_count'] if levels_config['enable_level2'] else 0) +
        (levels_config['level3_count'] if levels_config['enable_level3'] else 0)
    )
    
    total_keywords = len(keywords) + estimated_suggestions
    cost_info = dataforseo_service.estimate_cost(total_keywords, True)
    
    with st.expander("💰 Estimation des coûts DataForSEO"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Mots-clés estimés", total_keywords)
        with col2:
            st.metric("Coût volumes", f"${cost_info['search_volume_cost']:.2f}")
        with col3:
            st.metric("Coût total estimé", f"${cost_info['total_cost']:.2f}")

def run_analysis(keywords_input, levels_config, google_client, question_generator,
                dataforseo_service, api_key, analysis_options):
    """Exécution de l'analyse avec workflow manager"""
    
    keywords = [kw.strip() for kw in keywords_input.split('\n') if kw.strip()]
    
    if not keywords:
        st.error("❌ Veuillez entrer au moins un mot-clé")
        return
    
    # Vérification des prérequis
    current_generate_questions = analysis_options['generate_questions']
    if current_generate_questions and not api_key:
        st.warning("⚠️ API OpenAI requise pour la génération de questions")
        current_generate_questions = False
    
    # Réinitialisation
    st.session_state.analysis_results = None
    st.session_state.analysis_metadata = None
    
    # Initialisation du workflow
    workflow = WorkflowManager()
    workflow.initialize_workflow(
        enable_dataforseo=bool(dataforseo_service and dataforseo_service.is_configured()),
        generate_questions=current_generate_questions
    )
    workflow.start_workflow()
    
    try:
        # Étape 1: Collecte des suggestions Google
        workflow.update_step("collect_suggestions", "running")
        all_suggestions = collect_google_suggestions(
            keywords, levels_config, google_client, analysis_options['language']
        )
        
        if not all_suggestions:
            workflow.error_step("collect_suggestions", "Aucune suggestion trouvée")
            st.error("❌ Aucune suggestion trouvée")
            return
        
        workflow.complete_step("collect_suggestions")
        
        # Étape 2: Enrichissement DataForSEO (optionnel)
        enriched_data = {}
        if dataforseo_service and dataforseo_service.is_configured():
            workflow.update_step("dataforseo_volumes", "running")
            
            suggestion_texts = [s['Suggestion Google'] for s in all_suggestions]
            enriched_data = dataforseo_service.process_complete_analysis(keywords, suggestion_texts)
            
            if enriched_data:
                workflow.complete_step("dataforseo_volumes")
                if "dataforseo_ads" in [step.name for step in workflow.steps]:
                    workflow.complete_step("dataforseo_ads")  # Ads inclus dans process_complete_analysis
            else:
                workflow.error_step("dataforseo_volumes", "Erreur lors de l'enrichissement DataForSEO")
        
        # Étape 3: Analyse des thèmes (si demandée)
        themes_analysis = {}
        if current_generate_questions:
            workflow.update_step("analyze_themes", "running")
            themes_analysis = analyze_themes_with_volume_filter(
                keywords, all_suggestions, enriched_data, 
                question_generator, analysis_options['language']
            )
            workflow.complete_step("analyze_themes")
        
        # Finalisation
        workflow.update_step("finalize", "running")
        save_analysis_results(
            all_suggestions, enriched_data, themes_analysis,
            keywords, levels_config, current_generate_questions, analysis_options
        )
        workflow.complete_step("finalize")
        
        workflow.finish_workflow()
        st.success("✅ Analyse terminée!")
        st.rerun()
        
    except Exception as e:
        workflow.finish_workflow()
        st.error(f"❌ Erreur lors de l'analyse: {str(e)}")

def collect_google_suggestions(keywords, levels_config, google_client, language):
    """Collecte des suggestions Google"""
    all_suggestions = []
    for keyword in keywords:
        suggestions = google_client.get_multilevel_suggestions(
            keyword,
            language,
            levels_config['level1_count'],
            levels_config['level2_count'],
            levels_config['level3_count'],
            levels_config['enable_level2'],
            levels_config['enable_level3']
        )
        all_suggestions.extend(suggestions)
    
    return all_suggestions

def analyze_themes_with_volume_filter(keywords, all_suggestions, enriched_data, question_generator, language):
    """Analyse des thèmes uniquement sur les mots-clés avec volume de recherche"""
    themes_by_keyword = {}
    
    # Filtrer uniquement les mots-clés avec volume de recherche
    enriched_keywords = enriched_data.get('enriched_keywords', [])
    keywords_with_volume = [k for k in enriched_keywords if k.get('search_volume', 0) > 0]
    
    if not keywords_with_volume:
        st.warning("⚠️ Aucun mot-clé avec volume de recherche trouvé pour l'analyse des thèmes")
        return {}
    
    for keyword in keywords:
        # Trouver les mots-clés et suggestions associés avec volume
        related_keywords_with_volume = []
        
        # Mots-clés principaux avec volume
        main_keyword_with_volume = [k for k in keywords_with_volume if k['keyword'].lower() == keyword.lower()]
        related_keywords_with_volume.extend(main_keyword_with_volume)
        
        # Suggestions Google avec volume
        for suggestion in all_suggestions:
            if suggestion['Mot-clé'] == keyword and suggestion['Niveau'] > 0:
                suggestion_with_volume = [k for k in keywords_with_volume if k['keyword'].lower() == suggestion['Suggestion Google'].lower()]
                related_keywords_with_volume.extend(suggestion_with_volume)
        
        if related_keywords_with_volume:
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
                for enriched_kw in related_keywords_with_volume
                if enriched_kw['keyword'] != keyword
            ]
            
            if fake_suggestions:
                themes = question_generator.analyze_suggestions_themes(fake_suggestions, keyword, language)
                themes_by_keyword[keyword] = themes
    
    return themes_by_keyword

def save_analysis_results(all_suggestions, enriched_data, themes_analysis,
                         keywords, levels_config, generate_questions, analysis_options):
    """Sauvegarde des résultats d'analyse avec déduplication"""
    
    level_counts = {}
    for suggestion in all_suggestions:
        level = suggestion['Niveau']
        level_counts[level] = level_counts.get(level, 0) + 1
    
    # Dédupliquer les mots-clés enrichis
    deduplicated_keywords = []
    if enriched_data.get('enriched_keywords'):
        deduplicated_keywords = deduplicate_keywords_with_origins(enriched_data['enriched_keywords'])
    
    st.session_state.analysis_results = {
        'all_suggestions': all_suggestions,
        'level_counts': level_counts,
        'themes_analysis': themes_analysis,
        'enriched_keywords': deduplicated_keywords,
        'dataforseo_data': enriched_data,
        'stage': 'themes_analyzed' if themes_analysis else 'suggestions_collected'
    }
    
    st.session_state.analysis_metadata = {
        'keywords': keywords,
        **levels_config,
        'generate_questions': generate_questions,
        'final_questions_count': analysis_options.get('final_questions_count', 20),
        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
        'language': analysis_options['language']
    }

def render_results_section(question_generator, analysis_options):
    """Affichage de la section résultats avec le nouveau gestionnaire"""
    
    if not st.session_state.analysis_results:
        return
    
    results = st.session_state.analysis_results
    metadata = st.session_state.analysis_metadata
    
    # Utiliser le gestionnaire de résultats
    results_manager = ResultsManager(results, metadata)
    
    # Afficher le résumé
    results_manager.render_analysis_summary()
    
    # Interface de sélection des thèmes (si applicable)
    if (results.get('stage') == 'themes_analyzed' and 
        metadata.get('generate_questions')):
        render_theme_selection(question_generator, analysis_options['language'])
    
    # Affichage des résultats finaux
    elif results.get('stage') == 'questions_generated':
        results_manager.render_conversational_questions()
        results_manager.render_keywords_with_volume()
        results_manager.render_detailed_analysis()
    
    # Affichage des suggestions et mots-clés enrichis
    else:
        results_manager.render_suggestions_results()
        if results.get('enriched_keywords'):
            results_manager.render_keywords_with_volume()
            results_manager.render_detailed_analysis()

def render_theme_selection(question_generator, language):
    """Interface de sélection des thèmes - uniquement pour mots-clés avec volume"""
    st.markdown("---")
    st.markdown("## 🎨 Sélection des thèmes")
    
    # Vérifier quels mots-clés ont du volume
    results = st.session_state.analysis_results
    enriched_keywords = results.get('enriched_keywords', [])
    keywords_with_volume = [k['keyword'] for k in enriched_keywords if k.get('search_volume', 0) > 0]
    
    if not keywords_with_volume:
        st.warning("⚠️ Aucun mot-clé avec volume de recherche trouvé. Impossible de générer des questions conversationnelles.")
        return
    
    st.info(f"💡 Sélection des thèmes pour les mots-clés ayant du volume de recherche ({len(keywords_with_volume)} mots-clés)")
    
    themes_analysis = st.session_state.analysis_results.get('themes_analysis', {})
    selected_themes_by_keyword = {}
    
    for keyword, themes in themes_analysis.items():
        if themes:
            # Vérifier si ce mot-clé a du volume
            has_volume = keyword in keywords_with_volume
            
            # Vérifier les suggestions associées
            if not has_volume:
                keyword_suggestions = [s['Suggestion Google'] for s in results.get('all_suggestions', []) 
                                     if s['Mot-clé'] == keyword]
                for suggestion in keyword_suggestions:
                    if suggestion in keywords_with_volume:
                        has_volume = True
                        break
            
            if has_volume:
                st.markdown(f"### 🎯 Thèmes pour '{keyword}' 📊 (avec volume de recherche)")
                
                cols = st.columns(2)
                for i, theme in enumerate(themes):
                    with cols[i % 2]:
                        theme_name = theme.get('nom', f'Thème {i+1}')
                        is_selected = st.checkbox(
                            f"**{theme_name}**",
                            value=True,
                            key=f"{keyword}_{theme_name}_{i}",
                            help=f"Importance: {theme.get('importance', 3)}/5"
                        )
                        
                        if is_selected:
                            if keyword not in selected_themes_by_keyword:
                                selected_themes_by_keyword[keyword] = []
                            selected_themes_by_keyword[keyword].append(theme)
    
    # Bouton de génération
    if selected_themes_by_keyword:
        total_themes = sum(len(themes) for themes in selected_themes_by_keyword.values())
        st.info(f"🎯 {total_themes} thèmes sélectionnés pour {len(selected_themes_by_keyword)} mots-clés avec volume")
        
        if st.button("✨ Générer les questions", type="primary"):
            generate_questions_from_themes(
                selected_themes_by_keyword, question_generator, language
            )

def generate_questions_from_themes(selected_themes_by_keyword, question_generator, language):
    """Génération des questions à partir des thèmes sélectionnés"""
    
    metadata = st.session_state.analysis_metadata
    final_questions_count = metadata.get('final_questions_count', 20)
    
    all_questions_data = []
    
    for keyword, themes in selected_themes_by_keyword.items():
        questions = question_generator.generate_questions_from_themes(
            keyword, themes, final_questions_count // len(selected_themes_by_keyword), language
        )
        
        for q in questions:
            q['Mot-clé'] = keyword
            all_questions_data.append(q)
    
    # Tri par score d'importance
    sorted_questions = sorted(
        all_questions_data,
        key=lambda x: x.get('Score_Importance', 0),
        reverse=True
    )[:final_questions_count]
    
    # Sauvegarde
    st.session_state.analysis_results.update({
        'final_consolidated_data': sorted_questions,
        'selected_themes_by_keyword': selected_themes_by_keyword,
        'stage': 'questions_generated'
    })
    
    st.success(f"🎉 {len(sorted_questions)} questions générées!")
    st.rerun()

def render_instructions_tab():
    """Onglet des instructions"""
    st.markdown("""
    # 📖 Guide d'utilisation
    
    ## 🚀 Démarrage rapide
    
    1. **Configuration** : Ajoutez votre clé API OpenAI dans la sidebar
    2. **Mots-clés** : Entrez vos mots-clés (un par ligne)
    3. **Paramétrage** : Configurez les niveaux de suggestions
    4. **Analyse** : Lancez l'analyse et sélectionnez vos thèmes
    
    ## 📊 DataForSEO (Optionnel)
    
    Enrichissez votre analyse avec :
    - Volumes de recherche réels
    - Suggestions publicitaires Google Ads
    - Données de concurrence et CPC
    
    ## 🎯 Conseils d'optimisation
    
    - **Mots-clés spécifiques** plutôt que génériques
    - **Variez les intentions** (info, transaction, navigation)
    - **Adaptez la langue** selon votre audience
    - **Testez différents niveaux** de suggestions
    """)

def clear_results():
    """Effacement des résultats"""
    st.session_state.analysis_results = None
    st.session_state.analysis_metadata = None
    st.rerun()

if __name__ == "__main__":
    main()