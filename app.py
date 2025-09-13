import streamlit as st
from openai import OpenAI
import pandas as pd
import json
import time
from collections import Counter
import re
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from io import BytesIO

# Configuration de la page Streamlit
st.set_page_config(
    page_title="SEO Conversational Queries Optimizer",
    page_icon="🔍",
    layout="wide"
)

# Titre principal
st.title("🔍 Optimiseur de Requêtes Conversationnelles SEO")
st.subheader("Analyse basée sur les suggestions Google pour l'optimisation SEO")

# Configuration de l'API OpenAI
st.sidebar.header("⚙️ Configuration")
api_key = st.sidebar.text_input("Clé API OpenAI", type="password", help="Votre clé API OpenAI pour GPT-4o mini")

if api_key:
    client = OpenAI(api_key=api_key)
    st.sidebar.success("✅ API configurée")
else:
    st.sidebar.warning("⚠️ Veuillez entrer votre clé API OpenAI")
    client = None

# Fonctions utilitaires communes
def call_gpt4o_mini(prompt, max_retries=3):
    """Appel à l'API GPT-4o mini avec gestion d'erreurs"""
    if not client:
        st.error("❌ Clé API manquante")
        return None
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un expert SEO spécialisé dans l'analyse des requêtes conversationnelles et l'optimisation pour les moteurs de recherche."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=1500,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            else:
                st.error(f"❌ Erreur API après {max_retries} tentatives: {str(e)}")
                return None

def get_google_suggestions(keyword, lang='fr', max_suggestions=10):
    """Récupère les suggestions Google pour un mot-clé"""
    url = "https://suggestqueries.google.com/complete/search"
    params = {
        "q": keyword,
        "gl": lang,
        "client": "chrome",
        "_": str(int(time.time() * 1000))
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        suggestions = response.json()[1][:max_suggestions]
        return suggestions
    except Exception as e:
        st.error(f"❌ Erreur lors de la récupération des suggestions pour '{keyword}': {str(e)}")
        return []

def extract_questions_from_response(response_text):
    """Extrait les questions d'une réponse de GPT"""
    if not response_text:
        return []
    
    patterns = [
        r'^\d+\.?\s*["\']?([^"\']+\?)["\']?',  # Format numéroté avec ?
        r'^-\s*["\']?([^"\']+\?)["\']?',       # Format avec tirets avec ?
        r'^•\s*["\']?([^"\']+\?)["\']?'        # Format avec puces avec ?
    ]
    
    questions = []
    lines = response_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or not line.endswith('?'):
            continue
            
        for pattern in patterns:
            match = re.match(pattern, line, re.MULTILINE)
            if match:
                question = match.group(1).strip()
                if len(question) > 10:
                    questions.append(question)
                break
        else:
            # Si aucun pattern ne correspond mais que la ligne se termine par ?
            if line.endswith('?') and len(line) > 10:
                questions.append(line)
    
    return questions

def consolidate_and_deduplicate(questions_data, target_count):
    """Consolide et déduplique les questions en gardant les plus pertinentes"""
    if not questions_data:
        return []
    
    # Créer un dictionnaire pour comptabiliser les occurrences et garder les métadonnées
    question_stats = {}
    
    for item in questions_data:
        question = item['Question Conversationnelle'].strip()
        # Normalisation pour détecter les similitudes
        normalized = re.sub(r'[^\w\s]', '', question.lower()).strip()
        
        if normalized not in question_stats:
            question_stats[normalized] = {
                'original_question': question,
                'count': 1,
                'suggestions': [item['Suggestion Google']],
                'keywords': [item['Mot-clé']],
                'first_occurrence': item
            }
        else:
            question_stats[normalized]['count'] += 1
            if item['Suggestion Google'] not in question_stats[normalized]['suggestions']:
                question_stats[normalized]['suggestions'].append(item['Suggestion Google'])
            if item['Mot-clé'] not in question_stats[normalized]['keywords']:
                question_stats[normalized]['keywords'].append(item['Mot-clé'])
    
    # Trier par nombre d'occurrences (pertinence) et prendre les meilleures
    sorted_questions = sorted(
        question_stats.values(),
        key=lambda x: (x['count'], len(x['keywords'])),
        reverse=True
    )
    
    # Prendre le nombre demandé de questions
    final_questions = []
    for i, q_data in enumerate(sorted_questions[:target_count]):
        final_questions.append({
            'Requêtes Conversationnelles': q_data['original_question'],
            'Suggestion': q_data['suggestions'][0],  # Première suggestion associée
            'Mot-clé': q_data['keywords'][0],  # Premier mot-clé associé
            'Score_Pertinence': q_data['count'],
            'Nb_Keywords': len(q_data['keywords']),
            'Nb_Suggestions': len(q_data['suggestions'])
        })
    
    return final_questions

def create_excel_file(df):
    """Crée un fichier Excel avec formatage"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Questions_Conversationnelles')
        
        # Accéder au workbook et worksheet pour le formatage
        workbook = writer.book
        worksheet = writer.sheets['Questions_Conversationnelles']
        
        # Ajuster la largeur des colonnes
        worksheet.column_dimensions['A'].width = 60  # Questions
        worksheet.column_dimensions['B'].width = 40  # Suggestions
        worksheet.column_dimensions['C'].width = 25  # Mots-clés
        
        # Formatage de l'en-tête
        from openpyxl.styles import Font, PatternFill
        header_font = Font(bold=True)
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        
        for cell in worksheet[1]:
            cell.font = header_font
            cell.fill = header_fill
    
    output.seek(0)
    return output

# Interface principale - Analyse par Suggestions Google
st.markdown("### 🔍 Analyse basée sur les suggestions Google")

# Input pour les mots-clés
keywords_input = st.text_area(
    "🎯 Entrez vos mots-clés (un par ligne)",
    placeholder="restaurant paris\nhôtel luxe\nvoyage écologique",
    help="Entrez un ou plusieurs mots-clés, un par ligne"
)

# Configuration améliorée
col1, col2, col3 = st.columns(3)
with col1:
    max_suggestions = st.slider(
        "Nombre de suggestions par mot-clé", 
        min_value=3, 
        max_value=15, 
        value=10,
        help="Nombre de suggestions Google à récupérer pour chaque mot-clé"
    )
with col2:
    final_questions_count = st.slider(
        "Nombre de questions finales",
        min_value=5,
        max_value=50,
        value=15,
        help="Nombre de questions conversationnelles à conserver après consolidation"
    )
with col3:
    lang = st.selectbox("Langue", ["fr", "en", "es", "de", "it"], index=0)

if keywords_input and api_key:
    keywords = [kw.strip() for kw in keywords_input.split('\n') if kw.strip()]
    
    if st.button("🚀 Analyser les suggestions", type="primary"):
        if not keywords:
            st.error("❌ Veuillez entrer au moins un mot-clé")
        else:
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Container pour les résultats
            results_container = st.container()
            
            # Étape 1: Collecte des suggestions
            status_text.text("⏳ Étape 1/4: Collecte des suggestions Google...")
            all_suggestions = []
            
            for i, keyword in enumerate(keywords):
                suggestions = get_google_suggestions(keyword, lang, max_suggestions)
                
                for suggestion in suggestions:
                    all_suggestions.append({
                        'Mot-clé': keyword,
                        'Suggestion Google': suggestion
                    })
                
                progress_bar.progress((i + 1) * 20 // len(keywords))
                time.sleep(0.5)  # Éviter le rate limiting
            
            if not all_suggestions:
                st.error("❌ Aucune suggestion trouvée")
            else:
                st.info(f"✅ {len(all_suggestions)} suggestions collectées pour {len(keywords)} mot(s)-clé(s)")
                
                # Étape 2: Génération des questions conversationnelles (10 par suggestion)
                status_text.text("⏳ Étape 2/4: Génération de 10 questions par suggestion...")
                
                all_questions_data = []
                processed = 0
                total_items = len(all_suggestions)
                
                for item in all_suggestions:
                    keyword = item['Mot-clé']
                    suggestion = item['Suggestion Google']
                    
                    prompt = f"""
                    Basé sur le mot-clé "{keyword}" et la suggestion Google "{suggestion}", 
                    génère EXACTEMENT 10 questions conversationnelles SEO pertinentes au format question.
                    
                    Les questions doivent :
                    - Être naturelles et conversationnelles
                    - Optimisées pour la recherche vocale
                    - Pertinentes pour l'intention de recherche
                    - Se terminer par un point d'interrogation
                    - Être variées dans leur formulation
                    
                    Présente-les sous forme de liste numérotée de 1 à 10.
                    """
                    
                    response = call_gpt4o_mini(prompt)
                    if response:
                        questions = extract_questions_from_response(response)
                        # S'assurer d'avoir exactement 10 questions
                        for question in questions[:10]:
                            all_questions_data.append({
                                'Mot-clé': keyword,
                                'Suggestion Google': suggestion,
                                'Question Conversationnelle': question
                            })
                    
                    processed += 1
                    progress_bar.progress(20 + (processed * 50 // total_items))
                    time.sleep(0.8)  # Éviter le rate limiting
                    
                    # Affichage du progrès en temps réel
                    current_questions = len(all_questions_data)
                    status_text.text(f"⏳ Étape 2/4: {current_questions} questions générées...")
                
                if not all_questions_data:
                    st.error("❌ Aucune question générée")
                else:
                    st.info(f"✅ {len(all_questions_data)} questions générées au total")
                    
                    # Étape 3: Consolidation et déduplication
                    status_text.text("⏳ Étape 3/4: Consolidation et déduplication...")
                    progress_bar.progress(80)
                    
                    # Utiliser la fonction de consolidation améliorée
                    final_consolidated_data = consolidate_and_deduplicate(
                        all_questions_data, 
                        final_questions_count
                    )
                    
                    progress_bar.progress(90)
                    
                    # Étape 4: Préparation des résultats finaux
                    status_text.text("⏳ Étape 4/4: Préparation des résultats...")
                    
                    progress_bar.progress(100)
                    status_text.text("✅ Analyse terminée !")
                    
                    # Affichage des résultats
                    with results_container:
                        st.markdown("## 📊 Résultats de l'analyse")
                        
                        # Métriques améliorées
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Mots-clés analysés", len(keywords))
                        with col2:
                            st.metric("Suggestions collectées", len(all_suggestions))
                        with col3:
                            st.metric("Questions générées", len(all_questions_data))
                        with col4:
                            st.metric("Questions finales", len(final_consolidated_data))
                        
                        # Tableau des résultats avec tri par pertinence
                        st.markdown("### 📋 Tableau des résultats (par pertinence décroissante)")
                        
                        # Créer le DataFrame avec les colonnes dans l'ordre demandé
                        df_results = pd.DataFrame(final_consolidated_data)
                        
                        # Réorganiser les colonnes selon vos spécifications
                        df_display = df_results[['Requêtes Conversationnelles', 'Suggestion', 'Mot-clé']].copy()
                        
                        st.dataframe(df_display, use_container_width=True)
                        
                        # Statistiques de consolidation
                        with st.expander("📊 Statistiques de consolidation"):
                            st.markdown(f"**Taux de consolidation:** {(len(all_questions_data) - len(final_consolidated_data)) / len(all_questions_data) * 100:.1f}%")
                            st.markdown(f"**Questions éliminées:** {len(all_questions_data) - len(final_consolidated_data)}")
                            st.markdown(f"**Questions conservées:** {len(final_consolidated_data)}")
                            
                            # Top mots-clés
                            keyword_counts = df_results['Mot-clé'].value_counts()
                            st.markdown("**Répartition par mot-clé:**")
                            for keyword, count in keyword_counts.items():
                                st.markdown(f"- {keyword}: {count} questions")
                        
                        # Visualisation améliorée
                        st.markdown("### 🗺️ Répartition des résultats")
                        
                        if len(final_consolidated_data) > 0:
                            try:
                                # Graphique en barres de la répartition par mot-clé
                                keyword_counts = df_results['Mot-clé'].value_counts()
                                
                                fig_bar = px.bar(
                                    x=keyword_counts.index,
                                    y=keyword_counts.values,
                                    title="Répartition des questions par mot-clé",
                                    labels={'x': 'Mots-clés', 'y': 'Nombre de questions'}
                                )
                                st.plotly_chart(fig_bar, use_container_width=True)
                                
                                # Graphique en secteurs
                                fig_pie = px.pie(
                                    values=keyword_counts.values,
                                    names=keyword_counts.index,
                                    title="Proportion des questions par mot-clé"
                                )
                                st.plotly_chart(fig_pie, use_container_width=True)
                                
                            except Exception as e:
                                st.warning(f"⚠️ Impossible d'afficher la visualisation: {str(e)}")
                        
                        # Export amélioré des résultats
                        st.markdown("### 📤 Export des résultats")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Export Excel
                            excel_file = create_excel_file(df_display)
                            st.download_button(
                                label="📊 Télécharger Excel",
                                data=excel_file,
                                file_name="questions_conversationnelles_consolidees.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        
                        with col2:
                            # Export JSON avec métadonnées
                            export_json = {
                                "metadata": {
                                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                    "keywords_analyzed": keywords,
                                    "total_questions_generated": len(all_questions_data),
                                    "final_questions_count": len(final_consolidated_data),
                                    "consolidation_rate": f"{(len(all_questions_data) - len(final_consolidated_data)) / len(all_questions_data) * 100:.1f}%"
                                },
                                "results": final_consolidated_data
                            }
                            
                            json_data = json.dumps(export_json, ensure_ascii=False, indent=2)
                            st.download_button(
                                label="📋 Télécharger JSON",
                                data=json_data,
                                file_name="questions_conversationnelles_consolidees.json",
                                mime="application/json"
                            )

# Instructions d'utilisation
if not api_key:
    st.markdown("""
    ## 📖 Instructions d'utilisation
    
    ### 🔍 Processus d'analyse en 4 étapes
    
    1. **Configuration** : Entrez votre clé API OpenAI dans la barre latérale
    2. **Saisie des mots-clés** : Entrez vos mots-clés (un par ligne)
    3. **Paramétrage** : Ajustez le nombre de suggestions et questions finales
    4. **Analyse** : Lancez l'analyse et obtenez vos questions conversationnelles
    
    ### ⚙️ Fonctionnalités principales:
    - **Collecte automatique** des suggestions Google réelles
    - **Génération intelligente** de 10 questions par suggestion
    - **Consolidation avancée** avec déduplication et scoring
    - **Export professionnel** en Excel et JSON
    
    ### 🎯 Exemples de mots-clés:
    - restaurant paris
    - formation développement web
    - voyage écologique
    - coaching personnel
    - e-commerce bio
    
    ### 📊 Résultats obtenus:
    - Questions conversationnelles optimisées SEO
    - Triées par pertinence décroissante
    - Prêtes pour l'intégration dans votre contenu
    """)

# Footer
st.markdown("---")
st.markdown("*Outil d'optimisation SEO pour requêtes conversationnelles | Powered by GPT-4o mini & Streamlit*")
