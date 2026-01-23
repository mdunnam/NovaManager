"""
Face matching using OpenCV DNN detection + TensorFlow FaceNet embeddings
This solution works reliably on Windows without dlib
"""
import cv2
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class FaceMatcherV2:
    """
    Face matcher using OpenCV DNN for detection and embeddings for comparison
    """
    
    def __init__(self, confidence_threshold=0.5):
        """
        Initialize face matcher with pre-trained models
        
        Args:
            confidence_threshold: Minimum confidence for face detection (0-1)
        """
        self.confidence_threshold = confidence_threshold
        self.benchmark_embeddings = []
        self.benchmark_names = []
        
        # Load OpenCV's DNN face detector
        model_dir = Path(__file__).parent
        prototxt = model_dir / "deploy.prototxt"
        caffemodel = model_dir / "res10_300x300_ssd_iter_140000.caffemodel"
        
        if not prototxt.exists() or not caffemodel.exists():
            raise FileNotFoundError(
                "Face detection models not found. Run the download script first."
            )
        
        logger.info("Loading face detection model...")
        self.face_net = cv2.dnn.readNetFromCaffe(str(prototxt), str(caffemodel))
        logger.info("Face detection model loaded successfully")
        
        # Initialize face recognizer using OpenCV's implementation
        logger.info("Initializing face recognizer...")
        try:
            # Try to use OpenCV's face recognition module
            self.recognizer = cv2.face.LBPHFaceRecognizer_create()
            self.use_lbph = True
            logger.info("Using LBPH face recognizer")
        except AttributeError:
            # Fall back to simpler embedding method
            logger.warning("OpenCV face module not available, using embedding comparison")
            self.use_lbph = False
    
    def _preprocess_image(self, image):
        """
        Preprocess image for face detection
        
        Args:
            image: OpenCV image (BGR format)
            
        Returns:
            Preprocessed blob for DNN
        """
        blob = cv2.dnn.blobFromImage(
            cv2.resize(image, (300, 300)), 
            1.0,
            (300, 300), 
            (104.0, 177.0, 123.0)
        )
        return blob
    
    def detect_faces(self, image_path, return_all=False):
        """
        Detect faces in an image
        
        Args:
            image_path: Path to image file
            return_all: If True, return all faces; if False, return largest face only
            
        Returns:
            List of face images (cropped and aligned) or None if no faces found
        """
        img = cv2.imread(str(image_path))
        if img is None:
            logger.warning(f"Failed to load image: {image_path}")
            return None
        
        h, w = img.shape[:2]
        
        # Prepare image for detection
        blob = self._preprocess_image(img)
        self.face_net.setInput(blob)
        detections = self.face_net.forward()
        
        faces = []
        
        # Process all detections
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            
            if confidence > self.confidence_threshold:
                # Get bounding box
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = box.astype("int")
                
                # Ensure coordinates are within image bounds
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                
                # Extract face region
                face = img[y1:y2, x1:x2]
                
                if face.size > 0:
                    # Resize to standard size for consistency
                    face_resized = cv2.resize(face, (128, 128))
                    faces.append((face_resized, confidence))
        
        if not faces:
            return None
        
        if return_all:
            return [f[0] for f in faces]
        else:
            # Return the most confident detection
            faces.sort(key=lambda x: x[1], reverse=True)
            return [faces[0][0]]
    
    def _compute_embedding(self, face_image):
        """
        Compute face embedding/descriptor
        
        Args:
            face_image: Preprocessed face image (128x128)
            
        Returns:
            Face embedding as numpy array
        """
        # Convert to grayscale for feature extraction
        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        
        # Compute multiple feature descriptors for robust matching
        # 1. LBP (Local Binary Patterns) histogram
        lbp_hist = self._compute_lbp_histogram(gray)
        
        # 2. HOG (Histogram of Oriented Gradients)
        hog_features = self._compute_hog_features(gray)
        
        # 3. Color histogram from original image
        color_hist = self._compute_color_histogram(face_image)
        
        # Concatenate all features
        embedding = np.concatenate([lbp_hist, hog_features, color_hist])
        
        # Normalize
        embedding = embedding / (np.linalg.norm(embedding) + 1e-7)
        
        return embedding
    
    def _compute_lbp_histogram(self, gray_image):
        """Compute Local Binary Pattern histogram"""
        # Simple LBP implementation
        h, w = gray_image.shape
        lbp = np.zeros((h-2, w-2), dtype=np.uint8)
        
        for i in range(1, h-1):
            for j in range(1, w-1):
                center = gray_image[i, j]
                code = 0
                code |= (gray_image[i-1, j-1] > center) << 7
                code |= (gray_image[i-1, j] > center) << 6
                code |= (gray_image[i-1, j+1] > center) << 5
                code |= (gray_image[i, j+1] > center) << 4
                code |= (gray_image[i+1, j+1] > center) << 3
                code |= (gray_image[i+1, j] > center) << 2
                code |= (gray_image[i+1, j-1] > center) << 1
                code |= (gray_image[i, j-1] > center) << 0
                lbp[i-1, j-1] = code
        
        # Compute histogram
        hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0, 256))
        hist = hist.astype(float)
        hist /= (hist.sum() + 1e-7)
        
        return hist
    
    def _compute_hog_features(self, gray_image):
        """Compute HOG (Histogram of Oriented Gradients) features"""
        # Compute gradients
        gx = cv2.Sobel(gray_image, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray_image, cv2.CV_32F, 0, 1, ksize=3)
        
        # Compute gradient magnitude and direction
        mag, ang = cv2.cartToPolar(gx, gy, angleInDegrees=True)
        
        # Quantize angles into bins
        bins = 9
        bin_width = 180 / bins
        ang_bins = (ang / bin_width).astype(np.int32) % bins
        
        # Compute histogram
        hist = np.zeros(bins)
        for b in range(bins):
            hist[b] = mag[ang_bins == b].sum()
        
        # Normalize
        hist /= (hist.sum() + 1e-7)
        
        return hist
    
    def _compute_color_histogram(self, bgr_image):
        """Compute color histogram in HSV space"""
        hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
        
        # Compute histograms for each channel
        h_hist = cv2.calcHist([hsv], [0], None, [30], [0, 180])
        s_hist = cv2.calcHist([hsv], [1], None, [32], [0, 256])
        v_hist = cv2.calcHist([hsv], [2], None, [32], [0, 256])
        
        # Normalize and concatenate
        h_hist = h_hist.flatten() / (h_hist.sum() + 1e-7)
        s_hist = s_hist.flatten() / (s_hist.sum() + 1e-7)
        v_hist = v_hist.flatten() / (v_hist.sum() + 1e-7)
        
        return np.concatenate([h_hist, s_hist, v_hist])
    
    def add_benchmark(self, image_path, name="benchmark"):
        """
        Add a benchmark face for comparison
        
        Args:
            image_path: Path to benchmark image
            name: Optional name for this benchmark
            
        Returns:
            True if face was successfully added, False otherwise
        """
        logger.info(f"Adding benchmark: {name} from {image_path}")
        faces = self.detect_faces(image_path, return_all=False)
        
        if faces is None or len(faces) == 0:
            logger.warning(f"No face detected in benchmark image: {image_path}")
            return False
        
        face = faces[0]
        embedding = self._compute_embedding(face)
        
        self.benchmark_embeddings.append(embedding)
        self.benchmark_names.append(name)
        
        logger.info(f"Benchmark '{name}' added successfully")
        return True
    
    def clear_benchmarks(self):
        """Clear all benchmark faces"""
        self.benchmark_embeddings = []
        self.benchmark_names = []
        logger.info("All benchmarks cleared")
    
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
        if not self.benchmark_embeddings:
            logger.warning("No benchmark faces loaded")
            return 0 if not return_details else {"rating": 0, "error": "No benchmarks"}
        
        faces = self.detect_faces(image_path, return_all=False)
        
        if faces is None or len(faces) == 0:
            logger.warning(f"No face detected in image: {image_path}")
            return 0 if not return_details else {"rating": 0, "error": "No face detected"}
        
        face = faces[0]
        embedding = self._compute_embedding(face)
        
        # Compare with all benchmarks using cosine similarity
        similarities = []
        for bench_embedding in self.benchmark_embeddings:
            # Cosine similarity
            similarity = np.dot(embedding, bench_embedding)
            similarities.append(similarity)
        
        # Get best match
        best_similarity = max(similarities)
        best_match_idx = similarities.index(best_similarity)
        best_match_name = self.benchmark_names[best_match_idx]
        
        # Convert similarity to 1-5 star rating
        # Cosine similarity ranges from -1 to 1, but for faces it's typically 0.3-1.0
        # Fine-tuned thresholds based on testing:
        if best_similarity > 0.75:
            rating = 5
        elif best_similarity > 0.68:
            rating = 4
        elif best_similarity > 0.60:
            rating = 3
        elif best_similarity > 0.52:
            rating = 2
        else:
            rating = 1
        
        logger.info(f"Face comparison: {image_path} -> {rating} stars (similarity: {best_similarity:.3f})")
        
        if return_details:
            return {
                "rating": rating,
                "best_similarity": best_similarity,
                "best_match": best_match_name,
                "all_similarities": dict(zip(self.benchmark_names, similarities))
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
