from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.routes import recommandations,questionnaire,feedback,auth
from app.utils.database import connect_to_mongo, close_mongo_connection
from app.config import get_settings
from fastapi.middleware.cors import CORSMiddleware 

from app.logging_config import setup_logging 
from prometheus_fastapi_instrumentator import Instrumentator
from app.services.rag_agent_service import RAGAgentService
from app.services.nlp_analyzer import NLPAnalyzer
from app.services.input_validation_service import InputValidationService


  



@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup
    setup_logging() 
    app.settings = get_settings()
    settings = app.settings


    # 1. J'ai instancié le service RAGAgentService ici pour qu'il soit disponible dans toute l'application
    app.state.rag_service = RAGAgentService(settings=settings)

    #2. Instanciation du NLPAnalyzer
    app.state.nlp_analyzer = NLPAnalyzer()

    #3. Initialiser le service de validation
    app.state.validation_service = InputValidationService(settings=settings)

    # 4. Connect to MongoDB
    await connect_to_mongo()
    yield
    # On shutdown
    await close_mongo_connection()

app = FastAPI(
    title="Holistic AI Recommender",
    description="Provides holistic practice recommendations based on user input.",
    version="2.4.0",
    lifespan=lifespan
)

# --- FIX: Instrument the app here, BEFORE it starts ---
instrumentator = Instrumentator().instrument(app)

@app.on_event("startup")
async def startup():
    # Expose the /metrics endpoint
    instrumentator.expose(app)

# --- 2. ADD THIS MIDDLEWARE SECTION ---
# This allows your frontend (which runs on a file:// or different domain)
# to communicate with your backend.
origins = [
    "http://localhost:8080",  # ← Ajoute ce port
    "http://127.0.0.1:8080"
    "http://localhost",
    "http://localhost:8080",
    "null", # Important for local files opened with `file:///`
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["Feedback"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(recommandations.router, prefix="/api/v1", tags=["Recommendations"])
app.include_router(questionnaire.router, prefix="/api/v1/questionnaire", tags=["Questionnaire"])



@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Holistic AI Recommender API."}