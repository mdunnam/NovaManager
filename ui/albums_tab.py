"""
Albums tab for PhotoFlow — manual collections and smart albums.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QScrollArea, QGridLayout,
    QFrame, QInputDialog, QMessageBox, QSplitter, QMenu,
    QSizePolicy, QDialog, QDialogButtonBox, QAbstractItemView,
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QPixmap, QIcon, QAction
import os
from core.icons import icon as _icon


class AlbumThumbnail(QLabel):
    """Clickable thumbnail label for the photo grid."""
    def __init__(self, photo, controller, parent=None):
        super().__init__(parent)
        self.photo = photo
        self.controller = controller
        self.setFixedSize(120, 120)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("border: 1px solid #555; background: #2a2a2a;")
        self._load_thumb()

    def _load_thumb(self):
        fp = self.photo.get('filepath', '')
        if fp and os.path.exists(fp):
            pix = self.controller.get_cached_thumbnail(fp, 110)
            if pix and not pix.isNull():
                self.setPixmap(pix)
                return
        self.setText(self.photo.get('filename', '?')[:12])

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        set_cover_act = menu.addAction("Set as Album Cover")
        remove_act = menu.addAction("Remove from Album")
        act = menu.exec(event.globalPos())
        album_tab = getattr(self, 'parent_album_tab', None)
        if not album_tab:
            return
        if act == set_cover_act and album_tab.current_album_id:
            album_tab.controller.db.set_album_cover(album_tab.current_album_id, self.photo['id'])
            if album_tab.controller.statusBar():
                album_tab.controller.statusBar().showMessage(
                    f"Cover set: {self.photo.get('filename', '')}", 3000
                )
        elif act == remove_act:
            album_tab.remove_photo(self.photo['id'])


class AlbumsTab(QWidget):
    """Albums and Collections UI."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.current_album_id = None
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(lambda: self._load_album_grid(self.current_album_id) if self.current_album_id else None)
        self._build_ui()
        self.refresh_album_list()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start(150)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("<b>Albums & Collections</b>")
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left panel: album list ──────────────────────────────
        left = QWidget()
        left.setMinimumWidth(0)
        left.setMaximumWidth(240)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        album_btn_row = QHBoxLayout()
        new_btn = QPushButton(" New Album")
        new_btn.setIcon(_icon('new_album'))
        new_btn.setIconSize(QSize(16, 16))
        new_btn.clicked.connect(self.create_album)
        album_btn_row.addWidget(new_btn)

        smart_btn = QPushButton(" Smart")
        smart_btn.setIcon(_icon('smart_album'))
        smart_btn.setIconSize(QSize(16, 16))
        smart_btn.setToolTip("Create a smart album from current filters")
        smart_btn.clicked.connect(self.create_smart_album)
        album_btn_row.addWidget(smart_btn)

        date_btn = QPushButton(" By Date")
        date_btn.setIcon(_icon('calendar'))
        date_btn.setIconSize(QSize(16, 16))
        date_btn.setToolTip("Auto-create albums grouped by month/year from EXIF date")
        date_btn.clicked.connect(self.create_date_albums)
        album_btn_row.addWidget(date_btn)

        left_layout.addLayout(album_btn_row)

        self.album_list = QListWidget()
        self.album_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.album_list.customContextMenuRequested.connect(self._album_context_menu)
        self.album_list.currentItemChanged.connect(self._on_album_selected)
        left_layout.addWidget(self.album_list)

        splitter.addWidget(left)

        # ── Right panel: photo grid ─────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.album_title_label = QLabel("<i>Select an album</i>")
        self.album_title_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        right_layout.addWidget(self.album_title_label)

        # Toolbar for the grid
        grid_toolbar = QHBoxLayout()

        self.add_photos_btn = QPushButton(" Add Photos from Library")
        self.add_photos_btn.setIcon(_icon('add_photo'))
        self.add_photos_btn.setIconSize(QSize(16, 16))
        self.add_photos_btn.setEnabled(False)
        self.add_photos_btn.clicked.connect(self.add_photos_to_album)
        grid_toolbar.addWidget(self.add_photos_btn)

        self.set_cover_btn = QPushButton("Set Cover")
        self.set_cover_btn.setIcon(_icon('set_cover'))
        self.set_cover_btn.setIconSize(QSize(16, 16))
        self.set_cover_btn.setEnabled(False)
        self.set_cover_btn.clicked.connect(self.set_cover_photo)
        grid_toolbar.addWidget(self.set_cover_btn)

        self.photo_count_label = QLabel("")
        self.photo_count_label.setStyleSheet("color: gray;")
        grid_toolbar.addWidget(self.photo_count_label)
        grid_toolbar.addStretch()
        right_layout.addLayout(grid_toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(6)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self.grid_container)
        right_layout.addWidget(scroll)

        splitter.addWidget(right)
        splitter.setSizes([200, 600])
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, True)
        layout.addWidget(splitter)

    # ── Album list management ───────────────────────────────────

    def refresh_album_list(self):
        self.album_list.clear()
        albums = self.controller.db.get_albums()
        for album in albums:
            icon = "★" if album.get('is_smart') else "▣"
            item = QListWidgetItem(f"{icon} {album['name']}")
            item.setData(Qt.ItemDataRole.UserRole, album['id'])
            item.setToolTip(album.get('description') or '')
            self.album_list.addItem(item)

    def _on_album_selected(self, current, previous):
        if not current:
            return
        album_id = current.data(Qt.ItemDataRole.UserRole)
        self.current_album_id = album_id

        # Album name is already in the list item text — no extra DB call needed
        is_smart = current.text().startswith('\u2605')
        album_name = current.text()[2:].strip()
        prefix = '\u2605 Smart: ' if is_smart else '\u25a3 '
        self.album_title_label.setText(f'{prefix}{album_name}')

        self.add_photos_btn.setEnabled(True)
        self.set_cover_btn.setEnabled(True)
        self._load_album_grid(album_id)

    def _load_album_grid(self, album_id):
        # Clear grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        photos = self.controller.db.get_album_photos(album_id)
        self.photo_count_label.setText(f"{len(photos)} photo{'s' if len(photos) != 1 else ''}")

        # Dynamic columns based on available width
        grid_width = self.grid_container.parent().width() if self.grid_container.parent() else 600
        cell_width = 120 + self.grid_layout.spacing() + 6
        cols = max(1, grid_width // cell_width)
        for idx, photo in enumerate(photos):
            thumb = AlbumThumbnail(photo, self.controller)
            thumb.parent_album_tab = self
            self.grid_layout.addWidget(thumb, idx // cols, idx % cols)

    # ── Album CRUD ─────────────────────────────────────────────

    def create_album(self):
        name, ok = QInputDialog.getText(self, "New Album", "Album name:")
        if ok and name.strip():
            self.controller.db.create_album(name.strip())
            self.refresh_album_list()
            if self.controller.statusBar():
                self.controller.statusBar().showMessage(f'Created album "{name.strip()}"', 3000)

    def create_smart_album(self):
        """Create a smart album that auto-populates from current filters."""
        name, ok = QInputDialog.getText(self, 'New Smart Album', 'Smart album name:')
        if not ok or not name.strip():
            return

        # Build a filter description from current filter_tab state (if available)
        filter_str = ''
        ft = getattr(self.controller, 'filters_tab', None)
        if ft:
            parts = []
            for attr, label in [
                ('filter_scene', 'scene'), ('filter_mood', 'mood'),
                ('filter_subjects', 'subjects'), ('filter_quality', 'quality'),
                ('filter_content_rating', 'content_rating'),
            ]:
                combo = getattr(ft, attr, None)
                if combo and combo.currentIndex() > 0:
                    parts.append(f'{label}={combo.currentText()}')
            for attr, label in [
                ('filter_raw', 'status=raw'), ('filter_needs_edit', 'status=needs_edit'),
                ('filter_ready', 'status=ready'), ('filter_released', 'status=released'),
            ]:
                cb = getattr(ft, attr, None)
                if cb and cb.isChecked():
                    parts.append(label)
            for attr, label in [('filter_tag', 'tag'), ('filter_location', 'location'), ('filter_package', 'package')]:
                le = getattr(ft, attr, None)
                v = le.text().strip() if le else ''
                if v:
                    parts.append(f'{label}={v}')
            filter_str = '&'.join(parts)

        album_id = self.controller.db.create_album(name.strip(), is_smart=1, smart_filter=filter_str)

        # Auto-populate using current filtered photos if any filter is active
        if filter_str:
            photos = getattr(self.controller, '_current_filtered_photos', None)
            if photos is None:
                photos = self.controller.db.get_all_photos()
            added = 0
            for p in photos:
                if self.controller.db.add_photo_to_album(album_id, p['id']):
                    added += 1
        else:
            added = 0

        self.refresh_album_list()
        msg = f'Created smart album "{name.strip()}"'
        if filter_str:
            msg += f' with {added} matching photo(s).'
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(msg, 4000)

    def _album_context_menu(self, pos):
        item = self.album_list.itemAt(pos)
        if not item:
            return
        album_id = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        rename_act = menu.addAction("Rename")
        delete_act = menu.addAction("Delete Album")
        act = menu.exec(self.album_list.mapToGlobal(pos))
        if act == rename_act:
            self._rename_album(album_id)
        elif act == delete_act:
            self._delete_album(album_id)

    def _rename_album(self, album_id):
        albums = self.controller.db.get_albums()
        album = next((a for a in albums if a['id'] == album_id), None)
        if not album:
            return
        name, ok = QInputDialog.getText(self, 'Rename Album', 'New name:', text=album['name'])
        if ok and name.strip():
            self.controller.db.rename_album(album_id, name.strip())
            self.refresh_album_list()

    def _delete_album(self, album_id):
        reply = QMessageBox.question(
            self, "Delete Album",
            "Delete this album? Photos will NOT be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.controller.db.delete_album(album_id)
            self.current_album_id = None
            self.album_title_label.setText("<i>Select an album</i>")
            self.add_photos_btn.setEnabled(False)
            self.set_cover_btn.setEnabled(False)
            self.photo_count_label.setText("")
            self.refresh_album_list()
            while self.grid_layout.count():
                w = self.grid_layout.takeAt(0).widget()
                if w:
                    w.deleteLater()

    # ── Photo management ────────────────────────────────────────

    def add_photos_to_album(self):
        """Open a multi-select dialog to pick photos from the library."""
        if not self.current_album_id:
            return

        all_photos = self.controller.db.get_all_photos()
        if not all_photos:
            QMessageBox.information(self, 'Empty Library', 'No photos in the library yet.')
            return

        dlg = QDialog(self)
        dlg.setWindowTitle('Add Photos to Album')
        dlg.setMinimumSize(520, 440)
        vbox = QVBoxLayout(dlg)
        vbox.addWidget(QLabel('Select one or more photos (Ctrl/Shift to multi-select):', dlg))

        list_widget = QListWidget(dlg)
        list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        for photo in all_photos:
            item = QListWidgetItem(photo.get('filename') or str(photo['id']))
            item.setData(Qt.ItemDataRole.UserRole, photo['id'])
            list_widget.addItem(item)
        vbox.addWidget(list_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dlg
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        vbox.addWidget(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected_ids = [
            item.data(Qt.ItemDataRole.UserRole)
            for item in list_widget.selectedItems()
        ]
        if not selected_ids:
            return

        added = 0
        for pid in selected_ids:
            if self.controller.db.add_photo_to_album(self.current_album_id, pid):
                added += 1
        self._load_album_grid(self.current_album_id)
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(f'Added {added} photo(s) to album.', 3000)

    def remove_photo(self, photo_id):
        if not self.current_album_id:
            return
        self.controller.db.remove_photo_from_album(self.current_album_id, photo_id)
        self._load_album_grid(self.current_album_id)

    def set_cover_photo(self):
        """Set the currently selected thumbnail as the album cover"""
        if not self.current_album_id:
            return
        # Find the first photo in the grid as a fallback, or show instruction
        photos = self.controller.db.get_album_photos(self.current_album_id)
        if not photos:
            QMessageBox.information(self, "No Photos", "Add photos to the album first.")
            return
        # Use cover_photo_id from DB if already set, else guide user
        QMessageBox.information(
            self, "Set Cover",
            "Right-click any photo thumbnail in the grid and choose 'Set as Album Cover'."
        )

    # ── Auto-populate smart albums by date ─────────────────────

    def create_date_albums(self):
        """Create albums grouped by month/year from EXIF date. Uses one transaction."""
        photos = self.controller.db.get_all_photos()
        months: dict = {}
        for p in photos:
            dt = p.get('exif_date_taken') or p.get('date_created')
            if dt:
                try:
                    from datetime import datetime
                    if isinstance(dt, str):
                        dt = datetime.fromisoformat(dt.split('.')[0])
                    key = dt.strftime('%B %Y')
                    months.setdefault(key, []).append(p['id'])
                except Exception:
                    pass

        created = 0
        try:
            # Disable auto-commit for batch speed
            self.controller.db.conn.execute('BEGIN')
            for month_name, photo_ids in months.items():
                album_id = self.controller.db.create_album(month_name, is_smart=1)
                for pid in photo_ids:
                    self.controller.db.cursor.execute(
                        'INSERT OR IGNORE INTO album_photos (album_id, photo_id) VALUES (?, ?)',
                        (album_id, pid),
                    )
                created += 1
            self.controller.db.conn.commit()
        except Exception as e:
            self.controller.db.conn.rollback()
            QMessageBox.critical(self, 'Error', f'Failed to create date albums: {e}')
            return

        self.refresh_album_list()
        QMessageBox.information(self, 'Date Albums', f'Created {created} date-based album(s).')
