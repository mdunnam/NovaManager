"""
Trash tab for PhotoFlow — soft-deleted photos with restore and permanent-delete.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGridLayout, QFrame, QMessageBox, QSizePolicy,
    QCheckBox,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap
from core.icons import icon as _icon


class _TrashCard(QFrame):
    """Thumbnail card for a single trashed photo."""

    def __init__(self, photo: dict, controller, parent_tab, parent=None):
        super().__init__(parent)
        self.photo = photo
        self.controller = controller
        self.parent_tab = parent_tab
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setMaximumWidth(170)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        # Selection checkbox
        self.select_cb = QCheckBox()
        self.select_cb.setToolTip("Select for bulk action")
        layout.addWidget(self.select_cb)

        # Thumbnail
        img = QLabel()
        img.setFixedSize(150, 120)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setStyleSheet("background: #1e1e1e;")
        fp = self.photo.get("filepath", "")
        if fp and os.path.exists(fp):
            pix = self.controller.get_cached_thumbnail(fp, 150)
            if pix and not pix.isNull():
                img.setPixmap(pix)
            else:
                img.setText("[No Preview]")
        else:
            img.setText("[File Missing]")
            img.setStyleSheet("background: #2a1a1a; color: #f44;")
        layout.addWidget(img)

        # Filename
        name = QLabel((self.photo.get("filename") or "")[:20])
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet("font-size: 9px; color: #aaa;")
        layout.addWidget(name)

        # Date trashed
        dt = str(self.photo.get("date_trashed") or "")[:16]
        date_lbl = QLabel(f"Trashed: {dt}" if dt else "")
        date_lbl.setStyleSheet("font-size: 9px; color: #777;")
        date_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(date_lbl)

        # Restore button
        restore_btn = QPushButton("Restore")
        restore_btn.setIcon(_icon("revert"))
        restore_btn.setIconSize(QSize(14, 14))
        restore_btn.setStyleSheet("font-size: 9px; padding: 2px;")
        restore_btn.clicked.connect(self._restore)
        layout.addWidget(restore_btn)

        # Delete permanently button
        del_btn = QPushButton("Delete Forever")
        del_btn.setIcon(_icon("trash"))
        del_btn.setIconSize(QSize(14, 14))
        del_btn.setStyleSheet("font-size: 9px; padding: 2px; color: #f44336;")
        del_btn.clicked.connect(self._delete_forever)
        layout.addWidget(del_btn)

    def _restore(self):
        """Restore this photo back to the active library."""
        self.controller.db.restore_from_trash(self.photo["id"])
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(
                f"Restored: {self.photo.get('filename', '')}", 3000
            )
        self.parent_tab.refresh()

    def _delete_forever(self):
        """Permanently delete this photo record (and optionally the file)."""
        reply = QMessageBox.question(
            self,
            "Permanently Delete",
            f"Permanently delete '{self.photo.get('filename', '')}'?\n\n"
            "The record will be removed from the database.\n"
            "The file on disk will NOT be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.controller.db.delete_photo(self.photo["id"])
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(
                f"Permanently deleted: {self.photo.get('filename', '')}", 3000
            )
        self.parent_tab.refresh()


class TrashTab(QWidget):
    """Soft-deleted photos — restore or permanently remove."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header_row = QHBoxLayout()
        header = QLabel("<b>Trash</b>")
        header.setStyleSheet("font-size: 15px; padding: 4px;")
        header_row.addWidget(header)
        header_row.addStretch()

        refresh_btn = QPushButton()
        refresh_btn.setIcon(_icon("refresh"))
        refresh_btn.setIconSize(QSize(18, 18))
        refresh_btn.setToolTip("Refresh trash")
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        # Info bar
        self.info_label = QLabel(
            "Photos moved to Trash are kept here for review. "
            "Restore to return them to the library, or delete forever to remove the database record."
        )
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #aaa; font-size: 11px; padding: 4px;")
        layout.addWidget(self.info_label)

        # Bulk action row
        action_row = QHBoxLayout()
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #aaa; font-size: 11px;")
        action_row.addWidget(self.count_label)
        action_row.addStretch()

        restore_all_btn = QPushButton("Restore All")
        restore_all_btn.setIcon(_icon("revert"))
        restore_all_btn.setIconSize(QSize(16, 16))
        restore_all_btn.setToolTip("Restore all trashed photos to the library")
        restore_all_btn.clicked.connect(self._restore_all)
        action_row.addWidget(restore_all_btn)

        empty_btn = QPushButton("Empty Trash")
        empty_btn.setIcon(_icon("trash"))
        empty_btn.setIconSize(QSize(16, 16))
        empty_btn.setStyleSheet("color: #f44336; font-weight: bold;")
        empty_btn.setToolTip("Permanently delete all records in the Trash")
        empty_btn.clicked.connect(self._empty_trash)
        action_row.addWidget(empty_btn)
        layout.addLayout(action_row)

        # Grid of trashed photos
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.scroll.setWidget(self.grid_container)
        layout.addWidget(self.scroll)

    # ── Refresh ──────────────────────────────────────────────────────────

    def refresh(self):
        """Reload trashed photos and rebuild the grid."""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            photos = self.controller.db.get_trashed_photos()
        except Exception:
            photos = []

        if not photos:
            empty_lbl = QLabel("Trash is empty.")
            empty_lbl.setStyleSheet("color: #888; font-style: italic; padding: 20px;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(empty_lbl, 0, 0)
        else:
            cols = 5
            for idx, photo in enumerate(photos):
                card = _TrashCard(photo, self.controller, self)
                self.grid_layout.addWidget(card, idx // cols, idx % cols)

        n = len(photos)
        self.count_label.setText(
            f"{n} photo{'s' if n != 1 else ''} in trash"
            + (
                f"  —  Auto-empty after 30 days (not yet implemented)"
                if n > 0
                else ""
            )
        )

    # ── Bulk actions ─────────────────────────────────────────────────────

    def _restore_all(self):
        """Restore every trashed photo back to the active library."""
        photos = self.controller.db.get_trashed_photos()
        if not photos:
            return
        for photo in photos:
            self.controller.db.restore_from_trash(photo["id"])
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(
                f"Restored {len(photos)} photo(s) from Trash", 3000
            )
        self.refresh()
        if hasattr(self.controller, "gallery_tab"):
            self.controller.gallery_tab.refresh()
        if hasattr(self.controller, "photos_tab"):
            self.controller.photos_tab.refresh()

    def _empty_trash(self):
        """Permanently delete all trashed photo records."""
        photos = self.controller.db.get_trashed_photos()
        if not photos:
            QMessageBox.information(self, "Trash", "Trash is already empty.")
            return
        reply = QMessageBox.question(
            self,
            "Empty Trash",
            f"Permanently delete {len(photos)} record(s) from the database?\n\n"
            "Files on disk will NOT be deleted.\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        removed = self.controller.db.empty_trash()
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(
                f"Trash emptied: {removed} record(s) permanently deleted", 4000
            )
        self.refresh()
