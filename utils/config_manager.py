import streamlit as st
from typing import Dict, Any, Tuple
from dataforseo_client import DataForSEOClient

class ConfigManager:
    """Gestionnaire centrali            # Volume minimum avec slider amélioré
            st.markdown("**📊 Filtrage par volume**") de la configuration avec interface améliorée"""
    
    def __init__(self):
        self.config = {}
        self.dataforseo_client = DataForSEOClient()
    
    def render_credentials_section(self) -> Tuple[str, bool, Dict[str, Any]]:
        """Section centralisée pour tous les credentials et clés API"""
        st.sidebar.markdown("---")
        st.sidebar.markdown("## 🔐 Configuration API")
        
        # OpenAI Configuration
        with st.sidebar.expander("🤖 OpenAI", expanded=True):
            api_key = self._render_openai_config()
        
        # DataForSEO Configuration
        with st.sidebar.expander("📊 DataForSEO", expanded=False):
            enable_dataforseo, dataforseo_config = self._render_dataforseo_config()
        
        return api_key, enable_dataforseo, dataforseo_config
    
    def _render_openai_config(self) -> str:
        """Configuration OpenAI avec validation améliorée"""
        col1, col2 = st.columns([3, 1])
        
        with col1:
            api_key = st.text_input(
                "Clé API OpenAI", 
                type="password", 
                help="Votre clé API OpenAI pour GPT-4o mini",
                placeholder="sk-...",
                key="openai_api_key"
            )
        
        with col2:
            if api_key:
                if api_key.startswith("sk-") and len(api_key) > 20:
                    st.success("✅")
                else:
                    st.error("❌")
            else:
                st.warning("⚠️")
        
        if api_key:
            if api_key.startswith("sk-") and len(api_key) > 20:
                st.success("✅ Clé API OpenAI valide")
            else:
                st.error("❌ Format de clé API OpenAI invalide")
        else:
            st.warning("⚠️ Clé API OpenAI requise pour la génération de questions")
        
        return api_key
    
    def _render_dataforseo_config(self) -> Tuple[bool, Dict[str, Any]]:
        """Configuration DataForSEO améliorée"""
        enable_dataforseo = st.checkbox(
            "Activer DataForSEO",
            value=False,
            help="Enrichir l'analyse avec volumes de recherche et suggestions Ads",
            key="enable_dataforseo"
        )
        
        dataforseo_config = {
            'enabled': enable_dataforseo,
            'login': None,
            'password': None,
            'language': 'fr',
            'location': 'fr',
            'min_volume': 10
        }
        
        if enable_dataforseo:
            st.info("💡 DataForSEO ajoutera volumes de recherche et suggestions Ads à vos mots-clés")
            
            # Credentials avec validation
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                dataforseo_config['login'] = st.text_input(
                    "Login DataForSEO", 
                    placeholder="votre_login",
                    key="dataforseo_login"
                )
            
            with col2:
                dataforseo_config['password'] = st.text_input(
                    "Mot de passe DataForSEO", 
                    type="password",
                    placeholder="votre_password",
                    key="dataforseo_password"
                )
            
            with col3:
                credentials_valid = bool(dataforseo_config['login'] and dataforseo_config['password'])
                if credentials_valid:
                    if st.button("🔍 Tester", key="test_credentials"):
                        self.dataforseo_client.set_credentials(
                            dataforseo_config['login'], 
                            dataforseo_config['password']
                        )
                        is_valid, message = self.dataforseo_client.test_credentials()
                        if is_valid:
                            st.success("✅ Valide")
                        else:
                            st.error("❌ Invalide")
                else:
                    st.button("🔍 Tester", disabled=True, key="test_credentials_disabled")
            
            # Paramètres régionaux cohérents
            st.markdown("**📍 Paramètres régionaux**")
            col1, col2 = st.columns(2)
            
            with col1:
                language_options = {
                    'fr': '🇫🇷 Français',
                    'en': '🇺🇸 Anglais', 
                    'es': '🇪🇸 Espagnol',
                    'de': '🇩🇪 Allemand',
                    'it': '🇮🇹 Italien',
                    'pt': '🇵🇹 Português',
                    'pt-BR': '🇧🇷 Português (Brasil)'
                }
                selected_lang = st.selectbox(
                    "Langue",
                    options=list(language_options.keys()),
                    format_func=lambda x: language_options[x],
                    index=0,
                    help="Langue pour les données DataForSEO",
                    key="dataforseo_language"
                )
                dataforseo_config['language'] = selected_lang
            
            with col2:
                location_options = {
                    'fr': '🇫🇷 France',
                    'en-us': '🇺🇸 États-Unis',
                    'en-gb': '🇬🇧 Royaume-Uni', 
                    'es': '🇪🇸 Espagne',
                    'de': '🇩🇪 Allemagne',
                    'it': '🇮🇹 Italie',
                    'pt': '🇵🇹 Portugal',
                    'br': '🇧🇷 Brésil',
                    'ca': '🇨🇦 Canada',
                    'au': '🇦🇺 Australie'
                }
                selected_loc = st.selectbox(
                    "Pays cible",
                    options=list(location_options.keys()),
                    format_func=lambda x: location_options[x],
                    index=0,
                    help="Géolocalisation des volumes",
                    key="dataforseo_location"
                )
                dataforseo_config['location'] = selected_loc
            
            # Volume minimum avec slider amélioré
            st.markdown("**📊 Filtrage par volume**")
            dataforseo_config['min_volume'] = st.slider(
                "Volume minimum (recherches/mois)",
                min_value=0,
                max_value=1000,
                value=10,
                step=10,
                help="Seuls les mots-clés avec ce volume minimum seront conservés",
                key="dataforseo_min_volume"
            )
            
            st.info(f"🎯 Seuls les mots-clés avec ≥ {dataforseo_config['min_volume']} recherches/mois seront conservés")
            
            # Validation finale
            if dataforseo_config['login'] and dataforseo_config['password']:
                st.success("✅ DataForSEO configuré")
                st.caption("📈 Volumes + 💰 Suggestions Ads seront ajoutés")
            else:
                st.warning("⚠️ Login/Password requis")
        
        return enable_dataforseo, dataforseo_config
    
    def render_analysis_options(self) -> Dict[str, Any]:
        """Options d'analyse avec sélecteurs cohérents"""
        st.sidebar.markdown("---")
        st.sidebar.markdown("## 🎯 Options d'analyse")
        
        # Génération de questions
        generate_questions = st.sidebar.checkbox(
            "✨ Générer questions conversationnelles",
            value=False,
            help="Analyse thématique + génération de questions basées sur les volumes",
            key="generate_questions"
        )
        
        options = {
            'generate_questions': generate_questions,
            'final_questions_count': 20,
            'language': 'fr'
        }
        
        if generate_questions:
            st.sidebar.markdown("**📝 Paramètres de génération**")
            options['final_questions_count'] = st.sidebar.slider(
                "Nombre de questions finales",
                min_value=5,
                max_value=100,
                value=20,
                step=5,
                help="Nombre de questions à conserver après consolidation",
                key="final_questions_count"
            )
        
        # Langue d'analyse avec format cohérent
        st.sidebar.markdown("**🌍 Langue d'analyse**")
        language_options = {
            'fr': '🇫🇷 Français',
            'en': '🇺🇸 Anglais', 
            'es': '🇪🇸 Espagnol',
            'de': '🇩🇪 Allemand',
            'it': '🇮🇹 Italien',
            'pt': '🇵🇹 Português',
            'pt-BR': '🇧🇷 Português (Brasil)'
        }
        selected_lang = st.sidebar.selectbox(
            "Langue des suggestions et questions",
            options=list(language_options.keys()),
            format_func=lambda x: language_options[x],
            index=0,
            help="Langue pour les suggestions Google et la génération de questions",
            key="analysis_language"
        )
        options['language'] = selected_lang
        
        return options
    
    def render_suggestion_levels(self) -> Dict[str, int]:
        """Configuration des niveaux de suggestions avec interface améliorée"""
        
        # Niveau 1 - toujours actif
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**🎯 Niveau 1 - Suggestions**")
            level1_count = st.slider(
                "Nombre de suggestions",
                min_value=5, 
                max_value=20, 
                value=10,
                step=1,
                help="Nombre de suggestions directes à récupérer pour chaque mot-clé",
                key="level1_count"
            )
        
        with col2:
            st.markdown("**🔄 Niveau 2 - Suggestions²**")
            level2_count = st.slider(
                "Suggestions niveau 2",
                min_value=0,
                max_value=15, 
                value=5,
                step=1,
                help="Nombre de suggestions à récupérer pour chaque suggestion de niveau 1 (0 = désactivé)",
                key="level2_count"
            )
        
        with col3:
            st.markdown("**🔁 Niveau 3 - Suggestions³**")
            level3_count = st.slider(
                "Suggestions niveau 3",
                min_value=0,
                max_value=10, 
                value=0,
                step=1,
                help="Nombre de suggestions à récupérer pour chaque suggestion de niveau 2 (0 = désactivé, nécessite niveau 2)",
                key="level3_count",
                disabled=(level2_count == 0)
            )
        
        return {
            'level1_count': level1_count,
            'level2_count': level2_count,
            'level3_count': level3_count,
            'enable_level2': level2_count > 0,
            'enable_level3': level3_count > 0 and level2_count > 0
        }
    
    def render_cost_estimation(self, keywords_count: int, levels: Dict[str, int]):
        """Estimation des coûts DataForSEO"""
        if keywords_count > 0:
            estimated_total = keywords_count * (
                1 + levels['level1_count'] + 
                (levels['level2_count'] if levels['enable_level2'] else 0)
            )
            
            cost_estimate = self.dataforseo_client.estimate_cost(estimated_total, True)
            
            with st.expander("💰 Estimation coûts DataForSEO"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Mots-clés estimés", f"{cost_estimate['keywords_count']:,}")
                with col2:
                    st.metric("Coût volumes", f"${cost_estimate['search_volume_cost']:.2f}")
                with col3:
                    st.metric("Coût total", f"${cost_estimate['total_cost']:.2f}")
            
            cost_estimate = self.dataforseo_client.estimate_cost(estimated_total, True)
            
            with st.expander("💰 Estimation coûts DataForSEO"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Mots-clés estimés", f"{cost_estimate['keywords_count']:,}")
                with col2:
                    st.metric("Coût volumes", f"${cost_estimate['search_volume_cost']:.2f}")
                with col3:
                    st.metric("Coût total", f"${cost_estimate['total_cost']:.2f}")
                    st.metric("Coût volumes", f"${cost_estimate['search_volume_cost']:.2f}")
                with col3:
                    st.metric("Coût total", f"${cost_estimate['total_cost']:.2f}")
            
            cost_estimate = self.dataforseo_client.estimate_cost(estimated_total, True)
            
            with st.expander("💰 Estimation coûts DataForSEO"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Mots-clés estimés", f"{cost_estimate['keywords_count']:,}")
                with col2:
                    st.metric("Coût volumes", f"${cost_estimate['search_volume_cost']:.2f}")
                with col3:
                    st.metric("Coût total", f"${cost_estimate['total_cost']:.2f}")
            cost_estimate = self.dataforseo_client.estimate_cost(estimated_total, True)
            
            with st.expander("💰 Estimation coûts DataForSEO"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Mots-clés estimés", f"{cost_estimate['keywords_count']:,}")
                with col2:
                    st.metric("Coût volumes", f"${cost_estimate['search_volume_cost']:.2f}")
                with col3:
                    st.metric("Coût total", f"${cost_estimate['total_cost']:.2f}")
