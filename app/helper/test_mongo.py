from typing import Dict, List, Any
from fuzzywuzzy import fuzz
import logging

logger = logging.getLogger(__name__)



# Simuler l'entrée de l'utilisateur
structured_analysis = {
    'keywords': ['mal', 'dos', 'urgent'],
    'symptoms': [{'category': 'douleur', 'keyword': 'mal'}],
    'urgency_level': 0.9
}
user_symptoms = {'douleur'}


# Recommender class
class Recommender:
    def __init__(self, top_n: int = 3):
        self.top_n = top_n
        self.db = None  # Not used in this simulation
        self.practice = {
    "_id": "acupuncture_002",
    "practice": {
        "name": "Acupuncture",
        "category": "Pratiques Énergétiques",
        "subcategory": "Médecine Traditionnelle Chinoise",
        "popularity_rank": 2,
        "availability": "high",
        "regulation_status": "regulated"
    },
    "indications": {
        "primary": [
            {"condition": "douleurs_chroniques", "icd_10": ['M79.3', 'M25.5'], "effectiveness_score": 0.88, "evidence_level": "high", "typical_sessions": 6},
            {"condition": "migraines", "icd_10": ['G43'], "effectiveness_score": 0.8, "evidence_level": "high", "typical_sessions": 8}
        ],
        "secondary": ['stress_anxiete', 'troubles_sommeil', 'allergies_saisonnieres'],
        "preventive": ['equilibre_energetique', 'renforcement_immunitaire']
    },
    "keywords": {
        "symptoms": ['douleur', 'migraine', 'stress', 'insomnie', 'fatigue'],
        "desires": ['equilibre', 'energie', 'soulagement', 'relaxation'],
        "concepts": ['meridiens', 'qi', 'yin_yang']
    }}


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

    def recommend(self, nlp_analysis: Dict[str, Any]) -> List[Dict]:
        """
        Recommends practices by combining embedding similarity, keyword matching,
        and urgency level.
        """
        structured_analysis = nlp_analysis.get("structured_analysis", {})
        user_symptoms = {s['category'] for s in structured_analysis.get('symptoms', [])}

        print(f"Structured analysis: {structured_analysis} , User Symptoms: {user_symptoms}")

        # Simulating fetching all practices (in this case, just one practice for the example)
        all_practices = [self.practice]

        scored_practices = []

        for practice in all_practices:
            practice_indications = practice.get("indications", {})
            primary_indications = {p.get('condition') for p in practice_indications.get("primary", [])}
            secondary_indications = set(practice_indications.get("secondary", []))
            practice_keywords = set(practice.get("keywords", {}).get("symptoms", []))

            # Normalize user symptoms for keyword matching
            normalized_user_symptoms = {self._normalize_keyword(symptom) for symptom in user_symptoms}

            matched_symptoms_count = 0

            # Check for exact matches in primary and secondary indications
            matched_symptoms_count += len(normalized_user_symptoms.intersection(primary_indications.union(secondary_indications)))

            # Check for fuzzy matches between user symptoms and practice keywords
            for user_symptom in normalized_user_symptoms:
                if self._fuzzy_match(user_symptom, practice_keywords):
                    matched_symptoms_count += 1

            print(f"Practice: {practice['practice']['name']}, Matched Symptoms Count: {matched_symptoms_count}")  # Debugging line

            # Final score calculation based on matched symptoms
            final_score = matched_symptoms_count  # You can apply a score calculation here if necessary

            if final_score > 0:
                scored_practices.append({
                    "practice_name": practice["practice"]["name"],
                    "score_de_pertinence": final_score,
                    "matched_symptoms": list(normalized_user_symptoms),
                    "_id": str(practice["_id"])
                })

        # Sort the practices by the relevance score
        scored_practices.sort(key=lambda x: x["score_de_pertinence"], reverse=True)

        print(f"Top 3 practices: {[p['score_de_pertinence'] for p in scored_practices[:3]]}")
        
        return scored_practices[:self.top_n]

# Execute the recommendation
recommender = Recommender(top_n=3)
nlp_analysis = {
    "structured_analysis": {
        "keywords": ['mal', 'dos', 'urgent'],
        "symptoms": [{'category': 'douleur', 'keyword': 'mal'}],
        "urgency_level": 0.9
    }
}
recommendations = recommender.recommend(nlp_analysis)
print(recommendations)
