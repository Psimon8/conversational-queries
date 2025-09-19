import streamlit as st
from openai import OpenAI
import pandas as pd
import time
import unicodedata
import re

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

def normalize_keyword(keyword):
    """Normalise un mot-clé: supprime accents, caractères spéciaux, met en minuscule"""
    if not keyword:
        return ""
    
    # Convertir en minuscule
    keyword = keyword.lower()
    
    # Supprimer les accents
    keyword = unicodedata.normalize('NFD', keyword)
    keyword = ''.join(char for char in keyword if unicodedata.category(char) != 'Mn')
    
    # Supprimer les caractères spéciaux sauf espaces et traits d'union
    keyword = re.sub(r'[^\w\s-]', '', keyword)
    
    # Normaliser les espaces multiples
    keyword = ' '.join(keyword.split())
    
    return keyword.strip()

def deduplicate_keywords_with_origins(enriched_keywords):
    """Déduplique les mots-clés et fusionne les origines multiples"""
    if not enriched_keywords:
        return []
    
    # Dictionnaire pour regrouper par mot-clé normalisé
    normalized_keywords = {}
    
    for keyword_data in enriched_keywords:
        original_keyword = keyword_data.get('keyword', '')
        normalized = normalize_keyword(original_keyword)
        
        if normalized not in normalized_keywords:
            # Premier mot-clé de ce groupe
            normalized_keywords[normalized] = {
                'keyword': original_keyword,  # Garder la version originale
                'search_volume': keyword_data.get('search_volume', 0),
                'cpc': keyword_data.get('cpc', 0),
                'competition': keyword_data.get('competition', 0),
                'competition_level': keyword_data.get('competition_level', 'UNKNOWN'),
                'sources': set(),  # Utiliser un set pour éviter les doublons d'origine
                'type': keyword_data.get('type', 'original')
            }
        else:
            # Fusionner avec le mot-clé existant
            existing = normalized_keywords[normalized]
            
            # Prendre les meilleures valeurs (volume max, etc.)
            if keyword_data.get('search_volume', 0) > existing['search_volume']:
                existing['search_volume'] = keyword_data.get('search_volume', 0)
            if keyword_data.get('cpc', 0) > existing['cpc']:
                existing['cpc'] = keyword_data.get('cpc', 0)
            if keyword_data.get('competition', 0) > existing['competition']:
                existing['competition'] = keyword_data.get('competition', 0)
        
        # Déterminer l'origine pour ce mot-clé
        source = keyword_data.get('source', 'google_suggest')
        if source == 'google_ads':
            normalized_keywords[normalized]['sources'].add('💰 Suggestion Ads')
        else:
            # Vérifier si c'est un mot-clé principal
            if keyword_data.get('type') == 'original':
                normalized_keywords[normalized]['sources'].add('🎯 Mot-clé principal')
            else:
                normalized_keywords[normalized]['sources'].add('🔍 Suggestion Google')
    
    # Convertir en liste avec origines concaténées
    result = []
    for normalized, data in normalized_keywords.items():
        # Joindre toutes les sources
        origins = sorted(list(data['sources']))  # Trier pour un ordre cohérent
        data['origine'] = ' + '.join(origins)
        
        # Nettoyer les sources du dictionnaire
        del data['sources']
        
        result.append(data)
    
    return result

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
    
    # Suppression de l'estimation des coûts DataForSEO
    
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
    """Analyse des thèmes uniquement sur les mots-clés avec volume de recherche"""
    st.info("⏳ Analyse des thèmes...")
    
    themes_by_keyword = {}
    
    # Filtrer uniquement les mots-clés avec volume de recherche
    enriched_keywords = enriched_data.get('enriched_keywords', [])
    keywords_with_volume = [k for k in enriched_keywords if k.get('search_volume', 0) > 0]
    
    if not keywords_with_volume:
        st.warning("⚠️ Aucun mot-clé avec volume de recherche trouvé pour l'analyse des thèmes")
        return {}
    
    # Grouper par mot-clé principal d'origine
    for keyword in keywords:
        # Trouver tous les mots-clés enrichis avec volume liés à ce mot-clé principal
        related_keywords_with_volume = []
        
        # Mots-clés principaux avec volume
        main_keyword_with_volume = [k for k in keywords_with_volume if k['keyword'].lower() == keyword.lower()]
        related_keywords_with_volume.extend(main_keyword_with_volume)
        
        # Suggestions Google avec volume
        for suggestion in all_suggestions:
            if suggestion['Mot-clé'] == keyword and suggestion['Niveau'] > 0:
                suggestion_with_volume = [k for k in keywords_with_volume if k['keyword'].lower() == suggestion['Suggestion Google'].lower()]
                related_keywords_with_volume.extend(suggestion_with_volume)
        
        # Suggestions Ads avec volume (déjà filtrées car dans keywords_with_volume)
        ads_suggestions = [k for k in keywords_with_volume if k.get('source') == 'google_ads']
        for ads_suggestion in ads_suggestions:
            # Associer les suggestions Ads aux mots-clés principaux
            if any(kw.lower() in ads_suggestion.get('source_keyword', '').lower() or 
                  ads_suggestion.get('source_keyword', '').lower() in kw.lower() 
                  for kw in [keyword]):
                if ads_suggestion not in related_keywords_with_volume:
                    related_keywords_with_volume.append(ads_suggestion)
        
        if related_keywords_with_volume:
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
                for enriched_kw in related_keywords_with_volume
                if enriched_kw['keyword'] != keyword  # Exclure le mot-clé principal
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
        'enriched_keywords': deduplicated_keywords,  # Utiliser la version dédupliquée
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
            # Vérifier si ce mot-clé a du volume (lui ou ses suggestions)
            has_volume = False
            
            # Vérifier le mot-clé principal
            if keyword in keywords_with_volume:
                has_volume = True
            
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
            else:
                st.markdown(f"### ⚪ Thèmes pour '{keyword}' (sans volume de recherche - ignoré)")
                st.caption("Ce mot-clé et ses suggestions n'ont pas de volume de recherche significatif")
    
    # Bouton de génération
    if selected_themes_by_keyword:
        total_themes = sum(len(themes) for themes in selected_themes_by_keyword.values())
        st.info(f"🎯 {total_themes} thèmes sélectionnés pour {len(selected_themes_by_keyword)} mots-clés avec volume")
        
        if st.button("✨ Générer les questions", type="primary"):
            generate_questions_from_themes(
                selected_themes_by_keyword, question_generator, language
            )
    else:
        st.warning("⚠️ Aucun thème sélectionné pour des mots-clés avec volume de recherche")

def generate_questions_from_themes(selected_themes_by_keyword, question_generator, language):
    """Génération des questions à partir des thèmes sélectionnés - uniquement pour mots-clés avec volume"""
    
    metadata = st.session_state.analysis_metadata
    final_questions_count = metadata.get('final_questions_count', 20)
    
    # Filtrer les thèmes pour ne garder que ceux des mots-clés avec volume
    results = st.session_state.analysis_results
    enriched_keywords = results.get('enriched_keywords', [])
    keywords_with_volume = [k['keyword'] for k in enriched_keywords if k.get('search_volume', 0) > 0]
    
    # Filtrer les thèmes sélectionnés
    filtered_themes_by_keyword = {}
    for keyword, themes in selected_themes_by_keyword.items():
        # Vérifier si ce mot-clé ou ses suggestions ont du volume
        has_volume = False
        
        # Vérifier le mot-clé principal
        if keyword in keywords_with_volume:
            has_volume = True
        
        # Vérifier les suggestions associées
        if not has_volume:
            keyword_suggestions = [s['Suggestion Google'] for s in results.get('all_suggestions', []) 
                                 if s['Mot-clé'] == keyword]
            for suggestion in keyword_suggestions:
                if suggestion in keywords_with_volume:
                    has_volume = True
                    break
        
        if has_volume:
            filtered_themes_by_keyword[keyword] = themes
    
    if not filtered_themes_by_keyword:
        st.warning("⚠️ Aucun thème sélectionné ne correspond à des mots-clés avec volume de recherche")
        return
    
    st.info(f"💡 Génération de questions pour {len(filtered_themes_by_keyword)} mots-clés avec volume de recherche")
    
    all_questions_data = []
    
    for keyword, themes in filtered_themes_by_keyword.items():
        questions = question_generator.generate_questions_from_themes(
            keyword, themes, final_questions_count // len(filtered_themes_by_keyword), language
        )
        
        for q in questions:
            q['Mot-clé'] = keyword
            # Associer le volume de recherche si disponible
            matching_keyword = next((k for k in enriched_keywords 
                                   if k['keyword'].lower() == q.get('Suggestion Google', '').lower()), None)
            if matching_keyword:
                q['Volume_Recherche'] = matching_keyword.get('search_volume', 0)
                q['CPC'] = matching_keyword.get('cpc', 0)
                q['Source'] = matching_keyword.get('source', 'google_suggest')
            
            all_questions_data.append(q)
    
    # Tri par volume de recherche puis par score d'importance
    sorted_questions = sorted(
        all_questions_data,
        key=lambda x: (x.get('Volume_Recherche', 0), x.get('Score_Importance', 0)),
        reverse=True
    )[:final_questions_count]
    
    # Sauvegarde
    st.session_state.analysis_results.update({
        'final_consolidated_data': sorted_questions,
        'selected_themes_by_keyword': filtered_themes_by_keyword,
        'stage': 'questions_generated'
    })
    
    st.success(f"🎉 {len(sorted_questions)} questions générées à partir de mots-clés avec volume de recherche!")
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
        
        # Compter les suggestions Ads (celles qui contiennent cette origine)
        ads_keywords = [k for k in enriched_keywords if '💰 Suggestion Ads' in k.get('origine', '')]
        
        metrics.update({
            "Avec volume": len(keywords_with_volume),
            "Suggestions Ads": len(ads_keywords)
        })
    
    render_metrics(metrics)
    
    # Afficher la liste des mots-clés avec volume AVANT les questions
    if results.get('enriched_keywords'):
        render_keywords_with_volume_list(results)
    
    # Tableau des questions avec volumes si disponible
    if results.get('final_consolidated_data'):
        st.markdown("### 📋 Questions conversationnelles")
        st.info("💡 Ces questions sont générées uniquement à partir des mots-clés ayant un volume de recherche")
        
        df = pd.DataFrame(results['final_consolidated_data'])
        
        # Si on a des données enrichies, essayer de les associer aux questions
        if results.get('enriched_keywords'):
            enriched_df = pd.DataFrame(results['enriched_keywords'])
            if not enriched_df.empty and 'keyword' in enriched_df.columns:
                # Merger les données de volume avec les questions
                merged_df = df.merge(
                    enriched_df[['keyword', 'search_volume', 'cpc', 'origine']],
                    left_on='Suggestion Google',
                    right_on='keyword',
                    how='left'
                )
                
                display_cols = ['Question Conversationnelle', 'Suggestion Google', 'Thème', 'Intention', 'Score_Importance', 'search_volume', 'cpc', 'origine']
                available_cols = [col for col in display_cols if col in merged_df.columns]
                
                display_df = merged_df[available_cols].copy()
                
                # Renommer et formater les colonnes
                column_mapping = {
                    'search_volume': 'Volume',
                    'cpc': 'CPC',
                    'origine': 'Origine'
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

def render_keywords_with_volume_list(results):
    """Affichage de la liste des mots-clés avec volume de recherche utilisés pour les questions"""
    st.markdown("### 🎯 Mots-clés avec volume de recherche")
    st.info("📊 Ces mots-clés ont été utilisés pour générer les questions conversationnelles")
    
    enriched_keywords = results.get('enriched_keywords', [])
    keywords_with_volume = [k for k in enriched_keywords if k.get('search_volume', 0) > 0]
    
    if not keywords_with_volume:
        st.warning("⚠️ Aucun mot-clé avec volume de recherche trouvé")
        return
    
    # Créer le DataFrame avec les données dédupliquées
    keywords_df = pd.DataFrame(keywords_with_volume)
    
    # Préparer l'affichage avec la colonne origine fusionnée
    display_cols = ['keyword', 'search_volume', 'cpc', 'competition_level', 'origine']
    available_cols = [col for col in display_cols if col in keywords_df.columns]
    
    display_keywords = keywords_df[available_cols].copy()
    display_keywords.columns = ['Mot-clé', 'Volume/mois', 'CPC', 'Concurrence', 'Origine']
    
    # Formater les colonnes
    display_keywords['Volume/mois'] = display_keywords['Volume/mois'].fillna(0).astype(int)
    display_keywords['CPC'] = display_keywords['CPC'].fillna(0).round(2)
    
    # Trier par volume décroissant
    display_keywords = display_keywords.sort_values('Volume/mois', ascending=False)
    
    # Afficher avec mise en forme
    st.dataframe(display_keywords, width='stretch')
    
    # Statistiques rapides
    col1, col2, col3, col4 = st.columns(4)
    
    total_volume = display_keywords['Volume/mois'].sum()
    avg_volume = display_keywords['Volume/mois'].mean()
    max_volume = display_keywords['Volume/mois'].max()
    avg_cpc = display_keywords['CPC'].mean()
    
    with col1:
        st.metric("Volume total", f"{total_volume:,}")
    with col2:
        st.metric("Volume moyen", f"{avg_volume:.0f}")
    with col3:
        st.metric("Volume max", f"{max_volume:,}")
    with col4:
        st.metric("CPC moyen", f"${avg_cpc:.2f}")
    
    # Analyse des origines (compter les mots-clés par type d'origine)
    st.markdown("**Répartition par origine:**")
    
    # Compter les occurrences de chaque type d'origine
    origin_stats = {
        '🎯 Mot-clé principal': 0,
        '🔍 Suggestion Google': 0,
        '💰 Suggestion Ads': 0,
        'Multiples origines': 0
    }
    
    for origin in display_keywords['Origine']:
        if '+' in origin:  # Multiple origines
            origin_stats['Multiples origines'] += 1
        elif '🎯 Mot-clé principal' in origin:
            origin_stats['🎯 Mot-clé principal'] += 1
        elif '💰 Suggestion Ads' in origin:
            origin_stats['💰 Suggestion Ads'] += 1
        elif '🔍 Suggestion Google' in origin:
            origin_stats['🔍 Suggestion Google'] += 1
    
    for origin, count in origin_stats.items():
        if count > 0:
            st.write(f"- {origin}: {count} mots-clés")

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
        
        # Compter les suggestions Ads (celles qui contiennent cette origine)
        ads_keywords = [k for k in enriched_keywords if '💰 Suggestion Ads' in k.get('origine', '')]
        
        metrics.update({
            "Avec volume": len(keywords_with_volume),
            "Suggestions Ads": len(ads_keywords)
        })
    
    render_metrics(metrics)
    
    # Afficher la liste des mots-clés avec volume AVANT les questions
    if results.get('enriched_keywords'):
        render_keywords_with_volume_list(results)
    
    # Tableau des questions avec volumes si disponible
    if results.get('final_consolidated_data'):
        st.markdown("### 📋 Questions conversationnelles")
        st.info("💡 Ces questions sont générées uniquement à partir des mots-clés ayant un volume de recherche")
        
        df = pd.DataFrame(results['final_consolidated_data'])
        
        # Si on a des données enrichies, essayer de les associer aux questions
        if results.get('enriched_keywords'):
            enriched_df = pd.DataFrame(results['enriched_keywords'])
            if not enriched_df.empty and 'keyword' in enriched_df.columns:
                # Merger les données de volume avec les questions
                merged_df = df.merge(
                    enriched_df[['keyword', 'search_volume', 'cpc', 'origine']],
                    left_on='Suggestion Google',
                    right_on='keyword',
                    how='left'
                )
                
                display_cols = ['Question Conversationnelle', 'Suggestion Google', 'Thème', 'Intention', 'Score_Importance', 'search_volume', 'cpc', 'origine']
                available_cols = [col for col in display_cols if col in merged_df.columns]
                
                display_df = merged_df[available_cols].copy()
                
                # Renommer et formater les colonnes
                column_mapping = {
                    'search_volume': 'Volume',
                    'cpc': 'CPC',
                    'origine': 'Origine'
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
    """Affichage détaillé de l'analyse des mots-clés dédupliqués"""
    enriched_keywords = results.get('enriched_keywords', [])
    
    if not enriched_keywords:
        st.info("Aucune donnée enrichie disponible")
        return
    
    # Séparer par type d'origine principale
    google_suggest_keywords = [k for k in enriched_keywords if '🔍 Suggestion Google' in k.get('origine', '') and '💰 Suggestion Ads' not in k.get('origine', '')]
    google_ads_keywords = [k for k in enriched_keywords if '💰 Suggestion Ads' in k.get('origine', '') and '🔍 Suggestion Google' not in k.get('origine', '')]
    main_keywords = [k for k in enriched_keywords if '🎯 Mot-clé principal' in k.get('origine', '')]
    mixed_keywords = [k for k in enriched_keywords if '+' in k.get('origine', '')]
    
    tab1, tab2, tab3, tab4 = st.tabs(["🎯 Principaux", "🔍 Google Suggest", "💰 Google Ads", "🔗 Multiples origines"])
    
    with tab1:
        if main_keywords:
            st.markdown(f"**{len(main_keywords)} mots-clés principaux**")
            df = pd.DataFrame(main_keywords)
            display_df = df[['keyword', 'search_volume', 'cpc', 'competition_level']].copy()
            display_df.columns = ['Mot-clé', 'Volume', 'CPC', 'Concurrence']
            display_df['Volume'] = display_df['Volume'].fillna(0).astype(int)
            display_df['CPC'] = display_df['CPC'].fillna(0).round(2)
            st.dataframe(display_df.sort_values('Volume', ascending=False), width='stretch')
        else:
            st.info("Aucun mot-clé principal avec volume")
    
    with tab2:
        if google_suggest_keywords:
            st.markdown(f"**{len(google_suggest_keywords)} suggestions Google**")
            df = pd.DataFrame(google_suggest_keywords)
            display_df = df[['keyword', 'search_volume', 'cpc', 'competition_level']].copy()
            display_df.columns = ['Mot-clé', 'Volume', 'CPC', 'Concurrence']
            display_df['Volume'] = display_df['Volume'].fillna(0).astype(int)
            display_df['CPC'] = display_df['CPC'].fillna(0).round(2)
            st.dataframe(display_df.sort_values('Volume', ascending=False), width='stretch')
        else:
            st.info("Aucune suggestion Google avec volume")
    
    with tab3:
        if google_ads_keywords:
            st.markdown(f"**{len(google_ads_keywords)} suggestions Google Ads**")
            df = pd.DataFrame(google_ads_keywords)
            display_df = df[['keyword', 'search_volume', 'cpc', 'competition_level']].copy()
            display_df.columns = ['Mot-clé', 'Volume', 'CPC', 'Concurrence']
            display_df['Volume'] = display_df['Volume'].fillna(0).astype(int)
            display_df['CPC'] = display_df['CPC'].fillna(0).round(2)
            st.dataframe(display_df.sort_values('Volume', ascending=False), width='stretch')
        else:
            st.info("Aucune suggestion Ads avec volume")
    
    with tab4:
        if mixed_keywords:
            st.markdown(f"**{len(mixed_keywords)} mots-clés avec multiples origines**")
            st.info("Ces mots-clés apparaissent dans plusieurs sources (mot-clé principal + suggestions)")
            df = pd.DataFrame(mixed_keywords)
            display_df = df[['keyword', 'search_volume', 'cpc', 'competition_level', 'origine']].copy()
            display_df.columns = ['Mot-clé', 'Volume', 'CPC', 'Concurrence', 'Origines']
            display_df['Volume'] = display_df['Volume'].fillna(0).astype(int)
            display_df['CPC'] = display_df['CPC'].fillna(0).round(2)
            st.dataframe(display_df.sort_values('Volume', ascending=False), width='stretch')
        else:
            st.info("Aucun mot-clé avec multiples origines")

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

def render_suggestions_only():
    """Afficher uniquement les suggestions générées"""
    if 'suggestions_data' in st.session_state and st.session_state.suggestions_data:
        suggestions = st.session_state.suggestions_data
        
        st.subheader("📝 Suggestions générées")
        
        # Afficher les statistiques
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total suggestions", len(suggestions))
        with col2:
            unique_suggestions = len(set(suggestions))
            st.metric("Suggestions uniques", unique_suggestions)
        with col3:
            if len(suggestions) > 0:
                duplication_rate = (1 - unique_suggestions / len(suggestions)) * 100
                st.metric("Taux de duplication", f"{duplication_rate:.1f}%")
        
        # Afficher la liste des suggestions
        st.write("**Liste des suggestions:**")
        suggestions_df = pd.DataFrame(suggestions, columns=['Suggestion'])
        suggestions_df.index = suggestions_df.index + 1  # Commencer l'index à 1
        st.dataframe(suggestions_df, use_container_width=True)
        
        # Option de téléchargement
        csv_data = "\n".join(suggestions)
        st.download_button(
            label="📥 Télécharger les suggestions (TXT)",
            data=csv_data,
            file_name=f"suggestions_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
        )
    else:
        st.info("Aucune suggestion disponible. Lancez d'abord une génération de questions.")

if __name__ == "__main__":
    main()