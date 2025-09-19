import streamlit as st
import pandas as pd
import json
import time
from typing import Dict, Any, List, Optional

class ExportManager:
    """Gestionnaire amélioré pour les exports"""
    
    def __init__(self, results: Dict[str, Any], metadata: Dict[str, Any]):
        self.results = results
        self.metadata = metadata
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    def render_export_section(self):
        """Afficher la section d'export dans la sidebar"""
        if not self.results:
            return
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("## 📥 Exports")
        
        # Export des suggestions
        if self.results.get('all_suggestions'):
            self._render_suggestions_export()
        
        # Export des mots-clés avec volume
        if self.results.get('enriched_keywords'):
            self._render_keywords_export()
        
        # Export des questions conversationnelles
        if self.results.get('final_consolidated_data'):
            self._render_questions_export()
        
        # Export complet (JSON)
        self._render_complete_export()
    
    def _render_suggestions_export(self):
        """Export des suggestions"""
        suggestions_df = pd.DataFrame(self.results['all_suggestions'])
        
        # CSV
        csv_suggestions = suggestions_df.to_csv(index=False)
        st.sidebar.download_button(
            label="📝 Suggestions (CSV)",
            data=csv_suggestions,
            file_name=f"suggestions_{self.timestamp}.csv",
            mime="text/csv",
            help="Toutes les suggestions Google collectées"
        )
        
        # TXT (liste simple)
        txt_suggestions = "\n".join(suggestions_df['Suggestion Google'].tolist())
        st.sidebar.download_button(
            label="📄 Suggestions (TXT)",
            data=txt_suggestions,
            file_name=f"suggestions_{self.timestamp}.txt",
            mime="text/plain",
            help="Liste simple des suggestions"
        )
    
    def _render_keywords_export(self):
        """Export des mots-clés avec volume"""
        enriched_keywords = self.results['enriched_keywords']
        keywords_df = pd.DataFrame(enriched_keywords)
        
        # Préparer les colonnes pour l'export
        export_cols = ['keyword', 'search_volume', 'cpc', 'competition', 'competition_level', 'source', 'origine']
        available_cols = [col for col in export_cols if col in keywords_df.columns]
        export_df = keywords_df[available_cols].copy()
        
        # Renommer les colonnes
        column_mapping = {
            'keyword': 'Mot-clé',
            'search_volume': 'Volume/mois',
            'cpc': 'CPC',
            'competition': 'Concurrence',
            'competition_level': 'Niveau_Concurrence',
            'source': 'Source',
            'origine': 'Origine'
        }
        export_df = export_df.rename(columns=column_mapping)
        
        # CSV des mots-clés enrichis
        csv_keywords = export_df.to_csv(index=False)
        st.sidebar.download_button(
            label="📊 Mots-clés + Volumes (CSV)",
            data=csv_keywords,
            file_name=f"keywords_volumes_{self.timestamp}.csv",
            mime="text/csv",
            help="Mots-clés avec volumes de recherche et données DataForSEO"
        )
        
        # Export des mots-clés avec volume uniquement
        keywords_with_volume = export_df[export_df['Volume/mois'] > 0].copy()
        if not keywords_with_volume.empty:
            csv_volume_only = keywords_with_volume.to_csv(index=False)
            st.sidebar.download_button(
                label="🎯 Mots-clés avec volume (CSV)",
                data=csv_volume_only,
                file_name=f"keywords_with_volume_{self.timestamp}.csv",
                mime="text/csv",
                help="Uniquement les mots-clés avec volume de recherche"
            )
    
    def _render_questions_export(self):
        """Export des questions conversationnelles"""
        questions_df = pd.DataFrame(self.results['final_consolidated_data'])
        
        # CSV des questions
        csv_questions = questions_df.to_csv(index=False)
        st.sidebar.download_button(
            label="✨ Questions conversationnelles (CSV)",
            data=csv_questions,
            file_name=f"questions_{self.timestamp}.csv",
            mime="text/csv",
            help="Questions conversationnelles générées"
        )
        
        # Export optimisé pour SEO (questions + volumes)
        if self.results.get('enriched_keywords'):
            seo_export = self._create_seo_optimized_export(questions_df)
            if seo_export is not None:
                csv_seo = seo_export.to_csv(index=False)
                st.sidebar.download_button(
                    label="🚀 Export SEO optimisé (CSV)",
                    data=csv_seo,
                    file_name=f"seo_questions_{self.timestamp}.csv",
                    mime="text/csv",
                    help="Questions avec données de volume pour optimisation SEO"
                )
    
    def _create_seo_optimized_export(self, questions_df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Créer un export optimisé pour le SEO"""
        try:
            enriched_df = pd.DataFrame(self.results['enriched_keywords'])
            if enriched_df.empty or 'keyword' not in enriched_df.columns:
                return None
            
            # Merger avec les données de volume
            merged_df = questions_df.merge(
                enriched_df[['keyword', 'search_volume', 'cpc', 'competition_level', 'origine']],
                left_on='Suggestion Google',
                right_on='keyword',
                how='left'
            )
            
            # Sélectionner et renommer les colonnes pour le SEO
            seo_cols = {
                'Question Conversationnelle': 'Question_SEO',
                'Suggestion Google': 'Mot_cle_cible',
                'Thème': 'Theme',
                'Intention': 'Intention_recherche',
                'Score_Importance': 'Score_importance',
                'search_volume': 'Volume_mensuel',
                'cpc': 'CPC_estime',
                'competition_level': 'Niveau_concurrence',
                'origine': 'Source_mot_cle'
            }
            
            available_seo_cols = {k: v for k, v in seo_cols.items() if k in merged_df.columns}
            seo_export = merged_df[list(available_seo_cols.keys())].copy()
            seo_export = seo_export.rename(columns=available_seo_cols)
            
            # Formater les données
            if 'Volume_mensuel' in seo_export.columns:
                seo_export['Volume_mensuel'] = seo_export['Volume_mensuel'].fillna(0).astype(int)
            if 'CPC_estime' in seo_export.columns:
                seo_export['CPC_estime'] = seo_export['CPC_estime'].fillna(0).round(2)
            
            # Trier par volume décroissant puis par score d'importance
            sort_cols = []
            if 'Volume_mensuel' in seo_export.columns:
                sort_cols.append('Volume_mensuel')
            if 'Score_importance' in seo_export.columns:
                sort_cols.append('Score_importance')
            
            if sort_cols:
                seo_export = seo_export.sort_values(sort_cols, ascending=False)
            
            return seo_export
            
        except Exception as e:
            st.sidebar.error(f"Erreur export SEO: {str(e)}")
            return None
    
    def _render_complete_export(self):
        """Export complet au format JSON"""
        complete_data = {
            'metadata': self.metadata,
            'results': {
                'suggestions': self.results.get('all_suggestions', []),
                'enriched_keywords': self.results.get('enriched_keywords', []),
                'questions': self.results.get('final_consolidated_data', []),
                'themes_analysis': self.results.get('themes_analysis', {}),
                'selected_themes': self.results.get('selected_themes_by_keyword', {})
            },
            'export_timestamp': self.timestamp
        }
        
        json_data = json.dumps(complete_data, ensure_ascii=False, indent=2)
        st.sidebar.download_button(
            label="📦 Export complet (JSON)",
            data=json_data,
            file_name=f"analysis_complete_{self.timestamp}.json",
            mime="application/json",
            help="Toutes les données de l'analyse au format JSON"
        )
