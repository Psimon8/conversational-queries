import requests
import base64
import json
import time
import streamlit as st
from typing import List, Dict, Any, Tuple

class DataForSEOClient:
    """Client pour interagir avec l'API DataForSEO"""
    
    def __init__(self, login: str = None, password: str = None):
        self.login = login
        self.password = password
        self.base_url = "https://api.dataforseo.com"
        
        # Codes de langue et pays supportés
        self.language_codes = {
            'fr': {'code': 'fr', 'name': 'French'},
            'en': {'code': 'en', 'name': 'English'},
            'es': {'code': 'es', 'name': 'Spanish'},
            'de': {'code': 'de', 'name': 'German'},
            'it': {'code': 'it', 'name': 'Italian'}
        }
        
        self.location_codes = {
            'fr': {'code': 2250, 'name': 'France'},
            'en-us': {'code': 2840, 'name': 'United States'},
            'en-gb': {'code': 2826, 'name': 'United Kingdom'},
            'es': {'code': 2724, 'name': 'Spain'},
            'de': {'code': 2276, 'name': 'Germany'},
            'it': {'code': 2380, 'name': 'Italy'},
            'ca': {'code': 2124, 'name': 'Canada'},
            'au': {'code': 2036, 'name': 'Australia'}
        }
    
    def set_credentials(self, login: str, password: str):
        """Définir les credentials DataForSEO"""
        self.login = login
        self.password = password
    
    def _get_auth_header(self) -> str:
        """Créer l'header d'authentification"""
        if not self.login or not self.password:
            raise ValueError("Login et password DataForSEO requis")
        
        credentials = f"{self.login}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
    
    def test_credentials(self) -> Tuple[bool, str]:
        """Tester la validité des credentials"""
        try:
            headers = {
                'Authorization': self._get_auth_header(),
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{self.base_url}/v3/user/tasks_ready",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return True, "✅ Credentials DataForSEO valides"
            elif response.status_code == 401:
                return False, "❌ Credentials DataForSEO invalides"
            else:
                return False, f"❌ Erreur API: {response.status_code}"
                
        except Exception as e:
            return False, f"❌ Erreur de connexion: {str(e)}"
    
    def get_search_volume_batch(self, keywords: List[str], language: str = 'fr', 
                               location: str = 'fr', max_batch_size: int = 700) -> List[Dict[str, Any]]:
        """Récupérer les volumes de recherche par batch de mots-clés"""
        if not keywords:
            return []
        
        # Validation des paramètres
        if not self.login or not self.password:
            st.error("❌ Credentials DataForSEO manquants")
            return []
        
        # Limiter à la taille de batch maximale
        keywords = keywords[:max_batch_size]
        
        # Préparer les paramètres de localisation
        lang_code = self.language_codes.get(language, {'code': 'fr'})['code']
        location_code = self.location_codes.get(location, {'code': 2250})['code']
        
        post_data = [
            {
                "language_code": lang_code,
                "location_code": location_code,
                "keywords": keywords,
                "search_partners": False,
                "date_from": "2024-01-01",
                "date_to": "2024-12-31"
            }
        ]
        
        try:
            headers = {
                'Authorization': self._get_auth_header(),
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.base_url}/v3/keywords_data/google_ads/search_volume/live",
                headers=headers,
                data=json.dumps(post_data),
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['status_code'] == 20000:
                    results = []
                    for task in data.get('tasks', []):
                        if task['status_code'] == 20000:
                            for item in task.get('result', []):
                                # Gestion sécurisée des valeurs None
                                search_volume = item.get('search_volume')
                                if search_volume is None:
                                    search_volume = 0
                                
                                cpc = item.get('cpc')
                                if cpc is None:
                                    cpc = 0.0
                                
                                competition = item.get('competition')
                                if competition is None:
                                    competition = 0.0
                                
                                results.append({
                                    'keyword': item.get('keyword', ''),
                                    'search_volume': search_volume,
                                    'cpc': cpc,
                                    'competition': competition,
                                    'competition_level': item.get('competition_level', 'UNKNOWN')
                                })
                    return results
                else:
                    st.error(f"Erreur DataForSEO: {data.get('status_message', 'Unknown error')}")
                    return []
            else:
                st.error(f"Erreur HTTP {response.status_code}: {response.text}")
                return []
                
        except requests.exceptions.Timeout:
            st.error("❌ Timeout lors de la récupération des volumes")
            return []
        except requests.exceptions.ConnectionError:
            st.error("❌ Erreur de connexion DataForSEO")
            return []
        except Exception as e:
            st.error(f"❌ Erreur inattendue: {str(e)}")
            return []
    
    def get_keywords_for_keywords_batch(self, keywords: List[str], language: str = 'fr',
                                       location: str = 'fr', max_batch_size: int = 20) -> List[Dict[str, Any]]:
        """Récupérer les suggestions Ads par batch de mots-clés (max 20 par requête)"""
        if not keywords:
            return []
        
        # Validation des credentials
        if not self.login or not self.password:
            st.error("❌ Credentials DataForSEO manquants")
            return []
        
        all_suggestions = []
        
        # Traiter par chunks de max_batch_size
        for i in range(0, len(keywords), max_batch_size):
            batch = keywords[i:i + max_batch_size]
            
            # Préparer les paramètres de localisation
            lang_code = self.language_codes.get(language, {'code': 'fr'})['code']
            location_code = self.location_codes.get(location, {'code': 2250})['code']
            
            post_data = [
                {
                    "language_code": lang_code,
                    "location_code": location_code,
                    "keywords": batch,
                    "match_type": "broad",
                    "search_partners": False,
                    "date_from": "2024-01-01",
                    "date_to": "2024-12-31",
                    "sort_by": "search_volume",
                    "order_by": "desc",
                    "limit": 100
                }
            ]
            
            try:
                headers = {
                    'Authorization': self._get_auth_header(),
                    'Content-Type': 'application/json'
                }
                
                response = requests.post(
                    f"{self.base_url}/v3/keywords_data/google_ads/keywords_for_keywords/live",
                    headers=headers,
                    data=json.dumps(post_data),
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data['status_code'] == 20000:
                        for task in data.get('tasks', []):
                            if task['status_code'] == 20000:
                                for item in task.get('result', []):
                                    # Gestion sécurisée des valeurs None
                                    search_volume = item.get('search_volume')
                                    if search_volume is None:
                                        search_volume = 0
                                    
                                    cpc = item.get('cpc')
                                    if cpc is None:
                                        cpc = 0.0
                                    
                                    competition = item.get('competition')
                                    if competition is None:
                                        competition = 0.0
                                    
                                    all_suggestions.append({
                                        'keyword': item.get('keyword', ''),
                                        'search_volume': search_volume,
                                        'cpc': cpc,
                                        'competition': competition,
                                        'competition_level': item.get('competition_level', 'UNKNOWN'),
                                        'source_keyword': batch[0] if batch else '',  # Référence au mot-clé source
                                        'type': 'ads_suggestion'
                                    })
                    else:
                        st.warning(f"Erreur DataForSEO batch {i//max_batch_size + 1}: {data.get('status_message', 'Unknown error')}")
                else:
                    st.warning(f"Erreur HTTP {response.status_code} pour batch {i//max_batch_size + 1}: {response.text}")
                
                # Délai entre les requêtes pour éviter le rate limiting
                time.sleep(1)
                
            except requests.exceptions.Timeout:
                st.warning(f"❌ Timeout pour batch {i//max_batch_size + 1}")
                continue
            except requests.exceptions.ConnectionError:
                st.warning(f"❌ Erreur de connexion pour batch {i//max_batch_size + 1}")
                continue
            except Exception as e:
                st.warning(f"❌ Erreur inattendue batch {i//max_batch_size + 1}: {str(e)}")
                continue
        
        return all_suggestions
    
    def process_keywords_complete(self, initial_keywords: List[str], suggestions: List[str],
                                 language: str = 'fr', location: str = 'fr',
                                 min_volume: int = 0) -> Dict[str, Any]:
        """Processus complet: volumes + suggestions Ads pour tous les mots-clés"""
        
        # Étape 1: Combiner tous les mots-clés uniques
        all_keywords = list(set(initial_keywords + suggestions))
        
        st.info(f"🔍 Traitement de {len(all_keywords)} mots-clés uniques avec DataForSEO")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Étape 1: Récupérer les volumes de recherche
        status_text.text("⏳ Étape 1/2: Récupération des volumes de recherche...")
        progress_bar.progress(25)
        
        volume_data = self.get_search_volume_batch(
            all_keywords, language, location, max_batch_size=700
        )
        
        if not volume_data:
            st.error("❌ Aucun volume de recherche récupéré")
            progress_bar.empty()
            status_text.empty()
            return {'volume_data': [], 'ads_suggestions': [], 'enriched_keywords': []}
        
        # Filtrer par volume minimum - avec protection contre None
        keywords_with_volume = []
        for item in volume_data:
            search_volume = item.get('search_volume', 0)
            # S'assurer que search_volume n'est pas None
            if search_volume is None:
                search_volume = 0
            
            if search_volume >= min_volume:
                keywords_with_volume.append(item)
        
        st.success(f"✅ {len(volume_data)} volumes récupérés, {len(keywords_with_volume)} avec volume ≥ {min_volume}")
        
        progress_bar.progress(50)
        
        # Étape 2: Récupérer les suggestions Ads pour les mots-clés avec volume
        status_text.text("⏳ Étape 2/2: Récupération des suggestions Google Ads...")
        progress_bar.progress(75)
        
        keywords_for_ads = [item['keyword'] for item in keywords_with_volume[:100]]  # Limiter pour éviter trop de coûts
        
        ads_suggestions = []
        if keywords_for_ads:
            ads_suggestions = self.get_keywords_for_keywords_batch(
                keywords_for_ads, language, location, max_batch_size=20
            )
        
        progress_bar.progress(100)
        status_text.text("✅ Enrichissement DataForSEO terminé !")
        
        # Créer la liste enrichie finale
        enriched_keywords = []
        
        # Ajouter les mots-clés originaux avec leurs volumes
        keyword_volumes = {item['keyword']: item for item in volume_data}
        
        for keyword in all_keywords:
            volume_info = keyword_volumes.get(keyword, {
                'keyword': keyword,
                'search_volume': 0,
                'cpc': 0.0,
                'competition': 0.0,
                'competition_level': 'UNKNOWN'
            })
            
            # S'assurer que tous les champs numériques ne sont pas None
            if volume_info.get('search_volume') is None:
                volume_info['search_volume'] = 0
            if volume_info.get('cpc') is None:
                volume_info['cpc'] = 0.0
            if volume_info.get('competition') is None:
                volume_info['competition'] = 0.0
            
            enriched_keywords.append({
                **volume_info,
                'type': 'original',
                'source': 'google_suggest'
            })
        
        # Ajouter les suggestions Ads avec leurs volumes
        for ads_item in ads_suggestions:
            if ads_item['keyword'] not in [k['keyword'] for k in enriched_keywords]:
                # S'assurer que tous les champs numériques ne sont pas None
                if ads_item.get('search_volume') is None:
                    ads_item['search_volume'] = 0
                if ads_item.get('cpc') is None:
                    ads_item['cpc'] = 0.0
                if ads_item.get('competition') is None:
                    ads_item['competition'] = 0.0
                
                enriched_keywords.append({
                    **ads_item,
                    'source': 'google_ads'
                })
        
        progress_bar.empty()
        status_text.empty()
        
        return {
            'volume_data': volume_data,
            'ads_suggestions': ads_suggestions,
            'enriched_keywords': enriched_keywords,
            'total_keywords': len(enriched_keywords),
            'keywords_with_volume': len(keywords_with_volume)
        }
    
    def estimate_cost(self, keywords_count: int, enable_ads_suggestions: bool = True) -> Dict[str, Any]:
        """Estimer le coût des requêtes DataForSEO"""
        
        # Prix approximatifs DataForSEO (à ajuster selon les tarifs réels)
        search_volume_cost_per_1000 = 2.0  # $2 pour 1000 keywords
        keywords_for_keywords_cost_per_20 = 0.1  # $0.1 pour 20 keywords
        
        search_volume_cost = (keywords_count / 1000) * search_volume_cost_per_1000
        
        ads_suggestions_cost = 0
        if enable_ads_suggestions:
            # Estimation: environ 50% des mots-clés auront du volume et seront utilisés pour les suggestions Ads
            keywords_with_volume_estimate = min(keywords_count * 0.5, 100)  # Limité à 100 pour éviter les coûts
            ads_batches = (keywords_with_volume_estimate / 20)
            ads_suggestions_cost = ads_batches * keywords_for_keywords_cost_per_20
        
        total_cost = search_volume_cost + ads_suggestions_cost
        
        return {
            'search_volume_cost': search_volume_cost,
            'ads_suggestions_cost': ads_suggestions_cost,
            'total_cost': total_cost,
            'keywords_count': keywords_count,
            'estimated_ads_keywords': int(min(keywords_count * 0.5, 100)) if enable_ads_suggestions else 0
        }
