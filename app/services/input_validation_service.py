import logging
import json
from typing import Dict, List
from agno.agent import Agent
from agno.models.google import Gemini
from app.config import Settings
from fuzzywuzzy import fuzz


logger = logging.getLogger(__name__)

# Liste des mots-clés d'urgence. À enrichir en consultation avec des professionnels.
RED_FLAGS = [
    "douleur thoracique", "douleur poitrine", "pression poitrine", "serrement poitrine",
    "difficulté à respirer", "souffle court", "étouffement",
    "perte de conscience", "évanouissement",
    "confusion soudaine", "difficulté à parler",
    "engourdissement visage", "engourdissement bras", "engourdissement jambe",
    "saignement incontrôlable", "hémorragie",
    "pensées suicidaires", "faire du mal"
]

class InputValidationService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.context_analysis_agent = Agent(
            name="Analyseur de Contexte Utilisateur",
            model=Gemini(id=self.settings.GEMINI_MODEL_NAME, temperature=0.0),
            instructions=self._get_agent_prompt(),
            show_tool_calls=False,
            markdown=True,
        )
        logger.info("🤖 Agent d'analyse de contexte initialisé.")

    def _get_agent_prompt(self) -> str:
        return """
        Tu es un assistant IA expert en analyse de texte. Ta mission est d'évaluer la demande d'un utilisateur pour un système de recommandation de bien-être.
        Tu dois corriger le texte, évaluer s'il contient assez d'informations pour une recommandation pertinente, et retourner ta réponse dans un format JSON strict.

        ## TÂCHES
        1.  **Correction**: Corrige les fautes d'orthographe et de grammaire du texte fourni.
        2.  **Analyse de Contexte**: Évalue si le texte corrigé contient des informations suffisantes. Un contexte suffisant doit décrire un ou plusieurs symptômes, une durée, une intensité ou un contexte émotionnel sans etre exhaustif. Un simple "je suis fatigué" est insuffisant. "Je suis épuisé depuis des semaines et je n'arrive plus à me concentrer au travail" est suffisant.
        3.  **Génération de Question**: Si le contexte est insuffisant, formule UNE seule question ouverte et bienveillante pour encourager l'utilisateur à donner plus de détails.
        4.  **Notation**: Donne un score de confiance de 0.0 à 1.0 sur la suffisance du contexte, en cas de doute donne un score supérieur à 0.4.

        ## FORMAT DE SORTIE
        Ta réponse doit être UNIQUEMENT un objet JSON valide, sans aucun autre texte avant ou après. Voici la structure :
        {
          "corrected_text": "Le texte de l'utilisateur après correction.",
          "context_sufficient": true,
          "confidence_score": 0.9,
          "clarifying_question": null,
          "reasoning": "L'utilisateur décrit plusieurs symptômes et un contexte."
        }

        Si le contexte est insuffisant :
        {
          "corrected_text": "Le texte de l'utilisateur après correction.",
          "context_sufficient": false,
          "confidence_score": 0.2,
          "clarifying_question": "J'ai besoin de plus de contexte. Pourriez-vous m'en dire un peu plus sur ce que vous ressentez ?",
          "reasoning": "Le texte est trop court et ne décrit pas de symptôme précis."
        }
        """

    def check_for_red_flags(self, text: str) -> bool:
        """Vérifie la présence de mots-clés d'urgence dans le texte."""
        text_lower = text.lower()
        for flag in RED_FLAGS:
            if flag in text_lower:
                logger.warning(f"🚩 Red Flag détecté : '{flag}' dans le texte de l'utilisateur.")
                return True
            if fuzz.partial_ratio(text_lower, flag) > 80: 
                logger.warning(f"🚩 Red Flag détecté : '{flag}' dans le texte de l'utilisateur.")
                return True
        return False


    async def validate_and_process_input(self, text: str) -> Dict:
        """
        Orchestre la validation complète : vérification d'urgence puis analyse par l'agent.
        """
        # 1. Vérification des cas d'urgence
        if self.check_for_red_flags(text):
            return {
                "status": "emergency",
                "message": "Vos symptômes semblent nécessiter une attention médicale immédiate. Veuillez consulter un professionnel de santé sans tarder."
            }

        # 2. Analyse par l'agent IA
        try:
            response = await self.context_analysis_agent.arun(text)
            content = response.content

            # Supprimer les balises de bloc de code Markdown si elles existent
            if content.strip().startswith("```json"):
                content = content.strip()[7:-3].strip() # Enlève ```json et ```

            analysis_result = json.loads(content)
            
            # 3. Décision basée sur le score de confiance
            if analysis_result["confidence_score"] < 0.4:
                analysis_result["status"] = "insufficient"
            else:
                analysis_result["status"] = "ok"
            
            return analysis_result

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Erreur lors de l'analyse du contexte par l'agent : {e}. Réponse de l'agent : {response.content}")
            # Fallback de sécurité : on considère le contexte comme suffisant pour ne pas bloquer l'utilisateur
            return {
                "status": "ok",
                "corrected_text": text,
                "reasoning": "Fallback: L'analyse de l'agent a échoué, on procède avec le texte original."
            }
