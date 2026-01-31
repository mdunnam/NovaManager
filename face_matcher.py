"""
Face matching using OpenCV - more reliable than dlib on Windows
"""
import cv2
import numpy as np
from pathlib import Path

class FaceMatcher:
    def __init__(self):
        # Load OpenCV's DNN face detector
        self.face_net = cv2.dnn.readNetFromCaffe(
            str(Path(__file__).parent / "models" / "deploy.prototxt"),
            str(Path(__file__).parent / "models" / "res10_300x300_ssd_iter_140000.caffemodel")
        )
        self.benchmark_descriptors = []
    
    def detect_face(self, image_path):
        """Detect largest face in image"""
        img = cv2.imread(str(image_path))
        if img is None:
            return None
        
        h, w = img.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 1.0,
                                     (300, 300), (104.0, 177.0, 123.0))
        self.face_net.setInput(blob)
        detections = self.face_net.forward()
        
        # Find most confident face
        best_confidence = 0
        best_box = None
        
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > 0.5 and confidence > best_confidence:
                best_confidence = confidence
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                best_box = box.astype("int")
        
        if best_box is not None:
            x, y, x2, y2 = best_box
            face = img[y:y2, x:x2]
            if face.size > 0:
                return cv2.resize(face, (128, 128))
        
        return None
    
    def compute_histogram(self, face):
        """Compute color histogram as face descriptor"""
        hsv = cv2.cvtColor(face, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        return hist.flatten()
    
    def add_benchmark(self, image_path):
        """Add a benchmark face"""
        face = self.detect_face(image_path)
        if face is not None:
            descriptor = self.compute_histogram(face)
            self.benchmark_descriptors.append(descriptor)
            return True
        return False
    
    def compare_face(self, image_path):
        """Compare face in image to benchmarks. Returns similarity score 1-5"""
        if not self.benchmark_descriptors:
            return 0
        
        face = self.detect_face(image_path)
        if face is None:
            return 0
        
        descriptor = self.compute_histogram(face)
        
        # Compare with all benchmarks using correlation
        similarities = []
        for bench_desc in self.benchmark_descriptors:
            sim = cv2.compareHist(descriptor, bench_desc, cv2.HISTCMP_CORREL)
            similarities.append(sim)
        
        avg_sim = np.mean(similarities)
        
        # Convert correlation to 1-5 rating
        if avg_sim > 0.85:
            return 5
        elif avg_sim > 0.75:
            return 4
        elif avg_sim > 0.65:
            return 3
        elif avg_sim > 0.55:
            return 2
        else:
            return 1
