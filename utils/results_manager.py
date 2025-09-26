import streamlit as st
import pandas as pd
from typing import Dict, Any, List
from .ui_components import render_metrics
from collections import Counter
import re
import math

class ResultsManager:
    """Gestionnaire pour l'affichage des résultats"""
    
    def __init__(self, results: Dict[str, Any], metadata: Dict[str, Any]):
        self.results = results
        self.metadata = metadata
    
    def _extract_1grams(self, suggestions: List[str]) -> List[str]:
        """Extraire les 1-grams (mots uniques) des suggestions"""
        all_words = []
        for suggestion in suggestions:
            # Nettoyer et découper en mots
            words = re.findall(r'\b[a-zA-ZÀ-ÿ]+\b', suggestion.lower())
            all_words.extend(words)
        return all_words
    
    def _get_top_tags(self, suggestions_list: List[str], top_n: int = 20) -> List[tuple]:
        """Obtenir les top N tags (1-grams) les plus fréquents"""
        words = self._extract_1grams(suggestions_list)
        
        # Mots vides français et anglais à exclure
        stop_words = {
            'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'ou', 'à', 'au', 'aux',
            'pour', 'par', 'sur', 'avec', 'dans', 'en', 'ce', 'cette', 'ces', 'son', 'sa',
            'ses', 'mon', 'ma', 'mes', 'ton', 'ta', 'tes', 'notre', 'nos', 'votre', 'vos',
            'leur', 'leurs', 'que', 'qui', 'dont', 'où', 'quand', 'comment', 'pourquoi',
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
            'with', 'by', 'how', 'what', 'when', 'where', 'why', 'which', 'that', 'this',
            'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had'
        }
        
        # Filtrer les mots vides et compter les occurrences
        filtered_words = [word for word in words if word not in stop_words and len(word) > 2]
        word_counts = Counter(filtered_words)
        
        return word_counts.most_common(top_n)
    
    def _filter_suggestions_by_tags(self, suggestions_df: pd.DataFrame, selected_tags: List[str], all_tags: List[str], custom_exclude_words: str = "") -> pd.DataFrame:
        """Filtrer les suggestions basées sur les tags sélectionnés et les mots personnalisés à exclure"""
        # Trouver les tags qui ont été désélectionnés
        deselected_tags = [tag for tag in all_tags if tag not in selected_tags]
        
        # Traiter les mots personnalisés à exclure
        custom_words = []
        if custom_exclude_words.strip():
            # Séparer par virgules ou espaces et nettoyer
            custom_words = [word.strip().lower() for word in re.split(r'[,\s]+', custom_exclude_words.strip()) if word.strip()]
        
        # Combiner tous les mots à exclure
        all_exclude_words = deselected_tags + custom_words
        
        if not all_exclude_words:
            # Si aucun mot à exclure, montrer toutes les suggestions
            return suggestions_df
        
        # Créer un pattern regex pour tous les mots à exclure
        exclude_pattern = '|'.join([rf'\b{re.escape(word)}\b' for word in all_exclude_words])
        
        # Exclure les suggestions qui contiennent un des mots à exclure
        exclude_mask = suggestions_df['Suggestion Google'].str.contains(exclude_pattern, case=False, regex=True, na=False)
        
        # Garder les suggestions qui ne contiennent aucun mot à exclure
        # Toujours inclure le niveau 0 (mots-clés de base)
        level_0_mask = suggestions_df['Niveau'] == 0
        final_mask = ~exclude_mask | level_0_mask
        
        return suggestions_df[final_mask]
    
    def render_analysis_summary(self):
        """Afficher le résumé de l'analyse"""
        st.markdown("## 📊 Résumé de l'analyse")
        
        # Métriques principales
        metrics = self._calculate_main_metrics()
        render_metrics(metrics)
        
        # Informations contextuelles
        self._render_context_info()

        # Statut du pipeline DataForSEO le cas échéant
        self._render_dataforseo_pipeline_summary()
    
    def _calculate_main_metrics(self) -> Dict[str, Any]:
        """Calculer les métriques principales"""
        metrics = {
            "Mots-clés": len(self.metadata.get('keywords', [])),
            "Suggestions": len(self.results.get('all_suggestions', [])),
        }
        
        # Ajouter métriques DataForSEO si disponible
        if self.results.get('enriched_keywords'):
            enriched_keywords = self.results['enriched_keywords']
            keywords_with_volume = [k for k in enriched_keywords if k.get('search_volume', 0) > 0]
            ads_keywords = [k for k in enriched_keywords if '💰 Suggestion Ads' in k.get('origine', '')]
            
            metrics.update({
                "Avec volume": len(keywords_with_volume),
                "Suggestions Ads": len(ads_keywords)
            })
        
        # Ajouter métriques de questions si disponible
        if self.results.get('final_consolidated_data'):
            metrics["Questions"] = len(self.results['final_consolidated_data'])
        
        if self.results.get('selected_themes_by_keyword'):
            total_themes = sum(len(themes) for themes in self.results['selected_themes_by_keyword'].values())
            metrics["Thèmes sélectionnés"] = total_themes
        
        return metrics
    
    def _render_context_info(self):
        """Afficher les informations contextuelles"""
        col1, col2 = st.columns(2)
        
        with col1:
            st.info(f"🌍 **Langue:** {self.metadata.get('language', 'fr').upper()}")
            if self.metadata.get('timestamp'):
                st.info(f"⏰ **Analysé le:** {self.metadata['timestamp']}")
        
        with col2:
            if self.metadata.get('generate_questions'):
                st.info("✨ **Questions conversationnelles:** Activées")
            else:
                st.info("📝 **Mode:** Suggestions uniquement")

    def _render_dataforseo_pipeline_summary(self):
        """Afficher un résumé des étapes DataForSEO"""
        dataforseo_data = self.results.get('dataforseo_data', {})
        steps = dataforseo_data.get('steps', {})

        if not steps:
            return

        st.markdown("### ⚙️ Pipeline DataForSEO")

        status_icons = {
            'completed': '✅',
            'partial': '🟡',
            'error': '❌',
            'skipped': '⏭️',
            'running': '🔄',
            'pending': '⏳'
        }

        step_labels = {
            'dataforseo_volumes': 'Volumes de recherche',
            'dataforseo_ads': 'Suggestions Ads',
            'dataforseo_enrichment': 'Enrichissement des données',
            'dataforseo_deduplication': 'Déduplication'
        }

        for step_name, step_info in steps.items():
            status = step_info.get('status', 'pending')
            icon = status_icons.get(status, 'ℹ️')
            label = step_labels.get(step_name, step_name)
            duration = step_info.get('duration')
            metadata = step_info.get('metadata') or {}
            details = []

            if isinstance(duration, (int, float)) and duration:
                details.append(f"{duration:.2f}s")

            if status == 'error' and step_info.get('error'):
                details.append(f"Erreur : {step_info['error']}")

            if step_name == 'dataforseo_volumes' and metadata.get('keywords_with_volume') is not None:
                details.append(f"{metadata['keywords_with_volume']} mots-clés avec volume")

            if step_name == 'dataforseo_ads' and metadata.get('returned_suggestions') is not None:
                details.append(f"{metadata['returned_suggestions']} suggestions")

            if metadata.get('reason'):
                details.append(metadata['reason'])

            detail_text = " • ".join(details) if details else ""
            if detail_text:
                st.write(f"{icon} **{label}** — {detail_text}")
            else:
                st.write(f"{icon} **{label}**")
    
    def render_suggestions_results(self):
        """Afficher les résultats des suggestions"""
        if not self.results.get('all_suggestions'):
            return
        
        st.markdown("### 📝 Suggestions Google")
        
        suggestions_df = pd.DataFrame(self.results['all_suggestions'])
        selected_tags: List[str] = []
        all_tags: List[str] = []
        custom_exclude = ""
        
        # Extraire les suggestions pour l'analyse des tags (exclure niveau 0)
        suggestion_texts = [s['Suggestion Google'] for s in self.results['all_suggestions'] if s['Niveau'] > 0]
        
        if suggestion_texts:
            # Analyse des tags les plus fréquents
            top_tags = self._get_top_tags(suggestion_texts, 20)
            
            if top_tags:
                st.markdown("**🏷️ Filtrage des suggestions**")
                
                # Créer deux colonnes pour les filtres sur la même ligne
                col_tags, col_custom = st.columns([3, 1])
                
                with col_tags:
                    # Créer la liste des tags avec leurs occurrences pour l'affichage
                    tag_options = [f"{tag} ({count})" for tag, count in top_tags]
                    all_tags = [tag for tag, count in top_tags]
                    
                    # Widget multiselect pour choisir les tags à inclure
                    selected_tag_display = st.multiselect(
                        "Décochez un tag pour exclure toutes les suggestions contenant ce mot :",
                        options=tag_options,
                        default=tag_options,  # Tous sélectionnés par défaut
                        help="Les suggestions contenant les tags décochés seront exclues du tableau et de l'export",
                        key="tag_filter"
                    )
                
                with col_custom:
                    # Champ de saisie pour mots personnalisés à exclure
                    custom_exclude = st.text_area(
                        "Mots à exclure :",
                        placeholder="mot1, mot2, mot3",
                        help="Saisissez des mots séparés par des virgules ou des espaces. Les suggestions contenant ces mots seront exclues.",
                        key="custom_exclude_words",
                        height=132  # Hauteur similaire au multiselect
                    )
                
                # Extraire les tags réels (sans les comptes)
                selected_tags = []
                for display_tag in selected_tag_display:
                    # Extraire le tag avant la parenthèse
                    tag = display_tag.split(' (')[0]
                    selected_tags.append(tag)
                
                # Filtrer les suggestions basées sur les tags sélectionnés et les mots personnalisés
                filtered_df = self._filter_suggestions_by_tags(suggestions_df, selected_tags, all_tags, custom_exclude)
                
                # Afficher le nombre de suggestions filtrées
                if len(selected_tags) != len(all_tags) or custom_exclude.strip():
                    excluded_count = len(suggestions_df) - len(filtered_df)
                    exclusion_reasons = []
                    
                    deselected_tags = [tag for tag in all_tags if tag not in selected_tags]
                    if deselected_tags:
                        exclusion_reasons.append(f"tags: {', '.join(deselected_tags)}")
                    
                    if custom_exclude.strip():
                        custom_words = [word.strip() for word in re.split(r'[,\s]+', custom_exclude.strip()) if word.strip()]
                        exclusion_reasons.append(f"mots personnalisés: {', '.join(custom_words)}")
                    
                    if exclusion_reasons:
                        st.info(f"📊 {len(filtered_df)} suggestions affichées ({excluded_count} filtrées par exclusion des {' et '.join(exclusion_reasons)})")
            else:
                filtered_df = suggestions_df
        else:
            filtered_df = suggestions_df
        
        filter_active = (
            len(filtered_df) != len(suggestions_df)
            or bool(custom_exclude.strip())
            or (all_tags and len(selected_tags) != len(all_tags))
        )

        if filter_active:
            filtered_records = [
                {
                    key: (
                        None
                        if isinstance((cleaned_value := (value.item() if hasattr(value, "item") else value)), float) and math.isnan(cleaned_value)
                        else cleaned_value
                    )
                    for key, value in row.items()
                }
                for row in filtered_df.to_dict(orient='records')
            ]
            st.session_state['filtered_suggestions_records'] = filtered_records
            st.session_state['filtered_tags_state'] = {
                'selected_tags': selected_tags,
                'all_tags': all_tags,
                'custom_exclude_words': custom_exclude
            }
            if st.session_state.get('analysis_results'):
                st.session_state.analysis_results['filtered_suggestions'] = filtered_records
        else:
            st.session_state.pop('filtered_suggestions_records', None)
            st.session_state.pop('filtered_tags_state', None)
            if st.session_state.get('analysis_results'):
                st.session_state.analysis_results.pop('filtered_suggestions', None)

        # Statistiques par niveau sur les données filtrées
        level_stats = filtered_df['Niveau'].value_counts().sort_index()
        
        # Calculer le total
        total_suggestions = len(filtered_df)
        
        # Créer les colonnes pour toutes les métriques sur la même ligne
        if len(level_stats) > 0:
            cols = st.columns(len(level_stats) + 1)
            
            # Afficher les statistiques par niveau
            for i, (level, count) in enumerate(level_stats.items()):
                with cols[i]:
                    st.metric(f"Niveau {level}", count)
            
            # Afficher le total
            with cols[-1]:
                st.metric("**Total**", total_suggestions)
        
        # Boutons d'export sur la même ligne
        col1, col2 = st.columns([1, 1])
        
        with col1:
            export_clicked = st.button("📥 Exporter les Suggestions", type="primary")
        
        with col2:
            if 'suggestions_excel_data' in st.session_state:
                st.download_button(
                    label="📥 Télécharger Excel",
                    data=st.session_state['suggestions_excel_data'],
                    file_name=f"suggestions_google_{self.metadata.get('timestamp', 'export').replace(':', '-').replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
        if export_clicked:
            from utils.ui_components import create_excel_file
            # Réorganiser les colonnes pour l'export Excel dans l'ordre demandé
            export_columns = ['Mot-clé', 'Parent', 'Niveau', 'Suggestion Google']
            available_export_columns = [col for col in export_columns if col in filtered_df.columns]
            export_df = filtered_df[available_export_columns] if available_export_columns else filtered_df
            
            excel_data = create_excel_file(export_df)
            st.session_state['suggestions_excel_data'] = excel_data
            st.rerun()
        
        # Tableau des suggestions filtrées
        # Réorganiser les colonnes dans l'ordre demandé : Mot-clé / Parent / Niveau / Suggestion Google
        desired_columns = ['Mot-clé', 'Parent', 'Niveau', 'Suggestion Google']
        available_columns = [col for col in desired_columns if col in filtered_df.columns]
        if available_columns:
            display_df = filtered_df[available_columns]
        else:
            display_df = filtered_df
        
        st.dataframe(display_df, width='stretch')
    
    def render_keywords_with_volume(self):
        """Afficher les mots-clés avec volume de recherche"""
        enriched_keywords = self.results.get('enriched_keywords', [])
        keywords_with_volume = [k for k in enriched_keywords if k.get('search_volume', 0) > 0]
        
        if not keywords_with_volume:
            return
        
        st.markdown("### 🎯 Mots-clés avec volume de recherche")
        st.info("📊 Ces mots-clés ont été utilisés pour générer les questions conversationnelles")
        
        # Créer le DataFrame
        keywords_df = pd.DataFrame(keywords_with_volume)
        display_cols = ['keyword', 'search_volume', 'cpc', 'competition_level', 'origine']
        available_cols = [col for col in display_cols if col in keywords_df.columns]
        
        display_keywords = keywords_df[available_cols].copy()
        display_keywords.columns = ['Mot-clé', 'Volume/mois', 'CPC', 'Concurrence', 'Origine']
        
        # Formater les colonnes
        display_keywords['Volume/mois'] = display_keywords['Volume/mois'].fillna(0).astype(int)
        display_keywords['CPC'] = display_keywords['CPC'].fillna(0).round(2)
        
        # Trier par volume décroissant
        display_keywords = display_keywords.sort_values('Volume/mois', ascending=False)
        
        st.dataframe(display_keywords)
        
        # Statistiques
        self._render_keywords_statistics(display_keywords)
        
        # Analyse des origines
        self._render_origin_analysis(display_keywords)
    
    def _render_keywords_statistics(self, df: pd.DataFrame):
        """Afficher les statistiques des mots-clés"""
        col1, col2, col3, col4 = st.columns(4)
        
        total_volume = df['Volume/mois'].sum()
        avg_volume = df['Volume/mois'].mean()
        max_volume = df['Volume/mois'].max()
        avg_cpc = df['CPC'].mean()
        
        with col1:
            st.metric("Volume total", f"{total_volume:,}")
        with col2:
            st.metric("Volume moyen", f"{avg_volume:.0f}")
        with col3:
            st.metric("Volume max", f"{max_volume:,}")
        with col4:
            st.metric("CPC moyen", f"${avg_cpc:.2f}")
    
    def _render_origin_analysis(self, df: pd.DataFrame):
        """Afficher l'analyse des origines"""
        st.markdown("**Répartition par origine:**")
        
        origin_stats = {
            '🎯 Mot-clé principal': 0,
            '🔍 Suggestion Google': 0,
            '💰 Suggestion Ads': 0,
            'Multiples origines': 0
        }
        
        for origin in df['Origine']:
            if '+' in origin:
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
    
    def render_conversational_questions(self):
        """Afficher les questions conversationnelles"""
        if not self.results.get('final_consolidated_data'):
            return
        
        st.markdown("### 📋 Questions conversationnelles")
        st.info("💡 Ces questions sont générées uniquement à partir des mots-clés ayant un volume de recherche")
        
        df = pd.DataFrame(self.results['final_consolidated_data'])
        
        # Essayer d'associer avec les données enrichies
        if self.results.get('enriched_keywords'):
            enriched_df = pd.DataFrame(self.results['enriched_keywords'])
            if not enriched_df.empty and 'keyword' in enriched_df.columns:
                merged_df = df.merge(
                    enriched_df[['keyword', 'search_volume', 'cpc', 'origine']],
                    left_on='Suggestion Google',
                    right_on='keyword',
                    how='left'
                )
                
                display_cols = ['Question Conversationnelle', 'Suggestion Google', 'Thème', 'Intention', 'Score_Importance', 'search_volume', 'cpc', 'origine']
                available_cols = [col for col in display_cols if col in merged_df.columns]
                
                display_df = merged_df[available_cols].copy()
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
                
                st.dataframe(display_df)
            else:
                self._render_basic_questions_table(df)
        else:
            self._render_basic_questions_table(df)
    
    def _render_basic_questions_table(self, df: pd.DataFrame):
        """Afficher le tableau de questions basique"""
        display_cols = ['Question Conversationnelle', 'Suggestion Google', 'Thème', 'Intention', 'Score_Importance']
        available_cols = [col for col in display_cols if col in df.columns]
        st.dataframe(df[available_cols])
    
    def render_detailed_analysis(self):
        """Afficher l'analyse détaillée en expandeur"""
        if not self.results.get('enriched_keywords'):
            return
        
        with st.expander("📈 Analyse détaillée des mots-clés et volumes"):
            enriched_keywords = self.results['enriched_keywords']
            
            # Séparer par type d'origine
            google_suggest_keywords = [k for k in enriched_keywords if '🔍 Suggestion Google' in k.get('origine', '') and '💰 Suggestion Ads' not in k.get('origine', '')]
            google_ads_keywords = [k for k in enriched_keywords if '💰 Suggestion Ads' in k.get('origine', '') and '🔍 Suggestion Google' not in k.get('origine', '')]
            main_keywords = [k for k in enriched_keywords if '🎯 Mot-clé principal' in k.get('origine', '')]
            mixed_keywords = [k for k in enriched_keywords if '+' in k.get('origine', '')]
            
            tab1, tab2, tab3, tab4 = st.tabs(["🎯 Principaux", "🔍 Google Suggest", "💰 Google Ads", "🔗 Multiples origines"])
            
            with tab1:
                self._render_keywords_tab(main_keywords, "mots-clés principaux")
            
            with tab2:
                self._render_keywords_tab(google_suggest_keywords, "suggestions Google")
            
            with tab3:
                self._render_keywords_tab(google_ads_keywords, "suggestions Google Ads")
            
            with tab4:
                self._render_mixed_keywords_tab(mixed_keywords)
    
    def _render_keywords_tab(self, keywords: List[Dict[str, Any]], title: str):
        """Afficher un onglet de mots-clés"""
        if keywords:
            st.markdown(f"**{len(keywords)} {title}**")
            df = pd.DataFrame(keywords)
            display_df = df[['keyword', 'search_volume', 'cpc', 'competition_level']].copy()
            display_df.columns = ['Mot-clé', 'Volume', 'CPC', 'Concurrence']
            display_df['Volume'] = display_df['Volume'].fillna(0).astype(int)
            display_df['CPC'] = display_df['CPC'].fillna(0).round(2)
            st.dataframe(display_df.sort_values('Volume', ascending=False))
        else:
            st.info(f"Aucun {title.split()[0]} avec volume")
    
    def _render_mixed_keywords_tab(self, mixed_keywords: List[Dict[str, Any]]):
        """Afficher l'onglet des mots-clés avec multiples origines"""
        if mixed_keywords:
            st.markdown(f"**{len(mixed_keywords)} mots-clés avec multiples origines**")
            st.info("Ces mots-clés apparaissent dans plusieurs sources (mot-clé principal + suggestions)")
            df = pd.DataFrame(mixed_keywords)
            display_df = df[['keyword', 'search_volume', 'cpc', 'competition_level', 'origine']].copy()
            display_df.columns = ['Mot-clé', 'Volume', 'CPC', 'Concurrence', 'Origines']
            display_df['Volume'] = display_df['Volume'].fillna(0).astype(int)
            display_df['CPC'] = display_df['CPC'].fillna(0).round(2)
            st.dataframe(display_df.sort_values('Volume', ascending=False))
        else:
            st.info("Aucun mot-clé avec multiples origines")
            return
        
        with st.expander("📈 Analyse détaillée des mots-clés et volumes"):
            enriched_keywords = self.results['enriched_keywords']
            
            # Séparer par type d'origine
            google_suggest_keywords = [k for k in enriched_keywords if '🔍 Suggestion Google' in k.get('origine', '') and '💰 Suggestion Ads' not in k.get('origine', '')]
            google_ads_keywords = [k for k in enriched_keywords if '💰 Suggestion Ads' in k.get('origine', '') and '🔍 Suggestion Google' not in k.get('origine', '')]
            main_keywords = [k for k in enriched_keywords if '🎯 Mot-clé principal' in k.get('origine', '')]
            mixed_keywords = [k for k in enriched_keywords if '+' in k.get('origine', '')]
            
            tab1, tab2, tab3, tab4 = st.tabs(["🎯 Principaux", "🔍 Google Suggest", "💰 Google Ads", "🔗 Multiples origines"])
            
            with tab1:
                self._render_keywords_tab(main_keywords, "mots-clés principaux")
            
            with tab2:
                self._render_keywords_tab(google_suggest_keywords, "suggestions Google")
            
            with tab3:
                self._render_keywords_tab(google_ads_keywords, "suggestions Google Ads")
            
            with tab4:
                self._render_mixed_keywords_tab(mixed_keywords)
    
    def _render_keywords_tab(self, keywords: List[Dict[str, Any]], title: str):
        """Afficher un onglet de mots-clés"""
        if keywords:
            st.markdown(f"**{len(keywords)} {title}**")
            df = pd.DataFrame(keywords)
            display_df = df[['keyword', 'search_volume', 'cpc', 'competition_level']].copy()
            display_df.columns = ['Mot-clé', 'Volume', 'CPC', 'Concurrence']
            display_df['Volume'] = display_df['Volume'].fillna(0).astype(int)
            display_df['CPC'] = display_df['CPC'].fillna(0).round(2)
            st.dataframe(display_df.sort_values('Volume', ascending=False))
        else:
            st.info(f"Aucun {title.split()[0]} avec volume")
    
    def _render_mixed_keywords_tab(self, mixed_keywords: List[Dict[str, Any]]):
        """Afficher l'onglet des mots-clés avec multiples origines"""
        if mixed_keywords:
            st.markdown(f"**{len(mixed_keywords)} mots-clés avec multiples origines**")
            st.info("Ces mots-clés apparaissent dans plusieurs sources (mot-clé principal + suggestions)")
            df = pd.DataFrame(mixed_keywords)
            display_df = df[['keyword', 'search_volume', 'cpc', 'competition_level', 'origine']].copy()
            display_df.columns = ['Mot-clé', 'Volume', 'CPC', 'Concurrence', 'Origines']
            display_df['Volume'] = display_df['Volume'].fillna(0).astype(int)
            display_df['CPC'] = display_df['CPC'].fillna(0).round(2)
            st.dataframe(display_df.sort_values('Volume', ascending=False))
        else:
            st.info("Aucun mot-clé avec multiples origines")
