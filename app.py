import json
import streamlit as st
from openai import OpenAI
import pandas as pd
import time
from typing import Any, Dict, List, Optional

# Imports des modules refactorisés
from utils.ui_components import setup_page_config, render_header, render_social_links
from utils.config_manager import ConfigManager
from utils.export_manager import ExportManager
from utils.workflow_manager import WorkflowManager
from utils.results_manager import ResultsManager
from utils.keyword_utils import normalize_keyword, deduplicate_keywords_with_origins
from services.dataforseo_service import DataForSEOService, StepStatus
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
    if 'pipeline_state' not in st.session_state:
        st.session_state.pipeline_state = None

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
    
    # Interface principale en deux colonnes
    col_keywords, col_config = st.columns(2)
    
    with col_keywords:
        # Input des mots-clés
        keywords_input = st.text_area(
            "🎯 Entrez vos mots-clés (un par ligne)",
            placeholder="restaurant paris\nhôtel luxe\nvoyage écologique",
            help="Un mot-clé par ligne",
            height=200
        )
    
    with col_config:
        # Configuration des niveaux
        levels_config = config_manager.render_suggestion_levels()
    
    # Estimation des coûts DataForSEO si configuré
    if dataforseo_service and dataforseo_service.is_configured():
        render_cost_estimation(keywords_input, levels_config, dataforseo_service)
    
    # Gestion du workflow par étapes
    ensure_pipeline_state(
        keywords_input,
        levels_config,
        analysis_options,
        api_key,
        dataforseo_service
    )

    render_analysis_workflow_controls(
        keywords_input,
        levels_config,
        analysis_options,
        google_client,
        question_generator,
        dataforseo_service,
        api_key
    )
    
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


def parse_keywords_input(keywords_input: str) -> List[str]:
    """Nettoyer et transformer la saisie utilisateur en liste de mots-clés"""
    return [kw.strip() for kw in keywords_input.split('\n') if kw.strip()]


def compute_suggestions_signature(suggestions: List[Dict[str, Any]]) -> Optional[str]:
    """Calculer une signature déterministe des suggestions"""
    if not suggestions:
        return None

    normalized = [
        (
            item.get('Mot-clé', ''),
            item.get('Suggestion Google', ''),
            item.get('Niveau', 0),
            item.get('Parent', '')
        )
        for item in suggestions
    ]
    normalized.sort()
    return json.dumps(normalized, ensure_ascii=False)


def _build_default_pipeline_state(
    signature: str,
    levels_config: Dict[str, Any],
    analysis_options: Dict[str, Any]
) -> Dict[str, Any]:
    """Initialiser un état de pipeline vierge"""

    return {
        'signature': signature,
        'keywords': [],
        'suggestions_original': [],
        'levels_config': levels_config.copy(),
        'analysis_options': analysis_options.copy(),
        'generate_questions': False,
        'dataforseo_ready': False,
        'api_key_available': False,
        'filtered_applied': False,
        'suggestions_active_signature': None,
        'step_status': {
            'suggestions': 'pending',
            'volumes': 'pending',
            'ads': 'pending',
            'questions': 'pending'
        },
        'messages': {
            'suggestions': '',
            'volumes': '',
            'ads': '',
            'questions': ''
        },
        'suggestions': [],
        'volume_results': None,
        'ads_suggestions': [],
        'enriched_data': {},
        'themes_analysis': {},
        'errors': {}
    }


def ensure_pipeline_state(
    keywords_input: str,
    levels_config: Dict[str, Any],
    analysis_options: Dict[str, Any],
    api_key: Optional[str],
    dataforseo_service: Optional[DataForSEOService]
) -> None:
    """Synchroniser le state du pipeline avec la configuration actuelle"""

    config_signature = json.dumps(
        {
            'keywords_input': keywords_input,
            'levels_config': levels_config,
            'analysis_options': analysis_options
        },
        sort_keys=True
    )

    if st.session_state.pipeline_state is None:
        st.session_state.pipeline_state = _build_default_pipeline_state(
            config_signature,
            levels_config,
            analysis_options
        )
        st.session_state.analysis_results = None
        st.session_state.analysis_metadata = None
        st.session_state.pop('filtered_suggestions_records', None)
        st.session_state.pop('filtered_tags_state', None)
    elif st.session_state.pipeline_state.get('signature') != config_signature:
        st.session_state.pipeline_state = _build_default_pipeline_state(
            config_signature,
            levels_config,
            analysis_options
        )
        st.session_state.analysis_results = None
        st.session_state.analysis_metadata = None
        st.session_state.pop('filtered_suggestions_records', None)
        st.session_state.pop('filtered_tags_state', None)
    else:
        pipeline_state = st.session_state.pipeline_state
        pipeline_state['levels_config'] = levels_config.copy()
        pipeline_state['analysis_options'] = analysis_options.copy()

    pipeline_state = st.session_state.pipeline_state
    pipeline_state['signature'] = config_signature
    pipeline_state['api_key_available'] = bool(api_key)

    dataforseo_ready = bool(dataforseo_service and dataforseo_service.is_configured())
    pipeline_state['dataforseo_ready'] = dataforseo_ready

    if not dataforseo_ready:
        if pipeline_state['step_status'].get('volumes') != 'completed':
            pipeline_state['step_status']['volumes'] = 'disabled'
        if pipeline_state['step_status'].get('ads') != 'completed':
            pipeline_state['step_status']['ads'] = 'disabled'
    else:
        if pipeline_state['step_status'].get('volumes') == 'disabled':
            pipeline_state['step_status']['volumes'] = 'pending'
        if pipeline_state['step_status'].get('ads') == 'disabled':
            pipeline_state['step_status']['ads'] = 'pending'

    wants_questions = analysis_options.get('generate_questions', False)
    if not wants_questions or not api_key:
        if pipeline_state['step_status'].get('questions') != 'completed':
            pipeline_state['step_status']['questions'] = 'disabled'
    else:
        if pipeline_state['step_status'].get('questions') == 'disabled':
            pipeline_state['step_status']['questions'] = 'pending'


def reset_analysis_workflow(clear_results: bool = True) -> None:
    """Réinitialiser l'ensemble du workflow"""
    if 'pipeline_state' in st.session_state:
        st.session_state.pipeline_state = None
    if clear_results:
        st.session_state.analysis_results = None
        st.session_state.analysis_metadata = None
    st.session_state.pop('filtered_suggestions_records', None)
    st.session_state.pop('filtered_tags_state', None)
    st.rerun()


def invalidate_downstream_steps(pipeline_state: Dict[str, Any]) -> None:
    """Remettre à zéro les étapes dépendantes après changement de suggestions"""

    pipeline_state['volume_results'] = None
    pipeline_state['ads_suggestions'] = []
    pipeline_state['enriched_data'] = {}
    pipeline_state['themes_analysis'] = {}

    dataforseo_ready = pipeline_state.get('dataforseo_ready', False)
    generate_questions = pipeline_state.get('generate_questions', False)

    pipeline_state['step_status']['volumes'] = 'ready' if dataforseo_ready else 'disabled'
    pipeline_state['messages']['volumes'] = (
        "Prêt à récupérer les volumes" if dataforseo_ready else "Configurer DataForSEO pour activer cette étape"
    )

    pipeline_state['step_status']['ads'] = 'pending' if dataforseo_ready else 'disabled'
    pipeline_state['messages']['ads'] = (
        "En attente des volumes" if dataforseo_ready else "Indisponible (DataForSEO)"
    )

    if generate_questions:
        if dataforseo_ready:
            pipeline_state['step_status']['questions'] = 'pending'
            pipeline_state['messages']['questions'] = "En attente des données enrichies"
        else:
            pipeline_state['step_status']['questions'] = 'ready'
            pipeline_state['messages']['questions'] = "Prêt à générer à partir des suggestions"
    else:
        pipeline_state['step_status']['questions'] = 'disabled'
        pipeline_state['messages']['questions'] = "Génération désactivée"

    results = st.session_state.get('analysis_results')
    if results:
        results['filtered_suggestions'] = pipeline_state.get('suggestions', [])
        results['dataforseo_data'] = {}
        results['enriched_keywords'] = []
        results['themes_analysis'] = {}
        results['final_consolidated_data'] = []
        results['selected_themes_by_keyword'] = {}
        results['stage'] = 'suggestions_collected'


def synchronize_filtered_suggestions(pipeline_state: Dict[str, Any]) -> None:
    """Appliquer les filtres de suggestions au pipeline si nécessaire"""

    filtered_records = st.session_state.get('filtered_suggestions_records')
    use_filtered = bool(filtered_records)

    if use_filtered:
        target_suggestions = filtered_records
    else:
        target_suggestions = pipeline_state.get('suggestions_original') or pipeline_state.get('suggestions', [])

    new_signature = compute_suggestions_signature(target_suggestions)

    if new_signature == pipeline_state.get('suggestions_active_signature'):
        return

    pipeline_state['suggestions'] = target_suggestions
    pipeline_state['suggestions_active_signature'] = new_signature
    pipeline_state['filtered_applied'] = use_filtered

    if pipeline_state['step_status'].get('suggestions') == 'completed':
        if use_filtered:
            pipeline_state['messages']['suggestions'] = f"{len(target_suggestions)} suggestions filtrées"
        else:
            pipeline_state['messages']['suggestions'] = f"{len(target_suggestions)} suggestions collectées"
        invalidate_downstream_steps(pipeline_state)
    else:
        pipeline_state['messages']['suggestions'] = pipeline_state['messages'].get('suggestions', '')

    if st.session_state.get('analysis_results'):
        st.session_state.analysis_results['filtered_suggestions'] = target_suggestions


def run_step_collect_suggestions(
    keywords_input: str,
    levels_config: Dict[str, Any],
    analysis_options: Dict[str, Any],
    google_client: 'GoogleSuggestionsClient',
    dataforseo_service: Optional[DataForSEOService],
    api_key: Optional[str]
) -> None:
    """Étape 1 – Collecte des suggestions Google"""

    pipeline_state = st.session_state.pipeline_state
    keywords = parse_keywords_input(keywords_input)

    if not keywords:
        st.error("❌ Veuillez entrer au moins un mot-clé")
        pipeline_state['step_status']['suggestions'] = 'error'
        pipeline_state['messages']['suggestions'] = "Aucun mot-clé valide"
        return

    pipeline_state['step_status']['suggestions'] = 'running'
    pipeline_state['messages']['suggestions'] = "Collecte en cours..."

    st.info("🔍 Collecte des suggestions Google")
    all_suggestions = collect_google_suggestions(
        keywords,
        levels_config,
        google_client,
        analysis_options['language']
    )

    if not all_suggestions:
        pipeline_state['step_status']['suggestions'] = 'error'
        pipeline_state['messages']['suggestions'] = "Aucune suggestion trouvée"
        st.error("❌ Aucune suggestion trouvée")
        return

    pipeline_state['keywords'] = keywords
    pipeline_state['levels_config'] = levels_config.copy()
    pipeline_state['analysis_options'] = analysis_options.copy()
    pipeline_state['suggestions_original'] = all_suggestions
    pipeline_state['suggestions'] = all_suggestions
    pipeline_state['suggestions_active_signature'] = compute_suggestions_signature(all_suggestions)
    pipeline_state['filtered_applied'] = False
    pipeline_state['volume_results'] = None
    pipeline_state['ads_suggestions'] = []
    pipeline_state['enriched_data'] = {}
    pipeline_state['themes_analysis'] = {}

    wants_questions = analysis_options.get('generate_questions', False)
    has_api_key = bool(api_key)
    pipeline_state['generate_questions'] = wants_questions and has_api_key

    if wants_questions and not has_api_key:
        st.warning("⚠️ API OpenAI requise pour la génération de questions")

    pipeline_state['step_status']['suggestions'] = 'completed'
    pipeline_state['messages']['suggestions'] = f"{len(all_suggestions)} suggestions collectées"

    if pipeline_state['dataforseo_ready']:
        pipeline_state['step_status']['volumes'] = 'ready'
        pipeline_state['messages']['volumes'] = "Prêt à récupérer les volumes"
    else:
        pipeline_state['step_status']['volumes'] = 'disabled'
        pipeline_state['messages']['volumes'] = "Configurer DataForSEO pour activer cette étape"

    pipeline_state['step_status']['ads'] = 'pending'
    pipeline_state['messages']['ads'] = "En attente des volumes"

    if pipeline_state['generate_questions']:
        pipeline_state['step_status']['questions'] = 'ready'
        if pipeline_state['dataforseo_ready']:
            pipeline_state['messages']['questions'] = "Prêt (volumes recommandés avant la génération)"
        else:
            pipeline_state['messages']['questions'] = "Prêt à générer à partir des suggestions"
    else:
        pipeline_state['step_status']['questions'] = 'disabled'
        pipeline_state['messages']['questions'] = "Génération désactivée"

    st.session_state.analysis_results = None
    st.session_state.analysis_metadata = None

    save_analysis_results(
        all_suggestions,
        {},
        {},
        keywords,
        levels_config,
        pipeline_state['generate_questions'],
        analysis_options
    )

    if st.session_state.analysis_results:
        st.session_state.analysis_results['stage'] = 'suggestions_collected'
        st.session_state.analysis_results['filtered_suggestions'] = all_suggestions

    st.success("✅ Suggestions Google collectées")


def run_step_search_volume(
    dataforseo_service: Optional[DataForSEOService]
) -> None:
    """Étape 2 – Récupération des volumes DataForSEO"""

    pipeline_state = st.session_state.pipeline_state

    if not dataforseo_service or not dataforseo_service.is_configured():
        st.warning("⚠️ DataForSEO non configuré")
        pipeline_state['step_status']['volumes'] = 'error'
        pipeline_state['messages']['volumes'] = "Service indisponible"
        return

    if pipeline_state['step_status'].get('suggestions') != 'completed':
        st.warning("⚠️ Veuillez d'abord collecter les suggestions")
        return

    pipeline_state['step_status']['volumes'] = 'running'
    pipeline_state['messages']['volumes'] = "Récupération en cours"

    keywords = pipeline_state['keywords']
    suggestions = pipeline_state['suggestions']
    suggestion_texts = [s['Suggestion Google'] for s in suggestions]

    volume_results = dataforseo_service.enrich_keywords_with_volumes(keywords, suggestion_texts)

    if not volume_results:
        pipeline_state['step_status']['volumes'] = 'error'
        pipeline_state['messages']['volumes'] = "Aucune donnée de volume"
        return

    keywords_with_volume = volume_results.get('keywords_with_volume', [])
    total_unique_keywords = volume_results.get('total_keywords', len(set(keywords + suggestion_texts)))

    dataset = dataforseo_service.build_enriched_dataset(
        keywords,
        volume_results,
        ads_suggestions=[]
    )

    steps_summary = {
        'dataforseo_volumes': {
            'status': StepStatus.COMPLETED.value if keywords_with_volume else StepStatus.PARTIAL.value,
            'metadata': {
                'keywords_with_volume': len(keywords_with_volume),
                'total_keywords': total_unique_keywords
            }
        },
        'dataforseo_ads': {
            'status': StepStatus.PENDING.value if keywords_with_volume else StepStatus.SKIPPED.value,
            'metadata': {}
        },
        'dataforseo_enrichment': {
            'status': StepStatus.COMPLETED.value,
            'metadata': {'count': len(dataset.get('enriched_keywords', []))}
        },
        'dataforseo_deduplication': {
            'status': StepStatus.COMPLETED.value,
            'metadata': {'count': len(dataset.get('enriched_keywords', []))}
        }
    }

    dataset['steps'] = steps_summary

    pipeline_state['volume_results'] = volume_results
    pipeline_state['enriched_data'] = dataset
    pipeline_state['ads_suggestions'] = []

    pipeline_state['step_status']['volumes'] = steps_summary['dataforseo_volumes']['status']
    pipeline_state['messages']['volumes'] = (
        f"{len(keywords_with_volume)} mots-clés avec volume" if keywords_with_volume
        else "Aucun volume trouvé"
    )

    if keywords_with_volume:
        pipeline_state['step_status']['ads'] = 'ready'
        pipeline_state['messages']['ads'] = "Prêt pour la recherche Ads"
    else:
        pipeline_state['step_status']['ads'] = 'disabled'
        pipeline_state['messages']['ads'] = "Pas de volumes pour lancer Ads"

    if pipeline_state['generate_questions']:
        pipeline_state['step_status']['questions'] = 'pending'
        pipeline_state['messages']['questions'] = "En attente des suggestions Ads"

    save_analysis_results(
        suggestions,
        dataset,
        {},
        keywords,
        pipeline_state['levels_config'],
        pipeline_state['generate_questions'],
        pipeline_state['analysis_options']
    )

    if st.session_state.analysis_results:
        st.session_state.analysis_results['stage'] = 'volumes_retrieved'

    st.success("✅ Volumes de recherche récupérés")


def run_step_ads_keywords(dataforseo_service: Optional[DataForSEOService]) -> None:
    """Étape 3 – Suggestions Ads"""

    pipeline_state = st.session_state.pipeline_state

    if not dataforseo_service or not dataforseo_service.is_configured():
        st.warning("⚠️ DataForSEO non configuré")
        pipeline_state['step_status']['ads'] = 'error'
        pipeline_state['messages']['ads'] = "Service indisponible"
        return

    if pipeline_state['step_status'].get('volumes') not in ['completed', StepStatus.PARTIAL.value]:
        st.warning("⚠️ Lancez d'abord la récupération des volumes")
        return

    if pipeline_state['step_status'].get('ads') == 'disabled':
        st.warning("⚠️ Aucun volume disponible pour lancer Ads")
        return

    volume_results = pipeline_state.get('volume_results')
    if not volume_results or not volume_results.get('keywords_with_volume'):
        st.warning("⚠️ Aucun mot-clé avec volume pour interroger Ads")
        pipeline_state['step_status']['ads'] = 'disabled'
        pipeline_state['messages']['ads'] = "Aucun volume disponible"
        return

    pipeline_state['step_status']['ads'] = 'running'
    pipeline_state['messages']['ads'] = "Collecte des suggestions Ads"

    ads_suggestions = dataforseo_service.get_ads_suggestions(
        volume_results.get('keywords_with_volume', [])
    )

    ads_status = StepStatus.COMPLETED.value if ads_suggestions else StepStatus.PARTIAL.value

    dataset = dataforseo_service.build_enriched_dataset(
        pipeline_state['keywords'],
        volume_results,
        ads_suggestions=ads_suggestions
    )

    steps_summary = {
        'dataforseo_volumes': {
            'status': pipeline_state['step_status'].get('volumes', StepStatus.COMPLETED.value),
            'metadata': {
                'keywords_with_volume': len(volume_results.get('keywords_with_volume', []))
            }
        },
        'dataforseo_ads': {
            'status': ads_status,
            'metadata': {
                'returned_suggestions': len(ads_suggestions)
            }
        },
        'dataforseo_enrichment': {
            'status': StepStatus.COMPLETED.value,
            'metadata': {'count': len(dataset.get('enriched_keywords', []))}
        },
        'dataforseo_deduplication': {
            'status': StepStatus.COMPLETED.value,
            'metadata': {'count': len(dataset.get('enriched_keywords', []))}
        }
    }

    dataset['steps'] = steps_summary

    pipeline_state['ads_suggestions'] = ads_suggestions
    pipeline_state['enriched_data'] = dataset

    pipeline_state['step_status']['ads'] = ads_status
    pipeline_state['messages']['ads'] = (
        f"{len(ads_suggestions)} suggestions Ads" if ads_suggestions else "Aucune suggestion Ads"
    )

    if pipeline_state['generate_questions']:
        pipeline_state['step_status']['questions'] = 'ready'
        pipeline_state['messages']['questions'] = "Prêt pour la génération des questions"
    else:
        pipeline_state['step_status']['questions'] = 'disabled'
        pipeline_state['messages']['questions'] = "Génération désactivée"

    save_analysis_results(
        pipeline_state['suggestions'],
        dataset,
        {},
        pipeline_state['keywords'],
        pipeline_state['levels_config'],
        pipeline_state['generate_questions'],
        pipeline_state['analysis_options']
    )

    if st.session_state.analysis_results:
        st.session_state.analysis_results['stage'] = 'ads_completed'

    st.success("✅ Suggestions Ads récupérées")


def run_step_generate_questions(
    question_generator: 'QuestionGenerator',
    analysis_options: Dict[str, Any]
) -> None:
    """Étape 4 – Génération des questions"""

    pipeline_state = st.session_state.pipeline_state

    if not pipeline_state['generate_questions']:
        st.warning("⚠️ Génération de questions désactivée")
        pipeline_state['step_status']['questions'] = 'disabled'
        pipeline_state['messages']['questions'] = "Aucun générateur disponible"
        return

    if pipeline_state['step_status'].get('ads') not in ['completed', StepStatus.PARTIAL.value, 'disabled', 'pending']:
        st.warning("⚠️ Terminez d'abord les étapes précédentes")
        return

    pipeline_state['step_status']['questions'] = 'running'
    pipeline_state['messages']['questions'] = "Analyse des thèmes"

    has_enriched_keywords = bool(pipeline_state['enriched_data'].get('enriched_keywords'))

    if has_enriched_keywords:
        themes_analysis = analyze_themes_with_volume_filter(
            pipeline_state['keywords'],
            pipeline_state['suggestions'],
            pipeline_state['enriched_data'],
            question_generator,
            analysis_options['language']
        )
    else:
        st.info("ℹ️ Volumes indisponibles : génération basée sur les suggestions collectées")
        pipeline_state['messages']['questions'] = "Analyse des thèmes (suggestions)"

        dataset = pipeline_state['enriched_data'] or {}
        dataset.setdefault('volume_data', [])
        dataset.setdefault('ads_suggestions', pipeline_state.get('ads_suggestions', []))
        dataset.setdefault('enriched_keywords', [])
        dataset.setdefault('keywords_with_volume', [])
        dataset.setdefault('total_keywords', len(pipeline_state.get('suggestions', [])))
        dataset.setdefault('top_20_keywords_count', 0)

        steps_summary = dataset.get('steps', {})
        steps_summary.setdefault('dataforseo_volumes', {
            'status': StepStatus.SKIPPED.value,
            'metadata': {'reason': 'not_run'}
        })
        steps_summary.setdefault('dataforseo_ads', {
            'status': StepStatus.SKIPPED.value,
            'metadata': {'reason': 'not_run'}
        })
        steps_summary.setdefault('dataforseo_enrichment', {
            'status': StepStatus.SKIPPED.value,
            'metadata': {}
        })
        steps_summary.setdefault('dataforseo_deduplication', {
            'status': StepStatus.SKIPPED.value,
            'metadata': {}
        })
        dataset['steps'] = steps_summary
        pipeline_state['enriched_data'] = dataset

        themes_analysis = analyze_themes_from_suggestions(
            pipeline_state['keywords'],
            pipeline_state['suggestions'],
            question_generator,
            analysis_options['language']
        )

    if not themes_analysis:
        pipeline_state['step_status']['questions'] = 'error'
        pipeline_state['messages']['questions'] = "Aucun thème généré"
        st.warning("⚠️ Aucun thème généré à partir des données disponibles")
        return

    pipeline_state['themes_analysis'] = themes_analysis

    save_analysis_results(
        pipeline_state['suggestions'],
        pipeline_state['enriched_data'],
        themes_analysis,
        pipeline_state['keywords'],
        pipeline_state['levels_config'],
        pipeline_state['generate_questions'],
        pipeline_state['analysis_options']
    )

    selected_themes_by_keyword = {
        keyword: themes
        for keyword, themes in themes_analysis.items()
        if themes
    }

    if not selected_themes_by_keyword:
        pipeline_state['step_status']['questions'] = 'error'
        pipeline_state['messages']['questions'] = "Thèmes vides"
        st.warning("⚠️ Aucun thème exploitable pour générer des questions")
        return

    try:
        generate_questions_from_themes(
            selected_themes_by_keyword,
            question_generator,
            analysis_options['language'],
            auto_rerun=False
        )
        generated_count = len(st.session_state.analysis_results.get('final_consolidated_data', []))
        pipeline_state['step_status']['questions'] = 'completed'
        pipeline_state['messages']['questions'] = f"{generated_count} questions générées"
        st.success("🎉 Questions conversationnelles générées")
    except Exception as exc:  # pragma: no cover
        pipeline_state['step_status']['questions'] = 'error'
        pipeline_state['messages']['questions'] = str(exc)
        st.error(f"❌ Erreur lors de la génération des questions: {exc}")


def render_step_status_summary(pipeline_state: Dict[str, Any]) -> None:
    """Afficher le statut global des étapes"""

    status_labels = {
        'suggestions': "Suggestions Google",
        'volumes': "Volumes de recherche",
        'ads': "Recherche mots-clés (Ads)",
        'questions': "Génération de questions"
    }

    status_text = {
        'pending': "En attente",
        'ready': "Prêt",
        'running': "En cours",
        'completed': "Terminé",
        'partial': "Partiel",
        'error': "Erreur",
        'disabled': "Indisponible",
        'skipped': "Ignoré"
    }

    status_icons = {
        'pending': '⏳',
        'ready': '🟡',
        'running': '🔄',
        'completed': '✅',
        'partial': '🟡',
        'error': '❌',
        'disabled': '🚫',
        'skipped': '⏭️'
    }

    statuses = pipeline_state.get('step_status', {})
    messages = pipeline_state.get('messages', {})

    cols = st.columns(len(status_labels))

    for idx, (step_key, label) in enumerate(status_labels.items()):
        status_value = statuses.get(step_key, 'pending')
        icon = status_icons.get(status_value, '⏳')
        readable_status = status_text.get(status_value, status_value)
        message = messages.get(step_key, '')

        with cols[idx]:
            st.markdown(
                f"{icon} **{label}**\n\n`{readable_status}`" +
                (f"\n\n_{message}_" if message else "")
            )

    order = ['suggestions', 'volumes', 'ads', 'questions']
    next_step = next(
        (step for step in order if statuses.get(step) not in ['completed', 'disabled', 'skipped']),
        None
    )

    if next_step:
        st.info(f"➡️ Étape suivante : {status_labels[next_step]}")


def render_analysis_workflow_controls(
    keywords_input: str,
    levels_config: Dict[str, Any],
    analysis_options: Dict[str, Any],
    google_client: 'GoogleSuggestionsClient',
    question_generator: 'QuestionGenerator',
    dataforseo_service: Optional[DataForSEOService],
    api_key: Optional[str]
) -> None:
    """Interface utilisateur des étapes successives"""

    pipeline_state = st.session_state.pipeline_state

    synchronize_filtered_suggestions(pipeline_state)

    st.markdown("### 🧭 Workflow d'analyse")

    step_status = pipeline_state.get('step_status', {})

    btn_cols = st.columns(4)

    btn1 = btn_cols[0].button(
        "1️⃣ Suggestions",
        type="primary",
        width='stretch',
        disabled=not bool(parse_keywords_input(keywords_input))
    )

    volumes_disabled = (
        step_status.get('volumes') == 'disabled' or
        step_status.get('suggestions') != 'completed'
    )

    btn2 = btn_cols[1].button(
        "2️⃣ Volumes",
        type="secondary",
        width='stretch',
        disabled=volumes_disabled
    )

    ads_disabled = (
        step_status.get('ads') == 'disabled' or
        step_status.get('volumes') not in ['completed', StepStatus.PARTIAL.value]
    )

    btn3 = btn_cols[2].button(
        "3️⃣ Recherche mots-clés",
        type="secondary",
        width='stretch',
        disabled=ads_disabled
    )

    allowed_ads_states = {'completed', StepStatus.PARTIAL.value, 'disabled', 'pending'}
    questions_disabled = step_status.get('questions') == 'disabled'
    if not questions_disabled and step_status.get('ads') not in allowed_ads_states:
        questions_disabled = True

    btn4 = btn_cols[3].button(
        "4️⃣ Génération questions",
        type="secondary",
        width='stretch',
        disabled=questions_disabled
    )

    if btn1:
        run_step_collect_suggestions(
            keywords_input,
            levels_config,
            analysis_options,
            google_client,
            dataforseo_service,
            api_key
        )

    if btn2:
        run_step_search_volume(dataforseo_service)

    if btn3:
        run_step_ads_keywords(dataforseo_service)

    if btn4:
        run_step_generate_questions(question_generator, analysis_options)

    render_step_status_summary(pipeline_state)

    reset_col, _ = st.columns([1, 3])
    if reset_col.button("🧹 Réinitialiser le workflow", width='stretch'):
        reset_analysis_workflow()

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
            def pipeline_callback(step_name: str, status: StepStatus, payload: Dict[str, Any]):
                step_names = {step.name for step in workflow.steps}
                if step_name not in step_names:
                    return

                if status == StepStatus.RUNNING:
                    workflow.update_step(step_name, "running")
                elif status in {StepStatus.COMPLETED, StepStatus.PARTIAL, StepStatus.SKIPPED}:
                    workflow.complete_step(step_name)
                    if status == StepStatus.PARTIAL:
                        metadata = payload.get('metadata', {})
                        reason = metadata.get('reason')
                        if reason:
                            st.info(f"ℹ️ Étape {step_name} partielle: {reason}")
                    elif status == StepStatus.SKIPPED:
                        metadata = payload.get('metadata', {})
                        reason = metadata.get('reason')
                        if reason:
                            st.info(f"ℹ️ Étape {step_name} ignorée: {reason}")
                elif status == StepStatus.ERROR:
                    error_message = payload.get('error', 'Erreur inconnue')
                    workflow.error_step(step_name, error_message)

            suggestion_texts = [s['Suggestion Google'] for s in all_suggestions]
            enriched_report = dataforseo_service.process_complete_analysis(
                keywords,
                suggestion_texts,
                progress_callback=pipeline_callback
            )
            enriched_data = enriched_report.to_dict()

            has_critical_error = any(
                step_result.status == StepStatus.ERROR
                for name, step_result in enriched_report.steps.items()
                if name in {"dataforseo_volumes", "dataforseo_ads"}
            )

            if has_critical_error:
                workflow.finish_workflow()
                st.error("❌ Analyse interrompue: erreur lors de l'enrichissement DataForSEO")
                return
        
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


def analyze_themes_from_suggestions(keywords, all_suggestions, question_generator, language):
    """Analyse des thèmes en se basant uniquement sur les suggestions"""
    themes_by_keyword = {}

    for keyword in keywords:
        keyword_suggestions = [
            suggestion for suggestion in all_suggestions
            if suggestion['Mot-clé'] == keyword and suggestion['Niveau'] > 0
        ]

        if not keyword_suggestions:
            continue

        themes = question_generator.analyze_suggestions_themes(
            keyword_suggestions,
            keyword,
            language
        )

        if themes:
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

def generate_questions_from_themes(selected_themes_by_keyword, question_generator, language, auto_rerun: bool = True):
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
    if auto_rerun:
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