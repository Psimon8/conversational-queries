import sqlite3
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import hashlib
import json
import os
from collections import Counter

class Analytics:
    def __init__(self, db_path="analytics.db"):
        """Initialise le système d'analytics avec base de données SQLite"""
        self.db_path = db_path
        self.init_database()
        
    def init_database(self):
        """Crée les tables de la base de données"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table des sessions utilisateurs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                session_end TIMESTAMP,
                api_configured BOOLEAN DEFAULT FALSE,
                language TEXT DEFAULT 'fr'
            )
        """)
        
        # Table des requêtes d'analyse
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                keywords TEXT NOT NULL,
                keywords_count INTEGER,
                level1_count INTEGER DEFAULT 10,
                level2_count INTEGER DEFAULT 0,
                level3_count INTEGER DEFAULT 0,
                generate_questions BOOLEAN DEFAULT TRUE,
                target_questions INTEGER DEFAULT 20,
                language TEXT DEFAULT 'fr',
                suggestions_found INTEGER DEFAULT 0,
                questions_generated INTEGER DEFAULT 0,
                themes_identified INTEGER DEFAULT 0,
                processing_time REAL DEFAULT 0,
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        """)
        
        # Table des exports
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id INTEGER,
                query_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                export_type TEXT NOT NULL,
                file_name TEXT,
                success BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (session_id) REFERENCES sessions (id),
                FOREIGN KEY (query_id) REFERENCES queries (id)
            )
        """)
        
        # Table des événements généraux
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT NOT NULL,
                event_data TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def get_user_id(self):
        """Génère ou récupère un ID utilisateur unique basé sur la session Streamlit"""
        if 'user_id' not in st.session_state:
            # Créer un ID unique basé sur des informations de session
            session_info = f"{st.session_state.get('session_id', '')}{datetime.now().isoformat()}"
            user_id = hashlib.md5(session_info.encode()).hexdigest()[:12]
            st.session_state.user_id = user_id
            st.session_state.session_start = datetime.now()
        return st.session_state.user_id
    
    def start_session(self, api_configured=False, language='fr'):
        """Démarre une nouvelle session utilisateur"""
        user_id = self.get_user_id()
        
        if 'current_session_id' not in st.session_state:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO sessions (user_id, api_configured, language)
                VALUES (?, ?, ?)
            """, (user_id, api_configured, language))
            
            session_id = cursor.lastrowid
            st.session_state.current_session_id = session_id
            
            conn.commit()
            conn.close()
            
        return st.session_state.current_session_id
    
    def end_session(self):
        """Termine la session actuelle"""
        if 'current_session_id' in st.session_state:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE sessions SET session_end = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (st.session_state.current_session_id,))
            
            conn.commit()
            conn.close()
    
    def track_query(self, keywords_list, config, results=None, processing_time=0, error=None):
        """Enregistre une requête d'analyse"""
        user_id = self.get_user_id()
        session_id = self.start_session(
            api_configured=config.get('api_configured', False),
            language=config.get('language', 'fr')
        )
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        keywords_text = '\n'.join(keywords_list)
        suggestions_found = len(results.get('all_suggestions', [])) if results else 0
        questions_generated = len(results.get('final_consolidated_data', [])) if results else 0
        themes_identified = sum(len(themes) for themes in results.get('themes_analysis', {}).values()) if results else 0
        
        cursor.execute("""
            INSERT INTO queries (
                user_id, session_id, keywords, keywords_count,
                level1_count, level2_count, level3_count,
                generate_questions, target_questions, language,
                suggestions_found, questions_generated, themes_identified,
                processing_time, success, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, session_id, keywords_text, len(keywords_list),
            config.get('level1_count', 10), config.get('level2_count', 0), config.get('level3_count', 0),
            config.get('generate_questions', True), config.get('target_questions', 20), config.get('language', 'fr'),
            suggestions_found, questions_generated, themes_identified,
            processing_time, error is None, str(error) if error else None
        ))
        
        query_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return query_id
    
    def track_export(self, query_id, export_type, file_name=None, success=True):
        """Enregistre un export"""
        user_id = self.get_user_id()
        session_id = st.session_state.get('current_session_id')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO exports (user_id, session_id, query_id, export_type, file_name, success)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, session_id, query_id, export_type, file_name, success))
        
        conn.commit()
        conn.close()
    
    def track_event(self, event_type, event_data=None):
        """Enregistre un événement général"""
        user_id = self.get_user_id()
        session_id = st.session_state.get('current_session_id')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        event_data_json = json.dumps(event_data) if event_data else None
        
        cursor.execute("""
            INSERT INTO events (user_id, session_id, event_type, event_data)
            VALUES (?, ?, ?, ?)
        """, (user_id, session_id, event_type, event_data_json))
        
        conn.commit()
        conn.close()
    
    def get_dashboard_data(self, days=30):
        """Récupère les données pour le dashboard"""
        conn = sqlite3.connect(self.db_path)
        
        # Données des derniers X jours
        date_filter = datetime.now() - timedelta(days=days)
        
        # Statistiques générales
        stats = {}
        
        # Sessions
        sessions_df = pd.read_sql_query("""
            SELECT * FROM sessions 
            WHERE session_start >= ?
        """, conn, params=[date_filter])
        stats['total_sessions'] = len(sessions_df)
        stats['unique_users'] = sessions_df['user_id'].nunique()
        
        # Requêtes
        queries_df = pd.read_sql_query("""
            SELECT * FROM queries 
            WHERE timestamp >= ?
        """, conn, params=[date_filter])
        stats['total_queries'] = len(queries_df)
        stats['successful_queries'] = len(queries_df[queries_df['success'] == True])
        stats['avg_processing_time'] = queries_df['processing_time'].mean()
        
        # Exports
        exports_df = pd.read_sql_query("""
            SELECT * FROM exports 
            WHERE timestamp >= ?
        """, conn, params=[date_filter])
        stats['total_exports'] = len(exports_df)
        
        # Événements
        events_df = pd.read_sql_query("""
            SELECT * FROM events 
            WHERE timestamp >= ?
        """, conn, params=[date_filter])
        
        conn.close()
        
        return {
            'stats': stats,
            'sessions': sessions_df,
            'queries': queries_df,
            'exports': exports_df,
            'events': events_df
        }
    
    def create_dashboard(self, days=30):
        """Crée le dashboard d'analytics"""
        st.markdown("## 📊 Analytics & Statistiques d'usage")
        
        data = self.get_dashboard_data(days)
        stats = data['stats']
        
        # Métriques principales
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Sessions totales", stats['total_sessions'])
        with col2:
            st.metric("Utilisateurs uniques", stats['unique_users'])
        with col3:
            st.metric("Requêtes analysées", stats['total_queries'])
        with col4:
            st.metric("Taux de succès", f"{(stats['successful_queries']/max(stats['total_queries'],1)*100):.1f}%")
        with col5:
            st.metric("Temps moyen", f"{stats.get('avg_processing_time', 0):.1f}s")
        
        # Graphiques
        col1, col2 = st.columns(2)
        
        with col1:
            # Évolution des requêtes par jour
            if not data['queries'].empty:
                queries_daily = data['queries'].copy()
                queries_daily['date'] = pd.to_datetime(queries_daily['timestamp']).dt.date
                daily_counts = queries_daily.groupby('date').size()
                
                fig_daily = px.line(
                    x=daily_counts.index, 
                    y=daily_counts.values,
                    title="Requêtes par jour",
                    labels={'x': 'Date', 'y': 'Nombre de requêtes'}
                )
                st.plotly_chart(fig_daily, use_container_width=True)
        
        with col2:
            # Répartition des langues
            if not data['queries'].empty:
                lang_counts = data['queries']['language'].value_counts()
                fig_lang = px.pie(
                    values=lang_counts.values,
                    names=lang_counts.index,
                    title="Répartition des langues"
                )
                st.plotly_chart(fig_lang, use_container_width=True)
        
        # Tableau détaillé des requêtes récentes
        with st.expander("🔍 Requêtes récentes"):
            if not data['queries'].empty:
                recent_queries = data['queries'].sort_values('timestamp', ascending=False).head(20)
                display_queries = recent_queries[[
                    'timestamp', 'keywords_count', 'language', 
                    'suggestions_found', 'questions_generated', 
                    'processing_time', 'success'
                ]].copy()
                display_queries.columns = [
                    'Horodatage', 'Nb mots-clés', 'Langue', 
                    'Suggestions trouvées', 'Questions générées', 
                    'Temps (s)', 'Succès'
                ]
                st.dataframe(display_queries, use_container_width=True)
        
        # Analyse des mots-clés populaires
        with st.expander("🎯 Mots-clés populaires"):
            if not data['queries'].empty:
                all_keywords = []
                for keywords_text in data['queries']['keywords'].dropna():
                    keywords_list = keywords_text.split('\n')
                    all_keywords.extend([kw.strip().lower() for kw in keywords_list if kw.strip()])
                
                if all_keywords:
                    keyword_counts = Counter(all_keywords)
                    popular_keywords = keyword_counts.most_common(20)
                    
                    keywords_df = pd.DataFrame(popular_keywords, columns=['Mot-clé', 'Fréquence'])
                    
                    fig_keywords = px.bar(
                        keywords_df, 
                        x='Fréquence', 
                        y='Mot-clé',
                        orientation='h',
                        title="Top 20 des mots-clés les plus recherchés"
                    )
                    fig_keywords.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig_keywords, use_container_width=True)
        
        # Performances par configuration
        with st.expander("⚙️ Analyse des configurations"):
            if not data['queries'].empty:
                config_stats = data['queries'].groupby(['level1_count', 'generate_questions']).agg({
                    'processing_time': 'mean',
                    'success': 'mean',
                    'suggestions_found': 'mean',
                    'questions_generated': 'mean'
                }).round(2)
                
                st.markdown("**Performances moyennes par configuration:**")
                st.dataframe(config_stats, use_container_width=True)
    
    def export_analytics_data(self, days=30):
        """Exporte les données d'analytics"""
        data = self.get_dashboard_data(days)
        
        # Créer un fichier Excel avec plusieurs feuilles
        from io import BytesIO
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Statistiques générales
            stats_df = pd.DataFrame([data['stats']])
            stats_df.to_excel(writer, sheet_name='Statistiques', index=False)
            
            # Requêtes
            if not data['queries'].empty:
                data['queries'].to_excel(writer, sheet_name='Requetes', index=False)
            
            # Sessions
            if not data['sessions'].empty:
                data['sessions'].to_excel(writer, sheet_name='Sessions', index=False)
            
            # Exports
            if not data['exports'].empty:
                data['exports'].to_excel(writer, sheet_name='Exports', index=False)
        
        output.seek(0)
        return output

# Instance globale d'analytics
analytics = Analytics()
