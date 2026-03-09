"""
Embedding service using all-MiniLM-L6-v2 as specified in master prompt.
Generates semantic embeddings for question similarity detection.
"""
import logging
from typing import List, Optional
import numpy as np
import re

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Generates embeddings using sentence-transformers (all-MiniLM-L6-v2).
    Used for detecting repeated questions across years.
    """
    
    _model = None
    _model_name = None
    MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model_name = model_name
    
    def _load_model(self):
        """Lazy load the embedding model."""
        if EmbeddingService._model is None or EmbeddingService._model_name != self.model_name:
            try:
                from sentence_transformers import SentenceTransformer
                EmbeddingService._model = SentenceTransformer(self.model_name)
                EmbeddingService._model_name = self.model_name
                logger.info(f"✓ Loaded embedding model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise
    
    def _preprocess(self, text: str) -> str:
        """
        Preprocess text before embedding.
        - Remove extra whitespace
        - Remove special characters that don't affect meaning
        - Lowercase for consistency
        """
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove question marks (normalize)
        text = text.replace('?', '')
        
        # Strip
        text = text.strip()
        
        return text
    
    def get_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text (question)
            
        Returns:
            Embedding vector as numpy array, or None on failure
        """
        try:
            self._load_model()
            text = self._preprocess(text)
            embedding = EmbeddingService._model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None
    
    def get_embeddings_batch(self, texts: List[str], batch_size: int = 32) -> List[Optional[np.ndarray]]:
        """
        Generate embeddings for multiple texts efficiently.
        
        Args:
            texts: List of input texts
            batch_size: Batch size for encoding
            
        Returns:
            List of embedding vectors
        """
        try:
            self._load_model()
            texts = [self._preprocess(t) for t in texts]
            embeddings = EmbeddingService._model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=len(texts) > 100
            )
            logger.info(f"Generated {len(embeddings)} embeddings")
            return [emb for emb in embeddings]
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            return [None] * len(texts)
    
    def embed(self, text: str) -> np.ndarray:
        """Alias for get_embedding (compatibility)."""
        return self.get_embedding(text)
    
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Generate embeddings as numpy array."""
        embeddings = self.get_embeddings_batch(texts, batch_size)
        return np.array([e for e in embeddings if e is not None])
    
    def get_embedding_dim(self) -> int:
        """Get embedding dimension."""
        self._load_model()
        return EmbeddingService._model.get_sentence_embedding_dimension()
