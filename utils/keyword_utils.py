import unicodedata
import re
from typing import List, Dict, Any

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
