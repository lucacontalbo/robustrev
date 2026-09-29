# src/services/embedding_service.py

from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    A service for creating and comparing text embeddings using a sentence-transformer model.
    """

    def __init__(self, model_name: str = "sentence-transformers/allenai-specter"):
        """
        Initializes the service and loads the model.

        Args:
            model_name: The name of the sentence-transformer model to use.
        """
        self.model_name = model_name
        try:
            print(
                f"Loading embedding model: {self.model_name}. This may take a moment..."
            )
            self.model = SentenceTransformer(self.model_name)
            print("Embedding model loaded successfully.")
        except Exception as e:
            logger.error(
                f"Failed to load sentence-transformer model '{self.model_name}'. Please ensure torch and sentence-transformers are installed. Error: {e}"
            )
            self.model = None

        # In-memory cache for embeddings to avoid re-computation within a single run.
        self.embedding_cache: Dict[str, np.ndarray] = {}

    def get_embedding(
        self, paper_id: str, title: str, abstract: str
    ) -> Optional[np.ndarray]:
        """
        Computes the embedding for a paper's title and abstract, using a cache.
        SPECTER models expect the [SEP] token between title and abstract.
        """
        if not self.model:
            logger.error("Embedding model is not loaded. Cannot compute embedding.")
            return None

        if paper_id in self.embedding_cache:
            # print(f"Cache hit for embedding: {paper_id}")
            return self.embedding_cache[paper_id]

        # The Specter model was trained on inputs of the form: title + "[SEP]" + abstract
        text_to_embed = (
            (title or "") + self.model.tokenizer.sep_token + (abstract or "")
        )

        try:
            embedding = self.model.encode(
                text_to_embed, convert_to_tensor=False, show_progress_bar=False
            )
            self.embedding_cache[paper_id] = embedding
            return embedding
        except Exception as e:
            logger.error(f"Failed to compute embedding for paper {paper_id}: {e}")
            return None

    def get_similarities(
        self, main_embedding: np.ndarray, candidate_embeddings: Dict[str, np.ndarray]
    ) -> Dict[str, float]:
        """
        Calculates cosine similarity between a main embedding and a dictionary of candidate embeddings.
        """
        if main_embedding is None or not candidate_embeddings:
            return {}

        candidate_ids = list(candidate_embeddings.keys())
        candidate_vectors = np.array(
            [candidate_embeddings[cid] for cid in candidate_ids]
        )

        similarities = cosine_similarity([main_embedding], candidate_vectors)[0]

        return {
            candidate_ids[i]: float(similarities[i]) for i in range(len(candidate_ids))
        }
