from prometheus_client import Counter, Histogram

# --- Métriques de Recommandation ---

# 1. Counter: Compte le nombre total de requêtes de recommandation.
# Labels:
# - input_type: 'free_text' ou 'questionnaire'
# - match_found: 'true' ou 'false'
RECOMMENDATION_REQUESTS = Counter(
    "recommendation_requests_total",
    "Total number of recommendation requests.",
    ["input_type", "match_found"]
)

# 2. Histogram: Mesure la latence (temps de réponse) des requêtes.
RECOMMENDATION_LATENCY = Histogram(
    "recommendation_latency_seconds",
    "Latency of recommendation requests in seconds."
)

# --- Métriques de Feedback ---

# 3. Counter: Compte le nombre de feedbacks reçus pour chaque note.
# Label:
# - rating: La note donnée par l'utilisateur (1, 2, 3, 4, 5)
FEEDBACK_RECEIVED = Counter(
    "feedback_rating_total",
    "Total number of feedback submissions by rating.",
    ["rating"]
)

# --- Métriques de Performance Interne ---

# 4. Histogram: Compte le nombre de documents récupérés par l'agent RAG.
# Utile pour voir si Qdrant retourne un nombre cohérent de documents.
RAG_DOCUMENTS_RETRIEVED = Histogram(
    "rag_retrieved_documents_count",
    "Number of documents retrieved by the RAG agent from Qdrant."
)

# 5. Counter: Compte les erreurs critiques de l'API.
# Label:
# - error_type: 'nlp_analysis', 'qdrant_retrieval', 'rag_generation'
API_ERRORS = Counter(
    "api_errors_total",
    "Total number of critical API errors.",
    ["error_type"]
)
