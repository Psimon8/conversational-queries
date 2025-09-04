import streamlit as st
from openai import OpenAI
import pandas as pd
import json
import time
from collections import Counter
import re

# Configuration de la page Streamlit
st.set_page_config(
    page_title="SEO Conversational Queries Optimizer",
    page_icon="🔍",
    layout="wide"
)

# Titre principal
st.title("🔍 Optimiseur de Requêtes Conversationnelles SEO")
st.subheader("Méthode en 3 étapes pour identifier les meilleures requêtes conversationnelles")

# Configuration de l'API OpenAI
st.sidebar.header("⚙️ Configuration")
api_key = st.sidebar.text_input("Clé API OpenAI", type="password", help="Votre clé API OpenAI pour GPT-4o mini")

if api_key:
    client = OpenAI(api_key=api_key)
    st.sidebar.success("✅ API configurée")
else:
    st.sidebar.warning("⚠️ Veuillez entrer votre clé API OpenAI")
    client = None

# Input pour la thématique
thematique = st.text_input(
    "🎯 Thématique à analyser",
    placeholder="Ex: réservation restaurant, voyage écologique, formation en ligne...",
    help="Entrez la thématique pour laquelle vous souhaitez identifier les requêtes conversationnelles"
)

# Fonctions utilitaires
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
                time.sleep(2 ** attempt)  # Backoff exponentiel
                continue
            else:
                st.error(f"❌ Erreur API après {max_retries} tentatives: {str(e)}")
                return None

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

# Interface principale
if thematique and api_key:
    
    # Bouton pour lancer l'analyse
    if st.button("🚀 Lancer l'analyse complète", type="primary"):
        
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Container pour les résultats
        results_container = st.container()
        
        with results_container:
            st.markdown("## 📊 Résultats de l'analyse")
            
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
    # Instructions d'utilisation
    st.markdown("""
    ## 📖 Instructions d'utilisation
    
    1. **Configurez votre clé API OpenAI** dans la barre latérale
    2. **Entrez la thématique** à analyser dans le champ ci-dessus
    3. **Cliquez sur "Lancer l'analyse complète"** pour démarrer le processus
    
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

# Footer
st.markdown("---")
st.markdown("*Outil d'optimisation SEO pour requêtes conversationnelles | Powered by GPT-4o mini & Streamlit*")
