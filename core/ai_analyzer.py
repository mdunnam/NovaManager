"""
AI Analyzer - Refactored from nova_renamer.py
"""
import os
import ollama
from PIL import Image
import re

# Explicit level mapping
EXPLICIT_LEVELS = {
    "sfw": "sfw",
    "mild": "mild",
    "suggestive": "suggestive",
    "explicit": "explicit"
}

# Facing direction mapping - normalize AI output to allowed values
FACING_DIRECTION_MAP = {
    "camera": "camera",
    "atcamera": "camera",
    "at camera": "camera",
    "toward camera": "camera",
    "towards camera": "camera",
    "front": "camera",
    "away": "away",
    "back": "away",
    "up": "up",
    "upward": "up",
    "down": "down",
    "downward": "down",
    "left": "left",
    "right": "right",
    "side": "left"  # Default side views to left
}

def sanitize_filename(part):
    """Remove invalid filename characters"""
    # Remove invalid chars, periods, parentheses and extra spaces
    cleaned = re.sub(r'[<>:"/\\|?*,().\s]', '', part)
    return cleaned.strip().lower()

def get_correction_examples(db, limit=10):
    """Get examples of common user corrections to help AI learn"""
    try:
        # Get most recent corrections grouped by field
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
            # Make field name readable
            field_readable = field.replace('_', ' ').title()
            examples.append(f"- {field_readable}: '{orig}' → '{corrected}' ({count}x)")
        
        return '\n'.join(examples) + '\n'
    except Exception as e:
        print(f"  [Could not load correction examples: {e}]")
        return ""

def analyze_image(image_path, db=None):
    """Use LLaVA to extract structured info from the image"""
    image = Image.open(image_path)
    
    # Resize large images for faster processing (max 1024px on longest side)
    max_size = 1024
    if max(image.size) > max_size:
        ratio = max_size / max(image.size)
        new_size = tuple(int(dim * ratio) for dim in image.size)
        image = image.resize(new_size, Image.Resampling.LANCZOS)
        print(f"  [Resized image to {new_size} for faster processing]")
    
    # Build constrained vocabulary options from database
    vocab_constraints = ""
    if db:
        print(f"\n[Vocabulary] Loading controlled vocabularies...")
        try:
            fields_config = {
                'type_of_shot': 'Type of shot',
                'pose': 'Pose',
                'facing_direction': 'Facing direction',
                'explicit_level': 'Explicit level',
                'color_of_clothing': 'Main clothing color',
                'material': 'Material',
                'type_clothing': 'Type of clothing',
                'footwear': 'Footwear',
                'interior_exterior': 'Interior/Exterior',
                'location': 'Location/setting'
            }
            
            vocab_constraints = "\n\nIMPORTANT - You MUST use ONLY these exact values:\n"
            for field, label in fields_config.items():
                vocab_with_desc = db.get_vocabulary(field, include_descriptions=True)
                if vocab_with_desc:
                    vocab_list = []
                    for value, desc in vocab_with_desc:
                        if desc:
                            vocab_list.append(f"{value} ({desc})")
                        else:
                            vocab_list.append(value)
                    vocab_str = ' OR '.join(vocab_list)
                    vocab_constraints += f"{label}: [{vocab_str}]\n"
                    print(f"  - {field}: {len(vocab_with_desc)} allowed values")
            
            vocab_constraints += "\nDo NOT make up new values. Use only the values listed above.\n"
            
            # Add learning from past corrections
            learning_examples = get_correction_examples(db)
            if learning_examples:
                vocab_constraints += "\n\nLEARNING FROM CORRECTIONS - Users have corrected:\n"
                vocab_constraints += learning_examples
                print(f"  [Loaded {learning_examples.count('→')} correction examples]")
        except Exception as e:
            print(f"  [Could not load vocabularies: {e}]")
    else:
        print(f"\n[Vocabulary] No database provided")
    
    prompt = f"""
    Analyze this photo of a woman named Nova. IMPORTANT: You MUST respond with EXACTLY this format with field names and colons:{vocab_constraints}

    DO NOT use comma-separated format. Each field must be on its own line with a colon.

    Photo:
    """

    # Generate with options for faster processing
    response = ollama.generate(
        model='llava',
        prompt=prompt,
        images=[image_path],
        options={
            'num_predict': 150,  # Limit response length for speed
            'temperature': 0.1,   # Lower temperature = more consistent/faster
        }
    )
    
    text = response['response'].strip()
    
    # Parse the response
    result = {
        'type_of_shot': 'unknown',
        'pose': 'unknown',
        'facing_direction': 'unknown',
        'explicit_level': 'sfw',
        'color_of_clothing': 'unknown',
        'material': 'unknown',
        'type_clothing': 'unknown',
        'footwear': 'unknown',
        'interior_exterior': 'unknown',
        'location': 'unknown'
    }
    
    # Check if response is in comma-separated format (fallback)
    if ',' in text and text.count(',') >= 5 and text.count(':') < 3:
        print("  [Fallback: parsing comma-separated response]")
        values = [sanitize_filename(v.strip()) for v in text.split(',')]
        if len(values) >= 10:
            result['type_of_shot'] = values[0] if values[0] else 'unknown'
            result['pose'] = values[1] if values[1] else 'unknown'
            facing = values[2] if values[2] else 'camera'
            result['facing_direction'] = FACING_DIRECTION_MAP.get(facing, 'camera')
            result['explicit_level'] = EXPLICIT_LEVELS.get(values[3], 'sfw')
            result['color_of_clothing'] = values[4] if values[4] else 'unknown'
            result['material'] = values[5] if values[5] else 'unknown'
            result['type_clothing'] = values[6] if values[6] else 'unknown'
            result['footwear'] = values[7] if values[7] else 'unknown'
            result['interior_exterior'] = values[8] if values[8] else 'unknown'
            result['location'] = values[9] if values[9] else 'unknown'
    else:
        # Parse standard format with field names and colons
        for line in text.split('\n'):
            line = line.lower().strip()
            if 'type of shot:' in line:
                result['type_of_shot'] = sanitize_filename(line.split(':', 1)[1])
            elif 'pose:' in line:
                result['pose'] = sanitize_filename(line.split(':', 1)[1])
            elif 'facing direction:' in line:
                facing = sanitize_filename(line.split(':', 1)[1])
                result['facing_direction'] = FACING_DIRECTION_MAP.get(facing, 'camera')
            elif 'explicit level:' in line:
                level = sanitize_filename(line.split(':', 1)[1])
                result['explicit_level'] = EXPLICIT_LEVELS.get(level, 'sfw')
            elif 'main clothing color:' in line:
                result['color_of_clothing'] = sanitize_filename(line.split(':', 1)[1])
            elif 'material:' in line:
                result['material'] = sanitize_filename(line.split(':', 1)[1])
            elif 'type of clothing:' in line:
                result['type_clothing'] = sanitize_filename(line.split(':', 1)[1])
            elif 'footwear:' in line:
                footwear = sanitize_filename(line.split(':', 1)[1])
                # Convert "none" or empty to "barefoot"
                if not footwear or footwear == 'none' or 'none' in footwear:
                    result['footwear'] = 'barefoot'
                else:
                    result['footwear'] = footwear
            elif 'interior/exterior:' in line:
                result['interior_exterior'] = sanitize_filename(line.split(':', 1)[1])
            elif 'location' in line and ':' in line:
                result['location'] = sanitize_filename(line.split(':', 1)[1])
    
    # Validate all values against controlled vocabulary
    if db:
        print(f"\n[Validation] Constraining values to vocabulary...")
        validated_result = {}
        for field, value in result.items():
            validated = db.validate_and_constrain(field, value)
            validated_result[field] = validated
            if validated == 'unknown' and value != 'unknown':
                print(f"  - {field}: '{value}' not in vocabulary, set to 'unknown'")
            elif validated != value:
                print(f"  - {field}: '{value}' corrected to '{validated}'")
        result = validated_result
    
    return result
