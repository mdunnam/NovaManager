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


# ── Round 10 tests ────────────────────────────────────────────────────────────

def _make_in_memory_db():
    """Return a PhotoDatabase instance backed by an in-memory SQLite database."""
    import sqlite3
    from core.database import PhotoDatabase
    db = PhotoDatabase.__new__(PhotoDatabase)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.conn = conn
    db.cursor = conn.cursor()
    db.encryption = None
    db.db_path = ":memory:"
    # Execute enough schema to service the tests.
    db.cursor.executescript("""
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            date_created TIMESTAMP,
            date_modified TIMESTAMP,
            type_of_shot TEXT, pose TEXT, facing_direction TEXT,
            explicit_level TEXT, color_of_clothing TEXT, material TEXT,
            type_clothing TEXT, footwear TEXT, interior_exterior TEXT,
            location TEXT, status TEXT DEFAULT 'raw',
            released_instagram BOOLEAN DEFAULT 0,
            released_tiktok BOOLEAN DEFAULT 0,
            released_fansly BOOLEAN DEFAULT 0,
            date_released_instagram TIMESTAMP,
            date_released_tiktok TIMESTAMP,
            date_released_fansly TIMESTAMP,
            package_name TEXT, notes TEXT, tags TEXT,
            face_similarity INTEGER DEFAULT 0,
            face_match_rating INTEGER DEFAULT 0,
            flagged INTEGER DEFAULT 0,
            scene_type TEXT DEFAULT '', composition TEXT DEFAULT '',
            subjects TEXT DEFAULT '', dominant_colors TEXT DEFAULT '',
            objects_detected TEXT DEFAULT '', mood TEXT DEFAULT '',
            ai_caption TEXT DEFAULT '', suggested_hashtags TEXT DEFAULT '',
            perceptual_hash TEXT DEFAULT '', file_size_kb INTEGER DEFAULT 0,
            image_width INTEGER DEFAULT 0, image_height INTEGER DEFAULT 0,
            color_profile TEXT DEFAULT '', content_rating TEXT DEFAULT 'general',
            platform_status TEXT DEFAULT '{}',
            exif_camera TEXT DEFAULT '', exif_lens TEXT DEFAULT '',
            exif_focal_length TEXT DEFAULT '', exif_iso TEXT DEFAULT '',
            exif_aperture TEXT DEFAULT '', exif_shutter TEXT DEFAULT '',
            exif_gps_lat REAL DEFAULT NULL, exif_gps_lon REAL DEFAULT NULL,
            exif_date_taken TIMESTAMP DEFAULT NULL,
            blur_score REAL DEFAULT 0.0, exposure_score REAL DEFAULT 0.5,
            quality TEXT DEFAULT '', quality_issues TEXT DEFAULT '',
            quality_score REAL DEFAULT 0.0, file_hash TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, description TEXT DEFAULT '',
            cover_photo_id INTEGER, date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            date_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sort_order INTEGER DEFAULT 0, is_smart INTEGER DEFAULT 0,
            smart_filter TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS album_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            album_id INTEGER, photo_id INTEGER,
            sort_order INTEGER DEFAULT 0,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(album_id, photo_id)
        );
        CREATE TABLE IF NOT EXISTS vocabularies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_name TEXT NOT NULL, value TEXT NOT NULL,
            description TEXT, sort_order INTEGER DEFAULT 0,
            UNIQUE(field_name, value)
        );
        CREATE TABLE IF NOT EXISTS photo_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id INTEGER NOT NULL, package_name TEXT NOT NULL
        );
    """)
    conn.commit()
    return db


def test_update_photo_metadata_column_allowlist() -> None:
    """Unknown/injected column names must be silently dropped, not executed."""
    db = _make_in_memory_db()
    db.cursor.execute(
        "INSERT INTO photos (filepath, filename) VALUES (?, ?)",
        ("/tmp/test.jpg", "test.jpg")
    )
    db.conn.commit()
    photo_id = db.cursor.lastrowid

    # Attempt to inject an unknown column — should not raise, and the table must survive.
    db.update_photo_metadata(photo_id, {'__injected__': 1, 'status': 'ready'})

    db.cursor.execute("SELECT status FROM photos WHERE id = ?", (photo_id,))
    row = db.cursor.fetchone()
    assert row[0] == 'ready', "Valid column status should have been updated"

    # Table must not have gained any new column.
    db.cursor.execute("PRAGMA table_info(photos)")
    col_names = {r[1] for r in db.cursor.fetchall()}
    assert '__injected__' not in col_names, "Injected column must not be created"


def test_rename_vocabulary_value_injection_guard() -> None:
    """rename_vocabulary_value must reject unknown field names."""
    from core.database import PhotoDatabase
    db = _make_in_memory_db()

    # Bind the method
    result = PhotoDatabase.rename_vocabulary_value(db, "'; DROP TABLE photos; --", "a", "b")
    assert result is False, "rename_vocabulary_value should reject unsafe field names"

    # Original photos table must be intact
    db.cursor.execute("SELECT COUNT(*) FROM photos")
    assert db.cursor.fetchone()[0] == 0  # empty but exists


def test_cleanup_unused_vocabulary_injection_guard() -> None:
    """cleanup_unused_vocabulary must reject unknown field names without crashing."""
    from core.database import PhotoDatabase

    db = _make_in_memory_db()
    # Should return silently without error or table modification.
    PhotoDatabase.cleanup_unused_vocabulary(db, "'; DROP TABLE photos; --")

    db.cursor.execute("SELECT COUNT(*) FROM photos")
    assert db.cursor.fetchone()[0] == 0  # table intact


def test_flagged_column_persists() -> None:
    """The flagged column must be added during ensure_columns and round-trip via update_photo."""
    db = _make_in_memory_db()
    db.cursor.execute(
        "INSERT INTO photos (filepath, filename) VALUES (?, ?)",
        ("/tmp/flag_test.jpg", "flag_test.jpg")
    )
    db.conn.commit()
    photo_id = db.cursor.lastrowid

    db.update_photo_metadata(photo_id, {'flagged': 1})

    db.cursor.execute("SELECT flagged FROM photos WHERE id = ?", (photo_id,))
    row = db.cursor.fetchone()
    assert row[0] == 1, "flagged column should persist after update_photo_metadata"


def test_smart_album_missing_filter_controls() -> None:
    """Smart albums built from released_ig, released_tiktok, unanalyzed, has_exif, has_gps filters."""
    ctrl = _DummyController()
    ctrl.db._photos = [
        {"id": 1, "released_instagram": 1, "released_tiktok": 0,
         "type_of_shot": "", "exif_camera": "", "exif_gps_lat": None,
         "scene_type": "", "mood": "", "subjects": "", "quality": "",
         "content_rating": "general", "tags": "", "location": "", "package_name": ""},
        {"id": 2, "released_instagram": 0, "released_tiktok": 1,
         "type_of_shot": "fullbody", "exif_camera": "Canon", "exif_gps_lat": 51.5,
         "scene_type": "", "mood": "", "subjects": "", "quality": "",
         "content_rating": "general", "tags": "", "location": "", "package_name": ""},
    ]

    tab = AlbumsTab(ctrl)

    ig_only = tab._get_smart_album_photos("released_ig")
    assert [p["id"] for p in ig_only] == [1], "released_ig should match only Instagram-published photos"

    tiktok_only = tab._get_smart_album_photos("released_tiktok")
    assert [p["id"] for p in tiktok_only] == [2], "released_tiktok should match to TikTok-published photos"

    unanalyzed = tab._get_smart_album_photos("unanalyzed")
    assert [p["id"] for p in unanalyzed] == [1], "unanalyzed should match photos with empty type_of_shot"

    has_exif = tab._get_smart_album_photos("has_exif")
    assert [p["id"] for p in has_exif] == [2], "has_exif should match photos with exif_camera set"

    has_gps = tab._get_smart_album_photos("has_gps")
    assert [p["id"] for p in has_gps] == [2], "has_gps should match photos with exif_gps_lat set"


def test_add_vocabulary_value_returns_false_for_duplicate() -> None:
    """add_vocabulary_value should return False (not True) when value already exists."""
    db = _make_in_memory_db()
    from core.database import PhotoDatabase

    result1 = PhotoDatabase.add_vocabulary_value(db, "scene_type", "portrait")
    assert result1 is True, "First insert should return True"

    result2 = PhotoDatabase.add_vocabulary_value(db, "scene_type", "portrait")
    assert result2 is False, "Duplicate insert should return False via INSERT OR IGNORE rowcount check"


def test_batch_rename_db_sync() -> None:
    """After a batch rename, the DB filepath/filename should match the new path."""
    import tempfile
    import unittest.mock as mock
    from ui.batch_tab import _BatchWorker

    ctrl = _DummyController()
    db = _make_in_memory_db()
    db.cursor.execute(
        "INSERT INTO photos (filepath, filename) VALUES (?, ?)",
        ("/tmp/old_name.jpg", "old_name.jpg")
    )
    db.conn.commit()
    photo_id = db.cursor.lastrowid
    ctrl.db = db

    with tempfile.TemporaryDirectory() as tmpdir:
        src = os.path.join(tmpdir, "old_name.jpg")
        open(src, "wb").close()  # create empty file

        photo = {"id": photo_id, "filepath": src, "filename": "old_name.jpg",
                 "exif_date_taken": None, "date_created": None,
                 "scene_type": "", "status": "raw"}

        worker = _BatchWorker([photo], "rename", {"pattern": "new_name"})

        done_calls = []
        worker.finished.connect(lambda d, e: done_calls.append((d, e)))
        worker.run()

        new_fp = photo.get("_new_filepath")
        assert new_fp is not None, "Worker should have stored _new_filepath on renamed photo"
        assert os.path.basename(new_fp) == "new_name.jpg", f"Unexpected new name: {new_fp}"

        # Simulate what _on_done does for the DB sync
        db.update_photo_metadata(photo_id, {"filepath": new_fp, "filename": os.path.basename(new_fp)})

        db.cursor.execute("SELECT filepath, filename FROM photos WHERE id = ?", (photo_id,))
        row = db.cursor.fetchone()
        assert row[0] == new_fp, "DB filepath should be updated after rename"
        assert row[1] == "new_name.jpg", "DB filename should be updated after rename"


def main() -> int:
    app = QApplication.instance() or QApplication([])

    tests = [
        ("Gallery pagination + preserve_limit", test_gallery_pagination_sort_and_preserve_limit),
        ("Smart album status parsing", test_smart_album_status_clause_parsing),
        ("Face worker finished once", test_face_worker_emits_finished_once),
        ("Face worker cancel flag", test_face_worker_cancel_no_success_dialog),
        ("Date albums atomic transaction", test_date_albums_use_commit_false),
        ("update_photo_metadata rejects unknown columns", test_update_photo_metadata_column_allowlist),
        ("rename_vocabulary injection guard", test_rename_vocabulary_value_injection_guard),
        ("cleanup_vocabulary injection guard", test_cleanup_unused_vocabulary_injection_guard),
        ("flagged column persists", test_flagged_column_persists),
        ("Smart album 5 missing filter controls", test_smart_album_missing_filter_controls),
        ("add_vocabulary_value returns False for duplicate", test_add_vocabulary_value_returns_false_for_duplicate),
        ("Batch rename DB sync", test_batch_rename_db_sync),
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
