import streamlit as st
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class AnalysisStep:
    """Représente une étape d'analyse"""
    name: str
    description: str
    status: str = "pending"  # pending, running, completed, error
    progress: int = 0
    error_message: str = ""

class WorkflowManager:
    """Gestionnaire du workflow d'analyse"""
    
    def __init__(self):
        self.steps = []
        self.current_step_index = 0
        self.progress_bar = None
        self.status_text = None
    
    def initialize_workflow(self, enable_dataforseo: bool, generate_questions: bool):
        """Initialiser les étapes du workflow"""
        self.steps = [
            AnalysisStep("collect_suggestions", "🔍 Collecte des suggestions Google"),
        ]
        
        if enable_dataforseo:
            self.steps.extend([
                AnalysisStep("dataforseo_volumes", "📊 Récupération des volumes de recherche"),
                AnalysisStep("dataforseo_ads", "💰 Récupération des suggestions Ads")
            ])
        
        if generate_questions:
            self.steps.extend([
                AnalysisStep("analyze_themes", "🎨 Analyse des thèmes"),
                AnalysisStep("generate_questions", "✨ Génération des questions")
            ])
        
        self.steps.append(AnalysisStep("finalize", "✅ Finalisation"))
    
    def start_workflow(self):
        """Démarrer le workflow avec affichage"""
        self.progress_bar = st.progress(0)
        self.status_text = st.empty()
        self.current_step_index = 0
    
    def update_step(self, step_name: str, status: str, progress: int = None, error_message: str = ""):
        """Mettre à jour une étape"""
        step = next((s for s in self.steps if s.name == step_name), None)
        if step:
            step.status = status
            if progress is not None:
                step.progress = progress
            step.error_message = error_message
            
            self._update_display()
    
    def complete_step(self, step_name: str):
        """Marquer une étape comme terminée"""
        self.update_step(step_name, "completed", 100)
        self.current_step_index += 1
    
    def error_step(self, step_name: str, error_message: str):
        """Marquer une étape en erreur"""
        self.update_step(step_name, "error", error_message=error_message)
    
    def _update_display(self):
        """Mettre à jour l'affichage du progrès"""
        if not self.progress_bar or not self.status_text:
            return
        
        # Calculer le progrès global
        completed_steps = len([s for s in self.steps if s.status == "completed"])
        total_steps = len(self.steps)
        global_progress = int((completed_steps / total_steps) * 100) if total_steps > 0 else 0
        
        # Étape courante
        current_step = None
        for i, step in enumerate(self.steps):
            if step.status in ["running", "pending"]:
                current_step = step
                break
        
        if current_step:
            self.status_text.text(current_step.description)
            if current_step.status == "running" and current_step.progress > 0:
                # Afficher le progrès de l'étape courante
                step_progress = int((completed_steps + current_step.progress / 100) / total_steps * 100)
                self.progress_bar.progress(step_progress)
            else:
                self.progress_bar.progress(global_progress)
        else:
            self.status_text.text("✅ Analyse terminée!")
            self.progress_bar.progress(100)
    
    def finish_workflow(self):
        """Terminer le workflow"""
        if self.progress_bar:
            self.progress_bar.empty()
        if self.status_text:
            self.status_text.empty()
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Obtenir un résumé du statut"""
        return {
            'total_steps': len(self.steps),
            'completed_steps': len([s for s in self.steps if s.status == "completed"]),
            'error_steps': len([s for s in self.steps if s.status == "error"]),
            'current_step': self.current_step_index,
            'steps': self.steps
        }
