import streamlit as st
import pandas as pd
import json
from io import BytesIO
from typing import Dict, Any, List

def setup_page_config():
    """Configuration de la page Streamlit"""
    st.set_page_config(
        page_title="SEO Conversational Queries Optimizer",
        page_icon="🔍",
        layout="wide"
    )

def render_header():
    """Affichage de l'en-tête principal"""
    st.title("🔍 Optimiseur de Requêtes Conversationnelles SEO")
    st.subheader("Analyse basée sur les suggestions Google pour l'optimisation SEO")

def render_social_links():
    """Affichage des liens sociaux dans la sidebar"""
    st.sidebar.markdown(
        """
        <div style="position: fixed; bottom: 10px; left: 20px;">
            <a href="https://github.com/Psimon8" target="_blank" style="text-decoration: none;">
                <img src="https://github.githubassets.com/assets/pinned-octocat-093da3e6fa40.svg" 
                     alt="GitHub Simon le Coz" style="width:20px; vertical-align: middle; margin-right: 5px;">
            </a>    
            <a href="https://www.linkedin.com/in/simon-le-coz/" target="_blank" style="text-decoration: none;">
                <img src="https://static.licdn.com/aero-v1/sc/h/8s162nmbcnfkg7a0k8nq9wwqo" 
                     alt="LinkedIn Simon Le Coz" style="width:20px; vertical-align: middle; margin-right: 5px;">
            </a>
            <a href="https://twitter.com/lekoz_simon" target="_blank" style="text-decoration: none;">
                <img src="https://abs.twimg.com/favicons/twitter.3.ico" 
                     alt="Twitter Simon Le Coz" style="width:20px; vertical-align: middle; margin-right: 5px;">
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )

def create_excel_file(df: pd.DataFrame) -> BytesIO:
    """Crée un fichier Excel avec formatage professionnel"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Questions_Conversationnelles')
        
        workbook = writer.book
        worksheet = writer.sheets['Questions_Conversationnelles']
        
        # Ajuster la largeur des colonnes
        column_widths = {
            'A': 60,  # Questions
            'B': 50,  # Suggestions Google
            'C': 25,  # Mots-clés
            'D': 25,  # Thème
            'E': 20,  # Intention
            'F': 15,  # Importance
            'G': 15,  # Volume
            'H': 12,  # CPC
            'I': 15   # Origine
        }
        
        for col, width in column_widths.items():
            if col <= chr(ord('A') + len(df.columns) - 1):
                worksheet.column_dimensions[col].width = width
        
        # Formatage de l'en-tête
        from openpyxl.styles import Font, PatternFill, Alignment
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        center_alignment = Alignment(horizontal="center", vertical="center")
        
        for cell in worksheet[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_alignment
        
        # Formatage conditionnel pour les volumes
        if 'G' <= chr(ord('A') + len(df.columns) - 1):  # Si colonne Volume existe
            from openpyxl.formatting.rule import DataBarRule
            from openpyxl.styles import Color
            
            # Barre de données pour les volumes
            rule = DataBarRule(start_type='min', start_value=0, end_type='max', end_value=None,
                             color=Color(rgb='FF366092'))
            worksheet.conditional_formatting.add(f'G2:G{len(df)+1}', rule)
    
    output.seek(0)
    return output

def render_metrics(metrics: Dict[str, Any]):
    """Affichage des métriques sous forme de colonnes"""
    cols = st.columns(len(metrics))
    for i, (label, value) in enumerate(metrics.items()):
        with cols[i]:
            if isinstance(value, (int, float)):
                if isinstance(value, float):
                    st.metric(label, f"{value:.1f}")
                else:
                    st.metric(label, f"{value:,}")
            else:
                st.metric(label, str(value))

def render_progress_status(current_step: int, total_steps: int, message: str):
    """Affichage du statut de progression"""
    progress = current_step / total_steps
    progress_bar = st.progress(progress)
    status_text = st.empty()
    status_text.text(f"⏳ Étape {current_step}/{total_steps}: {message}")
    return progress_bar, status_text
