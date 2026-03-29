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


def test_face_worker_cancel_no_success_dialog() -> None:
    """Cancel should set cancelled=True on the finished signal."""

    class _Matcher:
        def __init__(self):
            self.calls = 0

        def compare_face(self, _filepath, return_details=True):
            self.calls += 1
            return {"rating": 3, "best_similarity": 0.7}

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f1, \
         tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f2, \
         tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f3:
        paths = [f1.name, f2.name, f3.name]

    try:
        matcher = _Matcher()
        photos = [{"id": i, "filepath": p} for i, p in enumerate(paths, 1)]
        worker = _AnalysisWorker(matcher, [], photos)
        worker._stop = True  # cancel before first iteration

        finished_calls = []
        worker.finished.connect(
            lambda a, r, c: finished_calls.append((a, r, c))
        )
        worker.run()

        assert len(finished_calls) == 1, "finished should emit exactly once even when cancelled"
        _, _, cancelled = finished_calls[0]
        assert cancelled is True, "cancelled flag must be True when stopped before first photo"
        assert matcher.calls == 0, "matcher should not be called after cancel"
    finally:
        for p in paths:
            try:
                os.remove(p)
            except OSError:
                pass


def test_date_albums_use_commit_false() -> None:
    """create_date_albums should batch all INSERTs into one transaction.

    We verify this indirectly: all albums and links are created correctly,
    and the helpers accept commit=False without raising.
    """
    import sqlite3
    import unittest.mock as mock
    from core.database import PhotoDatabase

    ctrl = _DummyController()

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, description TEXT DEFAULT '', is_smart INTEGER DEFAULT 0,
            smart_filter TEXT DEFAULT '', sort_order INTEGER DEFAULT 0,
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            date_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE album_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            album_id INTEGER, photo_id INTEGER,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sort_order INTEGER DEFAULT 0,
            UNIQUE(album_id, photo_id)
        );
    """)
    conn.commit()

    db = object.__new__(PhotoDatabase)
    db.conn = conn
    db.cursor = cur
    db.get_all_photos = lambda: [
        {"id": 1, "exif_date_taken": "2025-06-15", "date_created": None},
        {"id": 2, "exif_date_taken": "2025-06-20", "date_created": None},
        {"id": 3, "exif_date_taken": "2025-07-01", "date_created": None},
    ]
    ctrl.db = db

    tab = AlbumsTab(ctrl)
    tab.refresh_album_list = lambda: None

    with mock.patch("PyQt6.QtWidgets.QMessageBox.information"):
        tab.create_date_albums()

    # Both months exist as albums.
    cur.execute("SELECT name FROM albums ORDER BY name")
    names = {row[0] for row in cur.fetchall()}
    assert "June 2025" in names and "July 2025" in names, f"Unexpected albums: {names}"

    # All 3 photos are linked.
    cur.execute("SELECT COUNT(*) FROM album_photos")
    assert cur.fetchone()[0] == 3, "Expected all 3 photos linked to date albums"

    # create_album and add_photo_to_album accept commit=False without raising.
    album_id = db.create_album("Test Batch", commit=False)
    assert album_id is not None
    result = db.add_photo_to_album(album_id, 99, commit=False)
    assert result is True


def main() -> int:
    app = QApplication.instance() or QApplication([])

    tests = [
        ("Gallery pagination + preserve_limit", test_gallery_pagination_sort_and_preserve_limit),
        ("Smart album status parsing", test_smart_album_status_clause_parsing),
        ("Face worker finished once", test_face_worker_emits_finished_once),
        ("Face worker cancel flag", test_face_worker_cancel_no_success_dialog),
        ("Date albums atomic transaction", test_date_albums_use_commit_false),
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
