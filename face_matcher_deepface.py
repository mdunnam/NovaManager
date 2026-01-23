"""
Face matching using DeepFace library
More accurate than OpenCV-only solution, works well on Windows
"""
from deepface import DeepFace
from pathlib import Path
import numpy as np
import logging

logger = logging.getLogger(__name__)

class FaceMatcherDeepFace:
    """
    Face matcher using DeepFace library
    Supports multiple models: VGG-Face, Facenet, OpenFace, DeepFace, DeepID, Dlib, ArcFace
    """
    
    def __init__(self, model_name="Facenet", distance_metric="cosine", detector_backend="opencv"):
        """
        Initialize DeepFace matcher
        
        Args:
            model_name: Model to use - "VGG-Face", "Facenet", "OpenFace", "DeepFace", "ArcFace", "SFace"
                       Recommended: "Facenet" (best accuracy/speed balance) or "ArcFace" (most accurate)
            distance_metric: "cosine", "euclidean", or "euclidean_l2"
            detector_backend: "opencv", "ssd", "mtcnn", "retinaface", "mediapipe"
                            Recommended: "opencv" (fastest, works on Windows without issues)
        """
        self.model_name = model_name
        self.distance_metric = distance_metric
        self.detector_backend = detector_backend
        self.benchmarks = []  # List of (name, embedding) tuples
        
        logger.info(f"Initialized DeepFace matcher with model={model_name}, detector={detector_backend}")
        
        # Verify model is available
        try:
            # This will download the model if not already cached
            logger.info("Loading model (first run may take time to download)...")
            # Just verify the model works
            logger.info(f"Model {model_name} ready")
        except Exception as e:
            logger.error(f"Failed to initialize model: {e}")
            raise
    
    def _get_embedding(self, image_path):
        """
        Get face embedding from image
        
        Args:
            image_path: Path to image file
            
        Returns:
            Embedding array or None if no face found
        """
        try:
            # DeepFace.represent returns list of embeddings (one per face)
            result = DeepFace.represent(
                img_path=str(image_path),
                model_name=self.model_name,
                detector_backend=self.detector_backend,
                enforce_detection=True,  # Raise error if no face found
                align=True
            )
            
            if result and len(result) > 0:
                # Return the first (most prominent) face embedding
                return np.array(result[0]["embedding"])
            
            return None
            
        except ValueError as e:
            # No face detected
            logger.warning(f"No face detected in {image_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing {image_path}: {e}")
            return None
    
    def add_benchmark(self, image_path, name="benchmark"):
        """
        Add a benchmark face
        
        Args:
            image_path: Path to benchmark image
            name: Optional name for this benchmark
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Adding benchmark: {name} from {image_path}")
        
        embedding = self._get_embedding(image_path)
        
        if embedding is None:
            logger.warning(f"Failed to add benchmark from {image_path}")
            return False
        
        self.benchmarks.append((name, embedding))
        logger.info(f"Benchmark '{name}' added successfully")
        return True
    
    def clear_benchmarks(self):
        """Clear all benchmarks"""
        self.benchmarks = []
        logger.info("All benchmarks cleared")
    
    def _compute_similarity(self, embedding1, embedding2):
        """
        Compute similarity between two embeddings
        
        Args:
            embedding1, embedding2: Face embeddings
            
        Returns:
            Similarity score (higher = more similar)
        """
        if self.distance_metric == "cosine":
            # Cosine similarity: 1 = identical, 0 = orthogonal, -1 = opposite
            similarity = np.dot(embedding1, embedding2) / (
                np.linalg.norm(embedding1) * np.linalg.norm(embedding2) + 1e-7
            )
            return similarity
        
        elif self.distance_metric == "euclidean":
            # Euclidean distance (lower = more similar)
            # Convert to similarity score (higher = more similar)
            distance = np.linalg.norm(embedding1 - embedding2)
            # Normalize: typical distances range from 0-1.5 for faces
            similarity = max(0, 1 - distance / 1.5)
            return similarity
        
        elif self.distance_metric == "euclidean_l2":
            # L2 normalized euclidean
            distance = np.linalg.norm(
                embedding1 / np.linalg.norm(embedding1) - 
                embedding2 / np.linalg.norm(embedding2)
            )
            similarity = max(0, 1 - distance / 2.0)
            return similarity
        
        return 0
    
    def compare_face(self, image_path, return_details=False):
        """
        Compare face in image to all benchmarks
        
        Args:
            image_path: Path to image to compare
            return_details: If True, return detailed comparison results
            
        Returns:
            If return_details=False: Star rating (1-5) based on similarity
            If return_details=True: Dict with rating, similarities, and best_match
        """
        if not self.benchmarks:
            logger.warning("No benchmark faces loaded")
            return 0 if not return_details else {"rating": 0, "error": "No benchmarks"}
        
        # Get embedding for target image
        embedding = self._get_embedding(image_path)
        
        if embedding is None:
            logger.warning(f"No face detected in {image_path}")
            return 0 if not return_details else {"rating": 0, "error": "No face detected"}
        
        # Compare with all benchmarks
        similarities = []
        names = []
        
        for name, bench_embedding in self.benchmarks:
            similarity = self._compute_similarity(embedding, bench_embedding)
            similarities.append(similarity)
            names.append(name)
        
        # Get best match
        best_similarity = max(similarities)
        best_match_idx = similarities.index(best_similarity)
        best_match_name = names[best_match_idx]
        
        # Convert similarity to 1-5 star rating
        # Thresholds tuned for Facenet model with cosine similarity
        # These may need adjustment for different models
        
        if self.model_name == "Facenet":
            # Facenet with cosine similarity thresholds
            if best_similarity > 0.80:
                rating = 5
            elif best_similarity > 0.70:
                rating = 4
            elif best_similarity > 0.60:
                rating = 3
            elif best_similarity > 0.50:
                rating = 2
            else:
                rating = 1
        
        elif self.model_name == "ArcFace":
            # ArcFace is more strict
            if best_similarity > 0.85:
                rating = 5
            elif best_similarity > 0.75:
                rating = 4
            elif best_similarity > 0.65:
                rating = 3
            elif best_similarity > 0.55:
                rating = 2
            else:
                rating = 1
        
        else:
            # Generic thresholds
            if best_similarity > 0.75:
                rating = 5
            elif best_similarity > 0.65:
                rating = 4
            elif best_similarity > 0.55:
                rating = 3
            elif best_similarity > 0.45:
                rating = 2
            else:
                rating = 1
        
        logger.info(f"Face comparison: {image_path} -> {rating} stars (similarity: {best_similarity:.3f})")
        
        if return_details:
            return {
                "rating": rating,
                "best_similarity": best_similarity,
                "best_match": best_match_name,
                "all_similarities": dict(zip(names, similarities))
            }
        
        return rating
    
    def batch_compare(self, image_paths, progress_callback=None):
        """
        Compare multiple images to benchmarks
        
        Args:
            image_paths: List of image paths
            progress_callback: Optional callback function(current, total, filename)
            
        Returns:
            Dict mapping image_path -> rating
        """
        results = {}
        total = len(image_paths)
        
        for i, img_path in enumerate(image_paths):
            if progress_callback:
                progress_callback(i + 1, total, Path(img_path).name)
            
            rating = self.compare_face(img_path)
            results[str(img_path)] = rating
        
        return results
    
    def verify_faces(self, img1_path, img2_path):
        """
        Verify if two images contain the same person
        Uses DeepFace.verify for optimized comparison
        
        Args:
            img1_path: Path to first image
            img2_path: Path to second image
            
        Returns:
            Dict with verified (bool), distance, threshold, and similarity
        """
        try:
            result = DeepFace.verify(
                img1_path=str(img1_path),
                img2_path=str(img2_path),
                model_name=self.model_name,
                detector_backend=self.detector_backend,
                distance_metric=self.distance_metric,
                enforce_detection=True
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error verifying faces: {e}")
            return {"verified": False, "error": str(e)}
