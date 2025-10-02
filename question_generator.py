import streamlit as st
import json
import re
import time
from typing import List, Dict, Optional, Any

class QuestionGenerator:
    """Classe pour gérer la génération de questions conversationnelles avec GPT"""
    
    def __init__(self, client=None):
        self.client = client
        self.language_prompts = {
            'fr': {
                'system': "Tu es un expert SEO spécialisé dans l'analyse des requêtes conversationnelles et l'optimisation pour les moteurs de recherche. Réponds TOUJOURS en français.",
                'examples': {
                    'informational': '"Comment...", "Pourquoi...", "Qu\'est-ce que...", "Quels sont..."',
                    'transactional': '"Combien coûte...", "Où acheter...", "Comment réserver...", "Quel prix..."',
                    'navigational': '"Où trouver...", "Comment accéder...", "Quelle adresse..."',
                    'local': '"... près de moi", "... dans ma ville", "... dans ma région"'
                }
            },
            'en': {
                'system': "You are an SEO expert specialized in conversational queries analysis and search engine optimization. ALWAYS respond in English.",
                'examples': {
                    'informational': '"How...", "Why...", "What is...", "What are..."',
                    'transactional': '"How much does... cost", "Where to buy...", "How to book...", "What price..."',
                    'navigational': '"Where to find...", "How to access...", "What address..."',
                    'local': '"... near me", "... in my city", "... in my area"'
                }
            },
            'es': {
                'system': "Eres un experto en SEO especializado en análisis de consultas conversacionales y optimización para motores de búsqueda. Responde SIEMPRE en español.",
                'examples': {
                    'informational': '"Cómo...", "Por qué...", "Qué es...", "Cuáles son..."',
                    'transactional': '"Cuánto cuesta...", "Dónde comprar...", "Cómo reservar...", "Qué precio..."',
                    'navigational': '"Dónde encontrar...", "Cómo acceder...", "Qué dirección..."',
                    'local': '"... cerca de mí", "... en mi ciudad", "... en mi región"'
                }
            },
            'de': {
                'system': "Du bist ein SEO-Experte, der sich auf die Analyse von Conversational Queries und Suchmaschinenoptimierung spezialisiert hat. Antworte IMMER auf Deutsch.",
                'examples': {
                    'informational': '"Wie...", "Warum...", "Was ist...", "Welche sind..."',
                    'transactional': '"Wie viel kostet...", "Wo kaufen...", "Wie buchen...", "Welcher Preis..."',
                    'navigational': '"Wo finden...", "Wie zugreifen...", "Welche Adresse..."',
                    'local': '"... in meiner Nähe", "... in meiner Stadt", "... in meiner Region"'
                }
            },
            'it': {
                'system': "Sei un esperto SEO specializzato nell'analisi delle query conversazionali e nell'ottimizzazione per i motori di ricerca. Rispondi SEMPRE in italiano.",
                'examples': {
                    'informational': '"Come...", "Perché...", "Cos\'è...", "Quali sono..."',
                    'transactional': '"Quanto costa...", "Dove comprare...", "Come prenotare...", "Che prezzo..."',
                    'navigational': '"Dove trovare...", "Come accedere...", "Quale indirizzo..."',
                    'local': '"... vicino a me", "... nella mia città", "... nella mia regione"'
                }
            },
            'pt': {
                'system': "És um especialista em SEO especializado na análise de consultas conversacionais e otimização para motores de busca. Responde SEMPRE em português.",
                'examples': {
                    'informational': '"Como...", "Porquê...", "O que é...", "Quais são..."',
                    'transactional': '"Quanto custa...", "Onde comprar...", "Como reservar...", "Que preço..."',
                    'navigational': '"Onde encontrar...", "Como aceder...", "Que morada..."',
                    'local': '"... perto de mim", "... na minha cidade", "... na minha região"'
                }
            },
            'pt-BR': {
                'system': "Você é um especialista em SEO especializado na análise de consultas conversacionais e otimização para mecanismos de busca. Responda SEMPRE em português brasileiro.",
                'examples': {
                    'informational': '"Como...", "Por que...", "O que é...", "Quais são..."',
                    'transactional': '"Quanto custa...", "Onde comprar...", "Como reservar...", "Qual preço..."',
                    'navigational': '"Onde encontrar...", "Como acessar...", "Qual endereço..."',
                    'local': '"... perto de mim", "... na minha cidade", "... na minha região"'
                }
            }
        }
        # Valeur par défaut pour générer les questions conversationnelles
        self.generate_questions_default = False
    
    def set_client(self, client):
        """Définir le client OpenAI"""
        self.client = client
    
    def call_gpt4o_mini(self, prompt: str, language: str = 'fr', max_retries: int = 3) -> Optional[str]:
        """Appel à l'API GPT-4o mini avec gestion d'erreurs et support multilingue"""
        if not self.client:
            st.error("❌ Clé API manquante")
            return None
        
        # Récupérer le prompt système dans la langue appropriée
        system_prompt = self.language_prompts.get(language, self.language_prompts['fr'])['system']
        
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=1500,
                    temperature=0.3
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    st.error(f"❌ Erreur API après {max_retries} tentatives: {str(e)}")
                    return None
    
    def extract_questions_from_response(self, response_text: str) -> List[str]:
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
    
    def analyze_suggestion_relevance(self, keyword: str, suggestion: str, level: int, language: str = 'fr') -> Dict[str, Any]:
        """Analyse la pertinence d'une suggestion par rapport au mot-clé principal"""
        if not self.client:
            return {"category": "unknown", "relevance_score": 0, "intent": "unknown"}
        
        # Adapter le prompt selon la langue
        if language == 'en':
            prompt = f"""
            Analyze the Google suggestion "{suggestion}" (level {level}) compared to the main keyword "{keyword}".
            
            Evaluate according to these criteria:
            1. RELEVANCE (0-10): How much is the suggestion related to the main keyword?
            2. CATEGORY: Classify the suggestion in one of these categories:
               - "core": Directly related to the main keyword
               - "related": Related but with a different nuance
               - "complementary": Complementary or associated service
               - "geographic": Geographic variation
               - "temporal": Temporal variation (schedules, seasons...)
               - "competitive": Comparison or alternative
               - "informational": Information search
               - "transactional": Purchase/booking intention
               - "navigational": Search for a specific place/site
            
            3. INTENT: Determine the search intent:
               - "informational": Looking for information
               - "navigational": Looking to go somewhere
               - "transactional": Wants to buy/book
               - "local": Local search
            
            Respond ONLY in JSON format:
            {{"relevance_score": X, "category": "xxx", "intent": "xxx", "justification": "short explanation"}}
            """
        elif language == 'es':
            prompt = f"""
            Analiza la sugerencia de Google "{suggestion}" (nivel {level}) en comparación con la palabra clave principal "{keyword}".
            
            Evalúa según estos criterios:
            1. RELEVANCIA (0-10): ¿Qué tan relacionada está la sugerencia con la palabra clave principal?
            2. CATEGORÍA: Clasifica la sugerencia en una de estas categorías:
               - "core": Directamente relacionada con la palabra clave principal
               - "related": Relacionada pero con un matiz diferente
               - "complementary": Complementaria o servicio asociado
               - "geographic": Variación geográfica
               - "temporal": Variación temporal (horarios, estaciones...)
               - "competitive": Comparación o alternativa
               - "informational": Búsqueda de información
               - "transactional": Intención de compra/reserva
               - "navigational": Búsqueda de un lugar/sitio específico
            
            3. INTENCIÓN: Determina la intención de búsqueda:
               - "informational": Busca información
               - "navigational": Busca ir a algún lugar
               - "transactional": Quiere comprar/reservar
               - "local": Búsqueda local
            
            Responde ÚNICAMENTE en formato JSON:
            {{"relevance_score": X, "category": "xxx", "intent": "xxx", "justification": "explicación breve"}}
            """
        else:  # Default français et autres langues
            prompt = f"""
            Analyse la suggestion Google "{suggestion}" (niveau {level}) par rapport au mot-clé principal "{keyword}".
            
            Évalue selon ces critères :
            1. PERTINENCE (0-10) : À quel point la suggestion est-elle liée au mot-clé principal ?
            2. CATÉGORIE : Classe la suggestion dans une de ces catégories :
               - "core" : Directement lié au mot-clé principal
               - "related" : Lié mais avec une nuance différente
               - "complementary" : Complémentaire ou service associé
               - "geographic" : Variation géographique
               - "temporal" : Variation temporelle (horaires, saisons...)
               - "competitive" : Comparaison ou alternative
               - "informational" : Recherche d'information
               - "transactional" : Intention d'achat/réservation
               - "navigational" : Recherche d'un lieu/site spécifique
            
            3. INTENTION : Détermine l'intention de recherche :
               - "informational" : Cherche de l'information
               - "navigational" : Cherche à aller quelque part
               - "transactional" : Veut acheter/réserver
               - "local" : Recherche locale
            
            Réponds UNIQUEMENT au format JSON :
            {{"relevance_score": X, "category": "xxx", "intent": "xxx", "justification": "courte explication"}}
            """
        
        try:
            response = self.call_gpt4o_mini(prompt, language)
            if response:
                # Nettoyer la réponse pour extraire le JSON
                response_clean = response.strip()
                if response_clean.startswith('```json'):
                    response_clean = response_clean[7:-3]
                elif response_clean.startswith('```'):
                    response_clean = response_clean[3:-3]
                
                return json.loads(response_clean)
        except Exception as e:
            st.warning(f"Erreur analyse suggestion '{suggestion}': {str(e)}")
        
        # Fallback basique si l'analyse GPT échoue
        return {
            "relevance_score": 5, 
            "category": "related", 
            "intent": "informational",
            "justification": "Analyse automatique indisponible"
        }
    
    def generate_contextual_questions(self, keyword: str, suggestion: str, analysis_data: Dict[str, Any], num_questions: int = 3, language: str = 'fr') -> List[str]:
        """Génère des questions conversationnelles contextuelles basées sur l'analyse"""
        if not self.client:
            return []
        
        category = analysis_data.get('category', 'related')
        intent = analysis_data.get('intent', 'informational')
        relevance = analysis_data.get('relevance_score', 5)
        
        # Récupérer les exemples de formulation dans la langue appropriée
        lang_config = self.language_prompts.get(language, self.language_prompts['fr'])
        examples = lang_config['examples']
        
        # Construire le prompt dans la langue appropriée
        if language == 'en':
            prompt = f"""
            Main keyword: "{keyword}"
            Analyzed suggestion: "{suggestion}"
            Category: {category}
            Intent: {intent}
            Relevance score: {relevance}/10
            
            Generate EXACTLY {num_questions} conversational SEO-optimized questions that:
            - Are adapted to the category "{category}" and intent "{intent}"
            - Naturally integrate the suggestion context
            - Are formulated as questions users would really ask
            - Are optimized for voice search
            - End with a question mark
            - Are of appropriate length (neither too short nor too long)
            
            Example formulations by intent:
            - Informational: {examples['informational']}
            - Transactional: {examples['transactional']}
            - Navigational: {examples['navigational']}
            - Local: {examples['local']}
            
            Present the questions as a numbered list from 1 to {num_questions}.
            """
        elif language == 'es':
            prompt = f"""
            Palabra clave principal: "{keyword}"
            Sugerencia analizada: "{suggestion}"
            Categoría: {category}
            Intención: {intent}
            Puntuación de relevancia: {relevance}/10
            
            Genera EXACTAMENTE {num_questions} preguntas conversacionales optimizadas para SEO que:
            - Estén adaptadas a la categoría "{category}" e intención "{intent}"
            - Integren naturalmente el contexto de la sugerencia
            - Estén formuladas como preguntas que los usuarios realmente harían
            - Estén optimizadas para búsqueda por voz
            - Terminen con signo de interrogación
            - Tengan longitud apropiada (ni muy cortas ni muy largas)
            
            Ejemplos de formulaciones según la intención:
            - Informacional: {examples['informational']}
            - Transaccional: {examples['transactional']}
            - Navegacional: {examples['navigational']}
            - Local: {examples['local']}
            
            Presenta las preguntas como una lista numerada del 1 al {num_questions}.
            """
        elif language in ['pt', 'pt-BR']:
            verb_form = "Analisa" if language == 'pt' else "Analise"
            prompt = f"""
            Palavra-chave principal: "{keyword}"
            Sugestão analisada: "{suggestion}"
            Categoria: {category}
            Intenção: {intent}
            Pontuação de relevância: {relevance}/10
            
            Gera EXATAMENTE {num_questions} perguntas conversacionais otimizadas para SEO que:
            - Estejam adaptadas à categoria "{category}" e intenção "{intent}"
            - Integrem naturalmente o contexto da sugestão
            - Sejam formuladas como perguntas que os utilizadores realmente fariam
            - Estejam otimizadas para busca por voz
            - Terminem com ponto de interrogação
            - Tenham comprimento apropriado (nem muito curtas nem muito longas)
            
            Exemplos de formulações conforme a intenção:
            - Informacional: {examples['informational']}
            - Transacional: {examples['transactional']}
            - Navegacional: {examples['navigational']}
            - Local: {examples['local']}
            
            Apresenta as perguntas como uma lista numerada de 1 a {num_questions}.
            """
        else:  # Default français
            prompt = f"""
            Mot-clé principal : "{keyword}"
            Suggestion analysée : "{suggestion}"
            Catégorie : {category}
            Intention : {intent}
            Score de pertinence : {relevance}/10
            
            Génère EXACTEMENT {num_questions} questions conversationnelles SEO optimisées qui :
            - Sont adaptées à la catégorie "{category}" et l'intention "{intent}"
            - Intègrent naturellement le contexte de la suggestion
            - Sont formulées comme des questions que les utilisateurs poseraient vraiment
            - Sont optimisées pour la recherche vocale
            - Se terminent par un point d'interrogation
            - Sont de longueur appropriée (ni trop courtes, ni trop longues)
            
            Exemples de formulations selon l'intention :
            - Informational : {examples['informational']}
            - Transactional : {examples['transactional']}
            - Navigational : {examples['navigational']}
            - Local : {examples['local']}
            
            Présente les questions sous forme de liste numérotée de 1 à {num_questions}.
            """
        
        response = self.call_gpt4o_mini(prompt, language)
        if response:
            return self.extract_questions_from_response(response)
        return []
    
    def analyze_suggestions_themes(self, all_suggestions: List[Dict[str, Any]], keyword: str, language: str = 'fr') -> List[Dict[str, Any]]:
        """Analyse les suggestions pour identifier les thèmes récurrents"""
        if not self.client or not all_suggestions:
            return []
        
        # Créer une liste des suggestions sans doublons pour analyse
        suggestions_text = []
        for item in all_suggestions:
            if item['Niveau'] > 0:  # Exclure le mot-clé de base
                suggestions_text.append(item['Suggestion Google'])
        
        # Limiter à 50 suggestions max pour l'analyse
        suggestions_sample = list(set(suggestions_text))[:50]
        
        if not suggestions_sample:
            return []
        
        # Construire le prompt dans la langue appropriée
        if language == 'en':
            prompt = f"""
            Analyze these Google suggestions for the main keyword "{keyword}" and identify recurring themes:
            
            Suggestions to analyze:
            {chr(10).join([f"- {s}" for s in suggestions_sample])}
            
            Identify the 5-10 MAIN THEMES that emerge from these suggestions.
            For each theme, indicate:
            1. The theme name
            2. Recurring keywords/concepts
            3. The dominant search intent
            4. The importance level (1-5)
            
            Respond ONLY in JSON format:
            {{
                "themes": [
                    {{
                        "nom": "theme_name",
                        "concepts": ["concept1", "concept2"],
                        "intention": "informational",
                        "importance": 4,
                        "exemples_suggestions": ["suggestion1", "suggestion2"]
                    }}
                ]
            }}
            """
        elif language == 'es':
            prompt = f"""
            Analiza estas sugerencias de Google para la palabra clave principal "{keyword}" e identifica temas recurrentes:
            
            Sugerencias a analizar:
            {chr(10).join([f"- {s}" for s in suggestions_sample])}
            
            Identifica los 5-10 TEMAS PRINCIPALES que emergen de estas sugerencias.
            Para cada tema, indica:
            1. El nombre del tema
            2. Palabras clave/conceptos recurrentes
            3. La intención de búsqueda dominante
            4. El nivel de importancia (1-5)
            
            Responde ÚNICAMENTE en formato JSON:
            {{
                "themes": [
                    {{
                        "nom": "nombre_del_tema",
                        "concepts": ["concepto1", "concepto2"],
                        "intention": "informational",
                        "importance": 4,
                        "exemples_suggestions": ["sugerencia1", "sugerencia2"]
                    }}
                ]
            }}
            """
        elif language in ['pt', 'pt-BR']:
            verb_form = "Analisa" if language == 'pt' else "Analise"
            prompt = f"""
            {verb_form} estas sugestões do Google para a palavra-chave principal "{keyword}" e identifica temas recorrentes:
            
            Sugestões para analisar:
            {chr(10).join([f"- {s}" for s in suggestions_sample])}
            
            Identifica os 5-10 TEMAS PRINCIPAIS que emergem destas sugestões.
            Para cada tema, indica:
            1. O nome do tema
            2. Palavras-chave/conceitos recorrentes
            3. A intenção de busca dominante
            4. O nível de importância (1-5)
            
            Responde APENAS em formato JSON:
            {{
                "themes": [
                    {{
                        "nom": "nome_do_tema",
                        "concepts": ["conceito1", "conceito2"],
                        "intention": "informational",
                        "importance": 4,
                        "exemples_suggestions": ["sugestao1", "sugestao2"]
                    }}
                ]
            }}
            """
        else:  # Default français
            prompt = f"""
            Analyse ces suggestions Google pour le mot-clé principal "{keyword}" et identifie les thèmes récurrents :
            
            Suggestions à analyser :
            {chr(10).join([f"- {s}" for s in suggestions_sample])}
            
            Identifie les 5-10 THÈMES PRINCIPAUX qui ressortent de ces suggestions.
            Pour chaque thème, indique :
            1. Le nom du thème
            2. Les mots-clés/concepts récurrents
            3. L'intention de recherche dominante
            4. Le niveau d'importance (1-5)
            
            Réponds UNIQUEMENT au format JSON :
            {{
                "themes": [
                    {{
                        "nom": "nom_du_theme",
                        "concepts": ["concept1", "concept2"],
                        "intention": "informational",
                        "importance": 4,
                        "exemples_suggestions": ["suggestion1", "suggestion2"]
                    }}
                ]
            }}
            """
        
        try:
            response = self.call_gpt4o_mini(prompt, language)
            if response:
                response_clean = response.strip()
                if response_clean.startswith('```json'):
                    response_clean = response_clean[7:-3]
                elif response_clean.startswith('```'):
                    response_clean = response_clean[3:-3]
                
                parsed = json.loads(response_clean)
                return parsed.get('themes', [])
        except Exception as e:
            st.warning(f"Erreur analyse thèmes pour '{keyword}': {str(e)}")
            return []
    
    def generate_questions_from_themes(self, keyword: str, themes: List[Dict[str, Any]], target_count: int, language: str = 'fr') -> List[Dict[str, Any]]:
        """Génère des questions conversationnelles basées sur les thèmes identifiés"""
        if not self.client or not themes or target_count <= 0:
            return []
        
        # Trier les thèmes par importance
        sorted_themes = sorted(themes, key=lambda x: x.get('importance', 0), reverse=True)
        
        # Calculer la répartition des questions par thème
        questions_per_theme = max(1, target_count // len(sorted_themes))
        remaining_questions = target_count
        
        all_questions = []
        
        # Récupérer les exemples de formulation dans la langue appropriée
        lang_config = self.language_prompts.get(language, self.language_prompts['fr'])
        examples = lang_config['examples']
        
        for i, theme in enumerate(sorted_themes):
            if remaining_questions <= 0:
                break
            
            # Calculer le nombre de questions pour ce thème
            if i == len(sorted_themes) - 1:  # Dernier thème
                theme_questions = remaining_questions
            else:
                theme_questions = min(questions_per_theme, remaining_questions)
            
            if theme_questions > 0:
                theme_name = theme.get('nom', 'theme')
                concepts = ', '.join(theme.get('concepts', []))
                intention = theme.get('intention', 'informational')
                exemples = ', '.join(theme.get('exemples_suggestions', [])[:3])
                
                # Construire le prompt dans la langue appropriée
                if language == 'en':
                    prompt = f"""
                    Generate EXACTLY {theme_questions} conversational SEO questions for:
                    
                    Main keyword: "{keyword}"
                    Theme: "{theme_name}"
                    Key concepts: {concepts}
                    Intent: {intention}
                    Example suggestions: {exemples}
                    
                    The questions must:
                    1. Be natural and conversational
                    2. Naturally integrate the theme "{theme_name}"
                    3. Match the intent "{intention}"
                    4. Be optimized for voice search
                    5. End with a question mark
                    6. Be varied and complementary
                    
                    Formulations by intent:
                    - Informational: {examples['informational']}
                    - Transactional: {examples['transactional']}
                    - Navigational: {examples['navigational']}
                    - Local: {examples['local']}
                    
                    Present the questions as a numbered list from 1 to {theme_questions}.
                    """
                elif language == 'es':
                    prompt = f"""
                    Genera EXACTAMENTE {theme_questions} preguntas conversacionales de SEO para:
                    
                    Palabra clave principal: "{keyword}"
                    Tema: "{theme_name}"
                    Conceptos clave: {concepts}
                    Intención: {intention}
                    Ejemplos de sugerencias: {exemples}
                    
                    Las preguntas deben:
                    1. Ser naturales y conversacionales
                    2. Integrar naturalmente el tema "{theme_name}"
                    3. Corresponder a la intención "{intention}"
                    4. Estar optimizadas para búsqueda por voz
                    5. Terminar con signo de interrogación
                    6. Ser variadas y complementarias
                    
                    Formulaciones según la intención:
                    - Informacional: {examples['informational']}
                    - Transaccional: {examples['transactional']}
                    - Navegacional: {examples['navigational']}
                    - Local: {examples['local']}
                    
                    Presenta las preguntas como una lista numerada del 1 al {theme_questions}.
                    """
                elif language in ['pt', 'pt-BR']:
                    prompt = f"""
                    Gera EXATAMENTE {theme_questions} perguntas conversacionais de SEO para:
                    
                    Palavra-chave principal: "{keyword}"
                    Tema: "{theme_name}"
                    Conceitos principais: {concepts}
                    Intenção: {intention}
                    Exemplos de sugestões: {exemples}
                    
                    As perguntas devem:
                    1. Ser naturais e conversacionais
                    2. Integrar naturalmente o tema "{theme_name}"
                    3. Corresponder à intenção "{intention}"
                    4. Estar otimizadas para busca por voz
                    5. Terminar com ponto de interrogação
                    6. Ser variadas e complementares
                    
                    Formulações conforme a intenção:
                    - Informacional: {examples['informational']}
                    - Transacional: {examples['transactional']}
                    - Navegacional: {examples['navigational']}
                    - Local: {examples['local']}
                    
                    Apresenta as perguntas como uma lista numerada de 1 a {theme_questions}.
                    """
                else:  # Default français
                    prompt = f"""
                    Génère EXACTEMENT {theme_questions} questions conversationnelles SEO pour :
                    
                    Mot-clé principal : "{keyword}"
                    Thème : "{theme_name}"
                    Concepts clés : {concepts}
                    Intention : {intention}
                    Exemples de suggestions : {exemples}
                    
                    Les questions doivent :
                    1. Être naturelles et conversationnelles
                    2. Intégrer le thème "{theme_name}" de manière naturelle
                    3. Correspondre à l'intention "{intention}"
                    4. Être optimisées pour la recherche vocale
                    5. Se terminer par un point d'interrogation
                    6. Être variées et complémentaires
                    
                    Formulations selon l'intention :
                    - Informational : {examples['informational']}
                    - Transactional : {examples['transactional']}
                    - Navigational : {examples['navigational']}
                    - Local : {examples['local']}
                    
                    Présente les questions sous forme de liste numérotée de 1 à {theme_questions}.
                    """
                
                response = self.call_gpt4o_mini(prompt, language)
                if response:
                    theme_questions_list = self.extract_questions_from_response(response)
                    for question in theme_questions_list[:theme_questions]:
                        # Déterminer la suggestion Google représentative pour cette question
                        representative_suggestion = keyword  # Fallback par défaut
                        exemples_suggestions = theme.get('exemples_suggestions', [])
                        if exemples_suggestions:
                            representative_suggestion = exemples_suggestions[0]  # Première suggestion du thème
                        
                        all_questions.append({
                            'Question Conversationnelle': question,
                            'Suggestion Google': representative_suggestion,
                            'Thème': theme_name,
                            'Intention': intention,
                            'Concepts': concepts,
                            'Score_Importance': theme.get('importance', 3)
                        })
                        remaining_questions -= 1
        
        return all_questions
    
    def smart_question_generation(self, all_suggestions_with_analysis: List[Dict[str, Any]], target_questions: int) -> List[Dict[str, Any]]:
        """Génère intelligemment les questions en fonction de l'analyse des suggestions"""
        if not all_suggestions_with_analysis:
            return []
        
        # Trier les suggestions par pertinence décroissante
        sorted_suggestions = sorted(
            all_suggestions_with_analysis, 
            key=lambda x: x.get('analysis', {}).get('relevance_score', 0), 
            reverse=True
        )
        
        # Grouper par catégorie et intention pour équilibrer
        categories = {}
        for suggestion in sorted_suggestions:
            analysis = suggestion.get('analysis', {})
            category = analysis.get('category', 'unknown')
            
            if category not in categories:
                categories[category] = []
            categories[category].append(suggestion)
        
        # Calculer la distribution des questions par catégorie
        total_suggestions = len(sorted_suggestions)
        questions_per_suggestion = max(1, target_questions // total_suggestions)
        
        all_generated_questions = []
        questions_generated = 0
        
        # Prioriser les catégories les plus pertinentes
        priority_categories = ['core', 'transactional', 'informational', 'related', 'complementary']
        
        for category in priority_categories:
            if category in categories and questions_generated < target_questions:
                category_suggestions = categories[category][:3]  # Max 3 suggestions par catégorie
                
                for suggestion_data in category_suggestions:
                    if questions_generated >= target_questions:
                        break
                    
                    # Calculer le nombre de questions pour cette suggestion
                    remaining_questions = target_questions - questions_generated
                    analysis = suggestion_data.get('analysis', {})
                    relevance = analysis.get('relevance_score', 5)
                    
                    # Plus la suggestion est pertinente, plus on génère de questions
                    if relevance >= 8:
                        num_questions = min(5, remaining_questions)
                    elif relevance >= 6:
                        num_questions = min(3, remaining_questions)
                    else:
                        num_questions = min(2, remaining_questions)
                    
                    if num_questions > 0:
                        questions = self.generate_contextual_questions(
                            suggestion_data['Mot-clé'],
                            suggestion_data['Suggestion Google'],
                            analysis,
                            num_questions
                        )
                        
                        for question in questions:
                            if questions_generated < target_questions:
                                all_generated_questions.append({
                                    'Mot-clé': suggestion_data['Mot-clé'],
                                    'Suggestion Google': suggestion_data['Suggestion Google'],
                                    'Question Conversationnelle': question,
                                    'Niveau': suggestion_data['Niveau'],
                                    'Parent': suggestion_data['Parent'],
                                    'Catégorie': category,
                                    'Intention': analysis.get('intent', 'unknown'),
                                    'Score_Pertinence': relevance
                                })
                                questions_generated += 1
        
        # Compléter avec les catégories restantes si nécessaire
        for category, suggestions in categories.items():
            if category not in priority_categories and questions_generated < target_questions:
                for suggestion_data in suggestions:
                    if questions_generated >= target_questions:
                        break
                    
                    remaining_questions = target_questions - questions_generated
                    questions = self.generate_contextual_questions(
                        suggestion_data['Mot-clé'],
                        suggestion_data['Suggestion Google'],
                        suggestion_data.get('analysis', {}),
                        min(2, remaining_questions)
                    )
                    
                    for question in questions:
                        if questions_generated < target_questions:
                            analysis = suggestion_data.get('analysis', {})
                            all_generated_questions.append({
                                'Mot-clé': suggestion_data['Mot-clé'],
                                'Suggestion Google': suggestion_data['Suggestion Google'],
                                'Question Conversationnelle': question,
                                'Niveau': suggestion_data['Niveau'],
                                'Parent': suggestion_data['Parent'],
                                'Catégorie': category,
                                'Intention': analysis.get('intent', 'unknown'),
                                'Score_Pertinence': analysis.get('relevance_score', 5)
                            })
                            questions_generated += 1
        
        return all_generated_questions
