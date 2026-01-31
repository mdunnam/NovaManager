"""
Compare OpenCV vs DeepFace face matching performance
Helps you decide which solution to use
"""
import time
from pathlib import Path
import sys

def compare_solutions(test_image1, test_image2=None):
    """Compare both face matching solutions"""
    
    print("=" * 70)
    print("  Face Matching Solutions Comparison")
    print("=" * 70)
    
    test_image1 = Path(test_image1)
    if not test_image1.exists():
        print(f"✗ Image not found: {test_image1}")
        return
    
    # If no second image, use first image for self-comparison
    if test_image2 is None:
        test_image2 = test_image1
    else:
        test_image2 = Path(test_image2)
        if not test_image2.exists():
            print(f"✗ Image not found: {test_image2}")
            return
    
    results = {}
    
    # Test OpenCV solution
    print("\n📊 Testing OpenCV Solution (face_matcher_v2.py)")
    print("-" * 70)
    try:
        from core.face_matcher_v2 import FaceMatcherV2
        
        start = time.time()
        matcher_cv = FaceMatcherV2()
        init_time = time.time() - start
        
        start = time.time()
        success = matcher_cv.add_benchmark(test_image1, name="Person")
        add_time = time.time() - start
        
        if not success:
            print("✗ No face detected in image")
            results['opencv'] = {'error': 'No face detected'}
        else:
            start = time.time()
            details = matcher_cv.compare_face(test_image2, return_details=True)
            compare_time = time.time() - start
            
            results['opencv'] = {
                'init_time': init_time,
                'add_time': add_time,
                'compare_time': compare_time,
                'total_time': init_time + add_time + compare_time,
                'rating': details['rating'],
                'similarity': details['best_similarity']
            }
            
            print(f"✓ Initialization: {init_time:.3f}s")
            print(f"✓ Add benchmark: {add_time:.3f}s")
            print(f"✓ Compare face: {compare_time:.3f}s")
            print(f"✓ Total time: {results['opencv']['total_time']:.3f}s")
            print(f"✓ Rating: {details['rating']} stars")
            print(f"✓ Similarity: {details['similarity']:.3f}")
    
    except ImportError as e:
        print(f"✗ Not installed: {e}")
        print("  Install with: pip install opencv-python opencv-contrib-python")
        results['opencv'] = {'error': 'Not installed'}
    except Exception as e:
        print(f"✗ Error: {e}")
        results['opencv'] = {'error': str(e)}
    
    # Test DeepFace solution
    print("\n📊 Testing DeepFace Solution (face_matcher_deepface.py)")
    print("-" * 70)
    try:
        from core.face_matcher_deepface import FaceMatcherDeepFace
        
        print("Initializing (may download models on first run)...")
        start = time.time()
        matcher_df = FaceMatcherDeepFace(
            model_name="Facenet",
            detector_backend="opencv"
        )
        init_time = time.time() - start
        
        start = time.time()
        success = matcher_df.add_benchmark(test_image1, name="Person")
        add_time = time.time() - start
        
        if not success:
            print("✗ No face detected in image")
            results['deepface'] = {'error': 'No face detected'}
        else:
            start = time.time()
            details = matcher_df.compare_face(test_image2, return_details=True)
            compare_time = time.time() - start
            
            results['deepface'] = {
                'init_time': init_time,
                'add_time': add_time,
                'compare_time': compare_time,
                'total_time': init_time + add_time + compare_time,
                'rating': details['rating'],
                'similarity': details['best_similarity']
            }
            
            print(f"✓ Initialization: {init_time:.3f}s")
            print(f"✓ Add benchmark: {add_time:.3f}s")
            print(f"✓ Compare face: {compare_time:.3f}s")
            print(f"✓ Total time: {results['deepface']['total_time']:.3f}s")
            print(f"✓ Rating: {details['rating']} stars")
            print(f"✓ Similarity: {details['best_similarity']:.3f}")
    
    except ImportError as e:
        print(f"✗ Not installed: {e}")
        print("  Install with: pip install deepface tf-keras tensorflow")
        results['deepface'] = {'error': 'Not installed'}
    except Exception as e:
        print(f"✗ Error: {e}")
        results['deepface'] = {'error': str(e)}
    
    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    
    if 'error' not in results.get('opencv', {}) and 'error' not in results.get('deepface', {}):
        print("\n📈 Performance Comparison:")
        print("-" * 70)
        print(f"{'Metric':<30} {'OpenCV':<20} {'DeepFace':<20}")
        print("-" * 70)
        
        cv = results['opencv']
        df = results['deepface']
        
        print(f"{'Initialization Time':<30} {cv['init_time']:.3f}s {df['init_time']:.3f}s")
        print(f"{'Add Benchmark Time':<30} {cv['add_time']:.3f}s {df['add_time']:.3f}s")
        print(f"{'Compare Time':<30} {cv['compare_time']:.3f}s {df['compare_time']:.3f}s")
        print(f"{'Total Time':<30} {cv['total_time']:.3f}s {df['total_time']:.3f}s")
        print(f"{'Rating':<30} {cv['rating']} stars {df['rating']} stars")
        print(f"{'Similarity Score':<30} {cv['similarity']:.3f} {df['similarity']:.3f}")
        
        print("\n💡 Recommendations:")
        print("-" * 70)
        
        if cv['total_time'] < df['total_time'] * 0.5:
            print("⚡ OpenCV is significantly faster")
        
        if df['total_time'] < cv['total_time'] * 0.5:
            print("⚡ DeepFace is significantly faster")
        
        # For self-comparison, both should be 5 stars
        if test_image1 == test_image2:
            if cv['rating'] >= 4 and df['rating'] >= 4:
                print("✓ Both solutions correctly identify same person")
            elif cv['rating'] >= 4:
                print("✓ OpenCV correctly identifies same person")
                print("⚠ DeepFace may need threshold adjustment")
            elif df['rating'] >= 4:
                print("✓ DeepFace correctly identifies same person")
                print("⚠ OpenCV may need threshold adjustment")
        
        print("\n🎯 Best for you:")
        if cv['total_time'] < df['total_time'] and abs(cv['rating'] - df['rating']) <= 1:
            print("   → OpenCV: Similar accuracy, faster performance")
        elif df['rating'] > cv['rating']:
            print("   → DeepFace: Better accuracy worth the extra time")
        else:
            print("   → Either solution works well!")
    
    elif 'error' in results.get('opencv', {}):
        print("\n⚠ OpenCV solution not available")
        if 'error' not in results.get('deepface', {}):
            print("✓ DeepFace solution is working")
    
    elif 'error' in results.get('deepface', {}):
        print("\n⚠ DeepFace solution not available")
        if 'error' not in results.get('opencv', {}):
            print("✓ OpenCV solution is working")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    print("\nFace Matching Solutions Comparison Tool")
    print("=" * 70)
    
    if len(sys.argv) < 2:
        print("\nUsage:")
        print(f"  python {Path(__file__).name} <image_path>")
        print(f"  python {Path(__file__).name} <image1_path> <image2_path>")
        print("\nExamples:")
        print(f'  python {Path(__file__).name} "photos/person.jpg"')
        print(f'  python {Path(__file__).name} "photos/person1.jpg" "photos/person2.jpg"')
        print("\nFor self-comparison (should be 5 stars), use same image twice.")
        sys.exit(1)
    
    img1 = sys.argv[1]
    img2 = sys.argv[2] if len(sys.argv) > 2 else None
    
    compare_solutions(img1, img2)
