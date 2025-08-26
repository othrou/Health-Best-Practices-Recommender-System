from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from app.models.models import FreeTextRequest, QuestionnaireRequest, RecommendationResponse, ErrorResponse
from app.services.nlp_analyzer import NLPAnalyzer
from app.services.recommender import Recommender
from app.services.rag_agent_service import RAGAgentService
from app.utils.dependencies import get_nlp_analyzer, get_recommender, get_rag_agent_service
from app.utils.database import get_database
from app.monitoring.monitoring import RECOMMENDATION_REQUESTS, RECOMMENDATION_LATENCY, API_ERRORS
from app.utils.dependencies import get_input_validation_service
from app.services.input_validation_service import InputValidationService


import logging 


# 2. Get a logger instance for this specific file
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/recommendations/free-text", 
             response_model=RecommendationResponse,
             responses={404: {"model": ErrorResponse},
                        400: {"model": ErrorResponse, "description": "Requête invalide ou contexte insuffisant"},
                        429: {"model": ErrorResponse, "description": "Cas d'urgence détecté"}     
                        })
async def recommend_from_text(
    request: FreeTextRequest,
    validation_service: InputValidationService = Depends(get_input_validation_service),
    nlp_analyzer: NLPAnalyzer = Depends(get_nlp_analyzer),
    recommender: Recommender = Depends(get_recommender),
    rag_agent: RAGAgentService = Depends(get_rag_agent_service)
):
    """
    Receives free text from a user (transcripted speech or other), analyzes it, and returns a practice recommendation
    with detailed, AI-generated advice.
    """
    #print(f"Received free-text request: {request}") # Debugging line
    #print(f"Received free-text request: {request.text}") # Debugging line

    input_type = 'free_text' # j'ai ajouté cette ligne pour les métriques prometheus

    logger.info(f"Received free-text request for session: {request.session_id}")


    # Valider l'entrée utilisateur

    # --- NOUVEAU FLUX DE VALIDATION ---
    if request.text:
        validation_result = await validation_service.validate_and_process_input(request.text)

        # premier check d'urgence : mots clés qui nécessitent une action immédiate
        if validation_result["status"] == "emergency":
            raise HTTPException(status_code=429, detail=validation_result["message"])
        
        # Deuxième check : le contexte est-il suffisant pour une recommandation fiable ?
        if validation_result["status"] == "insufficient":
            raise HTTPException( status_code=400, detail="Le contexte fourni est insuffisant pour générer une recommandation fiable, " \
            "veuillez fournir plus de détails sur vos symptômes, vous pouvez également répondre à un questionnaire pour obtenir une recommandation plus précise.")

        
        # Le contexte est suffisant, on utilise le texte corrigé
        # 1. Analyze input
        logger.info("Starting NLP analysis on free text...")
        logger.info(f"✅ Text to analyze: {validation_result['corrected_text']}")
        text_to_analyze = validation_result["corrected_text"]
        nlp_analysis = nlp_analyzer.analyze_free_text(text_to_analyze)

    elif request.responses:
        # Pour le questionnaire, on saute la validation de contexte
        nlp_analysis = nlp_analyzer.analyze_questionnaire_responses(request.responses)
    else:
        raise HTTPException(status_code=400, detail="Request must contain either 'text' or 'responses'.")
    # --- FIN DU NOUVEAU FLUX DE VALIDATION ---

    
    #nlp_analysis = nlp_analyzer.analyze_free_text(request.text)
    if not nlp_analysis or nlp_analysis.get("user_embedding") is None:

        API_ERRORS.labels(error_type='nlp_analysis').inc() # Incrémenter le compteur d'erreur (metrique promotheus)
        logger.error(f"NLP analysis failed for session: {request.session_id}. Input text was empty or invalid.")
        raise HTTPException(status_code=400, detail="Could not process input text.")
    logger.info("NLP analysis successful.")

    # 2. Get top recommendations
    logger.info("Fetching recommendations...")
    recommendations = await recommender.recommend(nlp_analysis)
    if not recommendations:
        RECOMMENDATION_REQUESTS.labels(input_type=input_type, match_found='false').inc() # Incrémenter le compteur
        logger.warning(f"No recommendations found for session: {request.session_id}")
        return ErrorResponse(
            session_id=request.session_id,
            error="No Match Found",
            message="D'après les informations que vous m'avez données, je ne trouve pas de correspondance parfaite dans ma base de connaissances actuelle."
        )
    
    RECOMMENDATION_REQUESTS.labels(input_type=input_type, match_found='true').inc() # Incrémenter le compteur prometheus
    top_recommendation = recommendations[0]
    practice_name = top_recommendation.get("practice_name")
    logger.info(f"Found {len(recommendations)} recommendations. Top choice for session {request.session_id}: {top_recommendation.get('practice_name')}")
    
    # 3. Fetch full data for the top recommended practice (BUG FIX: This block was commented out)
    
    practice_id = top_recommendation.get("_id")
    logger.info(f"Fetching data for practice ID: {practice_id}")
    db = await get_database()
    practice_data = await db.practices.find_one({"_id": practice_id})

    #  Extraire les besoins de l'utilisateur pour l'agent RAG
    user_needs_list = [s['keyword'] for s in nlp_analysis.get("structured_analysis", {}).get("symptoms", [])]
    user_needs = ", ".join(user_needs_list)
    
    if not practice_data:
        logger.error(f"Practice with ID {top_recommendation.get('_id')} found in recommender but not in DB.")
        raise HTTPException(status_code=404, detail=f"Practice with ID {top_recommendation.get('_id')} not found.")

    # 4. Generate detailed advice with RAG agent
    generated_advice = await rag_agent.generate_advice(
        user_needs=user_needs,
        practices=recommendations[:2]
    )
    logger.info("Advice generated successfully.")


    # 5. Formater et retourner la réponse finale
    logger.info(f"Sending successful response for session: {request.session_id}")
    return RecommendationResponse(
        session_id=request.session_id,
        recommended_practice=top_recommendation,
        generated_advice=generated_advice,
        sources=[{"name": practice_name, "description": "Internal Knowledge Base"}]
    )

    


# Endpoint for questionnaire-based recommendations

@router.post("/recommendations/questionnaire", 
             response_model=RecommendationResponse,
             responses={404: {"model": ErrorResponse}})
async def recommend_from_questionnaire(
    request: QuestionnaireRequest,
    nlp_analyzer: NLPAnalyzer = Depends(get_nlp_analyzer),
    recommender: Recommender = Depends(get_recommender),
    rag_agent: RAGAgentService = Depends(get_rag_agent_service)
):
    """
    Receives questionnaire responses, analyzes them, and returns a practice
    recommendation with detailed, AI-generated advice.
    """
    input_type = 'free_text'

    logger.info(f"Received questionnaire request for session: {request.session_id}")

    # 1. Analyze questionnaire responses directly
    logger.info("Starting NLP analysis on questionnaire responses...")
    nlp_analysis = nlp_analyzer.analyze_questionnaire_responses(request.responses)
    if not nlp_analysis or nlp_analysis.get("user_embedding") is None:
        API_ERRORS.labels(error_type='nlp_analysis').inc() 
        logger.error(f"NLP analysis failed for session: {request.session_id}. Questionnaire response was empty or invalid.")
        raise HTTPException(status_code=400, detail="Could not process questionnaire responses.")
    logger.info(f"NLP analysis successful{nlp_analysis}")

    # 2. Get top recommendations
    logger.info("Fetching recommendations...")
    recommendations = await recommender.recommend(nlp_analysis)
    logger.info(f"Recommendations fetched: {len(recommendations)} found.")
    if not recommendations:
        RECOMMENDATION_REQUESTS.labels(input_type=input_type, match_found='false').inc()
        logger.warning(f"No recommendations found for session: {request.session_id}")
        return ErrorResponse(
            session_id=request.session_id,
            error="No Match Found",
            message="D'après les informations que vous m'avez données, je ne trouve pas de correspondance parfaite dans ma base de connaissances actuelle."
        )
    RECOMMENDATION_REQUESTS.labels(input_type=input_type, match_found='false').inc()
    top_recommendation = recommendations[0]
    second_rank_recommendation = recommendations[1] if len(recommendations) > 1 else None #on garde la deuxième recommandation pour l'afficher dans le cas où l'utilisateur n'aime pas la première
    practice_name = top_recommendation.get("practice_name")
    logger.info(f"Found {len(recommendations)} recommendations. Top choice for session {request.session_id}: {top_recommendation.get('practice_name')}")

    # 3. Fetch full data for the top recommended practice
    logger.info(f"Fetching data for practice ID: {top_recommendation.get('_id')}")
    db = await get_database()
    practice_data = await db.practices.find_one({"_id": top_recommendation.get("_id")})
    
    if not practice_data:
        logger.error(f"Practice with ID {top_recommendation.get('_id')} found in recommender but not in DB.")
        raise HTTPException(status_code=404, detail=f"Practice with ID {top_recommendation.get('_id')} not found.")

    #  Extraire les besoins de l'utilisateur pour l'agent RAG
    user_needs_list = [s['keyword'] for s in nlp_analysis.get("structured_analysis", {}).get("symptoms", [])]
    user_needs = ", ".join(user_needs_list)


    # 4. Generate detailed advice with RAG agent
    generated_advice = await rag_agent.generate_advice(
        user_needs=user_needs,
        practice_name=practice_name
    )
    logger.info("Advice generated successfully.")


    # 5. Formater et retourner la réponse finale
    logger.info(f"Sending successful response for session: {request.session_id}")
    return RecommendationResponse(
        session_id=request.session_id,
        recommended_practice=top_recommendation,
        generated_advice=generated_advice,
        sources=[{"name": practice_name, "description": "Internal Knowledge Base"}]
    )




