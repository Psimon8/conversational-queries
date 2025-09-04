import requests
import json
import time
from typing import List, Dict, Set
import logging
import os
import aiohttp
import asyncio
import async_timeout
from tqdm import tqdm
import pandas as pd

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config(config_file: str = 'config.json') -> dict:
    default_config = {
        'max_retries': 3,
        'timeout': 5,
        'base_url': 'https://suggestqueries.google.com/complete/search',
        'export_dir': 'export_suggests',
        'categories_file': '0_1_dictionnary/sub_categories.json'
    }
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            return {**default_config, **config}
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(f"Config file {config_file} not found or invalid, using defaults")
        return default_config

class GoogleSuggestExtractor:
    def __init__(self, keyword: str, lang: str = 'fr', max_suggests_l1: int = 10, max_suggests_l2: int = 5, level2_enabled: bool = True, use_delay: bool = True, delay: float = 1.0, categories: Dict[str, List[str]] = None):
        self.keyword = keyword
        self.lang = lang
        self.max_suggests_l1 = max_suggests_l1
        self.max_suggests_l2 = max_suggests_l2
        self.level2_enabled = level2_enabled
        self.use_delay = use_delay
        self.delay_between_queries = delay if use_delay else 0

        # Default categories in case of file load failure
        default_categories = {
            "question": ["comment", "quelle", "quel", "est ce que", "combien"],
            "localisation": ["centre", "gare", "quartier"],
            "proximite": ["proche", "pres de", "a cote"],
            "economy": ["pas cher", "economique", "abordable"],
            "midscale": ["3 etoiles", "moyen de gamme", "standard"],
            "luxury": ["luxe", "haut de gamme", "premium"],
            "promotion": ["promo", "bon plan", "reduction"],
            "cible": ["famille", "business", "professionnel"],
            "service": ["spa", "restaurant", "parking"],
            "renseignement": ["adresse", "avis", "telephone"],
            "style": ["moderne", "charme", "contemporain"],
            "evenement": ["ce soir", "derniere minute", "saint valentin"]
        }

        if categories is None:
            categories = default_categories
        
        # Set prefixes from "question" category if it exists, otherwise use default
        self.prefixes = categories.get('question', default_categories['question'])
        
        # Set suffixes only from categories that exist in the selected categories
        suffix_categories = [
            "localisation", "proximite", "economy", "midscale", "luxury",
            "promotion", "cible", "service", "renseignement", "style", "evenement"
        ]
        
        self.suffixes = {
            category: categories[category]
            for category in suffix_categories
            if category in categories  # Only include categories that were selected
        }
        
        # Ajout d'un attribut pour le délai entre les requêtes
        self.delay_between_queries = 1  # Reduced from 3 to 1 second
        
        # Attributs pour suivre l'état des threads
        self.current_thread = None
        self.query_type = None
        self.results = {
            "keyword": self.keyword,
            "suggests_level1": set(),
            "suggests_level2": {}
        }
        self.temp_results = []

    def _get_suggestions(self, query: str) -> List[str]:
        """Récupère les suggestions pour une requête donnée"""
        url = "https://suggestqueries.google.com/complete/search"
        params = {
            "q": query,
            "gl": self.lang,
            "client": "chrome",
            "_": str(int(time.time() * 1000))
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            suggestions = response.json()[1][:self.max_suggests_l1]
            logger.info(f"Récupération réussie pour la requête: {query}")
            return suggestions
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des suggestions pour {query}: {str(e)}")
            return []

    async def _get_suggestions_async(self, session: aiohttp.ClientSession, query: str) -> List[str]:
        """Version asynchrone de _get_suggestions avec retry"""
        url = "https://suggestqueries.google.com/complete/search"
        params = {
            "q": query,
            "gl": self.lang,
            "client": "chrome",
            "_": str(int(time.time() * 1000))
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with async_timeout.timeout(5):  # Reduced timeout from 10 to 5 seconds
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            # Read the response content as bytes
                            content = await response.read()
                            # Decode the content using iso-8859-1
                            decoded_content = content.decode('iso-8859-1')
                            # Parse the decoded content as JSON
                            data = json.loads(decoded_content)
                            suggestions = data[1][:self.max_suggests_l1]
                            logger.info(f"Récupération réussie pour la requête: {query}")
                            if self.use_delay:
                                await asyncio.sleep(self.delay_between_queries)
                            return suggestions
                        else:
                            logger.warning(f"Tentative {attempt + 1}/{max_retries} - Status {response.status} pour {query}")
            except Exception as e:
                logger.error(f"Tentative {attempt + 1}/{max_retries} - Erreur pour {query}: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Wait before retry
                continue
        return []

    async def _process_suggestion(self, session: aiohttp.ClientSession, suggestion: str) -> tuple[str, Set[str]]:
        """Traite une suggestion de niveau 1 de manière asynchrone"""
        level2_suggests = set()
        
        # Collecter toutes les requêtes à effectuer
        queries = [suggestion]  # Suggestion directe
        queries.extend(f"{prefix} {suggestion}" for prefix in self.prefixes)
        for suffixes in self.suffixes.values():
            queries.extend(f"{suggestion} {suffix}" for suffix in suffixes)

        # Exécuter toutes les requêtes de manière asynchrone
        tasks = [self._get_suggestions_async(session, query) for query in queries]
        results = await asyncio.gather(*tasks)
        
        # Agréger les résultats
        for result in results:
            level2_suggests.update(result)
            if self.use_delay:
                await asyncio.sleep(0.1)  # Small delay if enabled

        return suggestion, level2_suggests

    async def collect_level2_suggestions_async(self):
        """Version asynchrone de collect_level2_suggestions"""
        async with aiohttp.ClientSession() as session:
            tasks = []
            # Créer une tâche pour chaque suggestion de niveau 1
            for suggestion in self.results["suggests_level1"]:
                task = self._process_suggestion(session, suggestion)
                tasks.append(task)
                if self.use_delay:
                    await asyncio.sleep(self.delay_between_queries)

            # Exécuter toutes les tâches de manière asynchrone
            results = await asyncio.gather(*tasks)
            
            # Mettre à jour les résultats
            self.results["suggests_level2"] = {
                suggestion: list(suggests)
                for suggestion, suggests in results
                if suggests
            }

    async def collect_level1_suggestions_async(self):
        """Version asynchrone de la collecte niveau 1"""
        total_queries = (
            1 +  # requête directe
            len(self.prefixes) +  # requêtes avec préfixes
            sum(len(suffixes) for suffixes in self.suffixes.values())  # requêtes avec suffixes
        )
        
        processed_queries = 0
        progress_tracker = ProgressTracker(total_queries)
        
        async with aiohttp.ClientSession() as session:
            # Requête directe
            direct_results = await self._get_suggestions_async(session, self.keyword)
            self.temp_results.extend(direct_results)
            processed_queries += 1
            progress_tracker.update()
            logger.info(f"Progression : {processed_queries}/{total_queries} requêtes traitées")
            if self.use_delay:
                await asyncio.sleep(0.1)

            # Traiter les préfixes
            for prefix in self.prefixes:
                query = f"{prefix} {self.keyword}"
                prefix_results = await self._get_suggestions_async(session, query)
                self.temp_results.extend(prefix_results)
                processed_queries += 1
                progress_tracker.update()
                logger.info(f"Progression : {processed_queries}/{total_queries} requêtes traitées")
                if self.use_delay:
                    await asyncio.sleep(0.1)

            # Traiter les suffixes par catégorie
            for suffix_category, suffixes in self.suffixes.items():
                logger.info(f"Traitement des suffixes de la catégorie: {suffix_category}")
                for suffix in suffixes:
                    query = f"{self.keyword} {suffix}"
                    suffix_results = await self._get_suggestions_async(session, query)
                    self.temp_results.extend(suffix_results)
                    processed_queries += 1
                    progress_tracker.update()
                    logger.info(f"Progression : {processed_queries}/{total_queries} requêtes traitées")
                    if self.use_delay:
                        await asyncio.sleep(0.1)

            self.results["suggests_level1"] = set(self.temp_results)
            progress_tracker.close()

    def collect_level2_suggestions(self):
        """Version synchrone de la collecte niveau 2"""
        total_queries = len(self.results["suggests_level1"])
        processed_queries = set()  # Pour éviter les doublons
        
        with tqdm(total=total_queries, desc="Collecting level 2 suggestions") as pbar:
            start_time = time.time()
            for suggestion in self.results["suggests_level1"]:
                if suggestion not in self.results["suggests_level2"]:
                    level2_suggests = set()
                    
                    # Collecter les requêtes à effectuer
                    queries = [q for q in self._generate_queries(suggestion) if q not in processed_queries]
                    
                    # Mettre à jour les requêtes traitées
                    processed_queries.update(queries)
                    
                    # Exécuter les requêtes avec délai
                    for query in queries:
                        suggestions = self._get_suggestions(query)
                        level2_suggests.update(suggestions)
                        if self.use_delay:
                            time.sleep(self.delay_between_queries)
                    
                    # Remove the parent suggestion from level2 suggestions
                    level2_suggests.discard(suggestion)
                    self.results["suggests_level2"][suggestion] = list(level2_suggests)
                    
                    # Mise à jour de la barre de progression
                    pbar.update(1)
                    
                    # Calcul du temps estimé restant
                    elapsed_time = time.time() - start_time
                    queries_per_second = (pbar.n) / elapsed_time if elapsed_time > 0 else 0
                    remaining_time = (total_queries - pbar.n) / queries_per_second if queries_per_second > 0 else 0
                    pbar.set_postfix({'ETA': f'{remaining_time:.1f}s'})

    def collect_level1_suggestions(self):
        """Point d'entrée pour la collecte niveau 1"""
        asyncio.run(self.collect_level1_suggestions_async())

    def extract_all(self):
        """Exécute l'extraction complète avec contrôle de progression"""
        logger.info(f"Démarrage de l'extraction pour le mot-clé: {self.keyword}")
        
        progress = {
            "level1_started": False,
            "level1_completed": False,
            "level2_started": False,
            "level2_completed": False
        }

        try:
            # Niveau 1
            progress["level1_started"] = True
            self.collect_level1_suggestions()
            progress["level1_completed"] = True

            if not self.results["suggests_level1"]:
                raise ValueError("Aucune suggestion de niveau 1 trouvée")

            # Niveau 2 (seulement si activé)
            if self.level2_enabled:
                progress["level2_started"] = True
                self.collect_level2_suggestions()
                progress["level2_completed"] = True

        except Exception as e:
            logger.error(f"Erreur pendant l'extraction: {str(e)}")
            return self._generate_error_results(progress)

        return self._generate_final_results(progress)

    def _generate_error_results(self, progress: dict) -> dict:
        """Génère un rapport en cas d'erreur"""
        return {
            "keyword": self.keyword,
            "metadata": {
                "date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "language": self.lang,
                "error": True,
                "progress": progress
            },
            "partial_results": self.results
        }

    def _generate_final_results(self, progress: dict) -> dict:
        """Génère les résultats finaux avec métadonnées de progression"""
        # Nettoyage des doublons dans level2_suggests
        cleaned_level2_suggests = {}
        for suggest in self.results["suggests_level1"]:
            if suggest in self.results["suggests_level2"]:
                suggests_set = set(self.results["suggests_level2"][suggest])
                suggests_set.discard(suggest)
                cleaned_level2_suggests[suggest] = list(suggests_set)

        level2_count = sum(len(suggests) for suggests in cleaned_level2_suggests.values())
        
        final_results = {
            "keyword": self.keyword,
            "metadata": {
                "date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "language": self.lang,
                "max_suggests_l1": self.max_suggests_l1,
                "max_suggests_l2": self.max_suggests_l2,
                "progress": progress,
                "stats": {
                    "level1_count": len(self.results["suggests_level1"]),
                    "level2_total_count": level2_count,
                    "processing_complete": progress.get("level2_completed", False)
                },
                "json_output_path": None, # Added
                "xlsx_export_status": "not_attempted", # Added
                "xlsx_output_path": None # Added
            },
            "hierarchy": {
                "level1": {
                    suggest: {
                        "query": suggest,
                        "level2_suggests": sorted(cleaned_level2_suggests.get(suggest, [])),
                        "level2_count": len(cleaned_level2_suggests.get(suggest, []))
                    }
                    for suggest in sorted(list(self.results["suggests_level1"]))
                }
            }
        }

        config = load_config()
        export_dir = config.get('export_dir', 'export_suggests')
        os.makedirs(export_dir, exist_ok=True)
        
        timestamp = time.strftime("%H%M_%d%m%Y")
        base_filename = f"google_suggests_{self.keyword}_{self.lang}_{timestamp}"
        
        output_file_json = os.path.join(export_dir, f"{base_filename}.json")
        with open(output_file_json, 'w', encoding='utf-8') as f:
            json.dump(final_results, f, ensure_ascii=False, indent=2)
        logger.info(f"Extraction terminée. Résultats JSON sauvegardés dans: {output_file_json}")
        final_results["metadata"]["json_output_path"] = output_file_json # Store actual JSON path

        try:
            data_for_df = []
            for l1_suggest_key in sorted(list(self.results["suggests_level1"])):
                l1_data = final_results["hierarchy"]["level1"].get(l1_suggest_key, {})
                l1_query = l1_data.get("query", l1_suggest_key)
                
                if l1_data.get("level2_suggests"):
                    for l2_suggest in l1_data["level2_suggests"]:
                        data_for_df.append({
                            "Keyword": final_results["keyword"],
                            "Language": final_results["metadata"]["language"],
                            "Level 1 Suggestion": l1_query,
                            "Level 2 Suggestion": l2_suggest
                        })
                else:
                    data_for_df.append({
                        "Keyword": final_results["keyword"],
                        "Language": final_results["metadata"]["language"],
                        "Level 1 Suggestion": l1_query,
                        "Level 2 Suggestion": ""
                    })
            
            if data_for_df:
                df = pd.DataFrame(data_for_df)
                output_file_xlsx = os.path.join(export_dir, f"{base_filename}.xlsx")
                df.to_excel(output_file_xlsx, index=False, engine='openpyxl')
                logger.info(f"Résultats XLSX sauvegardés dans: {output_file_xlsx}")
                final_results["metadata"]["xlsx_export_status"] = "success"
                final_results["metadata"]["xlsx_output_path"] = output_file_xlsx # Store actual XLSX path
            else:
                logger.info("Aucune donnée à exporter en XLSX.")
                final_results["metadata"]["xlsx_export_status"] = "no_data"

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des résultats XLSX: {str(e)}")
            final_results["metadata"]["xlsx_export_status"] = "error"

        return final_results

    def _generate_queries(self, suggestion: str) -> List[str]:
        """Generate all possible queries for a given suggestion"""
        queries = [suggestion]  # Direct suggestion
        queries.extend(f"{prefix} {suggestion}" for prefix in self.prefixes)
        for suffixes in self.suffixes.values():
            queries.extend(f"{suggestion} {suffix}" for suffix in suffixes)
        return list(set(queries))  # Remove duplicates

class ProgressTracker:
    def __init__(self, total_queries: int):
        self.progress_bar = tqdm(total=total_queries, desc="Processing queries")
    
    def update(self, n: int = 1):
        self.progress_bar.update(n)
    
    def close(self):
        self.progress_bar.close()

class RateLimiter:
    def __init__(self, calls: int, period: float):
        self.calls = calls
        self.period = period
        self.timestamps = []

    async def acquire(self):
        now = time.time()
        self.timestamps = [ts for ts in self.timestamps if now - ts <= self.period]
        
        if len(self.timestamps) >= self.calls:
            wait_time = self.timestamps[0] + self.period - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)

def validate_inputs(keyword: str, lang: str, max_suggests_l1: int, max_suggests_l2: int, delay: float) -> bool:
    if not keyword.strip():
        logger.error("Keyword cannot be empty")
        return False
    if not lang.strip():
        logger.error("Language code cannot be empty")
        return False
    if max_suggests_l1 <= 0 or max_suggests_l2 < 0:
        logger.error("Suggestion counts must be positive")
        return False
    if delay < 0:
        logger.error("Delay must be non-negative")
        return False
    return True

def select_categories() -> Dict[str, List[str]]:
    """Permet à l'utilisateur de sélectionner les catégories à utiliser"""
    try:
        with open('0_1_dictionnary/sub_categories.json', 'r', encoding='utf-8') as f:
            all_categories = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error loading categories: {str(e)}")
        return {}

    print("\nAvailable categories:")
    categories = list(all_categories.keys())
    for i, category in enumerate(categories, 1):
        print(f"{i}. {category}")
    
    print("\nSelect categories (comma-separated numbers, press Enter for all):")
    selection = input("> ").strip()
    
    if not selection:
        return all_categories
    
    try:
        selected_indices = [int(x.strip()) - 1 for x in selection.split(',')]
        selected_categories = {
            categories[i]: all_categories[categories[i]]
            for i in selected_indices
            if 0 <= i < len(categories)
        }
        return selected_categories
    except (ValueError, IndexError):
        logger.error("Invalid selection, using all categories")
        return all_categories

def main(selected_categories_from_notebook: Dict[str, List[str]] = None):
    try:
        # Load configuration
        config = load_config()
        
        # Select categories
        if selected_categories_from_notebook is not None:
            selected_categories = selected_categories_from_notebook
            logger.info("Using categories selected from the notebook.")
        else:
            selected_categories = select_categories()
        
        # Get user inputs with better validation
        while True:
            keyword = input("Enter your keyword: ").strip()
            if keyword:
                break
            print("Keyword cannot be empty")
        
        lang = input("Enter language code (default: fr): ").strip() or 'fr'
        
        while True:
            try:
                max_suggests_l1 = int(input("Number of level 1 suggestions (default: 10): ") or 10)
                if max_suggests_l1 > 0:
                    break
                print("Please enter a positive number")
            except ValueError:
                print("Please enter a valid number")
        
        # Level 2 suggestions configuration
        level2_enabled = input("Enable level 2 suggestions? (y/N): ").lower() == 'y'
        max_suggests_l2 = 0
        
        if level2_enabled:
            while True:
                try:
                    max_suggests_l2 = int(input("Number of level 2 suggestions (default: 5): ") or 5)
                    if max_suggests_l2 >= 0:
                        break
                    print("Please enter a non-negative number")
                except ValueError:
                    print("Please enter a valid number")
        
        # Delay configuration
        use_delay = input("Add delay between requests? (y/N): ").lower() == 'y'
        delay = 1.0
        if use_delay:
            while True:
                try:
                    delay = float(input("Delay in seconds (default: 1.0): ") or 1.0)
                    if delay >= 0:
                        break
                    print("Please enter a non-negative number")
                except ValueError:
                    print("Please enter a valid number")

        # Create extractor with selected categories
        extractor = GoogleSuggestExtractor(
            keyword=keyword,
            lang=lang,
            max_suggests_l1=max_suggests_l1,
            max_suggests_l2=max_suggests_l2,
            level2_enabled=level2_enabled,
            use_delay=use_delay,
            delay=delay,
            categories=selected_categories  # Add this parameter to constructor
        )

        # Execute extraction
        results = extractor.extract_all()
        
        # Print summary
        print("\nExtraction complete!")
        if not results.get("metadata", {}).get("error", False):
            stats = results.get("metadata", {}).get("stats", {})
            print(f"Level 1 suggestions: {stats.get('level1_count', 0)}")
            if level2_enabled:
                print(f"Total level 2 suggestions: {stats.get('level2_total_count', 0)}")
            
            json_output_path = results.get("metadata", {}).get("json_output_path")
            if json_output_path:
                print(f"JSON results saved to: {json_output_path}")
            else:
                print("JSON results were not saved.")

            xlsx_status = results.get("metadata", {}).get("xlsx_export_status")
            xlsx_output_path = results.get("metadata", {}).get("xlsx_output_path")

            if xlsx_status == "success" and xlsx_output_path:
                 print(f"XLSX results saved to: {xlsx_output_path}")
            elif xlsx_status == "no_data":
                print("No data to export to XLSX.")
            elif xlsx_status == "error":
                print("Error during XLSX export. Check logs.")
            else:
                print("XLSX export was not attempted or status is unknown.")
        else:
            print("Extraction completed with errors. Check the logs for details.")

    except KeyboardInterrupt:
        print("\nExtraction cancelled by user")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise

if __name__ == "__main__":
    main()

# Created/Modified files during execution:
# google_suggests_{keyword}_{lang}.json