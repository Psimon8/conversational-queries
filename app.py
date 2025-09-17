import streamlit as st
from openai import OpenAI
import pandas as pd
import time

# Imports des modules refactorisés
from utils.ui_components import setup_page_config, render_header, render_social_links, render_metrics
from utils.config_manager import ConfigManager
from utils.export_manager import ExportManager
from question_generator import QuestionGenerator
from dataforseo_client import DataForSEOClient
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
    
    # Configuration dans la sidebar
    api_key = config_manager.render_openai_config()
    enable_dataforseo, dataforseo_config = config_manager.render_dataforseo_config()
    analysis_options = config_manager.render_analysis_options()
    
    # Initialisation des clients
    client = OpenAI(api_key=api_key) if api_key else None
    question_generator = QuestionGenerator(client)
    google_client = GoogleSuggestionsClient()
    
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
        api_key, 
        enable_dataforseo, 
        dataforseo_config, 
        analysis_options
    )

def initialize_session_state():
    """Initialisation du session state"""
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    if 'analysis_metadata' not in st.session_state:
        st.session_state.analysis_metadata = None

def render_main_interface(config_manager, google_client, question_generator, 
                         api_key, enable_dataforseo, dataforseo_config, analysis_options):
    """Interface principale d'analyse"""
    
    # Création des onglets
    tab1, tab2 = st.tabs(["🔍 Analyseur de Requêtes", "📖 Instructions"])
    
    with tab1:
        render_analysis_tab(
            config_manager, google_client, question_generator,
            api_key, enable_dataforseo, dataforseo_config, analysis_options
        )
    
    with tab2:
        render_instructions_tab()

def render_analysis_tab(config_manager, google_client, question_generator,
                       api_key, enable_dataforseo, dataforseo_config, analysis_options):
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
    
    # Estimation des coûts si DataForSEO activé
    if enable_dataforseo and keywords_input:
        keywords = [kw.strip() for kw in keywords_input.split('\n') if kw.strip()]
        if keywords:
            config_manager.render_cost_estimation(len(keywords), levels_config)
    
    # Boutons d'action
    col_analyze, col_clear = st.columns([4, 1])
    
    with col_analyze:
        if keywords_input and st.button("🚀 Analyser les suggestions", type="primary"):
            run_analysis(
                keywords_input, levels_config, google_client, question_generator,
                api_key, enable_dataforseo, dataforseo_config, analysis_options
            )
    
    with col_clear:
        if st.button("🗑️ Effacer", help="Effacer les résultats"):
            clear_results()
    
    # Affichage des résultats
    render_results_section(question_generator, analysis_options)

def run_analysis(keywords_input, levels_config, google_client, question_generator,
                api_key, enable_dataforseo, dataforseo_config, analysis_options):
    """Exécution de l'analyse"""
    
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
    
    try:
        # Étape 1: Collecte des suggestions
        all_suggestions = collect_google_suggestions(
            keywords, levels_config, google_client, analysis_options['language']
        )
        
        if not all_suggestions:
            st.error("❌ Aucune suggestion trouvée")
            return
        
        # Étape 2: Enrichissement DataForSEO (optionnel)
        enriched_data = {}
        if enable_dataforseo and dataforseo_config.get('login') and dataforseo_config.get('password'):
            enriched_data = enrich_with_dataforseo(
                keywords, all_suggestions, dataforseo_config
            )
        
        # Étape 3: Analyse des thèmes (si demandée)
        themes_analysis = {}
        if current_generate_questions:
            themes_analysis = analyze_themes(
                keywords, all_suggestions, enriched_data, 
                question_generator, analysis_options['language']
            )
        
        # Sauvegarde des résultats
        save_analysis_results(
            all_suggestions, enriched_data, themes_analysis,
            keywords, levels_config, current_generate_questions, analysis_options
        )
        
        st.success("✅ Analyse terminée!")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Erreur lors de l'analyse: {str(e)}")

def collect_google_suggestions(keywords, levels_config, google_client, language):
    """Collecte des suggestions Google"""
    st.info("⏳ Collecte des suggestions Google...")
    
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

def enrich_with_dataforseo(keywords, all_suggestions, dataforseo_config):
    """Enrichissement avec DataForSEO"""
    from dataforseo_client import DataForSEOClient
    
    client = DataForSEOClient()
    client.set_credentials(dataforseo_config['login'], dataforseo_config['password'])
    
    suggestion_texts = [s['Suggestion Google'] for s in all_suggestions if s['Niveau'] > 0]
    
    return client.process_keywords_complete(
        keywords,
        suggestion_texts,
        dataforseo_config['language'],
        dataforseo_config['location'],
        dataforseo_config['min_volume']
    )

def analyze_themes(keywords, all_suggestions, enriched_data, question_generator, language):
    """Analyse des thèmes"""
    st.info("⏳ Analyse des thèmes...")
    
    themes_by_keyword = {}
    for keyword in keywords:
        keyword_suggestions = [s for s in all_suggestions if s['Mot-clé'] == keyword]
        themes = question_generator.analyze_suggestions_themes(
            keyword_suggestions, keyword, language
        )
        themes_by_keyword[keyword] = themes
    
    return themes_by_keyword

def save_analysis_results(all_suggestions, enriched_data, themes_analysis,
                         keywords, levels_config, generate_questions, analysis_options):
    """Sauvegarde des résultats d'analyse"""
    
    level_counts = {}
    for suggestion in all_suggestions:
        level = suggestion['Niveau']
        level_counts[level] = level_counts.get(level, 0) + 1
    
    st.session_state.analysis_results = {
        'all_suggestions': all_suggestions,
        'level_counts': level_counts,
        'themes_analysis': themes_analysis,
        'enriched_keywords': enriched_data.get('enriched_keywords', []),
        'dataforseo_data': enriched_data,
        'stage': 'themes_analyzed'
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
    """Affichage de la section résultats"""
    
    if not st.session_state.analysis_results:
        return
    
    results = st.session_state.analysis_results
    metadata = st.session_state.analysis_metadata
    
    # Interface de sélection des thèmes
    if (results.get('stage') == 'themes_analyzed' and 
        metadata.get('generate_questions')):
        render_theme_selection(question_generator, analysis_options['language'])
    
    # Affichage des résultats finaux
    elif results.get('stage') == 'questions_generated':
        render_final_results()
    
    # Affichage des suggestions seulement
    elif results.get('all_suggestions'):
        render_suggestions_only()

def render_theme_selection(question_generator, language):
    """Interface de sélection des thèmes"""
    st.markdown("---")
    st.markdown("## 🎨 Sélection des thèmes")
    
    themes_analysis = st.session_state.analysis_results.get('themes_analysis', {})
    selected_themes_by_keyword = {}
    
    for keyword, themes in themes_analysis.items():
        if themes:
            st.markdown(f"### 🎯 Thèmes pour '{keyword}'")
            
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
    
    # Tri et limitation
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

def render_final_results():
    """Affichage des résultats finaux"""
    results = st.session_state.analysis_results
    metadata = st.session_state.analysis_metadata
    
    st.markdown("---")
    st.markdown("## 📊 Résultats finaux")
    
    # Métriques principales
    metrics = {
        "Mots-clés": len(metadata['keywords']),
        "Suggestions": len(results['all_suggestions']),
        "Questions": len(results['final_consolidated_data']),
        "Thèmes sélectionnés": sum(len(themes) for themes in results.get('selected_themes_by_keyword', {}).values())
    }
    
    # Ajouter métriques DataForSEO si disponible
    if results.get('enriched_keywords'):
        enriched_keywords = results['enriched_keywords']
        keywords_with_volume = [k for k in enriched_keywords if k.get('search_volume', 0) > 0]
        ads_keywords = [k for k in enriched_keywords if k.get('source') == 'google_ads']
        
        metrics.update({
            "Avec volume": len(keywords_with_volume),
            "Suggestions Ads": len(ads_keywords)
        })
    
    render_metrics(metrics)
    
    # Tableau des questions avec volumes si disponible
    if results.get('final_consolidated_data'):
        st.markdown("### 📋 Questions conversationnelles")
        df = pd.DataFrame(results['final_consolidated_data'])
        
        # Si on a des données enrichies, essayer de les associer aux questions
        if results.get('enriched_keywords'):
            enriched_df = pd.DataFrame(results['enriched_keywords'])
            if not enriched_df.empty and 'keyword' in enriched_df.columns:
                # Merger les données de volume avec les questions
                merged_df = df.merge(
                    enriched_df[['keyword', 'search_volume', 'cpc']],
                    left_on='Suggestion Google',
                    right_on='keyword',
                    how='left'
                )
                
                display_cols = ['Question Conversationnelle', 'Suggestion Google', 'Thème', 'Intention', 'Score_Importance', 'search_volume', 'cpc']
                available_cols = [col for col in display_cols if col in merged_df.columns]
                
                display_df = merged_df[available_cols].copy()
                
                # Renommer et formater les colonnes
                column_mapping = {
                    'search_volume': 'Volume',
                    'cpc': 'CPC'
                }
                display_df = display_df.rename(columns=column_mapping)
                
                if 'Volume' in display_df.columns:
                    display_df['Volume'] = display_df['Volume'].fillna(0).astype(int)
                if 'CPC' in display_df.columns:
                    display_df['CPC'] = display_df['CPC'].fillna(0).round(2)
                
                st.dataframe(display_df, width='stretch')
            else:
                # Fallback sans données de volume
                display_cols = ['Question Conversationnelle', 'Suggestion Google', 'Thème', 'Intention', 'Score_Importance']
                available_cols = [col for col in display_cols if col in df.columns]
                st.dataframe(df[available_cols], width='stretch')
        else:
            # Pas de données DataForSEO
            display_cols = ['Question Conversationnelle', 'Suggestion Google', 'Thème', 'Intention', 'Score_Importance']
            available_cols = [col for col in display_cols if col in df.columns]
            st.dataframe(df[available_cols], width='stretch')
    
    # Afficher aussi l'analyse des mots-clés si DataForSEO activé
    if results.get('enriched_keywords'):
        with st.expander("📈 Analyse détaillée des mots-clés et volumes"):
            render_detailed_keywords_analysis(results)

def render_detailed_keywords_analysis(results):
    """Affichage détaillé de l'analyse des mots-clés"""
    enriched_keywords = results.get('enriched_keywords', [])
    
    if not enriched_keywords:
        st.info("Aucune donnée enrichie disponible")
        return
    
    # Séparer par source
    google_suggest_keywords = [k for k in enriched_keywords if k.get('source') == 'google_suggest']
    google_ads_keywords = [k for k in enriched_keywords if k.get('source') == 'google_ads']
    
    tab1, tab2 = st.tabs(["🔍 Google Suggest", "💰 Google Ads"])
    
    with tab1:
        if google_suggest_keywords:
            st.markdown(f"**{len(google_suggest_keywords)} mots-clés de Google Suggest**")
            
            # Créer un DataFrame pour Google Suggest
            suggest_df = pd.DataFrame(google_suggest_keywords)
            display_suggest = suggest_df[['keyword', 'search_volume', 'cpc', 'competition_level']].copy()
            display_suggest.columns = ['Mot-clé', 'Volume', 'CPC', 'Concurrence']
            display_suggest['Volume'] = display_suggest['Volume'].fillna(0).astype(int)
            display_suggest['CPC'] = display_suggest['CPC'].fillna(0).round(2)
            
            # Trier par volume décroissant
            display_suggest = display_suggest.sort_values('Volume', ascending=False)
            
            st.dataframe(display_suggest, width='stretch')
            
            # Statistiques Google Suggest
            volumes = display_suggest['Volume'].tolist()
            st.markdown("**Statistiques:**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Volume total", f"{sum(volumes):,}")
            with col2:
                st.metric("Volume moyen", f"{sum(volumes)/len(volumes):.0f}")
            with col3:
                st.metric("Avec volume > 0", len([v for v in volumes if v > 0]))
            with col4:
                st.metric("Volume max", f"{max(volumes):,}")
        else:
            st.info("Aucun mot-clé Google Suggest enrichi")
    
    with tab2:
        if google_ads_keywords:
            st.markdown(f"**{len(google_ads_keywords)} suggestions Google Ads**")
            
            # Créer un DataFrame pour Google Ads
            ads_df = pd.DataFrame(google_ads_keywords)
            display_ads = ads_df[['keyword', 'search_volume', 'cpc', 'competition_level', 'source_keyword']].copy()
            display_ads.columns = ['Suggestion Ads', 'Volume', 'CPC', 'Concurrence', 'Basé sur']
            display_ads['Volume'] = display_ads['Volume'].fillna(0).astype(int)
            display_ads['CPC'] = display_ads['CPC'].fillna(0).round(2)
            
            # Trier par volume décroissant
            display_ads = display_ads.sort_values('Volume', ascending=False)
            
            st.dataframe(display_ads, width='stretch')
            
            # Statistiques Google Ads
            volumes_ads = display_ads['Volume'].tolist()
            cpcs = display_ads['CPC'].tolist()
            st.markdown("**Statistiques:**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Volume total", f"{sum(volumes_ads):,}")
            with col2:
                st.metric("Volume moyen", f"{sum(volumes_ads)/len(volumes_ads):.0f}")
            with col3:
                st.metric("CPC moyen", f"${sum(cpcs)/len(cpcs):.2f}")
            with col4:
                st.metric("Avec volume > 0", len([v for v in volumes_ads if v > 0]))
        else:
            st.info("Aucune suggestion Google Ads trouvée")

def render_suggestions_only():
    """Affichage des suggestions uniquement"""
    results = st.session_state.analysis_results
    metadata = st.session_state.analysis_metadata
    
    st.markdown("---")
    st.markdown("## 📊 Suggestions collectées")
    
    # Métriques principales
    metrics = {
        "Mots-clés": len(metadata['keywords']),
        "Suggestions": len(results['all_suggestions']),
        "Niveaux": max(results.get('level_counts', {}).keys()) + 1 if results.get('level_counts') else 1
    }
    
    # Ajouter métriques DataForSEO si disponible
    if results.get('enriched_keywords'):
        enriched_keywords = results['enriched_keywords']
        keywords_with_volume = [k for k in enriched_keywords if k.get('search_volume', 0) > 0]
        ads_keywords = [k for k in enriched_keywords if k.get('source') == 'google_ads']
        
        metrics.update({
            "Avec volume": len(keywords_with_volume),
            "Suggestions Ads": len(ads_keywords)
        })
    
    render_metrics(metrics)
    
    # Tableau des suggestions avec volumes si disponible
    df = pd.DataFrame(results['all_suggestions'])
    
    # Si on a des données DataForSEO, les merger
    if results.get('enriched_keywords'):
        enriched_df = pd.DataFrame(results['enriched_keywords'])
        if not enriched_df.empty and 'keyword' in enriched_df.columns:
            # Merger les données
            merged_df = df.merge(
                enriched_df[['keyword', 'search_volume', 'cpc', 'competition_level', 'source']],
                left_on='Suggestion Google',
                right_on='keyword',
                how='left'
            )
            
            # Colonnes à afficher
            display_cols = ['Mot-clé', 'Suggestion Google', 'Niveau', 'Parent', 'search_volume', 'cpc', 'competition_level', 'source']
            available_cols = [col for col in display_cols if col in merged_df.columns]
            
            # Renommer les colonnes pour l'affichage
            column_mapping = {
                'search_volume': 'Volume',
                'cpc': 'CPC',
                'competition_level': 'Concurrence',
                'source': 'Source'
            }
            
            display_df = merged_df[available_cols].copy()
            display_df = display_df.rename(columns=column_mapping)
            
            # Formater les colonnes numériques
            if 'Volume' in display_df.columns:
                display_df['Volume'] = display_df['Volume'].fillna(0).astype(int)
            if 'CPC' in display_df.columns:
                display_df['CPC'] = display_df['CPC'].fillna(0).round(2)
            
            # Remplacer les valeurs de source pour plus de clarté
            if 'Source' in display_df.columns:
                display_df['Source'] = display_df['Source'].fillna('google_suggest').replace({
                    'google_suggest': '🔍 Google Suggest',
                    'google_ads': '💰 Google Ads'
                })
            
            st.dataframe(display_df, width='stretch')
            
            # Section dédiée aux suggestions Google Ads
            ads_suggestions = results.get('dataforseo_data', {}).get('ads_suggestions', [])
            if ads_suggestions:
                st.markdown("### 💰 Suggestions Google Ads supplémentaires")
                st.info(f"📈 {len(ads_suggestions)} suggestions publicitaires découvertes via DataForSEO")
                
                ads_df = pd.DataFrame(ads_suggestions)
                ads_display_cols = ['keyword', 'search_volume', 'cpc', 'competition_level', 'source_keyword']
                ads_available_cols = [col for col in ads_display_cols if col in ads_df.columns]
                
                if ads_available_cols:
                    ads_display = ads_df[ads_available_cols].copy()
                    ads_display.columns = ['Mot-clé Ads', 'Volume', 'CPC', 'Concurrence', 'Basé sur']
                    
                    # Formater les colonnes
                    ads_display['Volume'] = ads_display['Volume'].fillna(0).astype(int)
                    ads_display['CPC'] = ads_display['CPC'].fillna(0).round(2)
                    
                    # Filtrer pour n'afficher que ceux avec du volume
                    ads_with_volume = ads_display[ads_display['Volume'] > 0].sort_values('Volume', ascending=False)
                    
                    if not ads_with_volume.empty:
                        st.dataframe(ads_with_volume, width='stretch')
                    else:
                        st.info("Aucune suggestion Ads avec volume significatif trouvée")
        else:
            # Pas de données DataForSEO, affichage simple
            st.dataframe(df[['Mot-clé', 'Suggestion Google', 'Niveau', 'Parent']], width='stretch')
    else:
        # Pas de données DataForSEO, affichage simple
        st.dataframe(df[['Mot-clé', 'Suggestion Google', 'Niveau', 'Parent']], width='stretch')
    
    # Statistiques détaillées si DataForSEO activé
    if results.get('enriched_keywords'):
        st.markdown("### 📈 Analyse des volumes de recherche")
        
        enriched_keywords = results['enriched_keywords']
        
        # Statistiques par source
        google_suggest_keywords = [k for k in enriched_keywords if k.get('source') == 'google_suggest']
        google_ads_keywords = [k for k in enriched_keywords if k.get('source') == 'google_ads']
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🔍 Google Suggest")
            if google_suggest_keywords:
                volumes_suggest = [k.get('search_volume', 0) for k in google_suggest_keywords]
                avg_volume_suggest = sum(volumes_suggest) / len(volumes_suggest)
                max_volume_suggest = max(volumes_suggest)
                
                st.metric("Suggestions totales", len(google_suggest_keywords))
                st.metric("Volume moyen", f"{avg_volume_suggest:.0f}")
                st.metric("Volume maximum", f"{max_volume_suggest:,}")
                
                # Top suggestions Google Suggest avec volume
                top_suggest = sorted(google_suggest_keywords, key=lambda x: x.get('search_volume', 0), reverse=True)[:5]
                if top_suggest and top_suggest[0].get('search_volume', 0) > 0:
                    st.markdown("**Top 5 suggestions Google:**")
                    for i, kw in enumerate(top_suggest, 1):
                        if kw.get('search_volume', 0) > 0:
                            st.write(f"{i}. **{kw['keyword']}** - {kw['search_volume']:,} vol/mois")
        
        with col2:
            st.markdown("#### 💰 Google Ads")
            if google_ads_keywords:
                volumes_ads = [k.get('search_volume', 0) for k in google_ads_keywords]
                avg_volume_ads = sum(volumes_ads) / len(volumes_ads)
                max_volume_ads = max(volumes_ads)
                
                st.metric("Suggestions Ads", len(google_ads_keywords))
                st.metric("Volume moyen", f"{avg_volume_ads:.0f}")
                st.metric("Volume maximum", f"{max_volume_ads:,}")
                
                # Top suggestions Google Ads avec volume
                top_ads = sorted(google_ads_keywords, key=lambda x: x.get('search_volume', 0), reverse=True)[:5]
                if top_ads and top_ads[0].get('search_volume', 0) > 0:
                    st.markdown("**Top 5 suggestions Ads:**")
                    for i, kw in enumerate(top_ads, 1):
                        if kw.get('search_volume', 0) > 0:
                            st.write(f"{i}. **{kw['keyword']}** - {kw['search_volume']:,} vol/mois - CPC: ${kw.get('cpc', 0):.2f}")
            else:
                st.info("Aucune suggestion Google Ads trouvée")

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