from app.services.nlp_analyzer import NLPAnalyzer
from app.services.recommender import Recommender
from app.services.rag_agent_service import RAGAgentService
from app.config import get_settings
from fastapi import Request
from app.services.input_validation_service import InputValidationService





def get_nlp_analyzer(request: Request) -> NLPAnalyzer:
    # Cette fonction instancie notre service unifié.
    return request.app.state.nlp_analyzer

def get_recommender() -> Recommender:
    return Recommender()


def get_rag_agent_service(request: Request) -> RAGAgentService:
    """
    Récupère l'instance unique du RAGAgentService qui a été
    pré-chargée au démarrage de l'application via la fonction lifespan.
    """
    return request.app.state.rag_service


def get_input_validation_service(request: Request) -> InputValidationService:
    """Récupère l'instance unique du service de validation."""
    return request.app.state.validation_service





