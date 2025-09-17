import streamlit as st
from typing import Dict, Any, Tuple
from dataforseo_client import DataForSEOClient

class ConfigManager:
    """Gestionnaire centralisé de la configuration"""
    
    def __init__(self):
        self.config = {}
        self.dataforseo_client = DataForSEOClient()
    
    def render_openai_config(self) -> str:
        """Configuration OpenAI dans la sidebar"""
        st.sidebar.header("🤖 Configuration OpenAI")
        
        api_key = st.sidebar.text_input(
            "Clé API OpenAI", 
            type="password", 
            help="Votre clé API OpenAI pour GPT-4o mini",
            placeholder="sk-..."
        )
        
        if api_key:
            st.sidebar.success("✅ API OpenAI configurée")
        else:
            st.sidebar.warning("⚠️ Clé API OpenAI requise pour la génération de questions")
        
        return api_key
    
    def render_dataforseo_config(self) -> Tuple[bool, Dict[str, Any]]:
        """Configuration DataForSEO dans la sidebar"""
        st.sidebar.header("📊 DataForSEO (Enrichissement)")
        
        enable_dataforseo = st.sidebar.checkbox(
            "Activer DataForSEO",
            value=False,
            help="Enrichir l'analyse avec volumes de recherche et suggestions Ads"
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
            st.sidebar.info("💡 DataForSEO ajoutera volumes de recherche et suggestions Ads à vos mots-clés")
            
            with st.sidebar.expander("🔧 Paramètres DataForSEO", expanded=True):
                dataforseo_config['login'] = st.text_input(
                    "Login DataForSEO", 
                    placeholder="votre_login"
                )
                dataforseo_config['password'] = st.text_input(
                    "Mot de passe DataForSEO", 
                    type="password",
                    placeholder="votre_password"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    dataforseo_config['language'] = st.selectbox(
                        "Langue",
                        options=['fr', 'en', 'es', 'de', 'it'],
                        index=0,
                        help="Langue pour les données DataForSEO"
                    )
                
                with col2:
                    dataforseo_config['location'] = st.selectbox(
                        "Pays cible",
                        options=['fr', 'en-us', 'en-gb', 'es', 'de', 'it', 'ca', 'au'],
                        index=0,
                        help="Géolocalisation des volumes"
                    )
                
                dataforseo_config['min_volume'] = st.slider(
                    "Volume minimum",
                    min_value=0,
                    max_value=1000,
                    value=10,
                    help="Volume mensuel minimum pour conserver un mot-clé"
                )
                
                st.info(f"🎯 Seuls les mots-clés avec ≥ {dataforseo_config['min_volume']} recherches/mois seront conservés")
            
            # Validation des credentials
            if dataforseo_config['login'] and dataforseo_config['password']:
                self.dataforseo_client.set_credentials(
                    dataforseo_config['login'], 
                    dataforseo_config['password']
                )
                
                if st.sidebar.button("🔍 Tester credentials"):
                    is_valid, message = self.dataforseo_client.test_credentials()
                    if is_valid:
                        st.sidebar.success(message)
                    else:
                        st.sidebar.error(message)
                
                st.sidebar.success("✅ DataForSEO configuré")
                st.sidebar.caption("📈 Volumes + 💰 Suggestions Ads seront ajoutés")
            else:
                st.sidebar.warning("⚠️ Login/Password requis")
        
        return enable_dataforseo, dataforseo_config
    
    def render_analysis_options(self) -> Dict[str, Any]:
        """Options d'analyse dans la sidebar"""
        st.sidebar.header("🎯 Options d'analyse")
        
        generate_questions = st.sidebar.checkbox(
            "Générer questions conversationnelles",
            value=True,
            help="Analyse thématique + génération de questions"
        )
        
        options = {
            'generate_questions': generate_questions,
            'final_questions_count': 20,
            'language': 'fr'
        }
        
        if generate_questions:
            options['final_questions_count'] = st.sidebar.slider(
                "Nombre de questions finales",
                min_value=5,
                max_value=100,
                value=20,
                help="Questions à conserver après consolidation"
            )
        
        options['language'] = st.sidebar.selectbox(
            "Langue d'analyse", 
            ["fr", "en", "es", "de", "it"], 
            index=0,
            help="Langue pour suggestions Google et questions"
        )
        
        return options
    
    def render_suggestion_levels(self) -> Dict[str, int]:
        """Configuration des niveaux de suggestions"""
        st.markdown("#### 📊 Configuration multi-niveaux")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            level1_count = st.slider(
                "Niveau 1 (direct)", 
                min_value=2, 
                max_value=15, 
                value=10,
                help="Suggestions directes du mot-clé"
            )
        
        with col2:
            level2_count = st.slider(
                "Niveau 2 (suggestions²)", 
                min_value=0,
                max_value=15, 
                value=0,
                help="Suggestions des suggestions (0 = désactivé)"
            )
        
        with col3:
            level3_count = st.slider(
                "Niveau 3 (suggestions³)", 
                min_value=0,
                max_value=15, 
                value=0,
                help="Niveau 3 des suggestions (0 = désactivé)"
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
