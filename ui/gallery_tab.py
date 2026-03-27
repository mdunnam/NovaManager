"""
Gallery tab UI for PhotoFlow.
Grid view with quality badges, search, EXIF details panel, and caption generator.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QScrollArea, QGridLayout, QSplitter,
    QLineEdit, QMessageBox, QFrame, QTextEdit, QGroupBox,
    QFormLayout, QMenu,
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QAction
from core.icons import icon as _icon


_QUALITY_BADGE = {
    'excellent': ('#4caf50', 'Excellent'),
    'good':      ('#8bc34a', 'Good'),
    'fair':      ('#ff9800', 'Fair'),
    'poor':      ('#f44336', 'Poor'),
}


class GalleryTab(QWidget):
    """Gallery grid with detail panel and search."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.current_gallery_photo_id = None
        self.selected_gallery_photo_id = None
        self._thumbnail_frames = {}
        self._all_photos = []
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_resize_debounced)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── Toolbar ─────────────────────────────────────────────
        toolbar = QHBoxLayout()

        # Search
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('Search by filename, caption, tags, objects, location...')
        self.search_edit.setMinimumWidth(80)
        self.search_edit.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_edit)

        # Clear search
        clear_search_btn = QPushButton()
        clear_search_btn.setIcon(_icon('close', 14))
        clear_search_btn.setIconSize(QSize(14, 14))
        clear_search_btn.setFixedWidth(28)
        clear_search_btn.setToolTip('Clear search')
        clear_search_btn.clicked.connect(lambda: self.search_edit.clear())
        toolbar.addWidget(clear_search_btn)

        toolbar.addSpacing(16)

        toolbar.addWidget(QLabel('Group:'))
        self.gallery_group = QComboBox()
        self.gallery_group.addItems(['None', 'By Date', 'By Scene', 'By Location', 'By Quality'])
        self.gallery_group.currentTextChanged.connect(self.refresh)
        toolbar.addWidget(self.gallery_group)

        toolbar.addWidget(QLabel('Sort:'))
        self.gallery_sort = QComboBox()
        self.gallery_sort.addItems(['Date (newest)', 'Date (oldest)', 'Filename', 'Quality', 'Status', 'Scene'])
        self.gallery_sort.currentTextChanged.connect(self.refresh)
        toolbar.addWidget(self.gallery_sort)

        toolbar.addWidget(QLabel('Size:'))
        self.gallery_size = QComboBox()
        self.gallery_size.addItems(['Small', 'Medium', 'Large'])
        self.gallery_size.setCurrentText('Medium')
        self.gallery_size.currentTextChanged.connect(self.refresh)
        toolbar.addWidget(self.gallery_size)

        toolbar.addStretch()
        self.photo_count_label = QLabel('')
        self.photo_count_label.setStyleSheet('color: #aaa; font-size: 11px;')
        toolbar.addWidget(self.photo_count_label)

        refresh_btn = QPushButton()
        refresh_btn.setIcon(_icon('refresh'))
        refresh_btn.setIconSize(QSize(18, 18))
        refresh_btn.setToolTip('Refresh gallery')
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)

        # ── Main splitter ────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.gallery_container = QWidget()
        self.gallery_grid = QGridLayout(self.gallery_container)
        self.gallery_grid.setSpacing(8)
        self.gallery_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self.gallery_container)
        splitter.addWidget(scroll)

        # Details panel
        self._detail_panel = self._build_detail_panel()
        splitter.addWidget(self._detail_panel)
        splitter.setSizes([1000, 320])
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, True)
        layout.addWidget(splitter)

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(0)
        panel.setMaximumWidth(380)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(6)

        # Preview
        self.detail_preview = QLabel()
        self.detail_preview.setFixedHeight(220)
        self.detail_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_preview.setStyleSheet('background: #1e1e1e; border: 1px solid #444;')
        self.detail_preview.setText('Select a photo')
        inner_layout.addWidget(self.detail_preview)

        # Quick actions
        action_row = QHBoxLayout()
        self.open_btn = QPushButton('Open')
        self.open_btn.setIcon(_icon('expand'))
        self.open_btn.setIconSize(QSize(16, 16))
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self._open_full)
        post_btn = QPushButton('Post...')
        post_btn.setIcon(_icon('send'))
        post_btn.setIconSize(QSize(16, 16))
        post_btn.setEnabled(False)
        post_btn.setObjectName('detail_post_btn')
        post_btn.clicked.connect(self._post_this)
        action_row.addWidget(self.open_btn)
        action_row.addWidget(post_btn)
        self._detail_post_btn = post_btn
        inner_layout.addLayout(action_row)

        # ID + path
        self.detail_id = QLabel('—')
        self.detail_id.setStyleSheet('font-size: 11px; color: #aaa;')
        self.detail_path = QLabel('—')
        self.detail_path.setWordWrap(True)
        self.detail_path.setStyleSheet('font-size: 9px; color: #777;')
        inner_layout.addWidget(self.detail_id)
        inner_layout.addWidget(self.detail_path)

        # Quality badge
        self.detail_quality = QLabel('')
        self.detail_quality.setStyleSheet('font-size: 11px; font-weight: bold;')
        inner_layout.addWidget(self.detail_quality)

        # Editable fields
        edit_group = QGroupBox('Photo Info')
        edit_form = QFormLayout(edit_group)
        edit_form.setSpacing(4)

        self.gallery_scene = QLineEdit()
        self.gallery_mood = QLineEdit()
        self.gallery_subjects = QLineEdit()
        self.gallery_location = QLineEdit()
        self.gallery_objects = QLineEdit()
        self.gallery_objects.setPlaceholderText('comma-separated')
        self.gallery_tags = QLineEdit()
        self.gallery_tags.setPlaceholderText('comma-separated')
        self.gallery_package = QLineEdit()

        edit_form.addRow('Scene:', self.gallery_scene)
        edit_form.addRow('Mood:', self.gallery_mood)
        edit_form.addRow('Subjects:', self.gallery_subjects)
        edit_form.addRow('Location:', self.gallery_location)
        edit_form.addRow('Objects:', self.gallery_objects)
        edit_form.addRow('Tags:', self.gallery_tags)
        edit_form.addRow('Package:', self.gallery_package)
        inner_layout.addWidget(edit_group)

        # AI Caption
        ai_group = QGroupBox('AI Caption')
        ai_layout = QVBoxLayout(ai_group)
        self.gallery_caption = QTextEdit()
        self.gallery_caption.setMaximumHeight(80)
        self.gallery_caption.setPlaceholderText('AI-suggested caption...')
        ai_layout.addWidget(self.gallery_caption)
        gen_cap_btn = QPushButton('Generate Caption')
        gen_cap_btn.setIcon(_icon('sparkle'))
        gen_cap_btn.setIconSize(QSize(16, 16))
        gen_cap_btn.clicked.connect(self._generate_caption)
        self.gallery_hashtags = QLineEdit()
        self.gallery_hashtags.setPlaceholderText('#hashtag1 #hashtag2 ...')
        ai_layout.addWidget(gen_cap_btn)
        ai_layout.addWidget(QLabel('Hashtags:'))
        ai_layout.addWidget(self.gallery_hashtags)
        inner_layout.addWidget(ai_group)

        # EXIF
        exif_group = QGroupBox('EXIF')
        exif_layout = QFormLayout(exif_group)
        exif_layout.setSpacing(3)
        self.exif_camera = QLabel('—')
        self.exif_lens = QLabel('—')
        self.exif_focal = QLabel('—')
        self.exif_aperture = QLabel('—')
        self.exif_shutter = QLabel('—')
        self.exif_iso = QLabel('—')
        self.exif_date = QLabel('—')
        self.exif_dims = QLabel('—')
        self.exif_size = QLabel('—')
        self.exif_gps = QLabel('—')
        self.detail_colors = QLabel('—')
        self.detail_rating = QLabel('—')
        for lbl, widget in [
            ('Camera:', self.exif_camera),
            ('Lens:', self.exif_lens),
            ('Focal:', self.exif_focal),
            ('Aperture:', self.exif_aperture),
            ('Shutter:', self.exif_shutter),
            ('ISO:', self.exif_iso),
            ('Date:', self.exif_date),
            ('Dimensions:', self.exif_dims),
            ('File size:', self.exif_size),
            ('GPS:', self.exif_gps),
            ('Colors:', self.detail_colors),
            ('Rating:', self.detail_rating),
        ]:
            widget.setStyleSheet('font-size: 11px;')
            exif_layout.addRow(lbl, widget)
        inner_layout.addWidget(exif_group)

        save_btn = QPushButton('Save Changes')
        save_btn.setIcon(_icon('save', 16, '#ffffff'))
        save_btn.setIconSize(QSize(16, 16))
        save_btn.setStyleSheet('background: #1a73e8; color: white; padding: 4px 12px;')
        save_btn.clicked.connect(self.save_details)
        inner_layout.addWidget(save_btn)
        inner_layout.addStretch()

        scroll.setWidget(inner)
        layout.addWidget(scroll)
        return panel

    # ── Search ───────────────────────────────────────────────────

    def _on_search(self, text: str):
        if not text.strip():
            self.refresh_with_photos(self._all_photos)
            return
        q = text.lower()
        filtered = [
            p for p in self._all_photos
            if any(q in str(p.get(f) or '').lower() for f in (
                'filename', 'ai_caption', 'suggested_hashtags', 'tags',
                'objects_detected', 'location', 'subjects', 'scene_type',
                'mood', 'notes', 'exif_camera',
            ))
        ]
        self.refresh_with_photos(filtered)

    # ── Data loading ─────────────────────────────────────────────

    def refresh(self):
        self._all_photos = self.controller.db.get_all_photos()
        q = self.search_edit.text().strip()
        if q:
            self._on_search(q)
        else:
            self.refresh_with_photos(self._all_photos)

    def refresh_with_photos(self, photos):
        self._thumbnail_frames = {}
        while self.gallery_grid.count():
            item = self.gallery_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sort_by = self.gallery_sort.currentText()
        if sort_by == 'Date (newest)':
            photos = sorted(photos, key=lambda p: str(p.get('exif_date_taken') or p.get('date_created') or ''), reverse=True)
        elif sort_by == 'Date (oldest)':
            photos = sorted(photos, key=lambda p: str(p.get('exif_date_taken') or p.get('date_created') or ''))
        elif sort_by == 'Filename':
            photos = sorted(photos, key=lambda p: (p.get('filename') or '').lower())
        elif sort_by == 'Quality':
            _order = {'excellent': 0, 'good': 1, 'fair': 2, 'poor': 3, '': 4}
            photos = sorted(photos, key=lambda p: _order.get(p.get('quality', ''), 4))
        elif sort_by == 'Status':
            photos = sorted(photos, key=lambda p: p.get('status') or '')
        elif sort_by == 'Scene':
            photos = sorted(photos, key=lambda p: p.get('scene_type') or '')

        size_map = {'Small': 140, 'Medium': 190, 'Large': 240}
        thumb_size = size_map[self.gallery_size.currentText()]

        scroll_width = self.gallery_container.parent().width() if self.gallery_container.parent() else 800
        cell_width = thumb_size + self.gallery_grid.spacing() + 10
        columns = max(1, scroll_width // cell_width)

        group_by = self.gallery_group.currentText()
        if group_by == 'None':
            self._render_flat(photos, thumb_size, columns)
        else:
            self._render_grouped(photos, thumb_size, columns, group_by)

        self.photo_count_label.setText(f'{len(photos)} photo{"s" if len(photos) != 1 else ""}')
        self._update_thumbnail_selection_styles()

    def _group_key(self, photo: dict, group_by: str) -> str:
        if group_by == 'By Date':
            dt = str(photo.get('exif_date_taken') or photo.get('date_created') or '')
            return dt[:7] or 'Unknown Date'   # YYYY-MM
        if group_by == 'By Scene':
            return (photo.get('scene_type') or 'Unknown').replace('_', ' ').title()
        if group_by == 'By Location':
            return (photo.get('location') or 'Unknown').title()
        if group_by == 'By Quality':
            return (photo.get('quality') or 'Unscored').title()
        return ''

    def _render_flat(self, photos, thumb_size, columns):
        for idx, photo in enumerate(photos):
            thumb = self._create_thumbnail(photo, thumb_size)
            self.gallery_grid.addWidget(thumb, idx // columns, idx % columns)

    def _render_grouped(self, photos, thumb_size, columns, group_by):
        from collections import OrderedDict
        groups: dict[str, list] = OrderedDict()
        for p in photos:
            key = self._group_key(p, group_by)
            groups.setdefault(key, []).append(p)

        grid_row = 0
        for group_label, group_photos in groups.items():
            # Section header spanning all columns
            header = QLabel(f'<b>{group_label}</b>  <span style="color:#888;font-size:11px;">{len(group_photos)} photo{"s" if len(group_photos)!=1 else ""}</span>')
            header.setTextFormat(Qt.TextFormat.RichText)
            header.setStyleSheet('padding: 6px 4px 2px 4px; background: transparent;')
            self.gallery_grid.addWidget(header, grid_row, 0, 1, columns)
            grid_row += 1

            for idx, photo in enumerate(group_photos):
                thumb = self._create_thumbnail(photo, thumb_size)
                self.gallery_grid.addWidget(thumb, grid_row + idx // columns, idx % columns)
            grid_row += (len(group_photos) + columns - 1) // columns

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Debounce: reflow grid 150ms after resize stops
        self._resize_timer.start(150)

    def _on_resize_debounced(self):
        if self._all_photos:
            q = self.search_edit.text().strip()
            if q:
                self._on_search(q)
            else:
                self.refresh_with_photos(self._all_photos)

    # ── Thumbnail creation ───────────────────────────────────────

    def _create_thumbnail(self, photo, size):
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        frame.setLineWidth(2)
        frame.setCursor(Qt.CursorShape.PointingHandCursor)
        frame.setProperty('photo_id', photo['id'])
        self._thumbnail_frames[photo['id']] = frame

        vl = QVBoxLayout(frame)
        vl.setContentsMargins(3, 3, 3, 3)
        vl.setSpacing(2)

        img_label = QLabel()
        img_label.setFixedSize(size, size)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if photo.get('filepath') and os.path.exists(photo['filepath']):
            pix = self.controller.get_cached_thumbnail(photo['filepath'], size)
            if pix and not pix.isNull():
                # Overlay quality badge
                quality = photo.get('quality', '')
                if quality in _QUALITY_BADGE:
                    pix = _add_quality_badge(pix, quality, size)
                img_label.setPixmap(pix)
            else:
                img_label.setText('[No Preview]')
        else:
            img_label.setText('[Missing]')
        vl.addWidget(img_label)

        # Info row
        scene = (photo.get('scene_type') or photo.get('type_of_shot') or '').replace('_', ' ')[:14]
        status = photo.get('status') or ''
        info = f"ID:{photo['id']}"
        if scene:
            info += f'  {scene}'
        if status:
            info += f'\n{status}'

        info_lbl = QLabel(info)
        info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_lbl.setStyleSheet('font-size: 9px; color: #ccc;')
        vl.addWidget(info_lbl)

        frame.mousePressEvent = lambda ev, p=photo: self._handle_click(ev, p)
        frame.mouseDoubleClickEvent = lambda ev, p=photo: self._handle_double_click(ev, p)
        frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        frame.customContextMenuRequested.connect(lambda pos, p=photo: self._thumb_context_menu(pos, p, frame))
        return frame

    def _handle_click(self, event, photo):
        try:
            if event.button() == Qt.MouseButton.MiddleButton:
                folder = os.path.dirname(photo.get('filepath', ''))
                if folder and os.path.isdir(folder):
                    os.startfile(folder)
                event.accept()
                return
            if event.button() == Qt.MouseButton.LeftButton:
                self.selected_gallery_photo_id = photo['id']
                self.show_details(photo)
                self._update_thumbnail_selection_styles()
                event.accept()
        except Exception as e:
            print(f'gallery click error: {e}')

    def _handle_double_click(self, event, photo):
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                self.controller.show_full_image(photo.get('filepath', ''), photo['id'])
                event.accept()
        except Exception as e:
            print(f'gallery double-click error: {e}')

    def _thumb_context_menu(self, pos, photo, frame):
        menu = QMenu(frame)
        menu.addAction('Open Full Size').triggered.connect(
            lambda: self.controller.show_full_image(photo.get('filepath', ''), photo['id']))
        menu.addAction('Post This Photo...').triggered.connect(lambda: self._post_photo(photo))
        menu.addSeparator()
        menu.addAction('Add to Album...').triggered.connect(lambda: self._add_to_album(photo))
        menu.addSeparator()
        menu.addAction('Open in Explorer').triggered.connect(
            lambda: os.startfile(os.path.dirname(photo.get('filepath', ''))))
        menu.exec(frame.mapToGlobal(pos))

    def _update_thumbnail_selection_styles(self):
        selected = self.selected_gallery_photo_id
        for photo_id, frame in self._thumbnail_frames.items():
            if photo_id == selected:
                frame.setStyleSheet('QFrame { border: 2px solid #3da5ff; }')
            else:
                frame.setStyleSheet('')

    # ── Details panel ────────────────────────────────────────────

    def show_details(self, photo):
        self.current_gallery_photo_id = photo['id']
        self.selected_gallery_photo_id = photo['id']
        self._update_thumbnail_selection_styles()

        # Preview
        fp = photo.get('filepath', '')
        if fp and os.path.exists(fp):
            pix = self.controller.get_cached_thumbnail(fp, 300)
            if pix and not pix.isNull():
                scaled = pix.scaled(
                    self.detail_preview.width(),
                    self.detail_preview.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.detail_preview.setPixmap(scaled)
            else:
                self.detail_preview.setText('[Preview N/A]')
        else:
            self.detail_preview.setText('[File not found]')

        self.open_btn.setEnabled(bool(fp))
        self._detail_post_btn.setEnabled(True)

        # ID + path
        w = photo.get('image_width', 0) or 0
        h = photo.get('image_height', 0) or 0
        dims = f'  {w}×{h}px' if w and h else ''
        self.detail_id.setText(f'ID: {photo["id"]:06d}{dims}')
        self.detail_path.setText(fp)

        # Quality
        quality = photo.get('quality', '')
        if quality in _QUALITY_BADGE:
            color, label = _QUALITY_BADGE[quality]
            self.detail_quality.setText(f'Quality: <span style="color:{color};">{label}</span>')
            self.detail_quality.setTextFormat(Qt.TextFormat.RichText)
        else:
            self.detail_quality.setText('')

        # Editable fields
        self.gallery_scene.setText(photo.get('scene_type') or '')
        self.gallery_mood.setText(photo.get('mood') or '')
        self.gallery_subjects.setText(photo.get('subjects') or '')
        self.gallery_location.setText(photo.get('location') or '')
        self.gallery_objects.setText(photo.get('objects_detected') or '')
        self.gallery_tags.setText(photo.get('tags') or '')
        self.gallery_package.setText(photo.get('package_name') or '')
        self.gallery_caption.setPlainText(photo.get('ai_caption') or '')
        self.gallery_hashtags.setText(photo.get('suggested_hashtags') or '')

        # EXIF
        self.exif_camera.setText(photo.get('exif_camera') or '—')
        self.exif_lens.setText(photo.get('exif_lens') or '—')
        self.exif_focal.setText(photo.get('exif_focal_length') or '—')
        self.exif_aperture.setText(photo.get('exif_aperture') or '—')
        self.exif_shutter.setText(photo.get('exif_shutter') or '—')
        self.exif_iso.setText(str(photo.get('exif_iso') or '—'))
        dt = photo.get('exif_date_taken') or photo.get('date_created') or '—'
        self.exif_date.setText(str(dt)[:19])
        w = photo.get('image_width', 0) or 0
        h = photo.get('image_height', 0) or 0
        self.exif_dims.setText(f'{w} × {h}' if w and h else '—')
        kb = photo.get('file_size_kb', 0) or 0
        self.exif_size.setText(f'{kb:,} KB' if kb else '—')
        lat = photo.get('exif_gps_lat')
        lon = photo.get('exif_gps_lon')
        self.exif_gps.setText(f'{lat:.5f}, {lon:.5f}' if lat and lon else '—')
        self.detail_colors.setText(photo.get('dominant_colors') or '—')
        rating = photo.get('content_rating') or ''
        rating_labels = {'general': 'General (SFW)', 'mature': 'Mature', 'restricted': 'Restricted'}
        self.detail_rating.setText(rating_labels.get(rating, rating or '—'))

    def save_details(self):
        if not self.current_gallery_photo_id:
            QMessageBox.warning(self, 'No Photo', 'Select a photo first.')
            return

        photo = self.controller.db.get_photo(self.current_gallery_photo_id)
        if not photo:
            QMessageBox.warning(self, 'Error', 'Photo not found in database.')
            return

        metadata = {
            'scene_type': self.gallery_scene.text().strip(),
            'mood': self.gallery_mood.text().strip(),
            'subjects': self.gallery_subjects.text().strip(),
            'location': self.gallery_location.text().strip(),
            'objects_detected': self.gallery_objects.text().strip(),
            'tags': self.gallery_tags.text().strip(),
            'package_name': self.gallery_package.text().strip(),
            'ai_caption': self.gallery_caption.toPlainText().strip(),
            'suggested_hashtags': self.gallery_hashtags.text().strip(),
        }

        # Track corrections for AI learning
        ai_fields = ['scene_type', 'mood', 'subjects', 'location', 'objects_detected']
        for field in ai_fields:
            old_val = photo.get(field)
            new_val = metadata.get(field)
            if old_val and new_val and old_val != new_val:
                try:
                    self.controller.db.save_correction(
                        self.current_gallery_photo_id, field, old_val, new_val
                    )
                except Exception:
                    pass

        try:
            self.controller.db.update_photo_metadata(self.current_gallery_photo_id, metadata)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save: {e}')
            return

        self.refresh()
        updated = self.controller.db.get_photo(self.current_gallery_photo_id)
        if updated:
            self.show_details(updated)
        try:
            self.controller.refresh_tag_cloud()
        except Exception:
            pass
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(
                f'Updated photo {self.current_gallery_photo_id:06d}', 3000
            )

    # ── Caption generator ────────────────────────────────────────

    def _generate_caption(self):
        if not self.current_gallery_photo_id:
            QMessageBox.information(self, 'No Photo', 'Select a photo first.')
            return
        photo = self.controller.db.get_photo(self.current_gallery_photo_id)
        if not photo:
            return

        # Use stored AI caption if present
        if photo.get('ai_caption'):
            self.gallery_caption.setPlainText(photo['ai_caption'])
            if photo.get('suggested_hashtags'):
                self.gallery_hashtags.setText(photo['suggested_hashtags'])
            if self.controller.statusBar():
                self.controller.statusBar().showMessage('Caption loaded from AI analysis.', 3000)
            return

        # Re-analyze if no caption stored
        fp = photo.get('filepath', '')
        if not fp or not os.path.exists(fp):
            QMessageBox.warning(self, 'Caption', 'Photo file not found.')
            return
        try:
            from core.ai_analyzer import analyze_image
            metadata = analyze_image(fp, self.controller.db)
            caption = metadata.get('ai_caption', '')
            hashtags = metadata.get('suggested_hashtags', '')
            if caption:
                self.gallery_caption.setPlainText(caption)
                self.controller.db.update_photo_metadata(
                    self.current_gallery_photo_id,
                    {'ai_caption': caption, 'suggested_hashtags': hashtags}
                )
            if hashtags:
                self.gallery_hashtags.setText(hashtags)
            if self.controller.statusBar():
                self.controller.statusBar().showMessage('Caption generated.', 3000)
        except Exception as e:
            QMessageBox.warning(self, 'Caption Error', str(e))

    # ── Quick actions ────────────────────────────────────────────

    def _open_full(self):
        if not self.current_gallery_photo_id:
            return
        photo = self.controller.db.get_photo(self.current_gallery_photo_id)
        if photo:
            self.controller.show_full_image(photo.get('filepath', ''), photo['id'])

    def _post_this(self):
        if not self.current_gallery_photo_id:
            return
        photo = self.controller.db.get_photo(self.current_gallery_photo_id)
        if photo:
            self._post_photo(photo)

    def _post_photo(self, photo):
        try:
            composer = getattr(self.controller, 'composer_tab', None)
            if composer:
                composer.set_photo_for_post(photo)
                # Switch tabs
                tabs = self.controller.tabs
                for i in range(tabs.count()):
                    if tabs.widget(i) is composer:
                        tabs.setCurrentIndex(i)
                        break
            else:
                QMessageBox.information(self, 'Post', 'Open the Compose tab to post this photo.')
        except Exception as e:
            QMessageBox.warning(self, 'Error', str(e))

    def _add_to_album(self, photo):
        try:
            albums = self.controller.db.get_albums()
            if not albums:
                QMessageBox.information(self, 'Albums', 'No albums yet. Create one in the Albums tab.')
                return
            from PyQt6.QtWidgets import QInputDialog
            names = [a['name'] for a in albums]
            name, ok = QInputDialog.getItem(self, 'Add to Album', 'Select album:', names, 0, False)
            if ok and name:
                album = next((a for a in albums if a['name'] == name), None)
                if album:
                    self.controller.db.add_photo_to_album(album['id'], photo['id'])
                    if self.controller.statusBar():
                        self.controller.statusBar().showMessage(f'Added to "{name}"', 2000)
        except Exception as e:
            QMessageBox.warning(self, 'Error', str(e))

    # ── Compatibility method ─────────────────────────────────────
    def set_gallery_size(self, size_label: str):
        if size_label in [self.gallery_size.itemText(i) for i in range(self.gallery_size.count())]:
            self.gallery_size.setCurrentText(size_label)


def _add_quality_badge(pix: QPixmap, quality: str, size: int) -> QPixmap:
    """Overlay a small quality badge in the top-right corner of a thumbnail."""
    color, label = _QUALITY_BADGE.get(quality, ('#888', ''))
    if not label:
        return pix
    result = QPixmap(pix)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    badge_w, badge_h = 56, 14
    margin = 3
    x = size - badge_w - margin
    y = margin
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(x, y, badge_w, badge_h, 4, 4)
    painter.setPen(QColor('#ffffff'))
    font = QFont()
    font.setPixelSize(9)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(x, y, badge_w, badge_h, Qt.AlignmentFlag.AlignCenter, label)
    painter.end()
    return result
