"""
AI Analyzer - General-purpose photo analysis using local LLaVA via Ollama
"""
import os
import json
import re

try:
    import ollama
except ImportError:
    ollama = None

try:
    from PIL import Image
except ImportError:
    Image = None


SCENE_TYPES = [
    'portrait', 'landscape', 'street', 'event', 'food', 'product',
    'travel', 'architecture', 'macro', 'abstract', 'sports', 'nature',
    'night', 'interior'
]

COMPOSITIONS = ['closeup', 'medium', 'wide', 'aerial', 'detail']

MOODS = [
    'bright', 'dark', 'dramatic', 'cozy', 'energetic', 'calm',
    'romantic', 'mysterious', 'playful'
]

SUBJECTS = [
    'people', 'animal', 'vehicle', 'building', 'food', 'plant',
    'sky', 'water', 'none'
]


def get_correction_examples(db, limit=10):
    """Get examples of recent user corrections to help AI learn."""
    try:
        corrections = db.cursor.execute('''
            SELECT field_name, original_value, corrected_value, COUNT(*) as count
            FROM ai_corrections
            WHERE original_value IS NOT NULL
            AND corrected_value IS NOT NULL
            AND original_value != corrected_value
            GROUP BY field_name, original_value, corrected_value
            ORDER BY count DESC, correction_date DESC
            LIMIT ?
        ''', (limit,)).fetchall()

        if not corrections:
            return ""

        examples = []
        for field, orig, corrected, count in corrections:
            field_readable = field.replace('_', ' ').title()
            examples.append(f"- {field_readable}: '{orig}' → '{corrected}' ({count}x)")

        return '\n'.join(examples) + '\n'
    except Exception as e:
        print(f"  [Could not load correction examples: {e}]")
        return ""


def analyze_image(image_path, db=None):
    """Use local LLaVA to extract general metadata from a photo.

    Returns a dict with keys: scene_type, composition, subjects,
    dominant_colors, objects_detected, mood, ai_caption,
    suggested_hashtags, content_rating, location.
    """
    if ollama is None:
        print("  [Ollama not available — skipping AI analysis]")
        return _empty_result()

    if Image is None:
        print("  [Pillow not available — skipping AI analysis]")
        return _empty_result()

    image = Image.open(image_path)

    # Resize large images for faster processing (max 1024px on longest side)
    max_size = 1024
    if max(image.size) > max_size:
        ratio = max_size / max(image.size)
        new_size = tuple(int(dim * ratio) for dim in image.size)
        image = image.resize(new_size, Image.Resampling.LANCZOS)
        print(f"  [Resized to {new_size} for analysis]")

    # Build learning context from past corrections
    learning_context = ""
    if db:
        examples = get_correction_examples(db)
        if examples:
            learning_context = (
                "\n\nLEARN FROM PAST CORRECTIONS — users have previously fixed:\n"
                + examples
            )

    prompt = f"""Analyze this photo and respond with ONLY a JSON object. No extra text, no markdown.

Return exactly this structure:
{{
  "scene_type": "<one of: {', '.join(SCENE_TYPES)}>",
  "composition": "<one of: {', '.join(COMPOSITIONS)}>",
  "subjects": "<comma-separated from: {', '.join(SUBJECTS)}>",
  "dominant_colors": "<top 3 colors as comma-separated color names>",
  "objects_detected": "<up to 10 notable objects, comma-separated>",
  "mood": "<one of: {', '.join(MOODS)}>",
  "location": "<brief location description, e.g. beach, urban street, kitchen, forest>",
  "content_rating": "<one of: general, mature, restricted>",
  "ai_caption": "<a natural 1-2 sentence caption suitable for social media>",
  "suggested_hashtags": "<10 relevant hashtags without # prefix, comma-separated>"
}}{learning_context}

Photo:"""

    try:
        response = ollama.generate(
            model='llava',
            prompt=prompt,
            images=[image_path],
            options={
                'num_predict': 300,
                'temperature': 0.1,
            }
        )
        text = response['response'].strip()
        return _parse_response(text)
    except Exception as e:
        print(f"  [AI analysis error: {e}]")
        return _empty_result()


def _empty_result():
    return {
        'scene_type': '',
        'composition': '',
        'subjects': '',
        'dominant_colors': '',
        'objects_detected': '',
        'mood': '',
        'location': '',
        'content_rating': 'general',
        'ai_caption': '',
        'suggested_hashtags': '',
    }


def _parse_response(text):
    """Parse the JSON response from LLaVA, with fallback for malformed output."""
    result = _empty_result()

    # Try to extract JSON block
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            for key in result:
                if key in parsed and parsed[key]:
                    result[key] = str(parsed[key]).strip()
            # Validate constrained fields
            result['scene_type'] = _constrain(result['scene_type'], SCENE_TYPES)
            result['composition'] = _constrain(result['composition'], COMPOSITIONS)
            result['mood'] = _constrain(result['mood'], MOODS)
            result['content_rating'] = _constrain(result['content_rating'], ['general', 'mature', 'restricted'], default='general')
            return result
        except json.JSONDecodeError:
            pass

    # Fallback: line-by-line colon parsing
    for line in text.split('\n'):
        line = line.strip().lower()
        for key in result:
            label = key.replace('_', ' ') + ':'
            if label in line:
                val = line.split(':', 1)[1].strip().strip('"').strip("'")
                result[key] = val

    result['scene_type'] = _constrain(result['scene_type'], SCENE_TYPES)
    result['composition'] = _constrain(result['composition'], COMPOSITIONS)
    result['mood'] = _constrain(result['mood'], MOODS)
    result['content_rating'] = _constrain(result['content_rating'], ['general', 'mature', 'restricted'], default='general')
    return result


def _constrain(value, allowed, default=''):
    """Return value if it's in the allowed list, else default."""
    v = (value or '').strip().lower()
    if v in allowed:
        return v
    # Partial match
    for a in allowed:
        if a in v or v in a:
            return a
    return default
