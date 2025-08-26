import yaml
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pathlib import Path # 1. Importez la bibliothèque Path

router = APIRouter()

@router.get("/config", response_model=Dict[str, Any])
def get_questionnaire_config():
    """
    Reads the questions.yaml file and returns its content as JSON.
    This allows the frontend to dynamically build the questionnaire.
    """
    try:
        # 2. Construisez un chemin absolu vers le fichier
        # Path(__file__) -> le fichier actuel (questionnaire.py)
        # .parent.parent.parent -> remonte de 3 niveaux (routes -> api -> app -> racine du projet)
        # / "data" / "questions.yaml" -> ajoute le chemin vers votre fichier
        config_path = Path(__file__).parent.parent.parent / "data" / "questions.yaml"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            questions = yaml.safe_load(f)
            return questions.get('questions', {})
            
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Questionnaire configuration file not found.")
    except yaml.YAMLError:
        raise HTTPException(status_code=500, detail="Error parsing the questionnaire configuration file.")
