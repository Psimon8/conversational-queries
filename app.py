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

# Configuration de la page Streamlit
st.set_page_config(
    page_title="SEO Conversational Queries Optimizer",
    page_icon="🔍",
    layout="wide"
)

# Titre principal
st.title("🔍 Optimiseur de Requêtes Conversationnelles SEO")
st.subheader("Analyse thématique et suggestions Google pour l'optimisation SEO")

# Configuration de l'API OpenAI
st.sidebar.header("⚙️ Configuration")
api_key = st.sidebar.text_input("Clé API OpenAI", type="password", help="Votre clé API OpenAI pour GPT-4o mini")

if api_key:
    client = OpenAI(api_key=api_key)
    st.sidebar.success("✅ API configurée")
else:
    st.sidebar.warning("⚠️ Veuillez entrer votre clé API OpenAI")
    client = None

# Création des onglets
tab1, tab2 = st.tabs(["📊 Analyse par Suggestions Google", "🎯 Analyse Thématique Classique"])

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

def create_mindmap_data(df):
    """Crée les données pour la visualisation mindmap"""
    nodes = []
    edges = []
    
    # Nœud central
    nodes.append({"id": "root", "label": "Mots-clés", "color": "#FF6B6B", "size": 30})
    
    # Couleurs pour les différents niveaux
    keyword_colors = ["#4ECDC4", "#45B7D1", "#96CEB4", "#FECA57", "#FF9FF3"]
    suggest_color = "#A8E6CF"
    question_color = "#FFD93D"
    
    # Grouper par mot-clé
    keyword_groups = df.groupby('Mot-clé')
    
    for i, (keyword, group) in enumerate(keyword_groups):
        keyword_color = keyword_colors[i % len(keyword_colors)]
        keyword_id = f"keyword_{i}"
        
        # Nœud mot-clé
        nodes.append({
            "id": keyword_id,
            "label": keyword,
            "color": keyword_color,
            "size": 25
        })
        edges.append({"source": "root", "target": keyword_id})
        
        # Grouper par suggestion
        suggest_groups = group.groupby('Suggestion Google')
        
        for j, (suggestion, suggest_group) in enumerate(suggest_groups):
            suggest_id = f"suggest_{i}_{j}"
            
            # Nœud suggestion
            nodes.append({
                "id": suggest_id,
                "label": suggestion[:30] + "..." if len(suggestion) > 30 else suggestion,
                "color": suggest_color,
                "size": 15
            })
            edges.append({"source": keyword_id, "target": suggest_id})
            
            # Nœuds questions
            for k, question in enumerate(suggest_group['Question Conversationnelle']):
                question_id = f"question_{i}_{j}_{k}"
                nodes.append({
                    "id": question_id,
                    "label": question[:40] + "..." if len(question) > 40 else question,
                    "color": question_color,
                    "size": 10
                })
                edges.append({"source": suggest_id, "target": question_id})
    
    return nodes, edges

# TAB 1: Analyse par Suggestions Google
with tab1:
    st.markdown("### 🔍 Analyse basée sur les suggestions Google")
    
    # Input pour les mots-clés
    keywords_input = st.text_area(
        "🎯 Entrez vos mots-clés (un par ligne)",
        placeholder="restaurant paris\nhôtel luxe\nvoyage écologique",
        help="Entrez un ou plusieurs mots-clés, un par ligne"
    )
    
    # Configuration
    col1, col2 = st.columns(2)
    with col1:
        max_suggestions = st.slider("Nombre de suggestions par mot-clé", 5, 15, 10)
    with col2:
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
                all_data = []
                
                for i, keyword in enumerate(keywords):
                    suggestions = get_google_suggestions(keyword, lang, max_suggestions)
                    
                    for suggestion in suggestions:
                        all_data.append({
                            'Mot-clé': keyword,
                            'Suggestion Google': suggestion
                        })
                    
                    progress_bar.progress((i + 1) * 20 // len(keywords))
                    time.sleep(0.5)  # Éviter le rate limiting
                
                if not all_data:
                    st.error("❌ Aucune suggestion trouvée")
                else:
                    # Étape 2: Génération des questions conversationnelles
                    status_text.text("⏳ Étape 2/4: Génération des questions conversationnelles...")
                    
                    questions_data = []
                    processed = 0
                    total_items = len(all_data)
                    
                    for item in all_data:
                        keyword = item['Mot-clé']
                        suggestion = item['Suggestion Google']
                        
                        prompt = f"""
                        Basé sur le mot-clé "{keyword}" et la suggestion Google "{suggestion}", 
                        génère 3 à 5 questions conversationnelles SEO pertinentes au format question.
                        
                        Les questions doivent :
                        - Être naturelles et conversationnelles
                        - Optimisées pour la recherche vocale
                        - Pertinentes pour l'intention de recherche
                        - Se terminer par un point d'interrogation
                        
                        Présente-les sous forme de liste numérotée.
                        """
                        
                        response = call_gpt4o_mini(prompt)
                        if response:
                            questions = extract_questions_from_response(response)
                            for question in questions:
                                questions_data.append({
                                    'Mot-clé': keyword,
                                    'Suggestion Google': suggestion,
                                    'Question Conversationnelle': question
                                })
                        
                        processed += 1
                        progress_bar.progress(20 + (processed * 50 // total_items))
                        time.sleep(0.8)  # Éviter le rate limiting
                    
                    if not questions_data:
                        st.error("❌ Aucune question générée")
                    else:
                        # Étape 3: Réanalyse et sélection finale
                        status_text.text("⏳ Étape 3/4: Réanalyse et sélection finale...")
                        
                        all_questions = [item['Question Conversationnelle'] for item in questions_data]
                        questions_text = "\n".join([f"- {q}" for q in all_questions])
                        
                        # Sélecteur pour le nombre de questions finales
                        num_final_questions = st.slider(
                            "Nombre de questions finales à sélectionner",
                            min_value=5,
                            max_value=min(20, len(all_questions)),
                            value=min(10, len(all_questions)),
                            key="final_questions_selector"
                        )
                        
                        final_selection_prompt = f"""
                        Analyse cette liste de questions conversationnelles et sélectionne les {num_final_questions} meilleures questions selon ces critères :
                        
                        1. Pertinence SEO et potentiel de recherche
                        2. Qualité conversationnelle et naturelle
                        3. Diversité des intentions de recherche
                        4. Optimisation pour la recherche vocale
                        
                        Questions à analyser :
                        {questions_text}
                        
                        Retourne uniquement les {num_final_questions} meilleures questions, une par ligne, sans numérotation.
                        """
                        
                        final_response = call_gpt4o_mini(final_selection_prompt)
                        final_questions = []
                        
                        if final_response:
                            final_questions = [q.strip() for q in final_response.split('\n') if q.strip() and q.strip().endswith('?')]
                        
                        progress_bar.progress(90)
                        
                        # Étape 4: Préparation des résultats finaux
                        status_text.text("⏳ Étape 4/4: Préparation des résultats...")
                        
                        # Filtrer les données pour ne garder que les questions sélectionnées
                        final_data = [
                            item for item in questions_data 
                            if item['Question Conversationnelle'] in final_questions
                        ]
                        
                        if not final_data:
                            # Si aucune correspondance exacte, prendre les premières
                            final_data = questions_data[:num_final_questions]
                        
                        progress_bar.progress(100)
                        status_text.text("✅ Analyse terminée !")
                        
                        # Affichage des résultats
                        with results_container:
                            st.markdown("## 📊 Résultats de l'analyse")
                            
                            # Métriques
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Mots-clés analysés", len(keywords))
                            with col2:
                                st.metric("Suggestions collectées", len(all_data))
                            with col3:
                                st.metric("Questions générées", len(questions_data))
                            with col4:
                                st.metric("Questions finales", len(final_data))
                            
                            # Tableau des résultats
                            st.markdown("### 📋 Tableau des résultats")
                            df_results = pd.DataFrame(final_data)
                            st.dataframe(df_results, use_container_width=True)
                            
                            # Visualisation Mindmap
                            st.markdown("### 🗺️ Carte mentale des résultats")
                            
                            if len(final_data) > 0:
                                try:
                                    # Graphique en réseau avec Plotly
                                    fig = go.Figure()
                                    
                                    # Préparer les données pour le graphique en réseau
                                    keywords_unique = df_results['Mot-clé'].unique()
                                    
                                    # Graphique en sunburst comme alternative
                                    labels = []
                                    parents = []
                                    values = []
                                    
                                    # Niveau racine
                                    labels.append("Mots-clés")
                                    parents.append("")
                                    values.append(len(final_data))
                                    
                                    # Niveau mots-clés
                                    for keyword in keywords_unique:
                                        labels.append(keyword)
                                        parents.append("Mots-clés")
                                        keyword_data = df_results[df_results['Mot-clé'] == keyword]
                                        values.append(len(keyword_data))
                                        
                                        # Niveau suggestions
                                        suggestions_unique = keyword_data['Suggestion Google'].unique()
                                        for suggestion in suggestions_unique:
                                            suggest_label = suggestion[:30] + "..." if len(suggestion) > 30 else suggestion
                                            labels.append(suggest_label)
                                            parents.append(keyword)
                                            suggest_data = keyword_data[keyword_data['Suggestion Google'] == suggestion]
                                            values.append(len(suggest_data))
                                    
                                    fig = go.Figure(go.Sunburst(
                                        labels=labels,
                                        parents=parents,
                                        values=values,
                                        branchvalues="total",
                                    ))
                                    
                                    fig.update_layout(
                                        title="Répartition hiérarchique des résultats",
                                        height=600
                                    )
                                    
                                    st.plotly_chart(fig, use_container_width=True)
                                    
                                except Exception as e:
                                    st.warning(f"⚠️ Impossible d'afficher la visualisation: {str(e)}")
                            
                            # Export des résultats
                            st.markdown("### 📤 Export des résultats")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                csv = df_results.to_csv(index=False, encoding='utf-8')
                                st.download_button(
                                    label="📊 Télécharger CSV",
                                    data=csv,
                                    file_name="questions_conversationnelles_suggestions.csv",
                                    mime="text/csv"
                                )
                            
                            with col2:
                                json_data = df_results.to_json(orient='records', force_ascii=False, indent=2)
                                st.download_button(
                                    label="📋 Télécharger JSON",
                                    data=json_data,
                                    file_name="questions_conversationnelles_suggestions.json",
                                    mime="application/json"
                                )

# TAB 2: Analyse Thématique Classique (code existant)
with tab2:
    st.markdown("### 🎯 Analyse thématique classique")
    
    # Input pour la thématique
    thematique = st.text_input(
        "🎯 Thématique à analyser",
        placeholder="Ex: réservation restaurant, voyage écologique, formation en ligne...",
        help="Entrez la thématique pour laquelle vous souhaitez identifier les requêtes conversationnelles"
    )

    # Fonctions utilitaires
    def extract_queries_from_response(response_text):
        """Extrait les requêtes d'une réponse de GPT"""
        if not response_text:
            return []
        
        # Patterns pour extraire les requêtes
        patterns = [
            r'^\d+\.?\s*["\']?([^"\']+)["\']?',  # Format numéroté
            r'^-\s*["\']?([^"\']+)["\']?',       # Format avec tirets
            r'^•\s*["\']?([^"\']+)["\']?'        # Format avec puces
        ]
        
        queries = []
        lines = response_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            for pattern in patterns:
                match = re.match(pattern, line, re.MULTILINE)
                if match:
                    query = match.group(1).strip()
                    if len(query) > 10:  # Filtrer les réponses trop courtes
                        queries.append(query)
                    break
        
        return queries[:10]  # Limiter à 10 requêtes

    def deduplicate_queries(queries):
        """Dédoublonne les requêtes en tenant compte des similarités"""
        if not queries:
            return []
        
        # Normalisation pour comparaison
        normalized = {}
        for query in queries:
            # Suppression ponctuation et mise en minuscules
            normalized_query = re.sub(r'[^\w\s]', '', query.lower()).strip()
            if normalized_query not in normalized:
                normalized[normalized_query] = query
        
        return list(normalized.values())

    # Interface principale pour l'analyse thématique
    if thematique and api_key:
        
        # Bouton pour lancer l'analyse
        if st.button("🚀 Lancer l'analyse thématique complète", type="primary"):
            
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Container pour les résultats
            results_container = st.container()
            
            with results_container:
                st.markdown("## 📊 Résultats de l'analyse thématique")
                
                # Étape 1: Collecte initiale
                status_text.text("⏳ Étape 1/3: Collecte initiale des requêtes...")
                progress_bar.progress(10)
                
                prompt_etape1 = f"En te basant sur la thématique '{thematique}', donne-moi les 10 meilleures requêtes conversationnelles recherchées par les utilisateurs. Présente-les sous forme de liste numérotée."
                
                # Simulation de 4 appels LLM (ici on utilise GPT-4o mini avec des variations)
                llm_responses = []
                
                for i in range(4):
                    variation_prompt = f"{prompt_etape1}\n\nVariation {i+1}: Focus sur les intentions de recherche spécifiques à cette thématique."
                    response = call_gpt4o_mini(variation_prompt)
                    if response:
                        queries = extract_queries_from_response(response)
                        llm_responses.extend(queries)
                    progress_bar.progress(10 + (i+1) * 15)
                    time.sleep(1)  # Éviter le rate limiting
                
                # Affichage des résultats Étape 1
                st.markdown("### 📋 Étape 1 - Requêtes collectées")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Requêtes collectées", len(llm_responses))
                with col2:
                    st.metric("Requêtes uniques", len(set(llm_responses)))
                
                # Dédoublonnage pour étape 2
                status_text.text("⏳ Étape 2/3: Affinage et sélection...")
                progress_bar.progress(70)
                
                deduplicated_queries = deduplicate_queries(llm_responses)
                queries_list = "\n".join([f"- {query}" for query in deduplicated_queries])
                
                prompt_etape2 = f"""En te basant sur la thématique '{thematique}' et sur cette liste de requêtes conversationnelles, fais-moi une sélection d'un top 10 des meilleures requêtes conversationnelles :

{queries_list}

Critères de sélection :
- Pertinence pour la thématique
- Potentiel de volume de recherche
- Intention de recherche claire
- Adaptabilité au SEO conversationnel"""

                refined_response = call_gpt4o_mini(prompt_etape2)
                refined_queries = extract_queries_from_response(refined_response) if refined_response else []
                
                progress_bar.progress(85)
                
                # Étape 3: Finalisation
                status_text.text("⏳ Étape 3/3: Finalisation par intention de recherche...")
                
                if refined_queries:
                    final_queries_list = "\n".join([f"- {query}" for query in refined_queries])
                    prompt_etape3 = f"""En te basant sur l'intention de recherche, dédoublonne cette liste et fournis-moi le top 10 des meilleures requêtes conversationnelles pour la thématique '{thematique}':

{final_queries_list}

Analyse chaque requête selon :
1. L'intention de recherche (informationnelle, navigationnelle, transactionnelle)
2. Le potentiel SEO
3. La pertinence pour les assistants vocaux
4. L'adaptabilité au contenu conversationnel

Présente le résultat final sous forme de liste numérotée."""
                    
                    final_response = call_gpt4o_mini(prompt_etape3)
                    final_queries = extract_queries_from_response(final_response) if final_response else refined_queries
                else:
                    final_queries = []
                
                progress_bar.progress(100)
                status_text.text("✅ Analyse terminée !")
                
                # Affichage des résultats finaux
                st.markdown("### 🏆 Résultats finaux - Top 10 des requêtes conversationnelles")
                
                if final_queries:
                    # Métriques
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Requêtes finales", len(final_queries))
                    with col2:
                        st.metric("Taux de conversion", f"{(len(final_queries)/max(len(llm_responses), 1)*100):.1f}%")
                    with col3:
                        st.metric("Étapes complétées", "3/3")
                    
                    # Liste des requêtes finales
                    st.markdown("#### 📝 Requêtes sélectionnées:")
                    for i, query in enumerate(final_queries, 1):
                        st.markdown(f"**{i}.** {query}")
                    
                    # Export des données
                    st.markdown("### 📤 Export des résultats")
                    
                    # Création du DataFrame pour export
                    export_data = {
                        'Rang': range(1, len(final_queries) + 1),
                        'Requête conversationnelle': final_queries,
                        'Thématique': [thematique] * len(final_queries)
                    }
                    df = pd.DataFrame(export_data)
                    
                    # Boutons d'export
                    col1, col2 = st.columns(2)
                    with col1:
                        csv = df.to_csv(index=False, encoding='utf-8')
                        st.download_button(
                            label="📊 Télécharger CSV",
                            data=csv,
                            file_name=f"requetes_conversationnelles_{thematique.replace(' ', '_')}.csv",
                            mime="text/csv"
                        )
                    
                    with col2:
                        json_data = df.to_json(orient='records', force_ascii=False, indent=2)
                        st.download_button(
                            label="📋 Télécharger JSON",
                            data=json_data,
                            file_name=f"requetes_conversationnelles_{thematique.replace(' ', '_')}.json",
                            mime="application/json"
                        )
                    
                    # Analyse détaillée
                    with st.expander("📊 Analyse détaillée du processus"):
                        st.markdown(f"**Thématique analysée:** {thematique}")
                        st.markdown(f"**Requêtes collectées initialement:** {len(llm_responses)}")
                        st.markdown(f"**Requêtes après dédoublonnage:** {len(deduplicated_queries)}")
                        st.markdown(f"**Requêtes finales sélectionnées:** {len(final_queries)}")
                        st.markdown(f"**Efficacité du processus:** {(len(final_queries)/max(len(llm_responses), 1)*100):.1f}%")
                
                else:
                    st.error("❌ Aucune requête n'a pu être extraite. Vérifiez votre thématique et réessayez.")

    else:
        # Instructions d'utilisation pour l'analyse thématique
        st.markdown("""
        ## 📖 Instructions d'utilisation - Analyse Thématique
        
        1. **Configurez votre clé API OpenAI** dans la barre latérale
        2. **Entrez la thématique** à analyser dans le champ ci-dessus
        3. **Cliquez sur "Lancer l'analyse thématique complète"** pour démarrer le processus
        
        ### 🎯 Exemples de thématiques:
        - "Réservation restaurant en ligne"
        - "Formation développement web"
        - "Voyage écologique et durable"
        - "E-commerce produits bio"
        - "Coaching personnel à distance"
        
        ### ⚡ Le processus automatisé comprend:
        - **Étape 1:** Collecte initiale via GPT-4o mini avec variations
        - **Étape 2:** Affinage et sélection des meilleures requêtes
        - **Étape 3:** Finalisation basée sur l'intention de recherche
        - **Export:** Téléchargement des résultats en CSV/JSON
        """)

# Instructions globales
if not api_key:
    st.markdown("""
    ## 📖 Instructions générales
    
    ### 🔍 Deux méthodes d'analyse disponibles:
    
    **1. Analyse par Suggestions Google** (Onglet 1)
    - Saisissez vos mots-clés
    - Récupération automatique des suggestions Google
    - Génération de questions conversationnelles par GPT
    - Visualisation en tableau et carte mentale
    
    **2. Analyse Thématique Classique** (Onglet 2)
    - Saisissez une thématique générale
    - Méthode en 3 étapes avec variations GPT
    - Focus sur l'intention de recherche
    
    ### ⚙️ Configuration requise:
    - Clé API OpenAI (configurée dans la barre latérale)
    - Connexion internet pour les suggestions Google
    """)

# Footer
st.markdown("---")
st.markdown("*Outil d'optimisation SEO pour requêtes conversationnelles | Powered by GPT-4o mini & Streamlit*")
