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
    """Affichage de l'en-tête principal avec design amélioré"""
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 2rem; border-radius: 15px; margin-bottom: 2rem; color: white;">
        <h1 style="color: white; margin: 0; font-size: 2.5rem;">
            🔍 Optimiseur de Requêtes Conversationnelles SEO
        </h1>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.2rem; opacity: 0.9;">
            Analyse basée sur les suggestions Google pour l'optimisation SEO avancée
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Métriques rapides
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("**Statut**", "✅ Prêt", help="Application opérationnelle")
    with col2:
        st.metric("**Version**", "2.0", help="Version améliorée avec Excel")
    with col3:
        st.metric("**Langues**", "5", help="Français, Anglais, Espagnol, Allemand, Italien")

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
    """Affichage des métriques sous forme de colonnes avec design amélioré"""
    if not metrics:
        return
    
    cols = st.columns(len(metrics))
    for i, (label, value) in enumerate(metrics.items()):
        with cols[i]:
            # Conteneur stylisé pour chaque métrique
            st.markdown(f"""
            <div style="background: white; border: 2px solid #e1e5e9; border-radius: 10px; 
                        padding: 1rem; margin: 0.5rem 0; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <div style="font-size: 0.9rem; color: #666; margin-bottom: 0.5rem;">{label}</div>
                <div style="font-size: 1.8rem; font-weight: bold; color: #2c3e50;">{value:,}</div>
            </div>
            """, unsafe_allow_html=True)

def render_status_indicator(label: str, status: str, details: str = ""):
    """Afficher un indicateur de statut avec icône"""
    status_config = {
        "ready": {"icon": "✅", "color": "green", "text": "Prêt"},
        "warning": {"icon": "⚠️", "color": "orange", "text": "Attention"},
        "error": {"icon": "❌", "color": "red", "text": "Erreur"},
        "loading": {"icon": "⏳", "color": "blue", "text": "Chargement"},
        "success": {"icon": "✅", "color": "green", "text": "Succès"}
    }
    
    config = status_config.get(status, {"icon": "❓", "color": "gray", "text": "Inconnu"})
    
    st.markdown(f"""
    <div style="display: flex; align-items: center; margin: 0.5rem 0; padding: 0.5rem; 
                border-radius: 5px; background: rgba({config['color']}, 0.1); border-left: 4px solid {config['color']};">
        <span style="font-size: 1.2rem; margin-right: 0.5rem;">{config['icon']}</span>
        <div>
            <div style="font-weight: bold; color: {config['color']};">{label}</div>
            {f'<div style="font-size: 0.9rem; color: #666;">{details}</div>' if details else ''}
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_progress_status(current_step: int, total_steps: int, message: str):
    """Affichage du statut de progression avec design amélioré"""
    progress = current_step / total_steps if total_steps > 0 else 0
    
    # Barre de progression stylisée
    st.markdown(f"""
    <div style="margin: 1rem 0;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
            <span style="font-weight: bold;">Étape {current_step}/{total_steps}</span>
            <span>{int(progress * 100)}%</span>
        </div>
        <div style="width: 100%; height: 8px; background: #e1e5e9; border-radius: 4px; overflow: hidden;">
            <div style="width: {progress * 100}%; height: 100%; background: linear-gradient(90deg, #667eea, #764ba2); 
                        border-radius: 4px; transition: width 0.3s ease;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Message de statut
    st.markdown(f"""
    <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin: 1rem 0; border-left: 4px solid #667eea;">
        <div style="display: flex; align-items: center;">
            <span style="font-size: 1.2rem; margin-right: 0.5rem;">⏳</span>
            <span style="font-weight: 500;">{message}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
