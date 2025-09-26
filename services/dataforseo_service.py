import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Tuple, Optional, Callable

import streamlit as st
from dataforseo_client import DataForSEOClient
from utils.keyword_utils import deduplicate_keywords_with_origins


class StepStatus(str, Enum):
    """Statuts possibles pour une étape du pipeline DataForSEO"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Résultat d'une étape du pipeline"""

    name: str
    status: StepStatus
    data: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataForSEOAnalysisReport:
    """Rapport global d'une exécution DataForSEO"""

    steps: Dict[str, StepResult] = field(default_factory=dict)
    payload: Dict[str, Any] = field(default_factory=dict)

    def add_step(self, result: StepResult) -> None:
        self.steps[result.name] = result

    def get_step(self, name: str) -> Optional[StepResult]:
        return self.steps.get(name)

    def to_dict(self) -> Dict[str, Any]:
        """Retourne un dictionnaire compatible avec l'ancien format"""

        steps_summary = {
            name: {
                'status': result.status.value,
                'duration': result.duration,
                'error': result.error,
                'metadata': result.metadata
            }
            for name, result in self.steps.items()
        }

        return {
            **self.payload,
            'steps': steps_summary
        }

    @property
    def volume_data(self) -> List[Dict[str, Any]]:
        return self.payload.get('volume_data', [])

    @property
    def ads_suggestions(self) -> List[Dict[str, Any]]:
        return self.payload.get('ads_suggestions', [])

    @property
    def enriched_keywords(self) -> List[Dict[str, Any]]:
        return self.payload.get('enriched_keywords', [])

    @property
    def keywords_with_volume(self) -> List[Dict[str, Any]]:
        return self.payload.get('keywords_with_volume', [])

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

        if not all_keywords:
            st.warning("⚠️ Aucun mot-clé à traiter")
            return {'volume_data': [], 'keywords_with_volume': []}

        st.info(f"📊 Récupération des volumes pour {len(all_keywords)} mots-clés uniques")

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

        # Filtrer par volume minimum avec gestion des valeurs None
        min_volume = self.config.get('min_volume', 0)
        keywords_with_volume = []

        for item in volume_data:
            search_volume = item.get('search_volume')
            # Gestion sécurisée des valeurs None et conversion en nombre
            if search_volume is None:
                search_volume = 0
            else:
                try:
                    search_volume = float(search_volume)
                except (ValueError, TypeError):
                    search_volume = 0

            if search_volume >= min_volume:
                # Mettre à jour l'item avec la valeur convertie
                item_copy = item.copy()
                item_copy['search_volume'] = search_volume
                keywords_with_volume.append(item_copy)

        # Trier par volume décroissant pour optimiser les futures opérations
        keywords_with_volume.sort(key=lambda x: x.get('search_volume', 0) or 0, reverse=True)

        st.success(f"✅ {len(volume_data)} volumes récupérés, {len(keywords_with_volume)} avec volume ≥ {min_volume}")

        return {
            'volume_data': volume_data,
            'keywords_with_volume': keywords_with_volume,
            'total_keywords': len(all_keywords)
        }

    def get_ads_suggestions(self, keywords_with_volume: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Récupérer les suggestions Google Ads pour les 20 mots-clés avec le plus fort volume"""
        if not keywords_with_volume:
            return []

        # Trier par volume décroissant et sélectionner les 20 premiers
        sorted_keywords = sorted(
            keywords_with_volume,
            key=lambda x: x.get('search_volume', 0) or 0,
            reverse=True
        )
        top_20_keywords = sorted_keywords[:20]

        keywords_for_ads = [item['keyword'] for item in top_20_keywords]

        st.info(f"💰 Récupération des suggestions Ads pour les 20 mots-clés les plus populaires (volume max: {top_20_keywords[0].get('search_volume', 0) if top_20_keywords else 0})")

        ads_suggestions = self.client.get_keywords_for_keywords_batch(
            keywords_for_ads,
            self.config.get('language', 'fr'),
            self.config.get('location', 'fr'),
            max_batch_size=20
        )

        if ads_suggestions:
            st.success(f"✅ {len(ads_suggestions)} suggestions Ads récupérées depuis les 20 mots-clés les plus populaires")

        return ads_suggestions

    def process_complete_analysis(
        self,
        keywords: List[str],
        suggestions: List[str],
        progress_callback: Optional[Callable[[str, StepStatus, Dict[str, Any]], None]] = None
    ) -> DataForSEOAnalysisReport:
        """Processus complet d'enrichissement DataForSEO avec suivi d'étapes"""

        report = DataForSEOAnalysisReport()

        def notify(step_name: str, status: StepStatus, payload: Optional[Dict[str, Any]] = None) -> None:
            if progress_callback:
                progress_callback(step_name, status, payload or {})

        default_payload = {
            'volume_data': [],
            'ads_suggestions': [],
            'enriched_keywords': [],
            'keywords_with_volume': [],
            'total_keywords': 0,
            'top_20_keywords_count': 0
        }

        if not self.is_configured():
            error_message = "Configuration DataForSEO manquante"
            metadata = {'reason': 'not_configured'}
            report.add_step(StepResult('dataforseo_volumes', StepStatus.SKIPPED, error=error_message, metadata=metadata))
            report.add_step(StepResult('dataforseo_ads', StepStatus.SKIPPED, metadata=metadata))
            notify('dataforseo_volumes', StepStatus.SKIPPED, {'error': error_message})
            notify('dataforseo_ads', StepStatus.SKIPPED, {'error': error_message})
            st.warning("⚠️ DataForSEO non configuré")
            report.payload = default_payload
            return report

        volume_results: Dict[str, Any] = {}
        ads_suggestions: List[Dict[str, Any]] = []
        enriched_keywords: List[Dict[str, Any]] = []
        deduplicated_keywords: List[Dict[str, Any]] = []

        # Étape 1: Récupération des volumes
        st.info("📊 Étape 1: Récupération des volumes de recherche pour tous les mots-clés et suggestions")
        notify('dataforseo_volumes', StepStatus.RUNNING)
        start = time.perf_counter()
        try:
            volume_results = self.enrich_keywords_with_volumes(keywords, suggestions)
            duration = time.perf_counter() - start
            keywords_with_volume = volume_results.get('keywords_with_volume', [])
            status = StepStatus.COMPLETED if keywords_with_volume else StepStatus.PARTIAL
            metadata = {
                'input_keywords': len(keywords),
                'input_suggestions': len(suggestions),
                'total_unique_keywords': volume_results.get('total_keywords', len(set(keywords + suggestions))),
                'keywords_with_volume': len(keywords_with_volume)
            }
            report.add_step(StepResult(
                'dataforseo_volumes',
                status,
                data=volume_results,
                duration=duration,
                metadata=metadata
            ))
            notify('dataforseo_volumes', status, {'metadata': metadata})
            if status == StepStatus.PARTIAL:
                st.warning("⚠️ Aucun mot-clé avec volume de recherche trouvé")
        except (ConnectionError, ValueError, KeyError, RuntimeError) as exc:
            duration = time.perf_counter() - start
            error_message = str(exc)
            st.error(f"❌ Erreur DataForSEO (volumes): {error_message}")
            report.add_step(StepResult(
                'dataforseo_volumes',
                StepStatus.ERROR,
                error=error_message,
                duration=duration
            ))
            notify('dataforseo_volumes', StepStatus.ERROR, {'error': error_message})
            report.payload = default_payload
            return report

        # Étape 2: Suggestions Ads si des volumes sont disponibles
        keywords_with_volume = volume_results.get('keywords_with_volume', [])
        if keywords_with_volume:
            st.info("🔍 Étape 2: Utilisation de l'API Keywords for Keywords pour les 20 mots-clés les plus populaires")
            notify('dataforseo_ads', StepStatus.RUNNING)
            start = time.perf_counter()
            try:
                ads_suggestions = self.get_ads_suggestions(keywords_with_volume)
                duration = time.perf_counter() - start
                status = StepStatus.COMPLETED if ads_suggestions else StepStatus.PARTIAL
                metadata = {
                    'requested_keywords': min(20, len(keywords_with_volume)),
                    'returned_suggestions': len(ads_suggestions)
                }
                report.add_step(StepResult(
                    'dataforseo_ads',
                    status,
                    data=ads_suggestions,
                    duration=duration,
                    metadata=metadata
                ))
                notify('dataforseo_ads', status, {'metadata': metadata})
            except (ConnectionError, ValueError, KeyError, RuntimeError) as exc:
                duration = time.perf_counter() - start
                error_message = str(exc)
                st.error(f"❌ Erreur DataForSEO (Ads): {error_message}")
                report.add_step(StepResult(
                    'dataforseo_ads',
                    StepStatus.ERROR,
                    error=error_message,
                    duration=duration
                ))
                notify('dataforseo_ads', StepStatus.ERROR, {'error': error_message})
        else:
            metadata = {'reason': 'no_keywords_with_volume'}
            report.add_step(StepResult('dataforseo_ads', StepStatus.SKIPPED, metadata=metadata))
            notify('dataforseo_ads', StepStatus.SKIPPED, {'metadata': metadata})

        # Étape 3: Création de la liste enrichie finale
        start = time.perf_counter()
        enriched_keywords = self._create_enriched_keywords_list(
            keywords,
            volume_results.get('volume_data', []),
            ads_suggestions
        )
        duration = time.perf_counter() - start
        report.add_step(StepResult(
            'dataforseo_enrichment',
            StepStatus.COMPLETED,
            data=enriched_keywords,
            duration=duration,
            metadata={'count': len(enriched_keywords)}
        ))

        # Étape 4: Déduplication des mots-clés
        start = time.perf_counter()
        deduplicated_keywords = deduplicate_keywords_with_origins(enriched_keywords)
        duration = time.perf_counter() - start
        report.add_step(StepResult(
            'dataforseo_deduplication',
            StepStatus.COMPLETED,
            data=deduplicated_keywords,
            duration=duration,
            metadata={'count': len(deduplicated_keywords)}
        ))

        report.payload = {
            'volume_data': volume_results.get('volume_data', []),
            'ads_suggestions': ads_suggestions,
            'enriched_keywords': deduplicated_keywords,
            'keywords_with_volume': volume_results.get('keywords_with_volume', []),
            'total_keywords': len(deduplicated_keywords),
            'top_20_keywords_count': min(20, len(volume_results.get('keywords_with_volume', [])))
        }

        st.success(
            f"✅ Analyse DataForSEO terminée: {len(deduplicated_keywords)} mots-clés enrichis, {len(ads_suggestions)} suggestions Ads"
        )
        return report

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
        """S'assurer que tous les champs numériques ne sont pas None et convertir les chaînes en nombres"""
        # Conversion sécurisée pour search_volume (en entier, car les volumes sont généralement des entiers)
        search_volume = item.get('search_volume')
        if search_volume is None:
            item['search_volume'] = 0
        else:
            try:
                item['search_volume'] = int(float(search_volume))  # Conversion via float pour gérer les décimaux, puis int
            except (ValueError, TypeError):
                item['search_volume'] = 0
        
        # Conversion pour cpc (en float)
        cpc = item.get('cpc')
        if cpc is None:
            item['cpc'] = 0.0
        else:
            try:
                item['cpc'] = float(cpc)
            except (ValueError, TypeError):
                item['cpc'] = 0.0
        
        # Conversion pour competition (en float)
        competition = item.get('competition')
        if competition is None:
            item['competition'] = 0.0
        else:
            try:
                item['competition'] = float(competition)
            except (ValueError, TypeError):
                item['competition'] = 0.0

    def estimate_cost(self, keywords_count: int, enable_ads_suggestions: bool = True) -> Dict[str, Any]:
        """Estimer le coût des requêtes DataForSEO"""
        return self.client.estimate_cost(keywords_count, enable_ads_suggestions)

    def build_enriched_dataset(
        self,
        original_keywords: List[str],
        volume_results: Dict[str, Any],
        ads_suggestions: Optional[List[Dict[str, Any]]] = None,
        steps_summary: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Assembler un jeu de données enrichi à partir des résultats intermédiaires"""

        ads_suggestions = ads_suggestions or []
        volume_data = volume_results.get('volume_data', [])
        keywords_with_volume = volume_results.get('keywords_with_volume', [])

        enriched_keywords = self._create_enriched_keywords_list(
            original_keywords,
            volume_data,
            ads_suggestions
        )
        deduplicated_keywords = deduplicate_keywords_with_origins(enriched_keywords)

        dataset = {
            'volume_data': volume_data,
            'ads_suggestions': ads_suggestions,
            'enriched_keywords': deduplicated_keywords,
            'keywords_with_volume': keywords_with_volume,
            'total_keywords': len(deduplicated_keywords),
            'top_20_keywords_count': min(20, len(keywords_with_volume))
        }

        if steps_summary is not None:
            dataset['steps'] = steps_summary

        return dataset
