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
    QComboBox, QSplitter,
)
from PyQt6.QtCore import Qt, QSize, QDateTime
from PyQt6.QtGui import QPixmap, QFont
from core.icons import icon as _icon


class ComposerTab(QWidget):
    """Compose and publish/schedule posts to multiple platforms."""

    _PLATFORMS = ['instagram', 'twitter', 'facebook', 'pinterest', 'threads']
    _PLATFORM_LABELS = {
        'instagram': 'Instagram',
        'twitter': 'Twitter / X',
        'facebook': 'Facebook',
        'pinterest': 'Pinterest',
        'threads': 'Threads',
    }

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._selected_photo = None
        self._build_ui()

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
        right_layout.addWidget(QLabel('<b>Caption</b>'))
        self.caption_edit = QTextEdit()
        self.caption_edit.setPlaceholderText('Write your caption here...')
        self.caption_edit.setMaximumHeight(120)
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
        right_layout.addStretch()

        splitter.addWidget(right)
        splitter.setSizes([250, 550])
        outer.addWidget(splitter)

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

    def set_photo_for_post(self, photo: dict):
        """Called externally (e.g., from gallery right-click) to pre-select a photo."""
        self._set_photo(photo)
        # Switch to composer tab in parent tabs widget
        try:
            tabs = self.parent()
            while tabs and not hasattr(tabs, 'setCurrentWidget'):
                tabs = tabs.parent()
            if tabs:
                tabs.setCurrentWidget(self)
        except Exception:
            pass

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
                else:
                    results.append(f'{platform}: not yet implemented')
                    continue

                if not api.is_connected():
                    results.append(f'{platform}: not connected (check Settings)')
                    continue

                result = api.post_photo(filepath, caption, hashtags)
                if result.success:
                    results.append(f'{platform}: posted! {result.url}')
                    # Log to DB
                    self.controller.db.schedule_post(
                        photo_id=self._selected_photo['id'],
                        platform=platform,
                        caption=caption,
                        hashtags=','.join(hashtags),
                        scheduled_time=datetime.utcnow().isoformat(),
                        status='sent',
                        post_id=result.post_id,
                    )
                else:
                    results.append(f'{platform}: failed — {result.error}')
            except Exception as e:
                results.append(f'{platform}: error — {e}')

        self.result_label.setText('\n'.join(results))
        if self.controller.statusBar():
            self.controller.statusBar().showMessage('Post attempt complete.', 4000)

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

    def _clear(self):
        self._selected_photo = None
        self.preview_label.setText('No photo selected')
        self.preview_label.setPixmap(QPixmap())
        self.caption_edit.clear()
        self.hashtags_edit.clear()
        self.photo_info_label.clear()
        self.result_label.clear()
        for cb in self._platform_checks.values():
            cb.setChecked(False)
