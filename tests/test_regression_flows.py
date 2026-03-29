#!/usr/bin/env python3
"""Regression tests for recent Gallery/Albums/FaceMatching fixes.

This is a script-style test (no pytest dependency), matching the existing test style
in this repository.
"""

import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt6.QtWidgets import QApplication, QWidget

from ui.gallery_tab import GalleryTab
from ui.albums_tab import AlbumsTab
from ui.face_matching_tab import _AnalysisWorker


class _DummyStatusBar:
    def showMessage(self, *_args, **_kwargs):
        pass


class _DummyDB:
    def __init__(self):
        self._photos = []

    def get_all_photos(self):
        return list(self._photos)

    def get_albums(self):
        return []

    def get_album_photos(self, _album_id):
        return []


class _DummyController:
    def __init__(self):
        self.db = _DummyDB()
        self.filters_tab = None
        self._status = _DummyStatusBar()

    def statusBar(self):
        return self._status

    def get_cached_thumbnail(self, *_args, **_kwargs):
        return None


def test_gallery_pagination_sort_and_preserve_limit() -> None:
    ctrl = _DummyController()
    tab = GalleryTab(ctrl)

    # Avoid heavy thumbnail creation in this logic test.
    tab._create_thumbnail = lambda _photo, _size: QWidget()
    tab._update_thumbnail_selection_styles = lambda: None

    photos = [
        {"id": i, "filename": f"img_{300 - i:03d}.jpg", "status": "raw"}
        for i in range(300)
    ]

    tab.gallery_group.setCurrentText("None")
    tab.gallery_sort.setCurrentText("Filename")

    tab.refresh_with_photos(photos)

    assert tab._display_photos[0]["filename"] == "img_001.jpg", "Expected sorted display list"
    assert tab._rendered_count == tab.PAGE_SIZE, "Expected first page rendered"
    assert len(tab._pending_photos) == 100, "Expected remaining photos queued"

    tab._load_next_page()
    assert tab._rendered_count == 300, "Expected all photos rendered after Load More"
    assert len(tab._pending_photos) == 0, "Expected no pending photos after second page"

    # Preserve loaded slice on refresh/reflow.
    tab.refresh_with_photos(photos, preserve_limit=True)
    assert tab._rendered_count == 300, "Expected preserve_limit to keep loaded slice"


def test_smart_album_status_clause_parsing() -> None:
    ctrl = _DummyController()
    ctrl.db._photos = [
        {"id": 1, "status": "raw", "scene_type": "portrait", "quality": "good", "mood": "calm", "subjects": "person", "content_rating": "general", "tags": "x", "location": "studio", "package_name": "pkg1"},
        {"id": 2, "status": "ready", "scene_type": "portrait", "quality": "good", "mood": "calm", "subjects": "person", "content_rating": "general", "tags": "x", "location": "studio", "package_name": "pkg1"},
        {"id": 3, "status": "released_tiktok", "scene_type": "portrait", "quality": "good", "mood": "calm", "subjects": "person", "content_rating": "general", "tags": "x", "location": "studio", "package_name": "pkg1"},
    ]

    tab = AlbumsTab(ctrl)

    raw = tab._get_smart_album_photos("status=raw")
    assert [p["id"] for p in raw] == [1], "status=raw should only match raw photos"

    ready = tab._get_smart_album_photos("status=ready")
    assert [p["id"] for p in ready] == [2], "status=ready should only match ready photos"

    released = tab._get_smart_album_photos("status=released")
    assert [p["id"] for p in released] == [3], "status=released should match released_* statuses"


def test_face_worker_emits_finished_once() -> None:
    class _Matcher:
        def compare_face(self, _filepath, return_details=True):
            return {"rating": 4, "best_similarity": 0.88}

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as a, tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as b:
        path_a = a.name
        path_b = b.name

    try:
        photos = [{"id": 1, "filepath": path_a}, {"id": 2, "filepath": path_b}]
        worker = _AnalysisWorker(_Matcher(), [], photos)

        finished_calls = []
        worker.finished.connect(lambda analyzed, rated, cancelled: finished_calls.append((analyzed, rated, cancelled)))

        # Run synchronously to make this deterministic.
        worker.run()

        assert len(finished_calls) == 1, "finished signal should emit exactly once per run"
        analyzed, rated, cancelled = finished_calls[0]
        assert analyzed == 2 and rated == 2 and cancelled is False, "Unexpected worker completion values"
    finally:
        try:
            os.remove(path_a)
        except OSError:
            pass
        try:
            os.remove(path_b)
        except OSError:
            pass


def main() -> int:
    app = QApplication.instance() or QApplication([])

    tests = [
        ("Gallery pagination + preserve_limit", test_gallery_pagination_sort_and_preserve_limit),
        ("Smart album status parsing", test_smart_album_status_clause_parsing),
        ("Face worker finished once", test_face_worker_emits_finished_once),
    ]

    print("=" * 60)
    print("NOVA MANAGER - REGRESSION FLOW TESTS")
    print("=" * 60)

    passed = 0
    failed = 0

    for name, fn in tests:
        try:
            fn()
            print(f"✓ {name}")
            passed += 1
        except Exception as exc:
            print(f"✗ {name}: {exc}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    # keep app referenced
    _ = app
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
