"""
Duplicate photo detection for PhotoFlow.
Uses MD5 (exact) and perceptual hash (similar/near-duplicate) matching.
"""
import hashlib
from pathlib import Path

try:
    import imagehash
    from PIL import Image
    _IMAGEHASH = True
except ImportError:
    _IMAGEHASH = False

try:
    from PIL import Image as _PILImage
    _PIL = True
except ImportError:
    _PIL = False


def md5_hash(filepath: str) -> str:
    """Compute MD5 hash of file bytes (exact duplicate detection)."""
    h = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ''


def perceptual_hash(filepath: str) -> str:
    """Compute perceptual hash (similar image detection). Returns hex string."""
    if not _IMAGEHASH:
        return ''
    try:
        img = _PILImage.open(filepath)
        return str(imagehash.phash(img))
    except Exception:
        return ''


def hash_distance(hash1: str, hash2: str) -> int:
    """Hamming distance between two perceptual hash strings. 0=identical."""
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 999
    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        return h1 - h2
    except Exception:
        return 999


def find_duplicates(photos: list, threshold: int = 8) -> list[list[dict]]:
    """
    Given a list of photo dicts (with 'perceptual_hash', 'filepath', 'id'),
    return groups of duplicates/near-duplicates.

    threshold: max hamming distance to consider similar (0=exact phash match,
               ≤8 = visually similar, ≤16 = loosely similar)

    Returns list of groups, each group is a list of photo dicts.
    Exact MD5 duplicates are always grouped regardless of threshold.
    """
    if not photos:
        return []

    # First pass: group by MD5 hash (exact file duplicates)
    exact_groups: dict[str, list] = {}
    no_md5 = []
    for p in photos:
        h = p.get('file_hash') or ''
        if h:
            exact_groups.setdefault(h, []).append(p)
        else:
            no_md5.append(p)

    groups = [g for g in exact_groups.values() if len(g) > 1]

    # Second pass: group ALL photos by perceptual hash similarity
    # (including those that have an MD5 hash but no exact match found)
    if _IMAGEHASH:
        # Build list of photos not already in an exact-match group
        already_grouped_ids = {p['id'] for g in groups for p in g}
        ungrouped = [p for p in photos if p.get('perceptual_hash') and p['id'] not in already_grouped_ids]
        used = set()

        for i, p1 in enumerate(ungrouped):
            if p1['id'] in used:
                continue
            group = [p1]
            for j, p2 in enumerate(ungrouped):
                if i == j or p2['id'] in used:
                    continue
                dist = hash_distance(p1['perceptual_hash'], p2['perceptual_hash'])
                if dist <= threshold:
                    group.append(p2)
            if len(group) > 1:
                for p in group:
                    used.add(p['id'])
                groups.append(group)

    return groups
