"""
Multi-platform post composer tab for PhotoFlow.
Select a photo, write a caption, pick platforms, post or schedule.
"""
import os
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QCheckBox, QGroupBox, QScrollArea, QGridLayout,
    QFrame, QSizePolicy, QDateTimeEdit, QMessageBox, QLineEdit,
    QComboBox, QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView,
    QTabWidget,
)
from PyQt6.QtCore import Qt, QSize, QDateTime
from PyQt6.QtGui import QPixmap, QFont, QColor
from core.icons import icon as _icon

# Per-platform caption character limits (0 = no hard limit)
_CAPTION_LIMITS = {
    'twitter':   280,
    'instagram': 2200,
    'facebook':  63206,
    'pinterest': 500,
    'threads':   500,
    'tiktok':    2200,
}


class ComposerTab(QWidget):
    """Compose and publish/schedule posts to multiple platforms."""

    _PLATFORMS = ['instagram', 'twitter', 'facebook', 'pinterest', 'threads', 'tiktok']
    _PLATFORM_LABELS = {
        'instagram': 'Instagram',
        'twitter': 'Twitter / X',
        'facebook': 'Facebook',
        'pinterest': 'Pinterest',
        'threads': 'Threads',
        'tiktok': 'TikTok',
    }

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._selected_photo = None
        self._platform_caption_edits: dict[str, QTextEdit] = {}
        self._platform_hashtag_edits: dict[str, QLineEdit] = {}
        self._build_ui()
        self.refresh_queue()

    def _build_ui(self):
        outer = QVBoxLayout(self)

        header = QLabel('<b>Post Composer</b>')
        header.setStyleSheet('font-size: 15px; padding: 4px;')
        outer.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: photo preview + picker ────────────────────────
        left = QWidget()
        left.setMaximumWidth(260)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_label = QLabel()
        self.preview_label.setFixedSize(240, 240)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet('border: 1px solid #555; background: #1e1e1e;')
        self.preview_label.setText('No photo selected')
        left_layout.addWidget(self.preview_label)

        pick_btn = QPushButton('Select Photo from Library')
        pick_btn.setIcon(_icon('image'))
        pick_btn.setIconSize(QSize(16, 16))
        pick_btn.clicked.connect(self._pick_photo)
        left_layout.addWidget(pick_btn)

        self.photo_info_label = QLabel('')
        self.photo_info_label.setWordWrap(True)
        self.photo_info_label.setStyleSheet('color: #aaa; font-size: 11px;')
        left_layout.addWidget(self.photo_info_label)
        left_layout.addStretch()

        splitter.addWidget(left)

        # ── Right: compose form ──────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)

        # Caption
        caption_header = QHBoxLayout()
        caption_header.addWidget(QLabel('<b>Caption</b>'))
        caption_header.addStretch()
        self.char_counter = QLabel('')
        self.char_counter.setStyleSheet('color: #aaa; font-size: 11px;')
        caption_header.addWidget(self.char_counter)
        right_layout.addLayout(caption_header)
        self.caption_edit = QTextEdit()
        self.caption_edit.setPlaceholderText('Write your caption here...')
        self.caption_edit.setMaximumHeight(120)
        self.caption_edit.textChanged.connect(self._update_char_counter)
        right_layout.addWidget(self.caption_edit)

        # Hashtags
        right_layout.addWidget(QLabel('<b>Hashtags</b>'))
        self.hashtags_edit = QLineEdit()
        self.hashtags_edit.setPlaceholderText('#photography #photo  (space-separated)')
        self.hashtags_edit.textChanged.connect(self._update_char_counter)
        right_layout.addWidget(self.hashtags_edit)

        right_layout.addWidget(QLabel('<b>Alt Text</b>'))
        self.alt_text_edit = QLineEdit()
        self.alt_text_edit.setPlaceholderText('Accessibility description for screen readers...')
        self.alt_text_edit.setToolTip(
            'Saved back to the selected photo. Supported APIs can use this for image accessibility.'
        )
        right_layout.addWidget(self.alt_text_edit)

        # AI suggestion row
        ai_row = QHBoxLayout()
        suggest_caption_btn = QPushButton('AI: Suggest Caption')
        suggest_caption_btn.setIcon(_icon('ai_caption'))
        suggest_caption_btn.setIconSize(QSize(16, 16))
        suggest_caption_btn.clicked.connect(self._suggest_caption)
        suggest_tags_btn = QPushButton('AI: Suggest Hashtags')
        suggest_tags_btn.setIcon(_icon('hashtag'))
        suggest_tags_btn.setIconSize(QSize(16, 16))
        suggest_tags_btn.clicked.connect(self._suggest_hashtags)
        template_btn = QPushButton('Templates…')
        template_btn.setIcon(_icon('template'))
        template_btn.setIconSize(QSize(16, 16))
        template_btn.setToolTip('Load or save caption templates')
        template_btn.clicked.connect(self._open_template_picker)
        ai_row.addWidget(suggest_caption_btn)
        ai_row.addWidget(suggest_tags_btn)
        ai_row.addWidget(template_btn)
        ai_row.addStretch()
        right_layout.addLayout(ai_row)

        # Platform checkboxes
        platform_group = QGroupBox('Post to')
        platform_layout = QHBoxLayout(platform_group)
        self._platform_checks: dict[str, QCheckBox] = {}
        for p in self._PLATFORMS:
            cb = QCheckBox(self._PLATFORM_LABELS[p])
            cb.toggled.connect(self._update_char_counter)
            platform_layout.addWidget(cb)
            self._platform_checks[p] = cb
        platform_layout.addStretch()
        right_layout.addWidget(platform_group)

        # Platform-specific overrides
        overrides_group = QGroupBox('Per-Platform Overrides')
        overrides_layout = QVBoxLayout(overrides_group)
        overrides_hint = QLabel(
            'Leave a platform tab blank to use the shared caption/hashtags above.'
        )
        overrides_hint.setWordWrap(True)
        overrides_hint.setStyleSheet('color: #888; font-size: 11px;')
        overrides_layout.addWidget(overrides_hint)

        self.platform_tabs = QTabWidget()
        self.platform_tabs.currentChanged.connect(self._update_char_counter)
        for platform in self._PLATFORMS:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(8, 8, 8, 8)

            cap_lbl = QLabel(f'{self._PLATFORM_LABELS[platform]} caption override')
            cap_lbl.setStyleSheet('font-size: 11px; color: #aaa;')
            tab_layout.addWidget(cap_lbl)

            cap_edit = QTextEdit()
            cap_edit.setMaximumHeight(90)
            cap_edit.setPlaceholderText('Optional caption override for this platform...')
            cap_edit.textChanged.connect(self._update_char_counter)
            tab_layout.addWidget(cap_edit)

            tags_lbl = QLabel(f'{self._PLATFORM_LABELS[platform]} hashtags override')
            tags_lbl.setStyleSheet('font-size: 11px; color: #aaa;')
            tab_layout.addWidget(tags_lbl)

            tags_edit = QLineEdit()
            tags_edit.setPlaceholderText('Optional hashtag override...')
            tags_edit.textChanged.connect(self._update_char_counter)
            tab_layout.addWidget(tags_edit)

            tab_layout.addStretch()
            self.platform_tabs.addTab(tab, self._PLATFORM_LABELS[platform])
            self._platform_caption_edits[platform] = cap_edit
            self._platform_hashtag_edits[platform] = tags_edit

        overrides_layout.addWidget(self.platform_tabs)
        right_layout.addWidget(overrides_group)

        # Schedule row
        schedule_group = QGroupBox('Schedule (optional — leave empty to post now)')
        sched_layout = QHBoxLayout(schedule_group)
        self.schedule_dt = QDateTimeEdit()
        self.schedule_dt.setDisplayFormat('yyyy-MM-dd HH:mm')
        self.schedule_dt.setDateTime(
            QDateTime.currentDateTime().addSecs(3600)
        )
        self.schedule_dt.setEnabled(False)
        self.use_schedule_cb = QCheckBox('Schedule for later')
        self.use_schedule_cb.toggled.connect(self.schedule_dt.setEnabled)
        sched_layout.addWidget(self.use_schedule_cb)
        sched_layout.addWidget(self.schedule_dt)
        sched_layout.addStretch()
        right_layout.addWidget(schedule_group)

        # Action buttons
        action_row = QHBoxLayout()
        post_btn = QPushButton('Post Now')
        post_btn.setIcon(_icon('send', 16, '#ffffff'))
        post_btn.setIconSize(QSize(16, 16))
        post_btn.setStyleSheet('background: #1a73e8; color: white; font-weight: bold; padding: 6px 16px;')
        post_btn.clicked.connect(self._post_now)
        schedule_btn = QPushButton('Add to Queue')
        schedule_btn.setIcon(_icon('clock'))
        schedule_btn.setIconSize(QSize(16, 16))
        schedule_btn.clicked.connect(self._schedule_post)
        clear_btn = QPushButton('Clear')
        clear_btn.setIcon(_icon('close'))
        clear_btn.setIconSize(QSize(16, 16))
        clear_btn.clicked.connect(self._clear)
        action_row.addWidget(post_btn)
        action_row.addWidget(schedule_btn)
        action_row.addStretch()
        action_row.addWidget(clear_btn)
        right_layout.addLayout(action_row)

        # Status / result
        self.result_label = QLabel('')
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet('color: #aaa; font-size: 11px; padding-top: 4px;')
        right_layout.addWidget(self.result_label)

        # Duplicate warning
        self.dupe_warning = QLabel('')
        self.dupe_warning.setWordWrap(True)
        self.dupe_warning.setStyleSheet('color: #e0a020; font-size: 11px;')
        self.dupe_warning.setVisible(False)
        right_layout.addWidget(self.dupe_warning)

        splitter.addWidget(right)
        splitter.setSizes([250, 550])
        outer.addWidget(splitter)

        # Queue preview
        queue_header = QHBoxLayout()
        queue_header.addWidget(QLabel('<b>Pending Queue</b>'))
        queue_header.addStretch()
        self.queue_refresh_btn = QPushButton()
        self.queue_refresh_btn.setIcon(_icon('refresh'))
        self.queue_refresh_btn.setIconSize(QSize(14, 14))
        self.queue_refresh_btn.setToolTip('Refresh queue')
        self.queue_refresh_btn.clicked.connect(self.refresh_queue)
        queue_header.addWidget(self.queue_refresh_btn)
        outer.addLayout(queue_header)

        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(5)
        self.queue_table.setHorizontalHeaderLabels(['Platform', 'Scheduled (UTC)', 'Status', 'Photo', 'Caption'])
        self.queue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.queue_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.queue_table.horizontalHeader().setStretchLastSection(True)
        self.queue_table.setAlternatingRowColors(True)
        self.queue_table.setMaximumHeight(160)
        outer.addWidget(self.queue_table)

        self.queue_count_label = QLabel('')
        self.queue_count_label.setStyleSheet('color: #aaa; font-size: 11px;')
        outer.addWidget(self.queue_count_label)

    # ── Photo selection ──────────────────────────────────────────

    def _pick_photo(self):
        try:
            from nova_manager import PhotoPickerDialog
            picker = PhotoPickerDialog(self.controller.db, self)
            picker.setWindowTitle('Select Photo for Post')
            if picker.exec():
                photo = picker.selected_photo
                if photo:
                    self._set_photo(photo)
        except Exception as e:
            QMessageBox.warning(self, 'Photo Picker', str(e))

    def _set_photo(self, photo: dict):
        self._selected_photo = photo
        fp = photo.get('filepath', '')
        if fp and os.path.exists(fp):
            pix = self.controller.get_cached_thumbnail(fp, 230)
            if pix and not pix.isNull():
                self.preview_label.setPixmap(pix)
            else:
                self.preview_label.setText('Preview N/A')
        else:
            self.preview_label.setText('File not found')

        # Info label
        parts = []
        if photo.get('exif_camera'):
            parts.append(photo['exif_camera'])
        if photo.get('filename'):
            parts.append(photo['filename'])
        self.photo_info_label.setText('\n'.join(parts))

        # Auto-fill AI caption if available
        if not self.caption_edit.toPlainText().strip():
            if photo.get('ai_caption'):
                self.caption_edit.setPlainText(photo['ai_caption'])

        # Auto-fill hashtags if available
        if not self.hashtags_edit.text().strip():
            if photo.get('suggested_hashtags'):
                self.hashtags_edit.setText(photo['suggested_hashtags'])

        if not self.alt_text_edit.text().strip() and photo.get('alt_text'):
            self.alt_text_edit.setText(photo['alt_text'])

        self._check_for_duplicates(photo['id'])
        self.refresh_queue()

    def set_photo_for_post(self, photo: dict):
        """Called externally (e.g., from gallery right-click) to pre-select a photo."""
        self._set_photo(photo)
        try:
            tabs = self.parent()
            while tabs and not hasattr(tabs, 'setCurrentWidget'):
                tabs = tabs.parent()
            if tabs:
                tabs.setCurrentWidget(self)
        except Exception:
            pass

    # ── Character counter ────────────────────────────────────────

    def _update_char_counter(self):
        active_platform = self._current_override_platform()
        if active_platform:
            text = self._platform_caption_edits[active_platform].toPlainText()
            limit = _CAPTION_LIMITS.get(active_platform, 0)
        else:
            text = self.caption_edit.toPlainText()
            platforms = self._get_selected_platforms()
            limits = [_CAPTION_LIMITS[p] for p in platforms if _CAPTION_LIMITS.get(p, 0) > 0]
            limit = min(limits) if limits else 0

        length = len(text)
        if limit > 0:
            over = length - limit
            if over > 0:
                self.char_counter.setText(f'{length} chars  ⚠ {over} over limit')
                self.char_counter.setStyleSheet('color: #e53935; font-size: 11px;')
            else:
                self.char_counter.setText(f'{length} / {limit}')
                self.char_counter.setStyleSheet('color: #aaa; font-size: 11px;')
        else:
            self.char_counter.setText(f'{length} chars')
            self.char_counter.setStyleSheet('color: #aaa; font-size: 11px;')

    def _selected_override_platform(self) -> str | None:
        """Return the platform for the currently selected override tab."""
        if not hasattr(self, 'platform_tabs'):
            return None
        idx = self.platform_tabs.currentIndex()
        if idx < 0 or idx >= len(self._PLATFORMS):
            return None
        return self._PLATFORMS[idx]

    def _current_override_platform(self) -> str | None:
        """Return the selected override platform only when it currently has override content."""
        platform = self._selected_override_platform()
        if not platform:
            return None
        caption_edit = self._platform_caption_edits.get(platform)
        hashtag_edit = self._platform_hashtag_edits.get(platform)
        if not caption_edit or not hashtag_edit:
            return None
        has_override = (
            caption_edit.toPlainText().strip() or
            hashtag_edit.text().strip()
        )
        return platform if has_override else None

    def _get_content_for_platform(self, platform: str) -> tuple[str, list[str]]:
        """Return the caption and hashtags to use for a platform.

        Platform-specific override fields win when populated; otherwise the
        shared caption and hashtags are used.
        """
        shared_caption = self.caption_edit.toPlainText().strip()
        shared_tags_text = self.hashtags_edit.text().strip()
        shared_tags = [token.strip() for token in shared_tags_text.split() if token.strip()]

        override_caption = self._platform_caption_edits[platform].toPlainText().strip()
        override_tags_text = self._platform_hashtag_edits[platform].text().strip()
        override_tags = [token.strip() for token in override_tags_text.split() if token.strip()]

        return (
            override_caption or shared_caption,
            override_tags or shared_tags,
        )

    def _persist_alt_text(self):
        """Save the composer alt text back to the selected photo record."""
        if not self._selected_photo:
            return
        new_alt_text = self.alt_text_edit.text().strip()
        old_alt_text = self._selected_photo.get('alt_text') or ''
        if new_alt_text == old_alt_text:
            return
        self.controller.db.update_photo_metadata(self._selected_photo['id'], {'alt_text': new_alt_text})
        self._selected_photo['alt_text'] = new_alt_text

    # ── Queue preview ────────────────────────────────────────────

    def refresh_queue(self):
        """Reload the pending queue table."""
        _STATUS_COLORS = {'pending': '#e0a020', 'sent': '#4caf50', 'failed': '#e53935'}
        try:
            posts = self.controller.db.get_scheduled_posts()
        except Exception:
            return
        pending = [p for p in posts if p.get('status') in ('pending', 'failed')]
        self.queue_table.setRowCount(0)
        for post in pending:
            photo_name = ''
            if post.get('photo_id'):
                try:
                    photo = self.controller.db.get_photo(post['photo_id'])
                    if photo:
                        photo_name = photo.get('filename', str(post['photo_id']))
                except Exception:
                    photo_name = str(post['photo_id'])
            row = self.queue_table.rowCount()
            self.queue_table.insertRow(row)
            values = [
                str(post.get('platform', '')).capitalize(),
                str(post.get('scheduled_time', '')),
                str(post.get('status', '')),
                photo_name,
                (post.get('caption') or '')[:60],
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                if col == 2:
                    color = _STATUS_COLORS.get(post.get('status', ''), '')
                    if color:
                        item.setForeground(QColor(color))
                self.queue_table.setItem(row, col, item)
        total = sum(1 for p in posts if p.get('status') == 'pending')
        failed = sum(1 for p in posts if p.get('status') == 'failed')
        parts = []
        if total:
            parts.append(f'{total} pending')
        if failed:
            parts.append(f'{failed} failed')
        self.queue_count_label.setText(', '.join(parts) if parts else 'Queue empty')

    # ── Duplicate check ──────────────────────────────────────────

    def _check_for_duplicates(self, photo_id: int):
        """Warn if this photo already has pending or recently sent posts."""
        try:
            posts = self.controller.db.get_scheduled_posts()
        except Exception:
            return
        relevant = [
            p for p in posts
            if p.get('photo_id') == photo_id and p.get('status') in ('pending', 'sent')
        ]
        if not relevant:
            self.dupe_warning.setVisible(False)
            return
        platforms = ', '.join(sorted({p.get('platform', '?').capitalize() for p in relevant}))
        statuses = {p['status'] for p in relevant}
        if 'pending' in statuses:
            msg = f'⚠ This photo is already queued for: {platforms}'
        else:
            msg = f'This photo was already posted to: {platforms}'
        self.dupe_warning.setText(msg)
        self.dupe_warning.setVisible(True)

    # ── AI helpers ───────────────────────────────────────────────

    def _suggest_caption(self):
        if not self._selected_photo:
            QMessageBox.information(self, 'No Photo', 'Select a photo first.')
            return
        cap = self._selected_photo.get('ai_caption', '')
        if cap:
            self.caption_edit.setPlainText(cap)
            self.result_label.setText('Caption filled from AI analysis.')
        else:
            self.result_label.setText('No AI caption stored. Re-analyze the photo to generate one.')

    def _suggest_hashtags(self):
        if not self._selected_photo:
            QMessageBox.information(self, 'No Photo', 'Select a photo first.')
            return
        tags = self._selected_photo.get('suggested_hashtags', '')
        if tags:
            self.hashtags_edit.setText(tags)
            self.result_label.setText('Hashtags filled from AI analysis.')
        else:
            self.result_label.setText('No suggested hashtags stored. Re-analyze the photo.')

    # ── Posting ──────────────────────────────────────────────────

    def _get_selected_platforms(self) -> list[str]:
        return [p for p, cb in self._platform_checks.items() if cb.isChecked()]

    def _validate(self) -> bool:
        if not self._selected_photo:
            QMessageBox.warning(self, 'Composer', 'Please select a photo first.')
            return False
        if not self._get_selected_platforms():
            QMessageBox.warning(self, 'Composer', 'Select at least one platform.')
            return False
        return True

    def _post_now(self):
        if not self._validate():
            return
        self._persist_alt_text()
        filepath = self._selected_photo.get('filepath', '')
        alt_text = self.alt_text_edit.text().strip()
        results = []

        for platform in self._get_selected_platforms():
            try:
                caption, hashtags = self._get_content_for_platform(platform)
                creds = self.controller.db.get_credentials(platform) or {}
                if platform == 'instagram':
                    from core.social.instagram_api import InstagramAPI
                    api = InstagramAPI(creds)
                elif platform == 'twitter':
                    from core.social.twitter_api import TwitterAPI
                    api = TwitterAPI(creds)
                elif platform == 'facebook':
                    from core.social.facebook_api import FacebookAPI
                    api = FacebookAPI(creds)
                elif platform == 'pinterest':
                    from core.social.pinterest_api import PinterestAPI
                    api = PinterestAPI(creds)
                elif platform == 'threads':
                    from core.social.threads_api import ThreadsAPI
                    api = ThreadsAPI(creds)
                elif platform == 'tiktok':
                    from core.social.tiktok_api import TikTokAPI
                    api = TikTokAPI(creds)
                else:
                    results.append(f'{platform}: not yet implemented')
                    continue

                if not api.is_connected():
                    results.append(f'{platform}: not connected (check Settings)')
                    continue

                result = api.post_photo(filepath, caption, hashtags, alt_text=alt_text)
                if result.success:
                    results.append(f'{platform}: posted! {result.url}')
                    # Log to posting history (permanent record)
                    self.controller.db.log_post(
                        photo_id=self._selected_photo['id'],
                        platform=platform,
                        post_type='post',
                        caption=caption,
                        post_url=result.url,
                        post_id=result.post_id,
                        status='success',
                    )
                else:
                    results.append(f'{platform}: failed — {result.error}')
            except Exception as e:
                results.append(f'{platform}: error — {e}')

        self.result_label.setText('\n'.join(results))
        if self.controller.statusBar():
            self.controller.statusBar().showMessage('Post attempt complete.', 4000)
        self.refresh_queue()
        if self._selected_photo:
            self._check_for_duplicates(self._selected_photo['id'])

    def _schedule_post(self):
        if not self._validate():
            return
        self._persist_alt_text()

        if self.use_schedule_cb.isChecked():
            scheduled_time = self.schedule_dt.dateTime().toPyDateTime().isoformat()
        else:
            scheduled_time = (datetime.utcnow() + timedelta(minutes=1)).isoformat()

        added = []
        for platform in self._get_selected_platforms():
            try:
                caption, hashtag_tokens = self._get_content_for_platform(platform)
                hashtags = ' '.join(hashtag_tokens)
                self.controller.db.schedule_post(
                    photo_id=self._selected_photo['id'],
                    platform=platform,
                    scheduled_time=scheduled_time,
                    caption=caption,
                    hashtags=hashtags,
                )
                added.append(self._PLATFORM_LABELS.get(platform, platform))
            except Exception as e:
                added.append(f'{platform} (error: {e})')

        self.result_label.setText('Queued for: ' + ', '.join(added))
        if self.controller.statusBar():
            self.controller.statusBar().showMessage('Posts added to schedule queue.', 3000)
        self.refresh_queue()
        if self._selected_photo:
            self._check_for_duplicates(self._selected_photo['id'])

    def _clear(self):
        self._selected_photo = None
        self.preview_label.setText('No photo selected')
        self.preview_label.setPixmap(QPixmap())
        self.caption_edit.clear()
        self.hashtags_edit.clear()
        self.alt_text_edit.clear()
        self.photo_info_label.clear()
        self.result_label.clear()
        self.dupe_warning.setVisible(False)
        self.char_counter.setText('')
        for cb in self._platform_checks.values():
            cb.setChecked(False)
        for platform in self._PLATFORMS:
            self._platform_caption_edits[platform].clear()
            self._platform_hashtag_edits[platform].clear()

    # ── Caption Template Library ─────────────────────────────────

    def _open_template_picker(self):
        """Open the caption template picker dialog."""
        from PyQt6.QtWidgets import (
            QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
            QVBoxLayout, QHBoxLayout, QInputDialog,
        )
        dlg = QDialog(self)
        dlg.setWindowTitle('Caption Templates')
        dlg.resize(520, 420)
        layout = QVBoxLayout(dlg)

        list_widget = QListWidget()
        templates = self.controller.db.get_caption_templates()

        def _reload():
            list_widget.clear()
            for t in self.controller.db.get_caption_templates():
                item = QListWidgetItem(
                    f"{t['name']}" + (f"  [{t['platform']}]" if t['platform'] else '')
                )
                item.setData(Qt.ItemDataRole.UserRole, t)
                list_widget.addItem(item)

        _reload()
        layout.addWidget(list_widget)

        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setMaximumHeight(100)
        preview.setPlaceholderText('Select a template to preview it…')
        layout.addWidget(preview)

        def _on_select(item):
            t = item.data(Qt.ItemDataRole.UserRole)
            preview.setPlainText(t.get('body', ''))

        list_widget.currentItemChanged.connect(
            lambda cur, _: _on_select(cur) if cur else None
        )

        btn_row = QHBoxLayout()
        use_btn = QPushButton('Use Template')
        use_btn.clicked.connect(dlg.accept)
        save_new_btn = QPushButton('Save Current as Template…')
        del_btn = QPushButton('Delete')
        del_btn.setStyleSheet('color: #f44336;')
        btn_row.addWidget(use_btn)
        btn_row.addStretch()
        btn_row.addWidget(save_new_btn)
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)

        def _save_new():
            target_platform = self._current_override_platform()
            body = (
                self._platform_caption_edits[target_platform].toPlainText().strip()
                if target_platform else
                self.caption_edit.toPlainText().strip()
            )
            if not body:
                return
            name, ok = QInputDialog.getText(dlg, 'Save Template', 'Template name:')
            if ok and name.strip():
                self.controller.db.create_caption_template(name.strip(), body, target_platform or '')
                _reload()

        def _delete_selected():
            item = list_widget.currentItem()
            if not item:
                return
            t = item.data(Qt.ItemDataRole.UserRole)
            self.controller.db.delete_caption_template(t['id'])
            _reload()

        save_new_btn.clicked.connect(_save_new)
        del_btn.clicked.connect(_delete_selected)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            item = list_widget.currentItem()
            if item:
                t = item.data(Qt.ItemDataRole.UserRole)
                body = t.get('body', '')
                # Substitute known tokens
                if self._selected_photo:
                    from datetime import datetime
                    replacements = {
                        '{caption}': self._selected_photo.get('ai_caption') or '',
                        '{hashtags}': self._selected_photo.get('suggested_hashtags') or '',
                        '{scene}': self._selected_photo.get('scene_type') or '',
                        '{location}': self._selected_photo.get('location') or '',
                        '{mood}': self._selected_photo.get('mood') or '',
                        '{date}': str(
                            self._selected_photo.get('exif_date_taken') or
                            self._selected_photo.get('date_created') or ''
                        )[:10],
                        '{filename}': self._selected_photo.get('filename') or '',
                    }
                    for token, value in replacements.items():
                        body = body.replace(token, value)
                target_platform = self._current_override_platform()
                if target_platform:
                    self._platform_caption_edits[target_platform].setPlainText(body)
                else:
                    self.caption_edit.setPlainText(body)

