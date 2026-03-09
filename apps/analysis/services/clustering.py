"""
Question clustering service using Agglomerative and HDBSCAN clustering.
Groups repeated questions and assigns priority tiers.
"""
import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class QuestionClusterer:
    """
    Clusters questions to identify repeated topics.
    Uses Agglomerative clustering (primary) and HDBSCAN (alternative).
    Assigns 4-tier priority based on repetition frequency.
    """
    
    def __init__(self, similarity_threshold: float = 0.75):
        """
        Args:
            similarity_threshold: Cosine similarity threshold for clustering (0.75 for better detection)
        """
        self.similarity_threshold = similarity_threshold
        self.distance_threshold = 1 - similarity_threshold
    
    def cluster_agglomerative(
        self,
        embeddings: np.ndarray,
        questions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Cluster questions using Agglomerative Clustering.
        
        Args:
            embeddings: Question embeddings [n_questions, embedding_dim]
            questions: Question metadata (text, year, marks, etc.)
            
        Returns:
            List of clusters with metadata and priority
        """
        from sklearn.cluster import AgglomerativeClustering
        
        # Perform clustering
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=self.distance_threshold,
            metric='cosine',
            linkage='average'
        )
        
        labels = clustering.fit_predict(embeddings)
        
        # Group questions by cluster
        clusters_dict = defaultdict(list)
        for idx, label in enumerate(labels):
            clusters_dict[label].append(idx)
        
        # Build cluster metadata
        clusters = []
        for cluster_id, question_indices in clusters_dict.items():
            cluster_questions = [questions[i] for i in question_indices]
            
            # Extract years
            years = sorted(set(q.get('year') for q in cluster_questions if 'year' in q))
            
            # Count frequency
            frequency = len(question_indices)
            
            # Assign tier
            tier = self._assign_tier(frequency)
            
            # Get representative question (first one)
            representative = cluster_questions[0] if cluster_questions else {}
            
            clusters.append({
                'cluster_id': cluster_id,
                'frequency': frequency,
                'tier': tier,
                'years': years,
                'questions': cluster_questions,
                'representative_text': representative.get('text', ''),
                'topic_name': self._extract_topic_name(representative.get('text', ''))
            })
        
        # Sort by frequency (highest first)
        clusters.sort(key=lambda x: x['frequency'], reverse=True)
        
        logger.info(f"Created {len(clusters)} clusters using Agglomerative clustering")
        return clusters
    
    def cluster_hdbscan(
        self,
        embeddings: np.ndarray,
        questions: List[Dict[str, Any]],
        min_cluster_size: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Cluster questions using HDBSCAN (alternative method).
        Better for noisy data and varying cluster sizes.
        
        Args:
            embeddings: Question embeddings
            questions: Question metadata
            min_cluster_size: Minimum questions per cluster
            
        Returns:
            List of clusters
        """
        try:
            import hdbscan
        except ImportError:
            logger.warning("HDBSCAN not available, falling back to Agglomerative")
            return self.cluster_agglomerative(embeddings, questions)
        
        # Perform clustering
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            metric='cosine',
            cluster_selection_method='eom'
        )
        
        labels = clusterer.fit_predict(embeddings)
        
        # Group questions by cluster (-1 = noise/outliers)
        clusters_dict = defaultdict(list)
        for idx, label in enumerate(labels):
            if label != -1:  # Skip noise points
                clusters_dict[label].append(idx)
        
        # Build cluster metadata
        clusters = []
        for cluster_id, question_indices in clusters_dict.items():
            cluster_questions = [questions[i] for i in question_indices]
            
            years = sorted(set(q.get('year') for q in cluster_questions if 'year' in q))
            frequency = len(question_indices)
            tier = self._assign_tier(frequency)
            representative = cluster_questions[0] if cluster_questions else {}
            
            clusters.append({
                'cluster_id': cluster_id,
                'frequency': frequency,
                'tier': tier,
                'years': years,
                'questions': cluster_questions,
                'representative_text': representative.get('text', ''),
                'topic_name': self._extract_topic_name(representative.get('text', ''))
            })
        
        # Handle noise points (assign each as single-question cluster)
        for idx, label in enumerate(labels):
            if label == -1:
                q = questions[idx]
                clusters.append({
                    'cluster_id': f'noise_{idx}',
                    'frequency': 1,
                    'tier': 4,  # Lowest priority
                    'years': [q.get('year')] if 'year' in q else [],
                    'questions': [q],
                    'representative_text': q.get('text', ''),
                    'topic_name': self._extract_topic_name(q.get('text', ''))
                })
        
        clusters.sort(key=lambda x: x['frequency'], reverse=True)
        
        logger.info(f"Created {len(clusters)} clusters using HDBSCAN")
        return clusters
    
    def _assign_tier(self, frequency: int) -> int:
        """
        Assign priority tier based on frequency (as per master prompt).
        
        Tier 1: 4+ appearances (TOP PRIORITY)
        Tier 2: 3 appearances (HIGH PRIORITY)
        Tier 3: 2 appearances (MEDIUM PRIORITY)
        Tier 4: 1 appearance (LOW PRIORITY)
        
        Args:
            frequency: Number of times question appears
            
        Returns:
            Tier number (1-4)
        """
        if frequency >= 4:
            return 1
        elif frequency == 3:
            return 2
        elif frequency == 2:
            return 3
        else:
            return 4
    
    def _extract_topic_name(self, question_text: str, max_words: int = 10) -> str:
        """
        Extract a concise topic name from question text.
        
        Args:
            question_text: Full question text
            max_words: Maximum words in topic name
            
        Returns:
            Abbreviated topic name
        """
        import re
        
        # Remove question marks and extra whitespace
        text = re.sub(r'[?.]', '', question_text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Take first N words
        words = text.split()[:max_words]
        topic = ' '.join(words)
        
        # Add ellipsis if truncated
        if len(text.split()) > max_words:
            topic += '...'
        
        return topic
    
    def get_tier_name(self, tier: int) -> str:
        """Get display name for tier."""
        tier_names = {
            1: 'TOP PRIORITY — Repeated 4–6 Times',
            2: 'HIGH PRIORITY — Repeated 3 Times',
            3: 'MEDIUM PRIORITY — Repeated 2 Times',
            4: 'LOW PRIORITY — Appears Only Once'
        }
        return tier_names.get(tier, 'UNKNOWN')
    
    def organize_by_tier(self, clusters: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
        """
        Organize clusters by tier for reporting.
        
        Returns:
            Dict mapping tier -> list of clusters
        """
        by_tier = {1: [], 2: [], 3: [], 4: []}
        
        for cluster in clusters:
            tier = cluster['tier']
            by_tier[tier].append(cluster)
        
        return by_tier
    
    def calculate_exam_likelihood(self, frequency: int, total_years: int) -> str:
        """
        Calculate exam likelihood comment based on frequency.
        
        Args:
            frequency: Number of repetitions
            total_years: Total years analyzed
            
        Returns:
            Likelihood comment
        """
        if total_years == 0:
            return "Insufficient data"
        
        percentage = (frequency / total_years) * 100
        
        if percentage >= 80:
            return "Very High (appears almost every year)"
        elif percentage >= 60:
            return "High (appears frequently)"
        elif percentage >= 40:
            return "Moderate (appears occasionally)"
        elif percentage >= 20:
            return "Low (appears rarely)"
        else:
            return "Very Low (appears once)"
