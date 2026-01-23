"""
Photos/Library tab extracted from the monolithic main window.
"""
import os
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
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap


class PhotosTab(QWidget):
    """Encapsulates the photos library table and batch operations."""

    # Column indices (must match table structure)
    COL_CHECKBOX = 0
    COL_ID = 1
    COL_THUMBNAIL = 2
    COL_TYPE = 3
    COL_POSE = 4
    COL_FACING = 5
    COL_LEVEL = 6
    COL_COLOR = 7
    COL_MATERIAL = 8
    COL_CLOTHING = 9
    COL_FOOTWEAR = 10
    COL_LOCATION = 11
    COL_STATUS = 12
    COL_IG = 13
    COL_TIKTOK = 14
    COL_FANSLY = 15
    COL_PACKAGE = 16
    COL_TAGS = 17
    COL_DATE = 18
    COL_FILEPATH = 19
    COL_NOTES = 20

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.persistent_selected_ids = set()
        self.thumbnail_sizes = {"off": 0, "small": 50, "medium": 100, "large": 150}
        self.current_thumb_size = "medium"
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Top toolbar
        toolbar = QHBoxLayout()

        refresh_btn = QPushButton()
        refresh_btn.setIcon(self.controller.get_icon("refresh.png", "↻"))
        refresh_btn.setIconSize(self.controller.icon_size)
        refresh_btn.setToolTip("Refresh photo table")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)

        reanalyze_btn = QPushButton()
        reanalyze_btn.setIcon(self.controller.get_icon("reanalyze.png", "AI"))
        reanalyze_btn.setIconSize(self.controller.icon_size)
        reanalyze_btn.setToolTip("Re-analyze selected photos with AI")
        reanalyze_btn.clicked.connect(self.reanalyze_selected)
        toolbar.addWidget(reanalyze_btn)

        train_ai_btn = QPushButton()
        train_ai_btn.setIcon(self.controller.get_icon("train.png", "T"))
        train_ai_btn.setIconSize(self.controller.icon_size)
        train_ai_btn.setToolTip("Train AI: Re-analyze using learned corrections")
        train_ai_btn.clicked.connect(self.reanalyze_selected)
        toolbar.addWidget(train_ai_btn)

        toolbar.addStretch()

        toolbar.addWidget(QLabel("Batch Actions:"))
        self.batch_package = QLineEdit()
        self.batch_package.setPlaceholderText("Package name...")
        self.batch_package.setMaximumWidth(200)
        toolbar.addWidget(self.batch_package)

        apply_package_btn = QPushButton("Set Package")
        apply_package_btn.clicked.connect(self.apply_package)
        toolbar.addWidget(apply_package_btn)

        toolbar.addStretch()

        self.thumb_btn = QPushButton(f"Thumbnails: {self.current_thumb_size.title()}")
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
            "Type",
            "Pose",
            "Facing",
            "Level",
            "Color",
            "Material",
            "Clothing",
            "Footwear",
            "Location",
            "Status",
            "IG",
            "TikTok",
            "Fansly",
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
        select_all_btn.clicked.connect(self.select_all_photos)
        bottom_toolbar.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self.deselect_all_photos)
        bottom_toolbar.addWidget(deselect_all_btn)

        bottom_toolbar.addStretch()

        bulk_edit_btn = QPushButton("Bulk Edit Cells")
        bulk_edit_btn.clicked.connect(self.bulk_edit_cells)
        bottom_toolbar.addWidget(bulk_edit_btn)

        bottom_toolbar.addWidget(QLabel("Set Status for Selected:"))

        self.status_dropdown = QComboBox()
        self.status_dropdown.addItems(["Raw", "Needs Edit", "Ready for Release", "Released"])
        bottom_toolbar.addWidget(self.status_dropdown)

        apply_status_btn = QPushButton("Apply Status")
        apply_status_btn.clicked.connect(self.apply_status_to_selected)
        bottom_toolbar.addWidget(apply_status_btn)

        bottom_toolbar.addStretch()

        # Staged controls
        bottom_toolbar.addWidget(QLabel("Toggle Staged:"))
        staged_ig = QPushButton()
        staged_ig.setIcon(self.controller.get_icon("instagram.png", "IG"))
        staged_ig.setIconSize(self.controller.icon_size)
        staged_ig.setToolTip("Stage to Instagram")
        staged_ig.clicked.connect(lambda: self.controller.toggle_staged("instagram"))
        bottom_toolbar.addWidget(staged_ig)

        staged_tiktok = QPushButton()
        staged_tiktok.setIcon(self.controller.get_icon("tiktok.png", "TT"))
        staged_tiktok.setIconSize(self.controller.icon_size)
        staged_tiktok.setToolTip("Stage to TikTok")
        staged_tiktok.clicked.connect(lambda: self.controller.toggle_staged("tiktok"))
        bottom_toolbar.addWidget(staged_tiktok)

        staged_fansly = QPushButton()
        staged_fansly.setIcon(self.controller.get_icon("fansly.png", "F"))
        staged_fansly.setIconSize(self.controller.icon_size)
        staged_fansly.setToolTip("Stage to Fansly")
        staged_fansly.clicked.connect(lambda: self.controller.toggle_staged("fansly"))
        bottom_toolbar.addWidget(staged_fansly)

        unstage_btn = QPushButton()
        unstage_btn.setIcon(self.controller.get_icon("unstage.png", "US"))
        unstage_btn.setIconSize(self.controller.icon_size)
        unstage_btn.setToolTip("Unstage: move selected photos back to root/<package>")
        unstage_btn.clicked.connect(self.controller.unstage_selected)
        bottom_toolbar.addWidget(unstage_btn)

        package_btn = QPushButton()
        package_btn.setIcon(self.controller.get_icon("package.png", "PK"))
        package_btn.setIconSize(self.controller.icon_size)
        package_btn.setToolTip("Manage packages for selected photos")
        package_btn.clicked.connect(self.controller.manage_packages_dialog)
        bottom_toolbar.addWidget(package_btn)

        unpackage_btn = QPushButton()
        unpackage_btn.setIcon(self.controller.get_icon("unpackage.png", "UP"))
        unpackage_btn.setIconSize(self.controller.icon_size)
        unpackage_btn.setToolTip("Unpackage: clear package and move files to root")
        unpackage_btn.clicked.connect(self.controller.unpackage_selected)
        bottom_toolbar.addWidget(unpackage_btn)

        # Release controls
        bottom_toolbar.addWidget(QLabel("Toggle Release:"))

        toggle_ig = QPushButton()
        toggle_ig.setIcon(self.controller.get_icon("instagram.png", "IG"))
        toggle_ig.setIconSize(self.controller.icon_size)
        toggle_ig.setToolTip("Release: Instagram")
        toggle_ig.clicked.connect(lambda: self.controller.toggle_release_status("released_instagram"))
        bottom_toolbar.addWidget(toggle_ig)

        toggle_tiktok = QPushButton()
        toggle_tiktok.setIcon(self.controller.get_icon("tiktok.png", "TT"))
        toggle_tiktok.setIconSize(self.controller.icon_size)
        toggle_tiktok.setToolTip("Release: TikTok")
        toggle_tiktok.clicked.connect(lambda: self.controller.toggle_release_status("released_tiktok"))
        bottom_toolbar.addWidget(toggle_tiktok)

        toggle_fansly = QPushButton()
        toggle_fansly.setIcon(self.controller.get_icon("fansly.png", "F"))
        toggle_fansly.setIconSize(self.controller.icon_size)
        toggle_fansly.setToolTip("Release: Fansly")
        toggle_fansly.clicked.connect(lambda: self.controller.toggle_release_status("released_fansly"))
        bottom_toolbar.addWidget(toggle_fansly)

        layout.addLayout(bottom_toolbar)

    # API methods
    def refresh(self):
        """Reload all photos and repopulate table."""
        self.photo_table.setRowCount(0)
        photos = self.controller.db.get_all_photos()

        for i, photo in enumerate(photos):
            self.photo_table.insertRow(i)
            self.photo_table.setRowHeight(i, self.thumbnail_sizes[self.current_thumb_size])

            # Checkbox column
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            from PyQt6.QtWidgets import QCheckBox

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

            # Metadata columns
            self.photo_table.setItem(i, self.COL_TYPE, QTableWidgetItem(photo["type_of_shot"] or ""))
            self.photo_table.setItem(i, self.COL_POSE, QTableWidgetItem(photo["pose"] or ""))
            self.photo_table.setItem(i, self.COL_FACING, QTableWidgetItem(photo["facing_direction"] or ""))
            self.photo_table.setItem(i, self.COL_LEVEL, QTableWidgetItem(photo["explicit_level"] or ""))
            self.photo_table.setItem(i, self.COL_COLOR, QTableWidgetItem(photo["color_of_clothing"] or ""))
            self.photo_table.setItem(i, self.COL_MATERIAL, QTableWidgetItem(photo["material"] or ""))
            self.photo_table.setItem(i, self.COL_CLOTHING, QTableWidgetItem(photo["type_clothing"] or ""))
            self.photo_table.setItem(i, self.COL_FOOTWEAR, QTableWidgetItem(photo["footwear"] or ""))
            self.photo_table.setItem(i, self.COL_LOCATION, QTableWidgetItem(photo["location"] or ""))

            # Status
            status_text = photo["status"] or "raw"
            self.photo_table.setItem(i, self.COL_STATUS, QTableWidgetItem(status_text))

            # Platform toggles
            ig_item = QTableWidgetItem("✓" if photo["released_instagram"] else "")
            self.photo_table.setItem(i, self.COL_IG, ig_item)

            tt_item = QTableWidgetItem("✓" if photo["released_tiktok"] else "")
            self.photo_table.setItem(i, self.COL_TIKTOK, tt_item)

            fansly_item = QTableWidgetItem("✓" if photo["released_fansly"] else "")
            self.photo_table.setItem(i, self.COL_FANSLY, fansly_item)

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
            self.COL_TYPE: "type_of_shot",
            self.COL_POSE: "pose",
            self.COL_FACING: "facing_direction",
            self.COL_LEVEL: "explicit_level",
            self.COL_COLOR: "color_of_clothing",
            self.COL_MATERIAL: "material",
            self.COL_CLOTHING: "type_clothing",
            self.COL_FOOTWEAR: "footwear",
            self.COL_LOCATION: "location",
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

        for photo_id in target_ids:
            self.controller.db.add_package(photo_id, package_name)

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

        self.controller.db.bulk_update(set(target_ids), {"status": status})
        self.refresh()
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(f"Updated status for {len(target_ids)} photo(s)", 3000)

    def reanalyze_selected(self):
        """Trigger re-analysis of selected photos."""
        from database import ReanalyzerThread

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
        """Open bulk edit dialog."""
        value, ok = QInputDialog.getText(self, "Bulk Edit", "Enter value for selected cells:")
        if ok and value:
            for index in self.photo_table.selectedIndexes():
                self.photo_table.item(index.row(), index.column()).setText(value)

    def get_target_photo_ids(self) -> list:
        """Get checked or selected photo IDs."""
        rows = {it.row() for it in self.photo_table.selectedItems()}
        ids = []
        for r in rows:
            pid = self.get_photo_id_from_row(r)
            if pid is not None:
                ids.append(pid)
        return ids
