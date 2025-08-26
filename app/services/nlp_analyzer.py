import spacy
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
from functools import lru_cache
import torch
from app.config import get_settings

@lru_cache(maxsize=1)
def get_nlp_resources():
    """Charge et met en cache les modèles NLP pour éviter de les recharger à chaque requête."""
    settings = get_settings()
    print("Chargement des ressources NLP (spaCy et SentenceTransformer)...")
    # Utilisation du modèle Spacy 
    nlp = spacy.load("fr_core_news_lg")
    # Utilisation du modèle d'embedding spécifié dans le notebook
    embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
    print("Ressources NLP chargées.")
    return nlp, embedding_model

class NLPAnalyzer:
    """
    Un service unifié pour analyser à la fois le texte libre et les réponses structurées
    d'un questionnaire.
    """
    def __init__(self):
        self.nlp, self.embedding_model = get_nlp_resources()
        # Mots-clés enrichis basés sur le notebook
        self.holistic_keywords = {
    'stress': ['stress', 'anxiété', 'angoisse', 'nervosité', 'tension', 'éprouver du stress', 'irritabilité', 'pression', 'tension nerveuse', 'stress_anxiety'],
    'douleur': ['douleur', 'mal', 'souffrance', 'inflammation', 'douleur physique', 'back_pain_specific', 'cervicalgie', 'lombalgie', 'mal de dos', 'tensions musculaires', 'douleur persistante', 'physical_pain'],
    'fatigue': ['fatigue', 'épuisement', 'burnout', 'surmenage', 'manque d’énergie', 'épuisement mental', 'fatigue chronique', 'épuisement physique'],
    'sommeil': ['insomnie', 'sommeil', 'dormir', 'cauchemar', 'troubles du sommeil', 'sommeil agité', 'dérèglement du sommeil', 'sleep_issues', 'fatigue liée au sommeil', 'trouble du sommeil'],
    'digestion': ['digestion', 'ventre', 'intestin', 'estomac', 'troubles digestifs', 'ballonnements', 'indigestion', 'digestive', 'problèmes digestifs', 'mal de ventre', 'acidité gastrique']
}


    def _dict_to_text(self, data: Dict[str, Any]) -> str:
        """Convertit un dictionnaire de réponses de QCM en une phrase lisible."""
        parts = []
        for key, values in data.items():
            # Remplace les clés techniques par des termes compréhensibles
            key_fr = key.replace('_', ' ').replace('main concern', 'préoccupation principale').replace('pain location', 'localisation de la douleur')
            if isinstance(values, list):
                value_fr = ", ".join(str(v).replace('_', ' ') for v in values)
                parts.append(f"{key_fr} est {value_fr}")
            else:
                parts.append(f"{key_fr} est {str(values).replace('_', ' ')}")
        # Joindre toutes les parties en une seule phrase descriptive
        return ". ".join(parts) + "."

    def _extract_keywords(self, doc) -> List[str]:
        """Extrait les mots-clés pertinents (Noms, Adjectifs, Verbes)."""
        keywords = []
        for token in doc:
            # Utiliser le lemme pour la normalisation et ignorer les mots vides
            if token.pos_ in ['NOUN', 'ADJ', 'VERB'] and not token.is_stop:
                keywords.append(token.lemma_.lower())  # Assurez-vous de convertir en minuscules
        return list(set(keywords))  # Supprimer les doublons

    
    def _identify_symptoms(self, doc) -> List[Dict[str, Any]]:
        """Identifie les catégories de symptômes basées sur les mots-clés."""
        symptoms = []
        text_lower = doc.text.lower()  # Convertir le texte en minuscules pour rendre la comparaison insensible à la casse
        
        for category, keywords in self.holistic_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:  # Assurez-vous que la recherche est insensible à la casse
                    symptoms.append({'category': category, 'keyword': keyword})
        
        # Supprimer les doublons
        return [dict(t) for t in {tuple(d.items()) for d in symptoms}]


    def _identify_symptoms(self, doc) -> List[Dict[str, Any]]:
        """Identifie les catégories de symptômes basées sur les mots-clés."""
        symptoms = []
        text_lower = doc.text.lower()
        for category, keywords in self.holistic_keywords.items():
            for keyword in keywords:
                if keyword.replace('_', ' ') in text_lower: # Gérer les espaces dans les mots-clés
                    symptoms.append({'category': category, 'keyword': keyword})
        return [dict(t) for t in {tuple(d.items()) for d in symptoms}] # Supprimer les doublons

    def _assess_urgency(self, doc) -> float:
        """Évalue un niveau d'urgence simple basé sur des marqueurs."""
        urgency_markers = {
    'high': ['urgent', 'insupportable', 'sévère', 'aigu', 'extrême', 'intolérable', 'critique', 'insoutenable', 'très intense', 'très grave'],
    'medium': ['gênant', 'difficile', 'intense', 'modéré', 'inconfortable', 'problématique', 'notable', 'significatif', 'perturbant'],
    'low': ['léger', 'occasionnel', 'faible', 'discret', 'supportable', 'modéré', 'bénin', 'peu dérangeant', 'passager']
}

        text_lower = doc.text.lower()
        if any(marker in text_lower for marker in urgency_markers['high']): return 0.9
        if any(marker in text_lower for marker in urgency_markers['medium']): return 0.6
        if any(marker in text_lower for marker in urgency_markers['low']): return 0.3
        return 0.3 # Niveau par défaut

    def _generate_embedding(self, text: str) -> torch.Tensor:
        """Génère l'embedding vectoriel pour un texte donné."""
        return self.embedding_model.encode(text, convert_to_tensor=True)

    def _analyze(self, text: str) -> Dict[str, Any]:
        """Méthode d'analyse interne, utilisée par les deux points d'entrée publics."""
        if not text or not text.strip():
             return {"structured_analysis": {"keywords": [], "symptoms": [], "urgency_level": 0.0}, "user_embedding": None}

        doc = self.nlp(text.lower())
        analysis = {
            'keywords': self._extract_keywords(doc),
            'symptoms': self._identify_symptoms(doc),
            'urgency_level': self._assess_urgency(doc)
        }
        user_embedding = self._generate_embedding(text)
        return {"structured_analysis": analysis, "user_embedding": user_embedding}
        
    def analyze_free_text(self, text: str) -> Dict[str, Any]:
        """
        Point d'entrée public pour l'analyse d'un texte libre.
        """
        return self._analyze(text)

    def analyze_questionnaire_responses(self, responses: Dict[str, Any]) -> Dict[str, Any]:
        """
        Point d'entrée public pour l'analyse des réponses d'un QCM.
        """
        # 1. Convertir le dictionnaire de réponses en texte
        text_from_responses = self._dict_to_text(responses)
        print(f"Texte généré à partir du QCM : {text_from_responses}") # Pour le débogage
        
        # 2. Analyser le texte généré
        return self._analyze(text_from_responses)