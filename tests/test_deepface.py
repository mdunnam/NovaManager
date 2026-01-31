"""
Test script for DeepFace face matcher
"""
from core.face_matcher_deepface import FaceMatcherDeepFace
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_deepface_matcher():
    """Test the DeepFace face matcher"""
    print("=" * 60)
    print("Testing DeepFace Face Matcher")
    print("=" * 60)
    
    # Initialize matcher
    print("\n1. Initializing DeepFace matcher...")
    print("   Model: Facenet (good balance of speed/accuracy)")
    print("   Detector: OpenCV (works reliably on Windows)")
    matcher = FaceMatcherDeepFace(
        model_name="Facenet",
        detector_backend="opencv"
    )
    print("✓ Face matcher initialized")
    
    # Test face detection and benchmark
    print("\n2. Testing face detection...")
    print("Please provide path to a test image with a face:")
    test_image = input("Image path: ").strip().strip('"')
    
    if not test_image:
        print("No image provided, skipping test")
        return
    
    test_image = Path(test_image)
    if not test_image.exists():
        print(f"✗ Image not found: {test_image}")
        return
    
    # Add as benchmark
    print("\n3. Adding benchmark face...")
    success = matcher.add_benchmark(test_image, name="Test Person")
    if success:
        print("✓ Benchmark added")
    else:
        print("✗ Failed to add benchmark (no face detected)")
        return
    
    # Test self-comparison
    print("\n4. Testing self-comparison (should be 5 stars)...")
    details = matcher.compare_face(test_image, return_details=True)
    print(f"   Rating: {details['rating']} stars")
    print(f"   Similarity: {details['best_similarity']:.3f}")
    print(f"   Best match: {details['best_match']}")
    
    if details['rating'] >= 4:
        print("   ✓ Self-comparison passed")
    else:
        print("   ⚠ Warning: Self-comparison should be 5 stars")
    
    # Test with another image
    print("\n5. Test with another image? (optional)")
    print("Provide path to compare against benchmark, or press Enter to skip:")
    compare_image = input("Image path: ").strip().strip('"')
    
    if compare_image:
        compare_image = Path(compare_image)
        if compare_image.exists():
            print("\n   Comparing...")
            details = matcher.compare_face(compare_image, return_details=True)
            if 'error' in details:
                print(f"   ✗ Error: {details['error']}")
            else:
                print(f"   Rating: {details['rating']} stars")
                print(f"   Similarity: {details['best_similarity']:.3f}")
                print(f"   Best match: {details['best_match']}")
        else:
            print(f"   ✗ Image not found: {compare_image}")
    
    # Test verification (if second image was provided)
    if compare_image and Path(compare_image).exists():
        print("\n6. Testing face verification...")
        result = matcher.verify_faces(test_image, compare_image)
        if 'error' in result:
            print(f"   ✗ Error: {result['error']}")
        else:
            print(f"   Verified: {result['verified']}")
            print(f"   Distance: {result['distance']:.3f}")
            print(f"   Threshold: {result['threshold']:.3f}")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
    print("\nTips:")
    print("- First run will download model files (~100MB)")
    print("- Models are cached for future use")
    print("- Try different models: 'Facenet', 'ArcFace', 'VGG-Face'")
    print("- ArcFace is most accurate but slower")

if __name__ == "__main__":
    test_deepface_matcher()
