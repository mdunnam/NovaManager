"""
Duplicate photo detection & resolution tab for PhotoFlow.
Groups exact and near-duplicate photos; lets the user keep one and discard the rest.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGridLayout, QFrame, QMessageBox, QProgressDialog,
    QCheckBox, QSplitter, QGroupBox, QRadioButton, QButtonGroup,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QColor
from core.icons import icon as _icon


class _ScanThread(QThread):
    finished = pyqtSignal(list)  # list of groups
    progress = pyqtSignal(str)

    def __init__(self, photos: list, threshold: int = 8):
        super().__init__()
        self.photos = photos
        self.threshold = threshold

    def run(self):
        try:
            self.progress.emit('Scanning for duplicates...')
            from core.duplicate_detector import find_duplicates
            groups = find_duplicates(self.photos, self.threshold)
            self.finished.emit(groups)
        except Exception as e:
            self.finished.emit([])
            print(f'[Duplicates] Scan error: {e}')


class DuplicatesTab(QWidget):
    """Find and resolve duplicate photos."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._groups: list[list[dict]] = []
        self._keep_selections: dict[int, int] = {}  # group_idx -> photo_id to keep
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header_row = QHBoxLayout()
        header = QLabel('<b>Duplicate Detection</b>')
        header.setStyleSheet('font-size: 15px; padding: 4px;')
        header_row.addWidget(header)
        header_row.addStretch()

        self.scan_btn = QPushButton('Scan Library for Duplicates')
        self.scan_btn.setIcon(_icon('scan', 16, '#ffffff'))
        self.scan_btn.setIconSize(QSize(16, 16))
        self.scan_btn.setStyleSheet('background: #1a73e8; color: white; padding: 6px 16px;')
        self.scan_btn.clicked.connect(self._scan)
        header_row.addWidget(self.scan_btn)
        layout.addLayout(header_row)

        # Info bar
        self.info_label = QLabel('Click "Scan Library" to find duplicate and near-duplicate photos.')
        self.info_label.setStyleSheet('color: #aaa; font-size: 11px; padding: 4px;')
        layout.addWidget(self.info_label)

        # Scroll area for groups
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.groups_container = QWidget()
        self.groups_layout = QVBoxLayout(self.groups_container)
        self.groups_layout.setSpacing(12)
        self.groups_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.groups_container)
        layout.addWidget(self.scroll)

        # Action bar
        action_row = QHBoxLayout()
        self.delete_btn = QPushButton('Delete Duplicates (keep selected)')
        self.delete_btn.setIcon(_icon('trash'))
        self.delete_btn.setIconSize(QSize(16, 16))
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet('color: #f44336;')
        self.delete_btn.clicked.connect(self._delete_duplicates)
        self.mark_btn = QPushButton('Mark as Reviewed (hide)')
        self.mark_btn.setIcon(_icon('eye_off'))
        self.mark_btn.setIconSize(QSize(16, 16))
        self.mark_btn.setEnabled(False)
        self.mark_btn.clicked.connect(self._mark_reviewed)
        action_row.addWidget(self.delete_btn)
        action_row.addWidget(self.mark_btn)
        action_row.addStretch()
        self.result_label = QLabel('')
        self.result_label.setStyleSheet('color: #aaa; font-size: 11px;')
        action_row.addWidget(self.result_label)
        layout.addLayout(action_row)

    # ── Scanning ─────────────────────────────────────────────────

    def _scan(self):
        self.scan_btn.setEnabled(False)
        self.info_label.setText('Scanning...')
        photos = self.controller.db.get_all_photos()

        self._thread = _ScanThread(photos)
        self._thread.progress.connect(self.info_label.setText)
        self._thread.finished.connect(self._on_scan_done)
        self._thread.start()

    def _on_scan_done(self, groups: list):
        self.scan_btn.setEnabled(True)
        self._groups = groups
        self._keep_selections.clear()
        self._render_groups()

        total_dupes = sum(len(g) - 1 for g in groups)
        if groups:
            self.info_label.setText(
                f'Found {len(groups)} duplicate group{"s" if len(groups) != 1 else ""}'
                f' ({total_dupes} extra copies). Select which photo to keep in each group.'
            )
            self.delete_btn.setEnabled(True)
            self.mark_btn.setEnabled(True)
        else:
            self.info_label.setText('No duplicates found.')
            self.delete_btn.setEnabled(False)
            self.mark_btn.setEnabled(False)

    def _render_groups(self):
        # Clear
        while self.groups_layout.count():
            item = self.groups_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for group_idx, group in enumerate(self._groups):
            group_box = QGroupBox(f'Group {group_idx + 1}  —  {len(group)} photos')
            group_box.setStyleSheet('QGroupBox { font-weight: bold; }')
            group_layout = QHBoxLayout(group_box)

            # Default: keep the first
            if group_idx not in self._keep_selections:
                self._keep_selections[group_idx] = group[0]['id']

            for photo in group:
                card = self._make_photo_card(group_idx, photo)
                group_layout.addWidget(card)

            group_layout.addStretch()
            self.groups_layout.addWidget(group_box)

    def _make_photo_card(self, group_idx: int, photo: dict) -> QWidget:
        card = QFrame()
        card.setMaximumWidth(160)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(4, 4, 4, 4)
        cl.setSpacing(2)

        # Thumbnail
        img = QLabel()
        img.setFixedSize(140, 140)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setStyleSheet('background: #1e1e1e;')
        fp = photo.get('filepath', '')
        if fp and os.path.exists(fp):
            pix = self.controller.get_cached_thumbnail(fp, 140)
            if pix and not pix.isNull():
                img.setPixmap(pix)
            else:
                img.setText('[No Preview]')
        else:
            img.setText('[Missing]')
        cl.addWidget(img)

        # Filename
        name_lbl = QLabel(photo.get('filename', '')[:20])
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setStyleSheet('font-size: 10px; color: #aaa;')
        cl.addWidget(name_lbl)

        # Size
        kb = photo.get('file_size_kb', 0) or 0
        size_lbl = QLabel(f'{kb:,} KB' if kb else '')
        size_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        size_lbl.setStyleSheet('font-size: 9px; color: #777;')
        cl.addWidget(size_lbl)

        # Keep radio (exclusive per group via QButtonGroup stored on parent)
        keep_rb = QRadioButton('Keep this')
        keep_rb.setChecked(self._keep_selections.get(group_idx) == photo['id'])
        keep_rb.toggled.connect(
            lambda checked, gi=group_idx, pid=photo['id']: self._set_keep(gi, pid, checked)
        )
        cl.addWidget(keep_rb)

        # Highlight if selected to keep
        if self._keep_selections.get(group_idx) == photo['id']:
            card.setStyleSheet('QFrame { border: 2px solid #4caf50; background: #1a2a1a; }')
        else:
            card.setStyleSheet('QFrame { border: 1px solid #444; }')

        return card

    def _set_keep(self, group_idx: int, photo_id: int, checked: bool):
        if checked:
            self._keep_selections[group_idx] = photo_id
            # Re-render to update highlights
            self._render_groups()

    # ── Actions ──────────────────────────────────────────────────

    def _delete_duplicates(self):
        to_delete = []
        for group_idx, group in enumerate(self._groups):
            keep_id = self._keep_selections.get(group_idx)
            for photo in group:
                if photo['id'] != keep_id:
                    to_delete.append(photo)

        if not to_delete:
            QMessageBox.information(self, 'Nothing to delete', 'No duplicates marked for deletion.')
            return

        reply = QMessageBox.question(
            self, 'Delete Duplicates',
            f'Delete {len(to_delete)} duplicate file(s) from disk and database?\n\nThis cannot be undone.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        errors = 0
        for photo in to_delete:
            try:
                fp = photo.get('filepath', '')
                if fp and os.path.exists(fp):
                    os.remove(fp)
                self.controller.db.delete_photo(photo['id'])
                deleted += 1
            except Exception as e:
                print(f'[Duplicates] Delete error: {e}')
                errors += 1

        self.result_label.setText(f'Deleted {deleted} files. {errors} errors.')
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(f'Deleted {deleted} duplicate files.', 4000)
        self._scan()  # Re-scan

    def _mark_reviewed(self):
        """Hide these groups from future scans by tagging photos."""
        for group_idx, group in enumerate(self._groups):
            for photo in group:
                try:
                    tags = photo.get('tags') or ''
                    if 'duplicate_reviewed' not in tags:
                        new_tags = (tags + ',duplicate_reviewed').strip(',')
                        self.controller.db.update_photo_metadata(photo['id'], {'tags': new_tags})
                except Exception:
                    pass
        self.result_label.setText(f'Marked {len(self._groups)} groups as reviewed.')
        self._groups = []
        self._render_groups()
        self.delete_btn.setEnabled(False)
        self.mark_btn.setEnabled(False)
        self.info_label.setText('Groups marked as reviewed. Re-scan to check again.')
