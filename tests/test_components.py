#!/usr/bin/env python3
"""Test script to verify all tab components load correctly."""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Create QApplication
app = QApplication.instance() or QApplication([])

print("=" * 60)
print("NOVA APP - COMPONENT IMPORT TEST")
print("=" * 60)

# Test imports
tests = [
    ("Main Application", "nova_manager", "MainWindow"),
    ("Gallery Tab", "ui.gallery_tab", "GalleryTab"),
    ("Photos Tab", "ui.photos_tab", "PhotosTab"),
    ("Face Matching Tab", "ui.face_matching_tab", "FaceMatchingTab"),
    ("Filters Tab", "ui.filters_tab", "FiltersTab"),
    ("Vocabularies Tab", "ui.vocabularies_tab", "VocabulariesTab"),
    ("AI Learning Tab", "ui.learning_tab", "AILearningTab"),
    ("Publish Tab", "ui.publish_tab", "PublishTab"),
    ("Instagram Tab", "ui.instagram_tab", "InstagramTab"),
    ("TikTok Tab", "ui.tiktok_tab", "TikTokTab"),
]

success_count = 0
fail_count = 0

for name, module_name, class_name in tests:
    try:
        module = __import__(module_name, fromlist=[class_name])
        cls = getattr(module, class_name)
        print(f"✓ {name:30s} {module_name:30s} OK")
        success_count += 1
    except Exception as e:
        print(f"✗ {name:30s} {str(e)}")
        fail_count += 1

print("=" * 60)
print(f"Results: {success_count} passed, {fail_count} failed")
print("=" * 60)

if fail_count > 0:
    sys.exit(1)
else:
    print("✓ All components ready!")
    sys.exit(0)
