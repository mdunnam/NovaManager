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
        right_layout.addWidget(self.hashtags_edit)

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
        ai_row.addWidget(suggest_caption_btn)
        ai_row.addWidget(suggest_tags_btn)
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
        text = self.caption_edit.toPlainText()
        length = len(text)
        platforms = self._get_selected_platforms()
        limits = [_CAPTION_LIMITS[p] for p in platforms if _CAPTION_LIMITS.get(p, 0) > 0]
        if limits:
            tightest = min(limits)
            over = length - tightest
            if over > 0:
                self.char_counter.setText(f'{length} chars  ⚠ {over} over limit')
                self.char_counter.setStyleSheet('color: #e53935; font-size: 11px;')
            else:
                self.char_counter.setText(f'{length} / {tightest}')
                self.char_counter.setStyleSheet('color: #aaa; font-size: 11px;')
        else:
            self.char_counter.setText(f'{length} chars')
            self.char_counter.setStyleSheet('color: #aaa; font-size: 11px;')

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
        caption = self.caption_edit.toPlainText().strip()
        hashtags = [t.strip() for t in self.hashtags_edit.text().split() if t.strip()]
        filepath = self._selected_photo.get('filepath', '')
        results = []

        for platform in self._get_selected_platforms():
            try:
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

                result = api.post_photo(filepath, caption, hashtags)
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

        caption = self.caption_edit.toPlainText().strip()
        hashtags = ' '.join(t.strip() for t in self.hashtags_edit.text().split() if t.strip())

        if self.use_schedule_cb.isChecked():
            scheduled_time = self.schedule_dt.dateTime().toPyDateTime().isoformat()
        else:
            scheduled_time = (datetime.utcnow() + timedelta(minutes=1)).isoformat()

        added = []
        for platform in self._get_selected_platforms():
            try:
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
        self.photo_info_label.clear()
        self.result_label.clear()
        self.dupe_warning.setVisible(False)
        self.char_counter.setText('')
        for cb in self._platform_checks.values():
            cb.setChecked(False)
