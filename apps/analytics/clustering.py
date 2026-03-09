"""
AI-Powered Topic Clustering Engine.
Uses sentence-transformers for semantic similarity and agglomerative clustering
to group questions by meaning across module+part combinations.

Optimized: model loads once (singleton), batch encoding, GPU acceleration.
"""
import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from django.db import transaction

# ---------------------------------------------------------------------------
# Optional dependency imports -- app will not crash if missing
# ---------------------------------------------------------------------------
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False
    logging.warning("torch not available -- CUDA acceleration disabled")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning("sentence-transformers not available -- clustering disabled")

try:
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics.pairwise import cosine_distances
    SKLEARN_AVAILABLE = True
except ImportError:
    AgglomerativeClustering = None
    cosine_distances = None
    SKLEARN_AVAILABLE = False
    logging.warning("scikit-learn not available -- clustering disabled")

from apps.questions.models import Question
from apps.subjects.models import Subject, Module
from apps.analytics.models import TopicCluster

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level device detection (runs once at import time)
# ---------------------------------------------------------------------------
if TORCH_AVAILABLE:
    _CUDA_AVAILABLE = torch.cuda.is_available()
    _DEVICE = "cuda" if _CUDA_AVAILABLE else "cpu"
    print(f"[Clustering Engine] CUDA available: {_CUDA_AVAILABLE} -- using device: {_DEVICE}")
else:
    _CUDA_AVAILABLE = False
    _DEVICE = "cpu"
    print("[Clustering Engine] torch not installed -- using device: cpu")

# ---------------------------------------------------------------------------
# Singleton model cache — loaded once, stays in memory
# ---------------------------------------------------------------------------
_CACHED_MODEL = None


def get_model():
    """Return the cached SentenceTransformer model, loading it once on first call.

    The model stays in memory for all subsequent calls (zero load time).
    Uses GPU if available.
    """
    global _CACHED_MODEL
    if _CACHED_MODEL is not None:
        return _CACHED_MODEL

    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        return None

    try:
        logger.info("Loading sentence-transformer model 'all-MiniLM-L6-v2' on %s (first-time load)...", _DEVICE)
        model = SentenceTransformer('all-MiniLM-L6-v2', device=_DEVICE)

        # Move to GPU if available for faster encoding
        if TORCH_AVAILABLE and _CUDA_AVAILABLE:
            model = model.to(torch.device('cuda'))
            logger.info("Model moved to GPU (CUDA)")

        _CACHED_MODEL = model
        logger.info("Model loaded and cached successfully on %s", _DEVICE)
        return _CACHED_MODEL
    except Exception as exc:
        logger.warning("Failed to load sentence-transformer model: %s", exc)
        return None


class TopicClusteringService:
    """
    Clusters questions by semantic similarity within each (module, part)
    combination using sentence-transformers and agglomerative clustering.

    Optimized with:
    - Singleton model (loaded once, cached in module variable)
    - Single batch encode for all questions across all groups
    - GPU acceleration when available
    """

    DISTANCE_THRESHOLD = 0.35  # distance = 1 - cosine_similarity

    def __init__(self, subject: Subject):
        self.subject = subject
        self.model = get_model()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def analyze_subject(self) -> Dict[str, Any]:
        """
        Main entry point.  Clears old clusters, groups questions by
        (module, part), clusters each group, and saves results.

        Returns a statistics dict with keys clusters_created and
        questions_clustered.
        """
        import time as _time
        t_start = _time.perf_counter()

        logger.info("Starting topic analysis for subject: %s", self.subject)

        # Universal filter: exclude bad data
        questions = Question.objects.filter(
            paper__subject=self.subject
        ).exclude(
            text=''
        ).exclude(
            text__isnull=True
        ).select_related('paper', 'module')

        # Additional filter: text must be longer than 10 chars and q_number valid
        valid_questions = []
        for q in questions:
            if len(q.text.strip()) <= 10:
                continue
            try:
                qn = int(q.question_number)
                if qn < 1 or qn > 20:
                    continue
            except (ValueError, TypeError):
                continue
            valid_questions.append(q)

        if not valid_questions:
            logger.warning("No valid questions found for subject %s", self.subject)
            return {'clusters_created': 0, 'questions_clustered': 0}

        # Wipe previous clusters for a clean re-analysis
        with transaction.atomic():
            TopicCluster.objects.filter(subject=self.subject).delete()

        # Pre-compute ALL embeddings in one batch call
        all_embeddings = self._batch_encode_all(valid_questions)

        total_clusters, total_questions = self._cluster_by_module_and_part(
            valid_questions, all_embeddings
        )

        elapsed = round(_time.perf_counter() - t_start, 3)
        logger.info(
            "Analysis complete -- %d clusters created, %d questions clustered in %.3fs",
            total_clusters, total_questions, elapsed,
        )
        return {
            'clusters_created': total_clusters,
            'questions_clustered': total_questions,
        }

    # ------------------------------------------------------------------
    # Batch encoding: single GPU call for all questions
    # ------------------------------------------------------------------
    def _batch_encode_all(self, questions: List[Question]) -> Optional[np.ndarray]:
        """Encode all question texts in a single batch call.

        Returns numpy array of embeddings (N x 384) or None if model unavailable.
        One batch encode of 120 questions takes roughly the same GPU time as
        encoding 8 questions individually.
        """
        if not self.model:
            return None

        texts = [q.text for q in questions]
        logger.info("Batch encoding %d questions in one call (batch_size=64)...", len(texts))

        embeddings = self.model.encode(
            texts,
            batch_size=64,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        logger.info("Batch encoding complete: %d embeddings generated", len(embeddings))
        return np.array(embeddings)

    # ------------------------------------------------------------------
    # Grouping: split questions into (module, part) buckets
    # ------------------------------------------------------------------
    def _cluster_by_module_and_part(
        self,
        questions: List[Question],
        all_embeddings: Optional[np.ndarray],
    ) -> Tuple[int, int]:
        """
        Group questions by their (module, part) combination and cluster
        each group independently. Uses pre-computed embeddings.

        Returns (total_clusters_created, total_questions_clustered).
        """
        # Build index mapping: question -> position in all_embeddings
        q_to_idx = {id(q): i for i, q in enumerate(questions)}

        buckets: Dict[Tuple[Optional[int], str], List[Question]] = defaultdict(list)

        for q in questions:
            module_id = q.module_id  # may be None
            part = getattr(q, 'part', '') or ''  # 'A', 'B', or ''
            buckets[(module_id, part)].append(q)

        total_clusters = 0
        total_questions = 0

        for (module_id, part), bucket_questions in buckets.items():
            if len(bucket_questions) == 0:
                continue

            # Pre-clustering deduplication: within same module+part,
            # if two questions have identical text (case-insensitive),
            # keep only one per year
            bucket_questions = self._deduplicate_questions(bucket_questions)

            module = bucket_questions[0].module  # could be None

            label = f"Module {module.number if module else '?'} Part {part if part else '?'}"
            logger.info("Clustering %d questions for %s", len(bucket_questions), label)

            # Extract embeddings for this bucket from pre-computed array
            if all_embeddings is not None:
                bucket_indices = [q_to_idx[id(q)] for q in bucket_questions if id(q) in q_to_idx]
                if len(bucket_indices) == len(bucket_questions):
                    bucket_embeddings = all_embeddings[bucket_indices]
                else:
                    bucket_embeddings = None
            else:
                bucket_embeddings = None

            cluster_map = self._cluster_questions(bucket_questions, bucket_embeddings)

            clusters_created, questions_clustered = self._save_clusters(
                module, part, cluster_map,
            )
            total_clusters += clusters_created
            total_questions += questions_clustered

        return total_clusters, total_questions

    @staticmethod
    def _deduplicate_questions(questions: List[Question]) -> List[Question]:
        """Remove exact text duplicates within the same year.

        For questions with identical text (lowercased, stripped),
        keep only one per year to prevent inflated frequency counts.
        """
        seen = {}  # (normalized_text, year) -> Question
        deduplicated = []

        for q in questions:
            normalized = q.text.lower().strip()
            year = q.paper.year if q.paper else ''
            key = (normalized, year)
            if key not in seen:
                seen[key] = q
                deduplicated.append(q)

        removed = len(questions) - len(deduplicated)
        if removed > 0:
            logger.info("Deduplication removed %d exact duplicates", removed)

        return deduplicated

    # ------------------------------------------------------------------
    # Core clustering logic
    # ------------------------------------------------------------------
    def _cluster_questions(
        self,
        questions: List[Question],
        precomputed_embeddings: Optional[np.ndarray] = None,
    ) -> Dict[int, List[Question]]:
        """
        Cluster questions using pre-computed embeddings or encode on the fly.
        Computes pairwise cosine distance and runs AgglomerativeClustering.

        Returns a dict mapping cluster_label -> list of Question objects.
        Falls back to one-cluster-per-question when dependencies are missing.
        """
        if not self.model or not SKLEARN_AVAILABLE:
            # Fallback: every question is its own cluster
            return {i: [q] for i, q in enumerate(questions)}

        if len(questions) == 1:
            return {0: questions}

        # Use pre-computed embeddings if available, otherwise encode
        if precomputed_embeddings is not None and len(precomputed_embeddings) == len(questions):
            embeddings = precomputed_embeddings
        else:
            texts = [q.text for q in questions]
            embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            embeddings = np.array(embeddings)

        # --- Pairwise cosine distance matrix ---
        dist_matrix = cosine_distances(embeddings)

        # --- Agglomerative clustering ---
        try:
            clustering = AgglomerativeClustering(
                n_clusters=None,
                metric='precomputed',
                linkage='average',
                distance_threshold=self.DISTANCE_THRESHOLD,
            )
        except TypeError:
            # Older sklearn uses 'affinity' instead of 'metric'
            clustering = AgglomerativeClustering(
                n_clusters=None,
                affinity='precomputed',
                linkage='average',
                distance_threshold=self.DISTANCE_THRESHOLD,
            )

        labels = clustering.fit_predict(dist_matrix)

        # Build label -> questions mapping
        cluster_map: Dict[int, List[Question]] = defaultdict(list)
        for idx, label in enumerate(labels):
            cluster_map[int(label)].append(questions[idx])

        logger.info(
            "Agglomerative clustering produced %d clusters from %d questions",
            len(cluster_map), len(questions),
        )
        return dict(cluster_map)

    # ------------------------------------------------------------------
    # Representative text selection
    # ------------------------------------------------------------------
    def _find_representative_text(self, questions: List[Question]) -> str:
        """
        Find the most *central* question in the cluster -- the one whose
        average cosine similarity to every other member is highest.

        Returns the text of that question.
        """
        if len(questions) == 1:
            return questions[0].text

        if not self.model:
            return questions[0].text

        texts = [q.text for q in questions]
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        embeddings = np.array(embeddings)

        # Cosine similarity matrix (1 - distance)
        dist_matrix = cosine_distances(embeddings)
        sim_matrix = 1.0 - dist_matrix

        # Average similarity of each question to all others
        avg_similarities = sim_matrix.mean(axis=1)
        best_idx = int(np.argmax(avg_similarities))

        return texts[best_idx]

    # ------------------------------------------------------------------
    # Persist clusters to the database
    # ------------------------------------------------------------------
    def _save_clusters(
        self,
        module: Optional[Module],
        part: str,
        cluster_map: Dict[int, List[Question]],
    ) -> Tuple[int, int]:
        """
        Create TopicCluster rows and link questions to them.

        Returns (clusters_created, questions_clustered).
        """
        created_count = 0
        questions_clustered = 0

        with transaction.atomic():
            for cluster_label, cluster_questions in cluster_map.items():
                if not cluster_questions:
                    continue

                # Post-clustering quality check: skip clusters with only empty-text questions
                valid_text_questions = [
                    q for q in cluster_questions
                    if q.text and q.text.strip()
                ]
                if not valid_text_questions:
                    logger.warning(
                        "Skipping cluster %d: all %d questions have empty text",
                        cluster_label, len(cluster_questions)
                    )
                    continue

                # --- Representative / cluster name ---
                representative_text = self._find_representative_text(cluster_questions)
                topic_name = representative_text[:500]

                # --- Distinct years ---
                years = set()
                total_marks = 0
                part_a_count = 0
                part_b_count = 0

                for q in cluster_questions:
                    if q.paper and q.paper.year:
                        years.add(str(q.paper.year))
                    if q.marks:
                        total_marks += q.marks
                    q_part = getattr(q, 'part', '') or ''
                    if q_part == 'A':
                        part_a_count += 1
                    elif q_part == 'B':
                        part_b_count += 1

                frequency_count = len(years)

                # --- Priority tier based on distinct years ---
                if frequency_count >= 5:
                    priority = 1   # Tier 1: 5+ distinct years
                elif frequency_count >= 3:
                    priority = 2   # Tier 2: 3-4 distinct years
                elif frequency_count >= 2:
                    priority = 3   # Tier 3: 2 distinct years
                else:
                    priority = 4   # Tier 4: 1 distinct year

                normalized_key = topic_name[:500]

                cluster = TopicCluster.objects.create(
                    subject=self.subject,
                    module=module,
                    topic_name=topic_name,
                    normalized_key=normalized_key,
                    representative_text=representative_text,
                    frequency_count=frequency_count,
                    years_appeared=sorted(list(years)),
                    total_marks=total_marks,
                    priority_tier=priority,
                    question_count=len(cluster_questions),
                    part_a_count=part_a_count,
                    part_b_count=part_b_count,
                    cluster_id=normalized_key[:100],
                )

                # Link questions back to this cluster
                question_ids = [q.id for q in cluster_questions]
                Question.objects.filter(id__in=question_ids).update(
                    topic_cluster=cluster,
                    repetition_count=frequency_count,
                    years_appeared=sorted(list(years)),
                )

                created_count += 1
                questions_clustered += len(cluster_questions)

                logger.debug(
                    "Cluster saved: '%s' | %d questions | %d years | tier %d",
                    topic_name[:60], len(cluster_questions), frequency_count, priority,
                )

        return created_count, questions_clustered


# -----------------------------------------------------------------------
# Module-level convenience function
# -----------------------------------------------------------------------
def analyze_subject_topics(subject: Subject) -> Dict[str, Any]:
    """
    Convenience wrapper -- instantiate the service and run analysis.

    Args:
        subject: Subject instance to analyze.

    Returns:
        Statistics dict with 'clusters_created' and 'questions_clustered'.
    """
    service = TopicClusteringService(subject=subject)
    return service.analyze_subject()
