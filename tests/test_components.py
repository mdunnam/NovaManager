#!/usr/bin/env python3
"""Test script to verify all tab components load correctly."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
# Force UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Create QApplication
app = QApplication.instance() or QApplication([])

print("=" * 60)
print("PHOTOFLOW - COMPONENT IMPORT TEST")
print("=" * 60)

# Test imports
tests = [
    ("Main Application", "nova_manager", "MainWindow"),
    ("Gallery Tab", "ui.gallery_tab", "GalleryTab"),
    ("Photos Tab", "ui.photos_tab", "PhotosTab"),
    ("Filters Tab", "ui.filters_tab", "FiltersTab"),
    ("Publish Tab", "ui.publish_tab", "PublishTab"),
    ("Instagram Tab", "ui.instagram_tab", "InstagramTab"),
    ("TikTok Tab", "ui.tiktok_tab", "TikTokTab"),
    ("Albums Tab", "ui.albums_tab", "AlbumsTab"),
    ("Composer Tab", "ui.composer_tab", "ComposerTab"),
    ("Schedule Tab", "ui.schedule_tab", "ScheduleTab"),
    ("Settings Tab", "ui.settings_tab", "SettingsTab"),
    ("Duplicates Tab", "ui.duplicates_tab", "DuplicatesTab"),
    ("Database", "core.database", "PhotoDatabase"),
    ("AI Analyzer", "core.ai_analyzer", "analyze_image"),
    ("EXIF Extractor", "core.exif_extractor", "extract_exif"),
    ("Quality Scorer", "core.quality_scorer", "score_image"),
    ("Duplicate Detector", "core.duplicate_detector", "find_duplicates"),
    ("Folder Watcher", "core.folder_watcher", "FolderWatcher"),
    ("Social Base", "core.social.base", "SocialPlatform"),
    ("Instagram API", "core.social.instagram_api", "InstagramAPI"),
    ("Twitter API", "core.social.twitter_api", "TwitterAPI"),
    ("Facebook API", "core.social.facebook_api", "FacebookAPI"),
    ("Pinterest API", "core.social.pinterest_api", "PinterestAPI"),
    ("Scheduler", "core.social.scheduler", "SchedulerWorker"),
    ("Threads API", "core.social.threads_api", "ThreadsAPI"),
    ("TikTok API", "core.social.tiktok_api", "TikTokAPI"),
    ("Batch Tab", "ui.batch_tab", "BatchTab"),
    ("History Tab", "ui.history_tab", "HistoryTab"),
    ("AI Learning Tab", "ui.learning_tab", "AILearningTab"),
    ("Vocabularies Tab", "ui.vocabularies_tab", "VocabulariesTab"),
    ("Face Matching Tab", "ui.face_matching_tab", "FaceMatchingTab"),
    ("Icon Library", "core.icons", "icon"),
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
