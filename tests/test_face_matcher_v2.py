"""
Test script for FaceMatcherV2
"""
from core.face_matcher_v2 import FaceMatcherV2
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_face_matcher():
    """Test the face matcher with sample images"""
    print("=" * 60)
    print("Testing FaceMatcherV2")
    print("=" * 60)
    
    # Initialize matcher
    print("\n1. Initializing face matcher...")
    matcher = FaceMatcherV2(confidence_threshold=0.5)
    print("✓ Face matcher initialized")
    
    # Test face detection
    print("\n2. Testing face detection...")
    print("Please provide path to a test image with a face:")
    test_image = input("Image path: ").strip()
    
    if not test_image:
        print("No image provided, skipping test")
        return
    
    test_image = Path(test_image)
    if not test_image.exists():
        print(f"✗ Image not found: {test_image}")
        return
    
    faces = matcher.detect_faces(test_image, return_all=True)
    if faces:
        print(f"✓ Detected {len(faces)} face(s)")
    else:
        print("✗ No faces detected")
        return
    
    # Test benchmark
    print("\n3. Adding benchmark face...")
    success = matcher.add_benchmark(test_image, name="Test Person")
    if success:
        print("✓ Benchmark added")
    else:
        print("✗ Failed to add benchmark")
        return
    
    # Test comparison
    print("\n4. Testing face comparison...")
    details = matcher.compare_face(test_image, return_details=True)
    print(f"Rating: {details['rating']} stars")
    print(f"Similarity: {details['best_similarity']:.3f}")
    print(f"Best match: {details['best_match']}")
    
    # Test with another image
    print("\n5. Test with another image? (optional)")
    print("Provide path to compare, or press Enter to skip:")
    compare_image = input("Image path: ").strip()
    
    if compare_image:
        compare_image = Path(compare_image)
        if compare_image.exists():
            details = matcher.compare_face(compare_image, return_details=True)
            print(f"Rating: {details['rating']} stars")
            print(f"Similarity: {details['best_similarity']:.3f}")
            print(f"Best match: {details['best_match']}")
        else:
            print(f"✗ Image not found: {compare_image}")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    test_face_matcher()
