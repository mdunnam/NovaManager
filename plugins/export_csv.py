"""
Example plugin: Export selected photos to a CSV file.
Drop this file in the ``plugins/`` folder to activate it.
"""
import csv
import tempfile
import os

PLUGIN_NAME = "Export to CSV"
PLUGIN_DESC = "Export selected photos' metadata to a CSV file in the system temp folder."


def run(photos: list, db) -> str:
    """Write photo metadata to a temporary CSV and return its path."""
    if not photos:
        return "No photos to export."

    fields = [
        'id', 'filename', 'filepath', 'scene_type', 'mood', 'subjects',
        'location', 'tags', 'status', 'ai_caption', 'exif_date_taken',
    ]

    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.csv', delete=False, newline='', encoding='utf-8'
    )
    try:
        writer = csv.DictWriter(tmp, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for photo in photos:
            writer.writerow({k: photo.get(k, '') for k in fields})
        tmp.close()
        return f"Exported {len(photos)} photos → {tmp.name}"
    except Exception as exc:
        tmp.close()
        return f"Export failed: {exc}"
