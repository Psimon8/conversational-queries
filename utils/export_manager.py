import streamlit as st
import pandas as pd
import json
from typing import Dict, Any
from .ui_components import create_excel_file

class ExportManager:
    """Gestionnaire des exports de données"""
    
    def __init__(self, results: Dict[str, Any], metadata: Dict[str, Any]):
        self.results = results
        self.metadata = metadata
    
    def render_export_section(self):
        """Affichage de la section export dans la sidebar"""
        if not self.results:
            return
        
        st.sidebar.header("📤 Exports")
        
        # Export des questions générées
        if (self.metadata.get('generate_questions') and 
            self.results.get('stage') == 'questions_generated' and 
            self.results.get('final_consolidated_data')):
            
            self._render_questions_export()
        
        # Export des suggestions (toujours disponible)
        if self.results.get('all_suggestions'):
            self._render_suggestions_export()
        
        # Export JSON complet
        self._render_json_export()
        
        # Affichage du statut
        self._render_status()
    
    def _render_questions_export(self):
        """Export des questions conversationnelles"""
        questions_df = pd.DataFrame(self.results['final_consolidated_data'])
        
        # Préparer les colonnes d'export selon les données disponibles
        base_columns = ['Question Conversationnelle', 'Suggestion Google', 'Mot-clé', 'Thème', 'Intention', 'Score_Importance']
        export_columns = []
        column_names = []
        
        for col in base_columns:
            if col in questions_df.columns:
                export_columns.append(col)
                # Renommer pour l'export
                if col == 'Question Conversationnelle':
                    column_names.append('Questions Conversationnelles')
                elif col == 'Score_Importance':
                    column_names.append('Importance')
                else:
                    column_names.append(col)
        
        # Ajouter les données DataForSEO si disponibles
        if 'Volume_Recherche' in questions_df.columns:
            export_columns.append('Volume_Recherche')
            column_names.append('Volume')
        
        if 'CPC' in questions_df.columns:
            export_columns.append('CPC')
            column_names.append('CPC')
        
        excel_display = questions_df[export_columns].copy()
        excel_display.columns = column_names
        
        excel_file = create_excel_file(excel_display)
        st.sidebar.download_button(
            label="📊 Questions (Excel)",
            data=excel_file,
            file_name="questions_conversationnelles.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_questions_excel",
            width='stretch'
        )
    
    def _render_suggestions_export(self):
        """Export des suggestions Google"""
        suggestions_df = pd.DataFrame(self.results['all_suggestions'])
        
        # Enrichir avec données DataForSEO si disponibles (version dédupliquée)
        if 'enriched_keywords' in self.results:
            enriched_df = pd.DataFrame(self.results['enriched_keywords'])
            if not enriched_df.empty and 'keyword' in enriched_df.columns:
                # Merger les données
                merged_df = suggestions_df.merge(
                    enriched_df[['keyword', 'search_volume', 'cpc', 'competition_level', 'origine']],
                    left_on='Suggestion Google',
                    right_on='keyword',
                    how='left'
                )
                
                export_cols = ['Mot-clé', 'Suggestion Google', 'Niveau', 'Parent', 'search_volume', 'cpc', 'competition_level', 'origine']
                export_names = ['Mot-clé', 'Suggestion Google', 'Niveau', 'Parent', 'Volume', 'CPC', 'Concurrence', 'Origine']
                
                # Garder seulement les colonnes existantes
                existing_cols = [col for col in export_cols if col in merged_df.columns]
                existing_names = [export_names[export_cols.index(col)] for col in existing_cols]
                
                suggestions_display = merged_df[existing_cols].copy()
                suggestions_display.columns = existing_names
                
                # Formater les colonnes pour l'export
                if 'Volume' in suggestions_display.columns:
                    suggestions_display['Volume'] = suggestions_display['Volume'].fillna(0).astype(int)
                if 'CPC' in suggestions_display.columns:
                    suggestions_display['CPC'] = suggestions_display['CPC'].fillna(0).round(2)
            else:
                suggestions_display = suggestions_df[['Mot-clé', 'Suggestion Google', 'Niveau', 'Parent']].copy()
        else:
            suggestions_display = suggestions_df[['Mot-clé', 'Suggestion Google', 'Niveau', 'Parent']].copy()
        
        suggestions_excel = create_excel_file(suggestions_display)
        st.sidebar.download_button(
            label="🔍 Suggestions (Excel)",
            data=suggestions_excel,
            file_name="suggestions_google.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_suggestions_excel",
            width='stretch'
        )
        
        # Export séparé pour les mots-clés dédupliqués avec volumes
        if self.results.get('enriched_keywords'):
            keywords_with_volume = [k for k in self.results['enriched_keywords'] if k.get('search_volume', 0) > 0]
            if keywords_with_volume:
                volume_df = pd.DataFrame(keywords_with_volume)
                volume_display = volume_df[['keyword', 'search_volume', 'cpc', 'competition_level', 'origine']].copy()
                volume_display.columns = ['Mot-clé', 'Volume', 'CPC', 'Concurrence', 'Origine']
                
                # Formater les colonnes
                volume_display['Volume'] = volume_display['Volume'].fillna(0).astype(int)
                volume_display['CPC'] = volume_display['CPC'].fillna(0).round(2)
                
                volume_excel = create_excel_file(volume_display)
                st.sidebar.download_button(
                    label="📊 Mots-clés avec volume (Excel)",
                    data=volume_excel,
                    file_name="mots_cles_volumes.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_volume_excel",
                    width='stretch'
                )

    def _render_json_export(self):
        """Export JSON complet"""
        export_data = {
            "metadata": {
                **self.metadata,
                "total_suggestions": len(self.results.get('all_suggestions', [])),
                "level_distribution": self.results.get('level_counts', {}),
                "stage": self.results.get('stage', 'unknown')
            },
            "suggestions": self.results.get('all_suggestions', []),
            "enriched_keywords": self.results.get('enriched_keywords', []),
            "themes_analysis": self.results.get('themes_analysis', {}),
            "questions": self.results.get('final_consolidated_data', []) if self.metadata.get('generate_questions') else []
        }
        
        # Ajouter les données DataForSEO si disponibles
        if 'dataforseo_data' in self.results:
            export_data["dataforseo_data"] = self.results['dataforseo_data']
        
        json_data = json.dumps(export_data, ensure_ascii=False, indent=2)
        st.sidebar.download_button(
            label="📋 Données complètes (JSON)",
            data=json_data,
            file_name="analyse_complete.json",
            mime="application/json",
            key="download_json",
            width='stretch'
        )
    
    def _render_status(self):
        """Affichage du statut actuel"""
        stage = self.results.get('stage', 'unknown')
        generate_questions = self.metadata.get('generate_questions', False)
        
        if stage == 'themes_analyzed' and generate_questions:
            st.sidebar.info("📋 Sélectionnez vos thèmes")
        elif stage == 'questions_generated':
            st.sidebar.success("✅ Questions générées")
        elif self.results.get('all_suggestions'):
            st.sidebar.success("✅ Suggestions collectées")
        else:
            st.sidebar.info("⏳ En attente d'analyse")
        if stage == 'themes_analyzed' and generate_questions:
            st.sidebar.info("📋 Sélectionnez vos thèmes")
        elif stage == 'questions_generated':
            st.sidebar.success("✅ Questions générées")
        elif self.results.get('all_suggestions'):
            st.sidebar.success("✅ Suggestions collectées")
        else:
            st.sidebar.info("⏳ En attente d'analyse")
