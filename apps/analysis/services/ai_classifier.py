"""
AI-based classification system for non-KTU universities.
Uses local LLM (Ollama), embeddings, clustering, and ML classifiers.
"""
import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class AIClassifier:
    """
    Comprehensive AI classification for non-KTU universities.
    Uses LLM, embeddings, clustering, and ML models.
    """
    
    def __init__(self, llm_client=None, embedding_service=None):
        self.llm_client = llm_client
        self.embedding_service = embedding_service
        self.clusterer = None
        self.ml_classifier = None
        
        # Initialize components
        self._init_clusterer()
        self._init_ml_classifier()
    
    def _init_clusterer(self):
        """Initialize clustering algorithms."""
        try:
            from sklearn.cluster import KMeans, AgglomerativeClustering
            self.kmeans = KMeans
            self.agglomerative = AgglomerativeClustering
            logger.info("Clustering algorithms initialized")
        except ImportError:
            logger.warning("scikit-learn not available for clustering")
    
    def _init_ml_classifier(self):
        """Initialize ML classifiers."""
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.linear_model import LogisticRegression
            self.rf_classifier = RandomForestClassifier
            self.lr_classifier = LogisticRegression
            logger.info("ML classifiers initialized")
        except ImportError:
            logger.warning("scikit-learn not available for ML classification")
    
    def classify_questions_semantic(
        self,
        questions: List[Dict[str, Any]],
        subject,
        syllabus_text: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Classify questions using semantic analysis and AI.
        
        Args:
            questions: List of extracted questions
            subject: Subject instance
            syllabus_text: Optional syllabus text for matching
            
        Returns:
            Questions with AI-based classification
        """
        logger.info(f"Starting AI classification for {len(questions)} questions")
        
        # Step 1: Generate embeddings for all questions
        question_embeddings = self._generate_embeddings(questions)
        
        # Step 2: Cluster questions semantically
        clusters = self._cluster_questions(question_embeddings, n_clusters=5)
        
        # Step 3: Label clusters using LLM
        cluster_labels = self._label_clusters(questions, clusters)
        
        # Step 4: If syllabus available, match to syllabus units
        if syllabus_text:
            syllabus_mapping = self._match_to_syllabus(
                questions, question_embeddings, syllabus_text
            )
        else:
            syllabus_mapping = {}
        
        # Step 5: Assign questions to modules/units
        classified_questions = []
        for i, question in enumerate(questions):
            cluster_id = clusters[i]
            
            # Get module assignment
            if syllabus_mapping:
                module_num = syllabus_mapping.get(i, cluster_id + 1)
            else:
                module_num = cluster_id + 1  # Default to cluster-based
            
            # Assign topic from cluster label
            topic = cluster_labels.get(cluster_id, f"Topic {cluster_id + 1}")
            
            # Classify question properties
            question_type = self._classify_question_type(question['text'])
            difficulty = self._classify_difficulty(question['text'])
            bloom_level = self._classify_bloom_level(question['text'])
            
            classified_questions.append({
                **question,
                'module_number': module_num,
                'topic': topic,
                'cluster_id': cluster_id,
                'question_type': question_type,
                'difficulty': difficulty,
                'bloom_level': bloom_level,
                'embedding': question_embeddings[i].tolist() if len(question_embeddings) > i else None
            })
        
        logger.info(f"AI classification completed for {len(classified_questions)} questions")
        return classified_questions
    
    def _generate_embeddings(
        self, 
        questions: List[Dict[str, Any]]
    ) -> np.ndarray:
        """
        Generate embeddings for questions.
        
        Args:
            questions: List of questions
            
        Returns:
            Numpy array of embeddings
        """
        if not self.embedding_service:
            logger.warning("Embedding service not available, using dummy embeddings")
            return np.random.rand(len(questions), 384)  # Dummy embeddings
        
        texts = [q['text'] for q in questions]
        embeddings = self.embedding_service.encode(texts)
        
        return np.array(embeddings)
    
    def _cluster_questions(
        self,
        embeddings: np.ndarray,
        n_clusters: int = 5
    ) -> np.ndarray:
        """
        Cluster questions using KMeans.
        
        Args:
            embeddings: Question embeddings
            n_clusters: Number of clusters (modules)
            
        Returns:
            Cluster assignments
        """
        if not self.kmeans:
            logger.warning("KMeans not available, using dummy clusters")
            return np.random.randint(0, n_clusters, size=len(embeddings))
        
        # Use KMeans clustering
        kmeans = self.kmeans(n_clusters=n_clusters, random_state=42)
        clusters = kmeans.fit_predict(embeddings)
        
        logger.info(f"Clustered {len(embeddings)} questions into {n_clusters} groups")
        return clusters
    
    def _label_clusters(
        self,
        questions: List[Dict[str, Any]],
        clusters: np.ndarray
    ) -> Dict[int, str]:
        """
        Label clusters using LLM topic inference.
        
        Args:
            questions: List of questions
            clusters: Cluster assignments
            
        Returns:
            Dictionary mapping cluster_id to topic label
        """
        if not self.llm_client:
            logger.warning("LLM not available, using generic labels")
            return {i: f"Module {i+1} Topics" for i in range(max(clusters) + 1)}
        
        cluster_labels = {}
        
        # Group questions by cluster
        cluster_questions = defaultdict(list)
        for i, cluster_id in enumerate(clusters):
            cluster_questions[cluster_id].append(questions[i]['text'])
        
        # Label each cluster
        for cluster_id, texts in cluster_questions.items():
            # Take sample of questions (max 5)
            sample_texts = texts[:5]
            
            # Generate topic label using LLM
            prompt = self._build_topic_labeling_prompt(sample_texts)
            
            try:
                topic = self.llm_client.generate(
                    prompt, 
                    max_tokens=50, 
                    temperature=0.3
                )
                cluster_labels[cluster_id] = topic.strip()
            except Exception as e:
                logger.error(f"LLM labeling failed for cluster {cluster_id}: {e}")
                cluster_labels[cluster_id] = f"Module {cluster_id + 1}"
        
        return cluster_labels
    
    def _build_topic_labeling_prompt(self, sample_texts: List[str]) -> str:
        """Build prompt for LLM topic labeling."""
        questions_text = "\n".join([f"- {text[:200]}" for text in sample_texts])
        
        prompt = f"""Given these exam questions, identify the main topic/subject area in 2-5 words:

Questions:
{questions_text}

Topic name:"""
        
        return prompt
    
    def _match_to_syllabus(
        self,
        questions: List[Dict[str, Any]],
        question_embeddings: np.ndarray,
        syllabus_text: str
    ) -> Dict[int, int]:
        """
        Match questions to syllabus units using embeddings.
        
        Args:
            questions: List of questions
            question_embeddings: Question embeddings
            syllabus_text: Syllabus text
            
        Returns:
            Mapping of question index to module number
        """
        if not self.embedding_service:
            return {}
        
        # Parse syllabus into units/modules
        syllabus_units = self._parse_syllabus_units(syllabus_text)
        
        # Generate embeddings for syllabus units
        unit_texts = [unit['text'] for unit in syllabus_units]
        unit_embeddings = self.embedding_service.encode(unit_texts)
        
        # Match questions to units using cosine similarity
        mapping = {}
        
        for i, q_emb in enumerate(question_embeddings):
            # Calculate similarity with all units
            similarities = []
            for u_emb in unit_embeddings:
                sim = self._cosine_similarity(q_emb, u_emb)
                similarities.append(sim)
            
            # Assign to most similar unit
            best_unit_idx = np.argmax(similarities)
            mapping[i] = syllabus_units[best_unit_idx]['module_number']
        
        return mapping
    
    def _parse_syllabus_units(self, syllabus_text: str) -> List[Dict[str, Any]]:
        """
        Parse syllabus into units/modules.
        
        Args:
            syllabus_text: Raw syllabus text
            
        Returns:
            List of syllabus units with module numbers
        """
        # Simple parsing - split by "Module" or "Unit"
        import re
        
        units = []
        
        # Pattern: Module 1, Unit 1, etc.
        pattern = r'(?:Module|Unit)\s+(\d+)[:\-\s]+(.+?)(?=(?:Module|Unit)\s+\d+|$)'
        
        matches = re.finditer(pattern, syllabus_text, re.IGNORECASE | re.DOTALL)
        
        for match in matches:
            module_num = int(match.group(1))
            text = match.group(2).strip()
            
            units.append({
                'module_number': module_num,
                'text': text[:1000]  # Limit text length
            })
        
        # If no modules found, create default 5 modules
        if not units:
            # Split into 5 equal parts
            chunks = self._split_text_into_chunks(syllabus_text, 5)
            units = [
                {'module_number': i+1, 'text': chunk}
                for i, chunk in enumerate(chunks)
            ]
        
        return units
    
    def _split_text_into_chunks(self, text: str, n: int) -> List[str]:
        """Split text into n chunks."""
        words = text.split()
        chunk_size = len(words) // n
        
        chunks = []
        for i in range(n):
            start = i * chunk_size
            end = start + chunk_size if i < n-1 else len(words)
            chunks.append(" ".join(words[start:end]))
        
        return chunks
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    def _classify_question_type(self, text: str) -> str:
        """Classify question type using LLM or keywords."""
        if not self.llm_client:
            # Fallback to keyword matching
            text_lower = text.lower()
            
            if any(word in text_lower for word in ['define', 'what is', 'explain briefly']):
                return 'definition'
            elif any(word in text_lower for word in ['derive', 'proof', 'show that']):
                return 'derivation'
            elif any(word in text_lower for word in ['calculate', 'compute', 'find']):
                return 'numerical'
            elif any(word in text_lower for word in ['draw', 'diagram', 'sketch']):
                return 'diagram'
            elif any(word in text_lower for word in ['compare', 'differentiate']):
                return 'comparison'
            else:
                return 'theory'
        
        # Use LLM for classification
        prompt = f"""Classify this exam question into ONE type:
- definition
- derivation
- numerical
- theory
- diagram
- comparison

Question: {text[:200]}

Type:"""
        
        try:
            result = self.llm_client.generate(prompt, max_tokens=20, temperature=0.1)
            return result.strip().lower()
        except:
            return 'theory'
    
    def _classify_difficulty(self, text: str) -> str:
        """Classify difficulty level using LLM or heuristics."""
        if not self.llm_client:
            # Fallback to heuristics
            words = text.split()
            
            if len(words) < 10:
                return 'easy'
            elif len(words) < 30:
                return 'medium'
            else:
                return 'hard'
        
        prompt = f"""Rate the difficulty of this exam question:
- easy
- medium
- hard

Question: {text[:200]}

Difficulty:"""
        
        try:
            result = self.llm_client.generate(prompt, max_tokens=10, temperature=0.1)
            return result.strip().lower()
        except:
            return 'medium'
    
    def _classify_bloom_level(self, text: str) -> str:
        """Classify Bloom's taxonomy level."""
        if not self.llm_client:
            # Keyword-based classification
            text_lower = text.lower()
            
            if any(word in text_lower for word in ['list', 'define', 'name', 'state']):
                return 'remember'
            elif any(word in text_lower for word in ['explain', 'describe', 'discuss']):
                return 'understand'
            elif any(word in text_lower for word in ['apply', 'calculate', 'solve']):
                return 'apply'
            elif any(word in text_lower for word in ['analyze', 'examine', 'compare']):
                return 'analyze'
            elif any(word in text_lower for word in ['evaluate', 'assess', 'justify']):
                return 'evaluate'
            elif any(word in text_lower for word in ['create', 'design', 'develop']):
                return 'create'
            else:
                return 'understand'
        
        prompt = f"""Classify this question by Bloom's Taxonomy:
- remember
- understand
- apply
- analyze
- evaluate
- create

Question: {text[:200]}

Level:"""
        
        try:
            result = self.llm_client.generate(prompt, max_tokens=15, temperature=0.1)
            return result.strip().lower()
        except:
            return 'understand'
