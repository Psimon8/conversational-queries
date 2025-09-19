import streamlit as st
from typing import List, Dict, Any, Tuple
from dataforseo_client import DataForSEOClient

class DataForSEOService:
    """Service pour gérer les interactions avec DataForSEO"""
    
    def __init__(self, dataforseo_config: Dict[str, Any]):
        self.config = dataforseo_config
        self.client = DataForSEOClient()
        if dataforseo_config.get('login') and dataforseo_config.get('password'):
            self.client.set_credentials(
                dataforseo_config['login'], 
                dataforseo_config['password']
            )
    
    def is_configured(self) -> bool:
        """Vérifier si DataForSEO est correctement configuré"""
        return bool(self.config.get('login') and self.config.get('password'))
    
    def test_connection(self) -> Tuple[bool, str]:
        """Tester la connexion DataForSEO"""
        if not self.is_configured():
            return False, "Configuration DataForSEO manquante"
        
        return self.client.test_credentials()
    
    def enrich_keywords_with_volumes(self, keywords: List[str], 
                                   suggestions: List[str]) -> Dict[str, Any]:
        """Enrichir les mots-clés avec les volumes de recherche"""
        if not self.is_configured():
            st.warning("⚠️ DataForSEO non configuré")
            return {}
        
        # Combiner tous les mots-clés uniques
        all_keywords = list(set(keywords + suggestions))
        
        st.info(f"📊 Récupération des volumes pour {len(all_keywords)} mots-clés")
        
        # Récupérer les volumes de recherche
        volume_data = self.client.get_search_volume_batch(
            all_keywords,
            self.config.get('language', 'fr'),
            self.config.get('location', 'fr'),
            max_batch_size=700
        )
        
        if not volume_data:
            st.warning("⚠️ Aucun volume de recherche récupéré")
            return {'volume_data': [], 'keywords_with_volume': []}
        
        # Filtrer par volume minimum
        min_volume = self.config.get('min_volume', 0)
        keywords_with_volume = [
            item for item in volume_data
            if (item.get('search_volume') or 0) >= min_volume
        ]
        
        st.success(f"✅ {len(volume_data)} volumes récupérés, {len(keywords_with_volume)} avec volume ≥ {min_volume}")
        
        return {
            'volume_data': volume_data,
            'keywords_with_volume': keywords_with_volume,
            'total_keywords': len(all_keywords)
        }
    
    def get_ads_suggestions(self, keywords_with_volume: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Récupérer les suggestions Google Ads"""
        if not keywords_with_volume:
            return []
        
        # Limiter le nombre de mots-clés pour éviter les coûts
        keywords_for_ads = [item['keyword'] for item in keywords_with_volume[:100]]
        
        st.info(f"💰 Récupération des suggestions Ads pour {len(keywords_for_ads)} mots-clés")
        
        ads_suggestions = self.client.get_keywords_for_keywords_batch(
            keywords_for_ads,
            self.config.get('language', 'fr'),
            self.config.get('location', 'fr'),
            max_batch_size=20
        )
        
        if ads_suggestions:
            st.success(f"✅ {len(ads_suggestions)} suggestions Ads récupérées")
        
        return ads_suggestions
    
    def process_complete_analysis(self, keywords: List[str], 
                                suggestions: List[str]) -> Dict[str, Any]:
        """Processus complet d'enrichissement DataForSEO"""
        if not self.is_configured():
            return {}
        
        try:
            # Étape 1: Volumes de recherche
            volume_results = self.enrich_keywords_with_volumes(keywords, suggestions)
            
            # Étape 2: Suggestions Ads
            ads_suggestions = []
            if volume_results.get('keywords_with_volume'):
                ads_suggestions = self.get_ads_suggestions(volume_results['keywords_with_volume'])
            
            # Étape 3: Création de la liste enrichie finale
            enriched_keywords = self._create_enriched_keywords_list(
                keywords, volume_results.get('volume_data', []), ads_suggestions
            )
            
            return {
                'volume_data': volume_results.get('volume_data', []),
                'ads_suggestions': ads_suggestions,
                'enriched_keywords': enriched_keywords,
                'keywords_with_volume': volume_results.get('keywords_with_volume', []),
                'total_keywords': len(enriched_keywords)
            }
            
        except Exception as e:
            st.error(f"❌ Erreur DataForSEO: {str(e)}")
            return {}
    
    def _create_enriched_keywords_list(self, original_keywords: List[str], 
                                     volume_data: List[Dict[str, Any]],
                                     ads_suggestions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Créer la liste enrichie finale des mots-clés"""
        enriched_keywords = []
        keyword_volumes = {item['keyword']: item for item in volume_data}
        
        # Ajouter les mots-clés originaux avec leurs volumes
        for keyword in original_keywords:
            volume_info = keyword_volumes.get(keyword, {
                'keyword': keyword,
                'search_volume': 0,
                'cpc': 0.0,
                'competition': 0.0,
                'competition_level': 'UNKNOWN'
            })
            
            # S'assurer que tous les champs numériques ne sont pas None
            self._sanitize_numeric_fields(volume_info)
            
            enriched_keywords.append({
                **volume_info,
                'type': 'original',
                'source': 'google_suggest'
            })
        
        # Ajouter les suggestions avec volumes
        suggestion_texts = [item['keyword'] for item in volume_data if item['keyword'] not in original_keywords]
        for keyword in suggestion_texts:
            volume_info = keyword_volumes.get(keyword)
            if volume_info:
                self._sanitize_numeric_fields(volume_info)
                enriched_keywords.append({
                    **volume_info,
                    'type': 'suggestion',
                    'source': 'google_suggest'
                })
        
        # Ajouter les suggestions Ads avec leurs volumes
        for ads_item in ads_suggestions:
            if ads_item['keyword'] not in [k['keyword'] for k in enriched_keywords]:
                self._sanitize_numeric_fields(ads_item)
                enriched_keywords.append({
                    **ads_item,
                    'source': 'google_ads'
                })
        
        return enriched_keywords
    
    def _sanitize_numeric_fields(self, item: Dict[str, Any]) -> None:
        """S'assurer que tous les champs numériques ne sont pas None"""
        if item.get('search_volume') is None:
            item['search_volume'] = 0
        if item.get('cpc') is None:
            item['cpc'] = 0.0
        if item.get('competition') is None:
            item['competition'] = 0.0
    
    def estimate_cost(self, keywords_count: int, enable_ads_suggestions: bool = True) -> Dict[str, Any]:
        """Estimer le coût des requêtes DataForSEO"""
        return self.client.estimate_cost(keywords_count, enable_ads_suggestions)
