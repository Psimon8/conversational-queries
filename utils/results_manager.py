import streamlit as st
import pandas as pd
from typing import Dict, Any, List
from .ui_components import render_metrics

class ResultsManager:
    """Gestionnaire pour l'affichage des résultats"""
    
    def __init__(self, results: Dict[str, Any], metadata: Dict[str, Any]):
        self.results = results
        self.metadata = metadata
    
    def render_analysis_summary(self):
        """Afficher le résumé de l'analyse"""
        st.markdown("## 📊 Résumé de l'analyse")
        
        # Métriques principales
        metrics = self._calculate_main_metrics()
        render_metrics(metrics)
        
        # Informations contextuelles
        self._render_context_info()
    
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
    
    def render_suggestions_results(self):
        """Afficher les résultats des suggestions"""
        if not self.results.get('all_suggestions'):
            return
        
        st.markdown("### 📝 Suggestions Google")
        
        suggestions_df = pd.DataFrame(self.results['all_suggestions'])
        
        # Statistiques par niveau
        level_stats = suggestions_df['Niveau'].value_counts().sort_index()
        
        # Calculer le total
        total_suggestions = len(suggestions_df)
        
        # Créer les colonnes pour les métriques (niveaux + total)
        cols = st.columns(len(level_stats) + 1)
        
        # Afficher les statistiques par niveau
        for i, (level, count) in enumerate(level_stats.items()):
            with cols[i]:
                st.metric(f"Niveau {level}", count)
        
        # Afficher le total
        with cols[-1]:
            st.metric("**Total**", total_suggestions)
        
        # Bouton d'export Excel
        col_export, _ = st.columns([1, 4])
        with col_export:
            if st.button("📊 Exporter Excel", type="secondary"):
                from utils.ui_components import create_excel_file
                excel_data = create_excel_file(suggestions_df)
                st.download_button(
                    label="📥 Télécharger Excel",
                    data=excel_data,
                    file_name=f"suggestions_google_{self.metadata.get('timestamp', 'export').replace(':', '-').replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
        # Tableau des suggestions
        st.dataframe(suggestions_df, use_container_width=True)
    
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
        
        st.dataframe(display_keywords, use_container_width=True)
        
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
                
                st.dataframe(display_df, use_container_width=True)
            else:
                self._render_basic_questions_table(df)
        else:
            self._render_basic_questions_table(df)
    
    def _render_basic_questions_table(self, df: pd.DataFrame):
        """Afficher le tableau de questions basique"""
        display_cols = ['Question Conversationnelle', 'Suggestion Google', 'Thème', 'Intention', 'Score_Importance']
        available_cols = [col for col in display_cols if col in df.columns]
        st.dataframe(df[available_cols], use_container_width=True)
    
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
            st.dataframe(display_df.sort_values('Volume', ascending=False), use_container_width=True)
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
            st.dataframe(display_df.sort_values('Volume', ascending=False), use_container_width=True)
        else:
            st.info("Aucun mot-clé avec multiples origines")
