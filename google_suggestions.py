import requests
import time
import streamlit as st
from typing import List, Dict, Any

class GoogleSuggestionsClient:
    """Client pour récupérer les suggestions Google"""
    
    def __init__(self):
        self.base_url = "https://suggestqueries.google.com/complete/search"
    
    def get_suggestions(self, keyword: str, lang: str = 'fr', max_suggestions: int = 10) -> List[str]:
        """Récupère les suggestions Google pour un mot-clé"""
        if not keyword or not keyword.strip():
            return []
        
        params = {
            "q": keyword.strip(),
            "gl": lang,
            "client": "chrome",
            "_": str(int(time.time() * 1000))
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=5)
            response.raise_for_status()
            suggestions = response.json()[1][:max_suggestions]
            return [s for s in suggestions if s and s.strip()]  # Filtrer les suggestions vides
        except requests.exceptions.Timeout:
            st.warning(f"⏰ Timeout pour '{keyword}'")
            return []
        except requests.exceptions.ConnectionError:
            st.warning(f"🌐 Erreur de connexion pour '{keyword}'")
            return []
        except (ValueError, IndexError) as e:
            st.warning(f"📄 Erreur de parsing pour '{keyword}': {str(e)}")
            return []
        except Exception as e:
            st.warning(f"❌ Erreur inattendue pour '{keyword}': {str(e)}")
            return []
    
    def get_multilevel_suggestions(self, keyword: str, lang: str = 'fr', 
                                 level1_count: int = 10, level2_count: int = 5, level3_count: int = 0,
                                 enable_level2: bool = True, enable_level3: bool = False) -> List[Dict[str, Any]]:
        """Récupère les suggestions Google à plusieurs niveaux"""
        
        all_suggestions = []
        processed_suggestions = set()
        
        # Niveau 0: Mot-clé de base
        all_suggestions.append({
            'Mot-clé': keyword,
            'Niveau': 0,
            'Suggestion Google': keyword,
            'Parent': None
        })
        processed_suggestions.add(keyword.lower().strip())
        
        # Niveau 1: Suggestions directes
        level1_suggestions = self.get_suggestions(keyword, lang, level1_count)
        
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
        
        # Niveau 2: Suggestions des suggestions
        if enable_level2:
            level2_parents = []
            level1_items = [s for s in all_suggestions if s['Niveau'] == 1]
            
            for suggestion_data in level1_items:
                level2_suggestions = self.get_suggestions(
                    suggestion_data['Suggestion Google'], lang, level2_count
                )
                
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
                
                time.sleep(0.3)  # Rate limiting
            
            # Niveau 3: Suggestions des suggestions de niveau 2
            if enable_level3:
                for suggestion_data in level2_parents:
                    level3_suggestions = self.get_suggestions(
                        suggestion_data['Suggestion Google'], lang, level3_count
                    )
                    
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
                    
                    time.sleep(0.3)  # Rate limiting
        
        return all_suggestions
