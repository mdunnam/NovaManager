"""
Photos/Library tab extracted from the monolithic main window.
"""
import os
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QInputDialog,
    QHeaderView,
    QAbstractItemView,
    QCheckBox,
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QPixmap, QKeySequence, QShortcut
from core.icons import icon as _icon


class PhotosTab(QWidget):
    """Encapsulates the photos library table and batch operations."""

    # Column indices (must match table structure)
    COL_CHECKBOX = 0
    COL_ID = 1
    COL_THUMBNAIL = 2
    COL_SCENE = 3
    COL_MOOD = 4
    COL_SUBJECTS = 5
    COL_LOCATION = 6
    COL_OBJECTS = 7
    COL_STATUS = 8
    COL_IG = 9
    COL_TIKTOK = 10
    COL_PACKAGE = 11
    COL_TAGS = 12
    COL_DATE = 13
    COL_FILEPATH = 14
    COL_NOTES = 15

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.persistent_selected_ids = set()
        self.thumbnail_sizes = {"off": 0, "small": 50, "medium": 100, "large": 150}
        self.current_thumb_size = "medium"
        self._batch_undo_stack = []
        self._max_batch_undo = 5
        self._custom_smart_presets = []
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_search_filter)
        self._search_query = ''
        self._build_ui()
        self._load_custom_smart_presets()
        self.refresh()

        # Shortcut: '/' focuses the search bar from anywhere within this tab
        QShortcut(QKeySequence('/'), self, activated=self._focus_search)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── Quick-search bar ──────────────────────────────────────
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search:"))
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Filter by filename, tags, scene, location, notes, caption…  (/ to focus)")
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.textChanged.connect(self._on_search_text_changed)
        search_row.addWidget(self.search_bar)
        layout.addLayout(search_row)

        # Top toolbar
        toolbar = QHBoxLayout()

        refresh_btn = QPushButton()
        refresh_btn.setIcon(_icon('refresh'))
        refresh_btn.setIconSize(QSize(18, 18))
        refresh_btn.setToolTip("Refresh photo table")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)

        reanalyze_btn = QPushButton()
        reanalyze_btn.setIcon(_icon('reanalyze'))
        reanalyze_btn.setIconSize(QSize(18, 18))
        reanalyze_btn.setToolTip("Re-analyze selected photos with AI")
        reanalyze_btn.clicked.connect(self.reanalyze_selected)
        toolbar.addWidget(reanalyze_btn)

        train_ai_btn = QPushButton()
        train_ai_btn.setIcon(_icon('train'))
        train_ai_btn.setIconSize(QSize(18, 18))
        train_ai_btn.setToolTip("Train AI: Re-analyze using learned corrections")
        train_ai_btn.clicked.connect(self.reanalyze_selected)
        toolbar.addWidget(train_ai_btn)

        batch_retouch_btn = QPushButton("Batch Retouch")
        batch_retouch_btn.setIcon(_icon('batch_retouch'))
        batch_retouch_btn.setIconSize(QSize(16, 16))
        batch_retouch_btn.setToolTip("Apply AI blemish retouch to checked/selected photos")
        batch_retouch_btn.clicked.connect(self.controller.batch_ai_retouch_selected)
        toolbar.addWidget(batch_retouch_btn)

        test_retouch_btn = QPushButton("Test 1 Photo")
        test_retouch_btn.setIcon(_icon('test_photo'))
        test_retouch_btn.setIconSize(QSize(16, 16))
        test_retouch_btn.setToolTip("Run AI blemish retouch on one checked/selected photo")
        test_retouch_btn.clicked.connect(self.controller.batch_ai_retouch_test_one)
        toolbar.addWidget(test_retouch_btn)

        preset_subtle_btn = QPushButton("Subtle")
        preset_subtle_btn.setIcon(_icon('subtle'))
        preset_subtle_btn.setIconSize(QSize(16, 16))
        preset_subtle_btn.setToolTip("Batch preset: telea, radius 2, padding 1")
        preset_subtle_btn.clicked.connect(lambda: self.controller.apply_batch_retouch_preset("subtle"))
        toolbar.addWidget(preset_subtle_btn)

        preset_balanced_btn = QPushButton("Balanced")
        preset_balanced_btn.setIcon(_icon('balanced'))
        preset_balanced_btn.setIconSize(QSize(16, 16))
        preset_balanced_btn.setToolTip("Batch preset: telea, radius 3, padding 2")
        preset_balanced_btn.clicked.connect(lambda: self.controller.apply_batch_retouch_preset("balanced"))
        toolbar.addWidget(preset_balanced_btn)

        preset_strong_btn = QPushButton("Strong")
        preset_strong_btn.setIcon(_icon('strong'))
        preset_strong_btn.setIconSize(QSize(16, 16))
        preset_strong_btn.setToolTip("Batch preset: ns, radius 5, padding 3")
        preset_strong_btn.clicked.connect(lambda: self.controller.apply_batch_retouch_preset("strong"))
        toolbar.addWidget(preset_strong_btn)

        self.batch_settings_label = QLabel()
        self.batch_settings_label.setStyleSheet("color: #d0d0d0;")
        toolbar.addWidget(self.batch_settings_label)
        self._refresh_batch_settings_label()

        revert_retouch_btn = QPushButton("Revert Retouch")
        revert_retouch_btn.setIcon(_icon('revert'))
        revert_retouch_btn.setIconSize(QSize(16, 16))
        revert_retouch_btn.setToolTip("Revert last overwrite retouch for checked/selected photos")
        revert_retouch_btn.clicked.connect(self.controller.revert_last_retouch_selected)
        toolbar.addWidget(revert_retouch_btn)

        history_btn = QPushButton("Retouch History")
        history_btn.setIcon(_icon('retouch_history'))
        history_btn.setIconSize(QSize(16, 16))
        history_btn.setToolTip("View retouch audit history and revert a selected entry")
        history_btn.clicked.connect(self.controller.open_retouch_history_dialog)
        toolbar.addWidget(history_btn)

        toolbar.addStretch()

        toolbar.addWidget(QLabel("Batch Actions:"))
        self.batch_package = QLineEdit()
        self.batch_package.setPlaceholderText("Package name...")
        self.batch_package.setMaximumWidth(160)
        toolbar.addWidget(self.batch_package)

        apply_package_btn = QPushButton("Set Package")
        apply_package_btn.setIcon(_icon('package'))
        apply_package_btn.setIconSize(QSize(16, 16))
        apply_package_btn.clicked.connect(self.apply_package)
        toolbar.addWidget(apply_package_btn)

        self.batch_status = QComboBox()
        self.batch_status.addItems(["Raw", "Needs Edit", "Ready", "Released"])
        self.batch_status.setMaximumWidth(120)
        toolbar.addWidget(self.batch_status)

        apply_status_quick_btn = QPushButton("Set Status")
        apply_status_quick_btn.setIcon(_icon('status'))
        apply_status_quick_btn.setIconSize(QSize(16, 16))
        apply_status_quick_btn.clicked.connect(self.apply_quick_status)
        toolbar.addWidget(apply_status_quick_btn)

        self.batch_tags = QLineEdit()
        self.batch_tags.setPlaceholderText("Tags to append (comma-separated)")
        self.batch_tags.setMaximumWidth(210)
        toolbar.addWidget(self.batch_tags)

        append_tags_btn = QPushButton("Append Tags")
        append_tags_btn.setIcon(_icon('tag'))
        append_tags_btn.setIconSize(QSize(16, 16))
        append_tags_btn.clicked.connect(self.append_tags)
        toolbar.addWidget(append_tags_btn)

        self.batch_notes = QLineEdit()
        self.batch_notes.setPlaceholderText("Notes to append")
        self.batch_notes.setMaximumWidth(200)
        toolbar.addWidget(self.batch_notes)

        append_notes_btn = QPushButton("Append Notes")
        append_notes_btn.setIcon(_icon('notes'))
        append_notes_btn.setIconSize(QSize(16, 16))
        append_notes_btn.clicked.connect(self.append_notes)
        toolbar.addWidget(append_notes_btn)

        self.smart_preset_combo = QComboBox()
        self.smart_preset_combo.addItems([
            "Raw -> Needs Edit",
            "Needs Edit -> Ready",
            "Ready -> Released",
        ])
        self.smart_preset_combo.setMaximumWidth(180)
        toolbar.addWidget(self.smart_preset_combo)

        apply_preset_btn = QPushButton("Smart Apply")
        apply_preset_btn.setIcon(_icon('smart'))
        apply_preset_btn.setIconSize(QSize(16, 16))
        apply_preset_btn.clicked.connect(self.apply_smart_preset)
        toolbar.addWidget(apply_preset_btn)

        add_preset_btn = QPushButton("Preset +")
        add_preset_btn.setIcon(_icon('preset_add'))
        add_preset_btn.setIconSize(QSize(16, 16))
        add_preset_btn.setToolTip("Add custom smart status preset")
        add_preset_btn.clicked.connect(self.add_custom_smart_preset)
        toolbar.addWidget(add_preset_btn)

        remove_preset_btn = QPushButton("Preset -")
        remove_preset_btn.setIcon(_icon('preset_remove'))
        remove_preset_btn.setIconSize(QSize(16, 16))
        remove_preset_btn.setToolTip("Remove selected custom smart preset")
        remove_preset_btn.clicked.connect(self.remove_selected_smart_preset)
        toolbar.addWidget(remove_preset_btn)

        self.undo_history_combo = QComboBox()
        self.undo_history_combo.setMaximumWidth(220)
        self.undo_history_combo.setToolTip("Select a recent batch operation to undo")
        self.undo_history_combo.addItem("Undo History (empty)")
        toolbar.addWidget(self.undo_history_combo)

        undo_apply_btn = QPushButton("Undo")
        undo_apply_btn.setIcon(_icon('undo'))
        undo_apply_btn.setIconSize(QSize(16, 16))
        undo_apply_btn.setToolTip("Restore selected undo snapshot")
        undo_apply_btn.clicked.connect(self.undo_selected_batch)
        toolbar.addWidget(undo_apply_btn)

        toolbar.addStretch()

        self.thumb_btn = QPushButton(f"Thumbnails: {self.current_thumb_size.title()}")
        self.thumb_btn.setIcon(_icon('thumbnail_grid'))
        self.thumb_btn.setIconSize(QSize(16, 16))
        self.thumb_btn.clicked.connect(self.toggle_thumbnail_size)
        toolbar.addWidget(self.thumb_btn)

        layout.addLayout(toolbar)

        # Table
        self.photo_table = QTableWidget()
        self.photo_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.photo_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.photo_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed
        )

        columns = [
            "",
            "ID",
            "Thumbnail",
            "Scene",
            "Mood",
            "Subjects",
            "Location",
            "Objects",
            "Status",
            "IG",
            "TikTok",
            "Package",
            "Tags",
            "Date Created",
            "Filepath",
            "Notes",
        ]
        self.photo_table.setColumnCount(len(columns))
        self.photo_table.setHorizontalHeaderLabels(columns)
        self.photo_table.setColumnWidth(0, 30)
        self.photo_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.photo_table.setSortingEnabled(True)

        self.photo_table.itemChanged.connect(self.on_table_item_changed)
        self.photo_table.cellDoubleClicked.connect(self.on_table_cell_double_clicked)
        self.photo_table.cellClicked.connect(self.debug_log_cell_click)
        self.photo_table.viewport().installEventFilter(self.controller)

        layout.addWidget(self.photo_table)

        # Bottom toolbar
        bottom_toolbar = QHBoxLayout()

        select_all_btn = QPushButton("Select All")
        select_all_btn.setIcon(_icon('select_all'))
        select_all_btn.setIconSize(QSize(16, 16))
        select_all_btn.clicked.connect(self.select_all_photos)
        bottom_toolbar.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.setIcon(_icon('deselect_all'))
        deselect_all_btn.setIconSize(QSize(16, 16))
        deselect_all_btn.clicked.connect(self.deselect_all_photos)
        bottom_toolbar.addWidget(deselect_all_btn)

        bottom_toolbar.addStretch()

        bulk_edit_btn = QPushButton("Bulk Edit Cells")
        bulk_edit_btn.setIcon(_icon('bulk_edit'))
        bulk_edit_btn.setIconSize(QSize(16, 16))
        bulk_edit_btn.clicked.connect(self.bulk_edit_cells)
        bottom_toolbar.addWidget(bulk_edit_btn)

        bottom_toolbar.addWidget(QLabel("Set Status for Selected:"))

        self.status_dropdown = QComboBox()
        self.status_dropdown.addItems(["Raw", "Needs Edit", "Ready for Release", "Released"])
        bottom_toolbar.addWidget(self.status_dropdown)

        apply_status_btn = QPushButton("Apply Status")
        apply_status_btn.setIcon(_icon('check'))
        apply_status_btn.setIconSize(QSize(16, 16))
        apply_status_btn.clicked.connect(self.apply_status_to_selected)
        bottom_toolbar.addWidget(apply_status_btn)

        bottom_toolbar.addStretch()

        # Staged controls
        bottom_toolbar.addWidget(QLabel("Toggle Staged:"))
        staged_ig = QPushButton()
        staged_ig.setIcon(_icon('instagram'))
        staged_ig.setIconSize(QSize(18, 18))
        staged_ig.setToolTip("Stage to Instagram")
        staged_ig.clicked.connect(lambda: self.controller.toggle_staged("instagram"))
        bottom_toolbar.addWidget(staged_ig)

        staged_tiktok = QPushButton()
        staged_tiktok.setIcon(_icon('tiktok'))
        staged_tiktok.setIconSize(QSize(18, 18))
        staged_tiktok.setToolTip("Stage to TikTok")
        staged_tiktok.clicked.connect(lambda: self.controller.toggle_staged("tiktok"))
        bottom_toolbar.addWidget(staged_tiktok)

        unstage_btn = QPushButton()
        unstage_btn.setIcon(_icon('unstage'))
        unstage_btn.setIconSize(QSize(18, 18))
        unstage_btn.setToolTip("Unstage: move selected photos back to root/<package>")
        unstage_btn.clicked.connect(self.controller.unstage_selected)
        bottom_toolbar.addWidget(unstage_btn)

        package_btn = QPushButton()
        package_btn.setIcon(_icon('package'))
        package_btn.setIconSize(QSize(18, 18))
        package_btn.setToolTip("Manage packages for selected photos")
        package_btn.clicked.connect(self.controller.manage_packages_dialog)
        bottom_toolbar.addWidget(package_btn)

        unpackage_btn = QPushButton()
        unpackage_btn.setIcon(_icon('unpackage'))
        unpackage_btn.setIconSize(QSize(18, 18))
        unpackage_btn.setToolTip("Unpackage: clear package and move files to root")
        unpackage_btn.clicked.connect(self.controller.unpackage_selected)
        bottom_toolbar.addWidget(unpackage_btn)

        # Release controls
        bottom_toolbar.addWidget(QLabel("Toggle Release:"))

        toggle_ig = QPushButton()
        toggle_ig.setIcon(_icon('instagram'))
        toggle_ig.setIconSize(QSize(18, 18))
        toggle_ig.setToolTip("Release: Instagram")
        toggle_ig.clicked.connect(lambda: self.controller.toggle_release_status("released_instagram"))
        bottom_toolbar.addWidget(toggle_ig)

        toggle_tiktok = QPushButton()
        toggle_tiktok.setIcon(_icon('tiktok'))
        toggle_tiktok.setIconSize(QSize(18, 18))
        toggle_tiktok.setToolTip("Release: TikTok")
        toggle_tiktok.clicked.connect(lambda: self.controller.toggle_release_status("released_tiktok"))
        bottom_toolbar.addWidget(toggle_tiktok)

        layout.addLayout(bottom_toolbar)

    def _refresh_batch_settings_label(self):
        if hasattr(self.controller, "get_batch_retouch_settings_label"):
            self.batch_settings_label.setText(self.controller.get_batch_retouch_settings_label())

    # API methods
    # ── Search helpers ──────────────────────────────────────────────────

    def _focus_search(self):
        """Give keyboard focus to the search bar."""
        self.search_bar.setFocus()
        self.search_bar.selectAll()

    def _on_search_text_changed(self, text: str):
        """Debounce search input and trigger filtering after 250 ms."""
        self._search_query = text.strip().lower()
        self._search_timer.stop()
        self._search_timer.start(250)

    def _apply_search_filter(self):
        """Re-render the table applying the current search query without a full DB reload."""
        self.refresh()

    # ── Data loading ────────────────────────────────────────────────────

    def refresh(self):
        """Reload all photos and repopulate table, respecting the active search query."""
        self._refresh_batch_settings_label()
        self.photo_table.setRowCount(0)
        photos = self.controller.db.get_all_photos()

        # Apply in-memory search filter when query is present
        q = self._search_query
        if q:
            _search_fields = (
                'filename', 'ai_caption', 'suggested_hashtags', 'tags',
                'objects_detected', 'location', 'subjects', 'scene_type',
                'mood', 'notes', 'exif_camera', 'package_name',
            )
            photos = [
                p for p in photos
                if any(q in str(p.get(f) or '').lower() for f in _search_fields)
            ]

        for i, photo in enumerate(photos):
            self.photo_table.insertRow(i)
            self.photo_table.setRowHeight(i, self.thumbnail_sizes[self.current_thumb_size])

            # Checkbox column
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            cb = QCheckBox()
            cb.setProperty("photo_id", photo["id"])
            cb.stateChanged.connect(self.controller.on_row_checkbox_toggled)
            checkbox_layout.addWidget(cb)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.photo_table.setCellWidget(i, self.COL_CHECKBOX, checkbox_widget)

            # ID
            id_item = QTableWidgetItem(str(photo["id"]))
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.photo_table.setItem(i, self.COL_ID, id_item)

            # Thumbnail
            thumb_label = QLabel()
            thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if photo["filepath"] and os.path.exists(photo["filepath"]):
                pixmap = self.controller.get_cached_thumbnail(photo["filepath"], 60)
                if pixmap and not pixmap.isNull():
                    thumb_label.setPixmap(pixmap)
                else:
                    thumb_label.setText("[No Preview]")
            else:
                thumb_label.setText("[Missing]")
            self.photo_table.setCellWidget(i, self.COL_THUMBNAIL, thumb_label)

            # AI metadata columns
            self.photo_table.setItem(i, self.COL_SCENE, QTableWidgetItem(photo.get("scene_type") or ""))
            self.photo_table.setItem(i, self.COL_MOOD, QTableWidgetItem(photo.get("mood") or ""))
            self.photo_table.setItem(i, self.COL_SUBJECTS, QTableWidgetItem(photo.get("subjects") or ""))
            self.photo_table.setItem(i, self.COL_LOCATION, QTableWidgetItem(photo.get("location") or ""))
            self.photo_table.setItem(i, self.COL_OBJECTS, QTableWidgetItem(photo.get("objects_detected") or ""))

            # Status
            status_text = photo["status"] or "raw"
            self.photo_table.setItem(i, self.COL_STATUS, QTableWidgetItem(status_text))

            # Platform toggles
            ig_item = QTableWidgetItem("✓" if photo.get("released_instagram") else "")
            self.photo_table.setItem(i, self.COL_IG, ig_item)

            tt_item = QTableWidgetItem("✓" if photo.get("released_tiktok") else "")
            self.photo_table.setItem(i, self.COL_TIKTOK, tt_item)

            packages = self.controller.db.get_packages(photo["id"])
            package_display = ", ".join(packages) if packages else (photo.get("package_name") or "")
            self.photo_table.setItem(i, self.COL_PACKAGE, QTableWidgetItem(package_display))

            self.photo_table.setItem(i, self.COL_TAGS, QTableWidgetItem(photo["tags"] or ""))

            raw_date = str(photo["date_created"] or "")
            if "." in raw_date:
                raw_date = raw_date.split(".")[0]
            date_item = QTableWidgetItem(raw_date)
            date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.photo_table.setItem(i, self.COL_DATE, date_item)

            filepath_item = QTableWidgetItem(photo["filepath"] or "")
            filepath_item.setToolTip(photo["filepath"] or "No path")
            self.photo_table.setItem(i, self.COL_FILEPATH, filepath_item)

            self.photo_table.setItem(i, self.COL_NOTES, QTableWidgetItem(photo.get("notes") or ""))

        self.photo_table.setSortingEnabled(True)
        self.controller.refresh_tag_cloud()

    def on_table_item_changed(self, item):
        """Handle edits to table cells."""
        row = item.row()
        col = item.column()
        photo_id = self.get_photo_id_from_row(row)
        if photo_id is None:
            return

        field_map = {
            self.COL_SCENE: "scene_type",
            self.COL_MOOD: "mood",
            self.COL_SUBJECTS: "subjects",
            self.COL_LOCATION: "location",
            self.COL_OBJECTS: "objects_detected",
            self.COL_STATUS: "status",
            self.COL_PACKAGE: "package_name",
            self.COL_TAGS: "tags",
            self.COL_NOTES: "notes",
        }

        field = field_map.get(col)
        if field:
            self.controller.db.update_photo_metadata(photo_id, {field: item.text()})

    def on_table_cell_double_clicked(self, row: int, col: int):
        """Open the folder when package cell is double-clicked."""
        try:
            if col == self.COL_PACKAGE:
                fp_item = self.photo_table.item(row, self.COL_FILEPATH)
                if fp_item:
                    path = fp_item.text()
                    folder = os.path.dirname(path)
                    if folder and os.path.isdir(folder):
                        os.startfile(folder)
        except Exception as exc:
            print(f"Open package folder error: {exc}")

    def debug_log_cell_click(self, row: int, col: int):
        """Log cell clicks for debugging."""
        try:
            photo_id = self.get_photo_id_from_row(row)
            header_item = self.photo_table.horizontalHeaderItem(col)
            header = header_item.text() if header_item else "<no header>"
            if self.controller.statusBar():
                self.controller.statusBar().showMessage(f"Clicked r{row} c{col} [{header}]", 2000)
        except Exception as exc:
            print(f"debug_log_cell_click error: {exc}")

    def get_photo_id_from_row(self, row: int) -> int:
        """Extract photo ID from table row."""
        try:
            id_item = self.photo_table.item(row, self.COL_ID)
            if id_item:
                return int(id_item.text())
        except (ValueError, AttributeError):
            pass
        return None

    def toggle_thumbnail_size(self):
        """Toggle thumbnail size between small, medium, large."""
        sizes = ["small", "medium", "large"]
        idx = sizes.index(self.current_thumb_size)
        self.current_thumb_size = sizes[(idx + 1) % len(sizes)]
        self.thumb_btn.setText(f"Thumbnails: {self.current_thumb_size.title()}")

        row_height = self.thumbnail_sizes[self.current_thumb_size]
        for i in range(self.photo_table.rowCount()):
            self.photo_table.setRowHeight(i, row_height)

    def apply_package(self):
        """Apply batch package name to selected photos."""
        package_name = self.batch_package.text().strip()
        if not package_name:
            QMessageBox.warning(self, "Empty Package", "Enter a package name first")
            return

        target_ids = self.get_target_photo_ids()
        if not target_ids:
            QMessageBox.information(self, "No Selection", "Please select photos first")
            return

        if not self._confirm_batch_action("Set Package", target_ids, [f"Package: {package_name}"]):
            return

        self._capture_undo_snapshot(target_ids, ["package_name"], label=f"Set Package: {package_name}")

        for photo_id in target_ids:
            self.controller.db.set_packages(photo_id, [package_name])

        self.refresh()
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(f"Set package for {len(target_ids)} photo(s)", 3000)

    def apply_status_to_selected(self):
        """Apply status to selected photos."""
        status_map = {"Raw": "raw", "Needs Edit": "needs_edit", "Ready for Release": "ready", "Released": "released"}
        status = status_map.get(self.status_dropdown.currentText(), "raw")

        target_ids = self.get_target_photo_ids()
        if not target_ids:
            QMessageBox.information(self, "No Selection", "Please select photos first")
            return

        if not self._confirm_batch_action("Set Status", target_ids, [f"Status: {status}"]):
            return

        self._capture_undo_snapshot(target_ids, ["status"], label=f"Set Status: {status}")

        self.controller.db.bulk_update(set(target_ids), {"status": status})
        self.refresh()
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(f"Updated status for {len(target_ids)} photo(s)", 3000)

    def apply_quick_status(self):
        """Apply quick status from the top batch toolbar."""
        status_map = {"Raw": "raw", "Needs Edit": "needs_edit", "Ready": "ready", "Released": "released"}
        status = status_map.get(self.batch_status.currentText(), "raw")

        target_ids = self.get_target_photo_ids()
        if not target_ids:
            QMessageBox.information(self, "No Selection", "Please check/select photos first")
            return

        if not self._confirm_batch_action("Set Status", target_ids, [f"Status: {status}"]):
            return

        self._capture_undo_snapshot(target_ids, ["status"], label=f"Quick Status: {status}")
        self.controller.db.bulk_update(set(target_ids), {"status": status})
        self.refresh()

    def append_tags(self):
        """Append tags to checked/selected photos with deduplication."""
        raw = self.batch_tags.text().strip()
        if not raw:
            QMessageBox.information(self, "Tags", "Enter tags first")
            return

        new_tags = [t.strip().lower() for t in raw.split(",") if t.strip()]
        if not new_tags:
            QMessageBox.information(self, "Tags", "No valid tags found")
            return

        target_ids = self.get_target_photo_ids()
        if not target_ids:
            QMessageBox.information(self, "No Selection", "Please check/select photos first")
            return

        if not self._confirm_batch_action("Append Tags", target_ids, [f"Tags: {', '.join(new_tags)}"]):
            return

        self._capture_undo_snapshot(target_ids, ["tags"], label=f"Append Tags: {', '.join(new_tags)[:40]}")
        for photo_id in target_ids:
            photo = self.controller.db.get_photo(photo_id)
            current = [t.strip().lower() for t in (photo.get("tags") or "").split(",") if t.strip()]
            merged = []
            seen = set()
            for tag in current + new_tags:
                if tag and tag not in seen:
                    seen.add(tag)
                    merged.append(tag)
            self.controller.db.update_photo_metadata(photo_id, {"tags": ", ".join(merged)})
        self.refresh()

    def append_notes(self):
        """Append notes text to checked/selected photos."""
        note = self.batch_notes.text().strip()
        if not note:
            QMessageBox.information(self, "Notes", "Enter note text first")
            return

        target_ids = self.get_target_photo_ids()
        if not target_ids:
            QMessageBox.information(self, "No Selection", "Please check/select photos first")
            return

        if not self._confirm_batch_action("Append Notes", target_ids, [f"Text: {note}"]):
            return

        self._capture_undo_snapshot(target_ids, ["notes"], label=f"Append Notes: {note[:40]}")
        for photo_id in target_ids:
            photo = self.controller.db.get_photo(photo_id)
            existing = (photo.get("notes") or "").strip()
            updated = f"{existing}\n{note}".strip() if existing else note
            self.controller.db.update_photo_metadata(photo_id, {"notes": updated})
        self.refresh()

    def apply_smart_preset(self):
        """Apply conditional status transitions to selected photos."""
        preset = self.smart_preset_combo.currentText()
        mapping = {
            "Raw -> Needs Edit": ("raw", "needs_edit"),
            "Needs Edit -> Ready": ("needs_edit", "ready"),
            "Ready -> Released": ("ready", "released"),
        }
        for item in self._custom_smart_presets:
            mapping[item["name"]] = (item["src"], item["dst"])
        src_status, dst_status = mapping.get(preset, ("raw", "needs_edit"))

        target_ids = self.get_target_photo_ids()
        if not target_ids:
            QMessageBox.information(self, "No Selection", "Please check/select photos first")
            return

        eligible = []
        for photo_id in target_ids:
            photo = self.controller.db.get_photo(photo_id)
            if (photo.get("status") or "raw") == src_status:
                eligible.append(photo_id)

        if not eligible:
            QMessageBox.information(self, "Smart Apply", f"No selected photos in '{src_status}' status")
            return

        if not self._confirm_batch_action("Smart Apply", eligible, [f"{src_status} -> {dst_status}"]):
            return

        self._capture_undo_snapshot(eligible, ["status"], label=f"Smart: {src_status} → {dst_status}")
        self.controller.db.bulk_update(set(eligible), {"status": dst_status})
        self.refresh()
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(f"Smart Apply updated {len(eligible)} photo(s)", 3000)

    def undo_selected_batch(self):
        """Undo the snapshot selected in the undo history dropdown."""
        if not self._batch_undo_stack:
            QMessageBox.information(self, "Undo History", "No batch operations to undo")
            return

        idx = self.undo_history_combo.currentIndex()
        # Stack is displayed newest-first; index 0 = top of stack
        stack_idx = len(self._batch_undo_stack) - 1 - idx
        if stack_idx < 0 or stack_idx >= len(self._batch_undo_stack):
            QMessageBox.information(self, "Undo History", "Select an operation from the dropdown")
            return

        snapshot = self._batch_undo_stack.pop(stack_idx)
        # Drop all snapshots that were captured after the restored one
        del self._batch_undo_stack[stack_idx:]

        restored = 0
        for row in snapshot.get("rows", []):
            photo_id = row.get("photo_id")
            if photo_id is None:
                continue
            updates = dict(row.get("updates") or {})
            if updates:
                self.controller.db.update_photo_metadata(photo_id, updates)
            if "packages" in row:
                self.controller.db.set_packages(photo_id, list(row.get("packages") or []))
            restored += 1

        self._refresh_undo_dropdown()
        self.refresh()
        label = snapshot.get("label", "Batch")
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(f"Undone '{label}' — {restored} photo(s) restored", 4000)

    def add_custom_smart_preset(self):
        name, ok = QInputDialog.getText(self, "Add Smart Preset", "Preset name:")
        if not ok or not name.strip():
            return
        src, ok = QInputDialog.getText(self, "Add Smart Preset", "Source status value (e.g., needs_edit):")
        if not ok or not src.strip():
            return
        dst, ok = QInputDialog.getText(self, "Add Smart Preset", "Destination status value (e.g., ready):")
        if not ok or not dst.strip():
            return
        item = {"name": name.strip(), "src": src.strip().lower(), "dst": dst.strip().lower()}
        self._custom_smart_presets = [p for p in self._custom_smart_presets if p.get("name") != item["name"]]
        self._custom_smart_presets.append(item)
        self._save_custom_smart_presets()
        self._rebuild_smart_preset_combo()

    def remove_selected_smart_preset(self):
        current = self.smart_preset_combo.currentText()
        removed = [p for p in self._custom_smart_presets if p.get("name") == current]
        if not removed:
            QMessageBox.information(self, "Preset", "Select a custom preset to remove")
            return
        self._custom_smart_presets = [p for p in self._custom_smart_presets if p.get("name") != current]
        self._save_custom_smart_presets()
        self._rebuild_smart_preset_combo()

    def reanalyze_selected(self):
        """Trigger re-analysis of selected photos."""
        from nova_manager import ReanalyzerThread

        target_ids = self.get_target_photo_ids()
        if not target_ids:
            QMessageBox.information(self, "No Selection", "Please select photos first")
            return

        photos_to_reanalyze = [self.controller.db.get_photo(pid) for pid in target_ids if self.controller.db.get_photo(pid)]

        self.controller.reanalyzer_thread = ReanalyzerThread(photos_to_reanalyze, self.controller.db.db_path)
        self.controller.reanalyzer_thread.progress.connect(self.on_reanalyze_progress)
        self.controller.reanalyzer_thread.finished.connect(self.on_reanalyze_finished)
        self.controller.reanalyzer_thread.error.connect(self.on_reanalyze_error)
        self.controller.reanalyzer_thread.start()

        self.controller.cancel_btn.setEnabled(True)

    def on_reanalyze_progress(self, current, total, status):
        """Handle progress updates during re-analysis."""
        self.controller.progress_bar.setVisible(True)
        self.controller.progress_bar.setMaximum(total)
        self.controller.progress_bar.setValue(current)
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(status, 0)

    def on_reanalyze_finished(self):
        """Handle re-analysis completion."""
        self.controller.progress_bar.setVisible(False)
        self.refresh()
        if self.controller.statusBar():
            self.controller.statusBar().showMessage("Re-analysis complete", 3000)
        self.controller.cancel_btn.setEnabled(False)

    def on_reanalyze_error(self, error_msg):
        """Handle re-analysis error."""
        self.controller.progress_bar.setVisible(False)
        QMessageBox.warning(self, "Analysis Error", error_msg)
        self.controller.cancel_btn.setEnabled(False)

    def select_all_photos(self):
        """Select all photos in the table."""
        self.photo_table.selectAll()

    def deselect_all_photos(self):
        """Deselect all photos in the table."""
        self.photo_table.clearSelection()

    def bulk_edit_cells(self):
        """Open bulk edit dialog and persist changes to the database."""
        value, ok = QInputDialog.getText(self, "Bulk Edit", "Enter value for selected cells:")
        if not ok or not value:
            return

        self.photo_table.blockSignals(True)
        updated_rows: set[int] = set()
        for index in self.photo_table.selectedIndexes():
            item = self.photo_table.item(index.row(), index.column())
            if item:
                item.setText(value)
                updated_rows.add(index.row())
        self.photo_table.blockSignals(False)

        # Persist each changed row to the database via on_table_item_changed logic
        field_map = {
            self.COL_SCENE: "scene_type",
            self.COL_MOOD: "mood",
            self.COL_SUBJECTS: "subjects",
            self.COL_LOCATION: "location",
            self.COL_OBJECTS: "objects_detected",
            self.COL_STATUS: "status",
            self.COL_PACKAGE: "package_name",
            self.COL_TAGS: "tags",
            self.COL_NOTES: "notes",
        }
        cols_in_selection = {idx.column() for idx in self.photo_table.selectedIndexes()}
        for row in updated_rows:
            photo_id = self.get_photo_id_from_row(row)
            if photo_id is None:
                continue
            updates = {}
            for col in cols_in_selection:
                field = field_map.get(col)
                if field:
                    updates[field] = value
            if updates:
                self.controller.db.update_photo_metadata(photo_id, updates)

    def get_target_photo_ids(self) -> list:
        """Get checked or selected photo IDs."""
        ids = []
        seen = set()

        # Prefer checked rows if any are checked.
        for row in range(self.photo_table.rowCount()):
            widget = self.photo_table.cellWidget(row, self.COL_CHECKBOX)
            if not widget:
                continue
            cb = widget.findChild(QCheckBox)
            if cb and cb.isChecked():
                pid = self.get_photo_id_from_row(row)
                if pid is not None and pid not in seen:
                    seen.add(pid)
                    ids.append(pid)

        if ids:
            return ids

        rows = {it.row() for it in self.photo_table.selectedItems()}
        ids = []
        for r in rows:
            pid = self.get_photo_id_from_row(r)
            if pid is not None:
                ids.append(pid)
        return ids

    def _capture_undo_snapshot(self, photo_ids, fields, label=None):
        """Capture previous values for multi-step batch undo."""
        rows = []
        for photo_id in photo_ids:
            photo = self.controller.db.get_photo(photo_id)
            if not photo:
                continue
            updates = {field: photo.get(field) for field in fields}
            row = {"photo_id": photo_id, "updates": updates}
            if "package_name" in fields:
                row["packages"] = self.controller.db.get_packages(photo_id)
            rows.append(row)
        snapshot_label = label or (fields[0].replace("_", " ").title() if fields else "Batch")
        self._batch_undo_stack.append({"rows": rows, "label": snapshot_label, "count": len(rows)})
        if len(self._batch_undo_stack) > self._max_batch_undo:
            self._batch_undo_stack.pop(0)
        self._refresh_undo_dropdown()

    def _refresh_undo_dropdown(self):
        """Rebuild the undo history dropdown from the current stack (newest first)."""
        if not hasattr(self, "undo_history_combo"):
            return
        self.undo_history_combo.blockSignals(True)
        self.undo_history_combo.clear()
        if not self._batch_undo_stack:
            self.undo_history_combo.addItem("Undo History (empty)")
        else:
            for entry in reversed(self._batch_undo_stack):
                lbl = entry.get("label", "Batch")
                cnt = entry.get("count", 0)
                self.undo_history_combo.addItem(f"{lbl}  ({cnt} photo(s))")
        self.undo_history_combo.blockSignals(False)

    def _confirm_batch_action(self, action_name, photo_ids, detail_lines=None):
        details = detail_lines or []
        body = [f"Apply '{action_name}' to {len(photo_ids)} photo(s)?"]
        body.extend(details)
        response = QMessageBox.question(
            self,
            "Batch Preview",
            "\n".join(body),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return response == QMessageBox.StandardButton.Yes

    def _load_custom_smart_presets(self):
        settings = getattr(self.controller, "settings", None)
        if settings is None:
            return
        raw = settings.value("photos/custom_smart_presets", "[]")
        try:
            data = json.loads(raw) if isinstance(raw, str) else []
        except Exception:
            data = []
        self._custom_smart_presets = []
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            src = str(item.get("src", "")).strip().lower()
            dst = str(item.get("dst", "")).strip().lower()
            if name and src and dst:
                self._custom_smart_presets.append({"name": name, "src": src, "dst": dst})
        self._rebuild_smart_preset_combo()

    def _save_custom_smart_presets(self):
        settings = getattr(self.controller, "settings", None)
        if settings is None:
            return
        settings.setValue("photos/custom_smart_presets", json.dumps(self._custom_smart_presets))
        settings.sync()

    def _rebuild_smart_preset_combo(self):
        defaults = [
            "Raw -> Needs Edit",
            "Needs Edit -> Ready",
            "Ready -> Released",
        ]
        current = self.smart_preset_combo.currentText() if hasattr(self, "smart_preset_combo") else ""
        self.smart_preset_combo.blockSignals(True)
        self.smart_preset_combo.clear()
        self.smart_preset_combo.addItems(defaults)
        for item in self._custom_smart_presets:
            self.smart_preset_combo.addItem(item["name"])
        if current:
            idx = self.smart_preset_combo.findText(current)
            if idx >= 0:
                self.smart_preset_combo.setCurrentIndex(idx)
        self.smart_preset_combo.blockSignals(False)
