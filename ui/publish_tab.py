"""
Publish tab for PhotoFlow — post queue, bulk scheduling, and quick-post.
"""
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QListWidget, QListWidgetItem, QScrollArea,
    QSplitter, QComboBox, QSpinBox, QTimeEdit, QGroupBox,
    QFormLayout, QMessageBox, QAbstractItemView,
)
from PyQt6.QtCore import Qt, QTime, QSize
from core.icons import icon as _icon

_PLATFORMS = ['instagram', 'twitter', 'facebook', 'pinterest', 'threads', 'tiktok']

_PLATFORM_ICONS = {
    'instagram': 'instagram',
    'tiktok': 'tiktok',
    'twitter': 'twitter_x',
    'facebook': 'facebook',
    'pinterest': 'pinterest',
    'threads': 'threads',
}


class PublishTab(QWidget):
    """Post queue management and bulk scheduling."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel('<b>Publish Queue</b>')
        header.setStyleSheet('font-size: 15px; padding: 4px;')
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: ready queue ────────────────────────────────────
        left = QWidget()
        left.setMinimumWidth(0)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 4, 0)

        ll.addWidget(QLabel('<b>Ready to Post</b>'))
        self.queue_list = QListWidget()
        self.queue_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.queue_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.queue_list.setToolTip('Drag to reorder. These are photos with status "ready".')
        ll.addWidget(self.queue_list)

        q_btn_row = QHBoxLayout()
        refresh_q_btn = QPushButton()
        refresh_q_btn.setIcon(_icon('refresh'))
        refresh_q_btn.setIconSize(QSize(18, 18))
        refresh_q_btn.setToolTip('Refresh post queue')
        refresh_q_btn.clicked.connect(self.refresh_queue)
        post_next_btn = QPushButton('Post Next \u2192')
        post_next_btn.setIcon(_icon('arrow_right', 16, '#ffffff'))
        post_next_btn.setIconSize(QSize(16, 16))
        post_next_btn.setStyleSheet('background: #1a73e8; color: white; font-weight: bold;')
        post_next_btn.clicked.connect(self._post_next)
        q_btn_row.addWidget(refresh_q_btn)
        q_btn_row.addWidget(post_next_btn)
        ll.addLayout(q_btn_row)

        splitter.addWidget(left)

        # ── Right: bulk schedule + stage controls ────────────────
        right = QWidget()
        right.setMinimumWidth(0)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 0, 0)

        # Stage buttons (quick flags)
        stage_group = QGroupBox('Stage Selected Photos')
        stage_layout = QHBoxLayout(stage_group)
        stage_layout.addWidget(QLabel('Mark as staged for:'))
        for platform in ['Instagram', 'TikTok', 'Twitter', 'Facebook']:
            btn = QPushButton(platform)
            pkey = platform.lower()
            if pkey in _PLATFORM_ICONS:
                btn.setIcon(_icon(_PLATFORM_ICONS[pkey]))
                btn.setIconSize(QSize(16, 16))
            btn.setCheckable(False)
            btn.clicked.connect(
                lambda checked, p=platform.lower(): self.controller.toggle_staged(p)
                if hasattr(self.controller, 'toggle_staged') else None
            )
            stage_layout.addWidget(btn)
        stage_layout.addStretch()
        rl.addWidget(stage_group)

        # Bulk schedule
        bulk_group = QGroupBox('Bulk Schedule')
        bulk_form = QFormLayout(bulk_group)

        self.bulk_platform = QComboBox()
        self.bulk_platform.addItems([p.capitalize() for p in _PLATFORMS])
        bulk_form.addRow('Platform:', self.bulk_platform)

        self.bulk_count = QSpinBox()
        self.bulk_count.setRange(1, 100)
        self.bulk_count.setValue(7)
        bulk_form.addRow('Number of posts:', self.bulk_count)

        self.bulk_days = QSpinBox()
        self.bulk_days.setRange(1, 365)
        self.bulk_days.setValue(7)
        self.bulk_days.setSuffix(' days')
        bulk_form.addRow('Spread over:', self.bulk_days)

        self.bulk_start_time = QTimeEdit()
        self.bulk_start_time.setTime(QTime(9, 0))
        self.bulk_start_time.setDisplayFormat('HH:mm')
        bulk_form.addRow('Post time (UTC):', self.bulk_start_time)

        schedule_bulk_btn = QPushButton('Schedule Queue to Platform')
        schedule_bulk_btn.setIcon(_icon('calendar', 16, '#ffffff'))
        schedule_bulk_btn.setIconSize(QSize(16, 16))
        schedule_bulk_btn.setStyleSheet('background: #1a73e8; color: white; padding: 5px 12px;')
        schedule_bulk_btn.clicked.connect(self._bulk_schedule)
        bulk_form.addRow('', schedule_bulk_btn)
        rl.addWidget(bulk_group)

        # Manage
        manage_group = QGroupBox('Manage')
        manage_layout = QHBoxLayout(manage_group)
        pkg_btn = QPushButton('Manage Packages')
        pkg_btn.setIcon(_icon('package'))
        pkg_btn.setIconSize(QSize(16, 16))
        pkg_btn.clicked.connect(
            lambda: self.controller.manage_packages_dialog()
            if hasattr(self.controller, 'manage_packages_dialog') else None
        )
        unstage_btn = QPushButton('Unstage Selected')
        unstage_btn.setIcon(_icon('unstage'))
        unstage_btn.setIconSize(QSize(16, 16))
        unstage_btn.clicked.connect(
            lambda: self.controller.unstage_selected()
            if hasattr(self.controller, 'unstage_selected') else None
        )
        manage_layout.addWidget(pkg_btn)
        manage_layout.addWidget(unstage_btn)
        manage_layout.addStretch()
        rl.addWidget(manage_group)

        rl.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([350, 450])
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, True)
        layout.addWidget(splitter)

        self.refresh_queue()

    def refresh_queue(self):
        self.queue_list.clear()
        try:
            photos = self.controller.db.get_all_photos()
            ready = [p for p in photos if p.get('status') == 'ready']
            for photo in ready:
                item = QListWidgetItem(
                    f"ID:{photo['id']:06d}  {photo.get('filename', '')}"
                    f"  [{photo.get('scene_type') or '—'}]"
                )
                item.setData(Qt.ItemDataRole.UserRole, photo['id'])
                self.queue_list.addItem(item)
        except Exception as e:
            print(f'[PublishTab] queue refresh error: {e}')

    def _post_next(self):
        item = self.queue_list.item(0)
        if not item:
            QMessageBox.information(self, 'Queue Empty', 'No ready photos in queue.')
            return
        photo_id = item.data(Qt.ItemDataRole.UserRole)
        photo = self.controller.db.get_photo(photo_id)
        if not photo:
            return
        try:
            composer = getattr(self.controller, 'composer_tab', None)
            if composer:
                composer.set_photo_for_post(photo)
                tabs = self.controller.tabs
                for i in range(tabs.count()):
                    if tabs.widget(i) is composer:
                        tabs.setCurrentIndex(i)
                        break
        except Exception as e:
            QMessageBox.warning(self, 'Error', str(e))

    def _bulk_schedule(self):
        platform = self.bulk_platform.currentText().lower()
        count = self.bulk_count.value()
        days = self.bulk_days.value()
        post_time = self.bulk_start_time.time()

        # Get ready photos not yet scheduled for this platform
        try:
            photos = self.controller.db.get_all_photos()
            ready = [p for p in photos if p.get('status') == 'ready'][:count]
        except Exception as e:
            QMessageBox.warning(self, 'Error', str(e))
            return

        if not ready:
            QMessageBox.information(self, 'Bulk Schedule', 'No "ready" photos to schedule.')
            return

        interval_hours = (days * 24) / max(len(ready), 1)
        now = datetime.utcnow().replace(hour=post_time.hour(), minute=post_time.minute(), second=0)
        scheduled = []
        for i, photo in enumerate(ready):
            post_dt = now + timedelta(hours=interval_hours * i)
            try:
                self.controller.db.schedule_post(
                    photo_id=photo['id'],
                    platform=platform,
                    caption=photo.get('ai_caption') or '',
                    hashtags=photo.get('suggested_hashtags') or '',
                    scheduled_time=post_dt.isoformat(),
                )
                scheduled.append(photo['id'])
            except Exception as e:
                print(f'[BulkSchedule] error: {e}')

        msg = f'Scheduled {len(scheduled)} posts to {platform.capitalize()} over {days} days.'
        QMessageBox.information(self, 'Bulk Schedule', msg)
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(msg, 5000)
        # Refresh schedule tab
        try:
            self.controller.schedule_tab.refresh()
        except Exception:
            pass
