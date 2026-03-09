"""
Local embedding service using sentence-transformers.
This is a wrapper around the EmbeddingService in apps.analysis.services.
"""
from apps.analysis.services.embedder import EmbeddingService

# Re-export for convenience
LocalEmbedder = EmbeddingService
