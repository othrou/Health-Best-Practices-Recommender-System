# app/api/routes/feedback.py

from fastapi import APIRouter, Depends, HTTPException
from app.models.models import Feedback
from app.utils.database import get_database
import logging
from datetime import datetime,timezone
from app.monitoring.monitoring import FEEDBACK_RECEIVED

# Logger
logger = logging.getLogger(__name__)
logger.info("✅ Routeur Feedback chargé !")

router = APIRouter()

@router.post("/", status_code=201)
async def submit_feedback(feedback: Feedback):
    """
    Reçoit un feedback utilisateur et le sauvegarde dans MongoDB.
    """
    try:
        # Récupère la collection MongoDB
        db = await get_database()
        collection = db["feedbacks_v1"]  # ou le nom que tu veux

        # Convertit le feedback en dictionnaire
        feedback_data = feedback.model_dump()

        # Ajoute un timestamp (optionnel)
        from datetime import datetime
        feedback_data["created_at"] = datetime.now(timezone.utc)

        # Insère dans MongoDB
        result = await collection.insert_one(feedback_data)

        # Log + métrique Prometheus
        logger.info(f"Feedback sauvegardé avec ID {result.inserted_id}: {feedback}")
        FEEDBACK_RECEIVED.labels(rating=str(feedback.rating)).inc()

        return {"message": "Feedback reçu avec succès"}

    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde du feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")
    



