#!/usr/bin/env python3
"""
Script de test pour vérifier que l'application peut être importée correctement
"""
import sys
import os

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Tester les imports principaux de l'application"""
    try:
        print("🔍 Test des imports...")

        # Test des imports principaux
        from utils.config_manager import ConfigManager
        print("✅ ConfigManager importé avec succès")

        from utils.export_manager import ExportManager
        print("✅ ExportManager importé avec succès")

        from utils.ui_components import render_header, render_metrics
        print("✅ UIComponents importé avec succès")

        from utils.workflow_manager import WorkflowManager
        print("✅ WorkflowManager importé avec succès")

        from utils.results_manager import ResultsManager
        print("✅ ResultsManager importé avec succès")

        from services.dataforseo_service import DataForSEOService
        print("✅ DataForSEOService importé avec succès")

        from google_suggestions import GoogleSuggestionsClient
        print("✅ GoogleSuggestionsClient importé avec succès")

        # Test de l'initialisation des classes
        print("\n🔧 Test de l'initialisation...")

        config_manager = ConfigManager()
        print("✅ ConfigManager initialisé")

        workflow = WorkflowManager()
        print("✅ WorkflowManager initialisé")

        print("\n🎉 Tous les tests d'import réussis !")
        print("L'application devrait maintenant fonctionner correctement.")

        return True

    except Exception as e:
        print(f"❌ Erreur lors du test : {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)