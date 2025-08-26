import torch
from sklearn.metrics.pairwise import cosine_similarity
from typing import Dict, List, Any
from app.utils.database import get_database
from fuzzywuzzy import fuzz
import logging

logger = logging.getLogger(__name__)




class Recommender:
    def __init__(self, top_n: int = 3):
        self.top_n = top_n
        self.db = None

    async def _get_all_practices(self) -> List[Dict]:
        """Fetches all practice documents from MongoDB."""
        if not self.db:
            self.db = await get_database()
        cursor = self.db.practices.find({})
        return await cursor.to_list(length=None)
    

    async def _get_feedback_stats(self):
        """
        Calcule les stats de feedback par pratique :
        - moyenne des notes
        - nombre total de feedbacks
        - confiance (plus de feedbacks = plus de poids)
        """

        pipeline = [
            {
                "$group": {
                    "_id": "$practice_name",
                    "avg_rating": {"$avg": "$rating"},
                    "count": {"$sum": 1},
                    "total_rating": {"$sum": "$rating"}
                }
            },
            {
                "$project": {
                    "avg_rating": 1,
                    "count": 1,
                    "normalized_rating": {
                        "$divide": [
                            {"$subtract": ["$total_rating", "$count"]},  # normalise 1-5 → 0-4
                            {"$multiply": ["$count", 4]}                # max possible = 4 * count
                        ]
                    }
                }
            }
        ]

        cursor = self.db.feedbacksv1.aggregate(pipeline)
        result = await cursor.to_list(length=None)

        # Convertir en dictionnaire par nom de pratique
        stats = {item["_id"]: item for item in result}
        logger.info(f"Loaded feedback stats for {len(stats)} practices")
        return stats


#### ici j'ajoute un 2e lot d'analyse nlp ####
    def _normalize_keyword(self, keyword: str) -> str:
        """Normalise the keyword by lowercasing it."""
        return keyword.lower()

    def _fuzzy_match(self, keyword: str, practice_keywords: List[str]) -> bool:
        """
        Uses fuzzy matching to check if a user's keyword matches a practice's keyword
        even with variations.
        """
        for practice_keyword in practice_keywords:
            if fuzz.partial_ratio(keyword, practice_keyword) > 80:  # fuzzy match threshold
                return True
        return False
#### fin du 2e lot d'analyse nlp ####

    async def recommend(self, nlp_analysis: Dict[str, Any]) -> List[Dict]:
        """
        Recommends practices by combining embedding similarity, keyword matching,
        and urgency level.
        """
        user_embedding = nlp_analysis.get("user_embedding")
        if user_embedding is None:
            return []

        structured_analysis = nlp_analysis.get("structured_analysis", {})
        user_symptoms = {s['category'] for s in structured_analysis.get('symptoms', [])}
        #urgency_level = structured_analysis.get('urgency_level', {}) # Get urgency from analysis

        logger.info(f"structured analysis {structured_analysis} , User Symptoms: {user_symptoms}")

        
        all_practices = await self._get_all_practices()
        feedback_stats = await self._get_feedback_stats() #get the collecytion of feedbacks
        scored_practices = []

        for practice in all_practices:

            practice_name = practice["practice"]["name"]
            # 1. Semantic Similarity Score (Embeddings)
            practice_embedding = torch.tensor(practice["embedding"])
            embedding_score = cosine_similarity(
                user_embedding.cpu().reshape(1, -1), 
                practice_embedding.reshape(1, -1)
            )[0][0]
            
            # 2. Keyword Matching
            practice_indications = practice.get("indications", {})
            # Correctly extract condition strings
            primary_indications = {p.get('condition') for p in practice_indications.get("primary", [])}
            secondary_indications = set(practice_indications.get("secondary", []))
            practice_keywords = set(practice.get("keywords", {}).get("symptoms", []))

            #logging.info(f"primary indications: {primary_indications}, secondary indications: {secondary_indications}") 

            # Normalize user symptoms for keyword matching
            normalized_user_symptoms = {self._normalize_keyword(symptom) for symptom in user_symptoms}

            matched_symptoms_count = 0

            matched_symptoms_count += len(normalized_user_symptoms.intersection(primary_indications.union(secondary_indications)))
            
            # Check for fuzzy matches between user symptoms and practice keywords
            for user_symptom in normalized_user_symptoms:
                if self._fuzzy_match(user_symptom, practice_keywords):
                    matched_symptoms_count += 1
          
            # 3. Combinaison des scores et ajustement par le niveau d'urgence
            # Le score final est une moyenne pondérée, ajustée par l'urgence pour prioriser les cas graves

            logging.info(f"Practice: {practice['practice']['name']}, Embedding Score: {embedding_score}, Matched Symptoms Count: {matched_symptoms_count}")
            final_score = (embedding_score * 0.5) + (matched_symptoms_count * 0.5)
            final_score *= (1 + nlp_analysis["structured_analysis"]['urgency_level'])


            # --- 5. Feedback Adjustment ---  ajouter un weight du feedback

            feedback_weight = 1.0  # par défaut
            if practice_name in feedback_stats:
                stat = feedback_stats[practice_name]
                avg_rating = stat["avg_rating"]
                count = stat["count"]

                # Lissage : plus de feedbacks = plus de confiance
                # Ex: 5 feedbacks de 4/5 → poids 1.2, 1 feedback de 1/5 → impact faible
                confidence = min(count / 50, 1.0)  # max 20 feedbacks = poids max
                rating_factor = (avg_rating - 3) / 2  # 1→-1, 3→0, 5→+1
                feedback_weight = 1 + (rating_factor * confidence)

            final_score = final_score * feedback_weight



            if final_score > 0:
                scored_practices.append({
                "practice_name": practice["practice"]["name"],
                "relevance_score": float(final_score),
                "matched_symptoms": list(user_symptoms),
                "feedback_weight": feedback_weight,
                "_id": str(practice["_id"]) # Ensure ID is a string
            })

        scored_practices.sort(key=lambda x: x["relevance_score"], reverse=True)

        logger.info(f"Top 3 scores: {[p['relevance_score'] for p in scored_practices[:3]]}")

        return scored_practices[:self.top_n]

            

"""          
            practice_indications = practice.get("indications", {})
            # Correctly extract condition strings
            primary_indications = {p.get('condition') for p in practice_indications.get("primary", [])}
            secondary_indications = set(practice_indications.get("secondary", []))
            
            # Count how many of the user's symptoms match the practice's indications
            matched_symptoms_count = len(user_symptoms.intersection(primary_indications.union(secondary_indications)))
            
            # Normalize keyword score
            normalized_keyword_score = matched_symptoms_count / len(user_symptoms) if user_symptoms else 0

            # 3. Combine scores (weighted average)
            combined_score = (float(embedding_score) * 0.5) + (normalized_keyword_score * 0.5)

            # --- 4. APPLY THE URGENCY MULTIPLIER (from your POC) ---
            final_score = combined_score * (1 + urgency_level)

            scored_practices.append({
                "practice_name": practice["practice"]["name"],
                "relevance_score": float(final_score),
                "matched_symptoms": list(user_symptoms),
                "_id": str(practice["_id"]) # Ensure ID is a string
            })

        # Sort and return top N results
        scored_practices.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        logger.info(f"Top 3 scores: {[p['relevance_score'] for p in scored_practices[:3]]}")

        return scored_practices[:self.top_n]"""
