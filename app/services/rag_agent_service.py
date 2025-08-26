import logging
import asyncio
from typing import List, Dict, Any

import google.generativeai as genai
from qdrant_client import QdrantClient
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from agno.agent import Agent
from agno.models.google import Gemini
from langchain_core.documents import Document
from langchain.retrievers import EnsembleRetriever,BM25Retriever
#from langchain_community.retrievers import BM25Retriever

from app.config import Settings

logger = logging.getLogger(__name__)

class GeminiEmbedder(Embeddings):
    """Classe d'embedding simple pour les modèles Gemini."""
    def __init__(self, model_name: str, api_key: str):
        genai.configure(api_key=api_key)
        self.model = model_name

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            return genai.embed_content(model=self.model, content=texts, task_type="retrieval_document")['embedding']
        except Exception as e:
            logger.error(f"Error embedding documents with Gemini: {e}")
            return [[] for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        try:
            return genai.embed_content(model=self.model, content=text, task_type="retrieval_query")['embedding']
        except Exception as e:
            logger.error(f"Error embedding query with Gemini: {e}")
            return []

class RAGAgentService:
    def __init__(self, settings: Settings):
        """
        Initialise le service RAG avec une connexion à Qdrant, un Ensemble Retriever, et l'agent Agno.
        """
        self.settings = settings
        self.qdrant_client = None
        self.ensemble_retriever = None

        # --- 1. Initialiser le client Qdrant ---
        try:
            self.qdrant_client = QdrantClient(
                url=self.settings.QDRANT_URL, 
                api_key=self.settings.QDRANT_API_KEY,
                timeout=60
            )
            logger.info("✅ Connecté à Qdrant.")
        except Exception as e:
            logger.error(f"🔴 Échec de la connexion à Qdrant : {e}")
            return # Stop initialization if Qdrant connection fails

        # --- 2. Initialiser le Vector Store (Dense Retriever) ---
        try:
            # --- CORRECTION ICI : On vérifie que la collection existe ---
            logger.info(f"Vérification de l'existence de la collection '{self.settings.QDRANT_COLLECTION_NAME}'...")
            self.qdrant_client.get_collection(collection_name=self.settings.QDRANT_COLLECTION_NAME)
            logger.info("Collection trouvée.")

            vector_store = QdrantVectorStore(
                client=self.qdrant_client,
                collection_name=self.settings.QDRANT_COLLECTION_NAME,
                embedding=GeminiEmbedder(
                    model_name=self.settings.GEMINI_EMBEDDING_MODEL_NAME, 
                    api_key=self.settings.GOOGLE_API_KEY
                )
            )
            dense_retriever = vector_store.as_retriever(search_kwargs={"k": 5})
            logger.info(f"📚 Dense retriever connecté à la collection : {self.settings.QDRANT_COLLECTION_NAME}")
        except Exception as e:
            logger.error(f"🔴 La collection '{self.settings.QDRANT_COLLECTION_NAME}' est introuvable ou la connexion a échoué : {e}.")
            return

        # --- 3. Initialiser le BM25 Retriever (Sparse Retriever) ---
        try:
            logger.info("Chargement des documents pour le retriever BM25...")
            all_docs = []
            # Utilise scroll pour récupérer efficacement tous les documents
            response, _ = self.qdrant_client.scroll(
                collection_name=self.settings.QDRANT_COLLECTION_NAME,
                with_payload=True, with_vectors=False, limit=25000
            )
            for record in response:
                all_docs.append(Document(page_content=record.payload.get('page_content', ''), metadata=record.payload.get('metadata', {})))

            if not all_docs:
                logger.warning("Aucun document trouvé dans Qdrant pour construire l'index BM25. Seule la recherche dense sera utilisée.")
                self.ensemble_retriever = dense_retriever
            else:
                bm25_retriever = BM25Retriever.from_documents(all_docs, k=5)
                
                # --- 4. Créer l'Ensemble Retriever ---
                self.ensemble_retriever = EnsembleRetriever(
                    retrievers=[dense_retriever, bm25_retriever],
                    weights=[0.5, 0.5]  # Poids 50% dense, 50% sparse.
                )
                logger.info("✅ Retriever d'Ensemble initialisé.")
        except Exception as e:
            logger.error(f"🔴 Échec de l'initialisation du Retriever d'Ensemble : {e}. Retour à la recherche dense seule.")
            self.ensemble_retriever = dense_retriever

        # --- 5. Initialiser l'agent Agno ---
        self.agent = Agent(
            name="Conseiller Holistique Expert",
            model=Gemini(id=self.settings.GEMINI_MODEL_NAME, temperature=0.5),
            instructions=self._get_prompt_template(),
            show_tool_calls=False,
            markdown=True,
        )
        logger.info("🤖 Agent Agno initialisé.")

    def _get_prompt_template(self) -> str:
        """
        Retourne le template de prompt pour l'agent, basé sur votre PDF.
        """
        return """ Tu es un assistant spécialisé dans les pratiques holistiques et le bien-être.
Ton rôle est d'analyser les besoins d'une personne et de recommander **deux pratiques spécifiques** en t'appuyant UNIQUEMENT sur les informations fournies dans le CONTEXTE.

## CONTEXTE RÉCUPÉRÉ DE LA BASE DE CONNAISSANCES
{retrieved_documents}

## PROFIL DE LA PERSONNE
- Pratiques recommandées par le premier système : {practice_name_1}, {practice_name_2}
- Besoins exprimés (détectés par l'analyse NLP) : {user_needs}

## INSTRUCTIONS
1. **Analyse** : Lis attentivement le CONTEXTE pour comprendre les pratiques `{practice_name_1}` et `{practice_name_2}`.
2. **Personnalisation** : Rédige une recommandation personnalisée pour la personne. Explique en quoi les pratiques `{practice_name_1}` et `{practice_name_2}` sont parfaitement adaptées à ses besoins `{user_needs}`.
3. **Justification** : Utilise les détails du CONTEXTE pour expliquer pourquoi ces pratiques sont recommandées, ce qu'elles peuvent apporter, et comment elles se déroulent.
4. **Points d'attention** : Si le contexte mentionne des contre-indications ou des précautions, inclus-les pour chaque pratique.
5. **Sources** : Mentionne explicitement les sources d'information utilisées pour chaque recommandation.

## FORMAT DE RÉPONSE ATTENDU (en Markdown)
# Recommandation Personnalisée : {practice_name_1} et {practice_name_2}

## Pratique 1 : {practice_name_1}
### 1- Définition de la pratique :
[Définition claire, concise et précise de la pratique `{practice_name_1}`.]

### 2-Pourquoi cette pratique est idéale pour vous :
[Explique ici le lien entre les `user_needs` et les bénéfices de la pratique `{practice_name_1}`, en te basant sur le `retrieved_documents`.]

### 3-Ce que la pratique `{practice_name_1}` peut vous apporter : 
[Liste ici les bénéfices spécifiques mentionnés dans le contexte.]

### 4-Déroulement type :
[Décris ici comment se passe une séance de `{practice_name_1}`, si l'information est disponible dans le contexte.]


## Pratique 2 : {practice_name_2}
### 1- Définition de la pratique :  
[Définition claire, concise et précise de la pratique `{practice_name_2}`.]

### 2- Pourquoi cette pratique est idéale pour vous :  
[Explique ici le lien entre les `user_needs` et les bénéfices de la pratique `{practice_name_2}`, en te basant sur le `retrieved_documents`.]

### 3- Ce que la pratique `{practice_name_2}` peut vous apporter : 
[Liste ici les bénéfices spécifiques mentionnés dans le contexte.]

### 4- Déroulement type :  
[Décris ici comment se passe une séance de `{practice_name_2}`, si l'information est disponible dans le contexte.]


## Points d'attention
[Pour `{practice_name_1}`, mentionne ici les précautions ou contre-indications du contexte. Si aucune n'est mentionnée, écris "Aucune précaution particulière n'a été mentionnée, mais il est toujours bon d'en discuter avec le praticien."]  
[Pour `{practice_name_2}`, mentionne ici les précautions ou contre-indications du contexte. Si aucune n'est mentionnée, écris "Aucune précaution particulière n'a été mentionnée, mais il est toujours bon d'en discuter avec le praticien."]

### Sources
[Liste ici les sources utilisées pour chaque pratique, si elles sont mentionnées dans le contexte.]


## RÈGLES STRICTES
- Base-toi UNIQUEMENT sur les informations du `retrieved_documents`. N'invente rien.
- Si dans les `retrieved_documents`, il n'y a mention des sources, exemple, nom de livre ou bouqin, essayes de les mentionner à la fin.
- Essayes de détailler la réponse pour chaque pratique.
- Dans ta réponse, ne dis pas d'après le contexte, mais donne la réponse sous une forme plus spontanée.
- Si le contexte est vide ou non pertinent, indique que tu n'as pas assez d'informations pour donner une recommandation détaillée sur ces pratiques.
- Rappelle TOUJOURS que ces recommandations ne remplacent pas un avis médical.
- Adopte un ton bienveillant et professionnel.
"""


    async def generate_advice(self, user_needs: str, practices: List[Dict]) -> str:
        """
        Génère une double recommandation en interrogeant Qdrant pour chaque pratique.
        """
        if not self.ensemble_retriever or not practices or len(practices) < 2:
            return "Erreur : Le service de recherche n'est pas disponible ou le nombre de pratiques est insuffisant."

        practice1 = practices[0]
        practice2 = practices[1]
        
        # --- Récupération pour la pratique 1 ---
        query1 = f"Informations détaillées sur la pratique {practice1['practice_name']} pour traiter {user_needs}"
        docs1 = await asyncio.to_thread(self.ensemble_retriever.invoke, query1)
        context1 = "\n\n".join([d.page_content for d in docs1])
        sources1_list = [d.metadata.get('file_name', f"Document sur {practice1['practice_name']}") for d in docs1]
        sources1_str = "\n".join([f"- {s}" for s in sources1_list[:3]])

        # --- Récupération pour la pratique 2 ---
        query2 = f"Informations détaillées sur la pratique {practice2['practice_name']} pour traiter {user_needs}"
        docs2 = await asyncio.to_thread(self.ensemble_retriever.invoke, query2)
        context2 = "\n\n".join([d.page_content for d in docs2])
        sources2_list = [d.metadata.get('file_name', f"Document sur {practice2['practice_name']}") for d in docs2]
        sources2_str = "\n".join([f"- {s}" for s in sources2_list[:3]])

        # --- Construction du contexte combiné pour le prompt ---
        combined_context = f"""
        CONTEXTE POUR {practice1['practice_name']}:
        {context1}
        SOURCES POUR {practice1['practice_name']}:
        {sources1_str}

        ---

        CONTEXTE POUR {practice2['practice_name']}:
        {context2}
        SOURCES POUR {practice2['practice_name']}:
        {sources2_str}
        """

        # --- Construction du prompt final ---
        final_prompt = self.agent.instructions.format(
            retrieved_documents=combined_context,
            user_needs=user_needs,
            practice_name_1=practice1['practice_name'],
            practice_name_2=practice2['practice_name']
        )

        try:
            response = await self.agent.arun(final_prompt)
            return response.content
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de l'agent Agno : {e}")
            return "Désolé, une erreur est survenue lors de la génération de la recommandation finale."

