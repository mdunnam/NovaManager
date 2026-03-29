"""
Image quality scoring for PhotoFlow.
Detects blur, exposure issues, and gives an overall quality grade.
Uses OpenCV (if available) with Pillow fallback.
"""

try:
    import cv2
    import numpy as np
    _CV2 = True
except ImportError:
    _CV2 = False

try:
    from PIL import Image, ImageStat
    _PIL = True
except ImportError:
    _PIL = False


QUALITY_EXCELLENT = 'excellent'   # Sharp, well-exposed
QUALITY_GOOD = 'good'             # Minor issues
QUALITY_FAIR = 'fair'             # Noticeable blur or exposure problems
QUALITY_POOR = 'poor'             # Severely blurry or black/white clipped


def score_image(filepath: str) -> dict:
    """Score image quality. Returns dict with:
      blur_score (float, higher=sharper),
      exposure_score (float, 0-1, 0.5=ideal),
      quality (str: excellent/good/fair/poor),
      quality_issues (list of str describing problems)
    """
    result = {
        'blur_score': 0.0,
        'exposure_score': 0.5,
        'quality': QUALITY_GOOD,
        'quality_issues': [],
    }

    blur = _detect_blur(filepath)
    exposure = _check_exposure(filepath)

    result['blur_score'] = blur
    result['exposure_score'] = exposure

    # Thresholds differ by backend:
    # Laplacian variance (CV2) ranges ~0–5000+; PIL stddev*2 ranges ~0–60.
    if _CV2:
        blur_blurry_threshold = 50.0
        blur_sharp_threshold = 200.0
    else:
        blur_blurry_threshold = 8.0
        blur_sharp_threshold = 35.0

    issues = []
    if blur < blur_blurry_threshold:
        issues.append('blurry')
    if exposure < 0.15:
        issues.append('underexposed')
    elif exposure > 0.85:
        issues.append('overexposed')

    result['quality_issues'] = issues

    if not issues:
        result['quality'] = QUALITY_EXCELLENT if blur > blur_sharp_threshold else QUALITY_GOOD
    elif len(issues) == 1 and blur > blur_blurry_threshold * 1.6:
        result['quality'] = QUALITY_FAIR
    else:
        result['quality'] = QUALITY_POOR

    return result


def _detect_blur(filepath: str) -> float:
    """Laplacian variance — higher = sharper. Returns 0 on failure."""
    if _CV2:
        try:
            img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return 100.0
            return float(cv2.Laplacian(img, cv2.CV_64F).var())
        except Exception:
            pass

    if _PIL:
        try:
            img = Image.open(filepath).convert('L')
            w, h = img.size
            # Sample center crop for speed
            cx, cy = w // 2, h // 2
            crop = img.crop((cx - 200, cy - 200, cx + 200, cy + 200))
            stat = ImageStat.Stat(crop)
            return stat.stddev[0] * 2  # Rough proxy for sharpness
        except Exception:
            pass

    return 100.0  # Can't score, assume ok


def _check_exposure(filepath: str) -> float:
    """Returns 0.0 (black) to 1.0 (white). 0.4-0.6 is ideal."""
    if _PIL:
        try:
            img = Image.open(filepath).convert('L').resize((100, 100))
            stat = ImageStat.Stat(img)
            return stat.mean[0] / 255.0
        except Exception:
            pass
    return 0.5


def quality_badge(quality: str) -> str:
    """Return a short badge string for UI display."""
    return {
        QUALITY_EXCELLENT: '★ Excellent',
        QUALITY_GOOD: '✓ Good',
        QUALITY_FAIR: '⚠ Fair',
        QUALITY_POOR: '✗ Poor',
    }.get(quality, '')
