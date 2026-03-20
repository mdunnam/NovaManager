"""
Post Schedule tab for PhotoFlow.
Shows the queue of scheduled and recently sent posts.
"""
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QComboBox, QGroupBox,
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QColor
from core.icons import icon as _icon


_STATUS_COLORS = {
    'pending': '#e0a020',
    'sent':    '#4caf50',
    'failed':  '#e53935',
    'cancelled': '#888',
}

_COLS = ['ID', 'Platform', 'Scheduled (UTC)', 'Status', 'Photo', 'Caption', 'Post ID']


class ScheduleTab(QWidget):
    """Post queue / schedule calendar UI."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._build_ui()
        self.refresh()
        # Auto-refresh every 30 seconds
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(30_000)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header_row = QHBoxLayout()
        header = QLabel('<b>Post Schedule</b>')
        header.setStyleSheet('font-size: 15px; padding: 4px;')
        header_row.addWidget(header)
        header_row.addStretch()

        filter_lbl = QLabel('Show:')
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(['All', 'Pending', 'Sent', 'Failed'])
        self.filter_combo.currentTextChanged.connect(self.refresh)
        header_row.addWidget(filter_lbl)
        header_row.addWidget(self.filter_combo)

        refresh_btn = QPushButton()
        refresh_btn.setIcon(_icon('refresh'))
        refresh_btn.setIconSize(QSize(18, 18))
        refresh_btn.setToolTip('Refresh schedule')
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        self.table = QTableWidget()
        self.table.setColumnCount(len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Best time to post hints
        hints_group = QGroupBox('Best Times to Post (UTC)')
        hints_layout = QVBoxLayout(hints_group)
        hints_layout.setSpacing(2)
        _HINTS = [
            ('Instagram', 'Mon–Fri  9:00, 12:00, 17:00 · Sat–Sun  11:00'),
            ('Twitter/X', 'Mon–Fri  8:00, 12:00, 17:00–18:00'),
            ('Facebook',  'Mon–Fri  9:00, 13:00, 15:00–16:00'),
            ('Pinterest',  'Sat  20:00–23:00 · Weekdays  20:00–23:00'),
            ('TikTok',    'Tue–Fri  6:00–10:00, 19:00–23:00'),
        ]
        for platform, times in _HINTS:
            lbl = QLabel(f'<b>{platform}:</b>  <span style="color:#aaa;">{times}</span>')
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setStyleSheet('font-size: 10px; padding: 1px;')
            hints_layout.addWidget(lbl)
        layout.addWidget(hints_group)

        action_row = QHBoxLayout()
        cancel_btn = QPushButton('Cancel Selected')
        cancel_btn.setIcon(_icon('stop'))
        cancel_btn.setIconSize(QSize(16, 16))
        cancel_btn.clicked.connect(self._cancel_selected)
        retry_btn = QPushButton('Retry Failed')
        retry_btn.setIcon(_icon('retry'))
        retry_btn.setIconSize(QSize(16, 16))
        retry_btn.clicked.connect(self._retry_failed)
        clear_sent_btn = QPushButton('Clear Sent')
        clear_sent_btn.setIcon(_icon('trash'))
        clear_sent_btn.setIconSize(QSize(16, 16))
        clear_sent_btn.clicked.connect(self._clear_sent)
        action_row.addWidget(cancel_btn)
        action_row.addWidget(retry_btn)
        action_row.addWidget(clear_sent_btn)
        action_row.addStretch()
        self.count_label = QLabel('')
        self.count_label.setStyleSheet('color: #aaa; font-size: 11px;')
        action_row.addWidget(self.count_label)
        layout.addLayout(action_row)

    # ── Data loading ─────────────────────────────────────────────

    def refresh(self):
        try:
            posts = self.controller.db.get_scheduled_posts()
        except Exception as e:
            self.count_label.setText(f'Error: {e}')
            return

        status_filter = self.filter_combo.currentText().lower()
        if status_filter != 'all':
            posts = [p for p in posts if p.get('status', '') == status_filter]

        self.table.setRowCount(0)
        for post in posts:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Resolve photo filename
            photo_name = ''
            if post.get('photo_id'):
                try:
                    photo = self.controller.db.get_photo(post['photo_id'])
                    if photo:
                        photo_name = photo.get('filename', str(post['photo_id']))
                except Exception:
                    photo_name = str(post['photo_id'])

            values = [
                str(post.get('id', '')),
                str(post.get('platform', '')).capitalize(),
                str(post.get('scheduled_time', '')),
                str(post.get('status', '')),
                photo_name,
                (post.get('caption') or '')[:60],
                str(post.get('post_id') or ''),
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, post.get('id'))
                status = post.get('status', '')
                color = _STATUS_COLORS.get(status, '')
                if color and col == 3:
                    item.setForeground(QColor(color))
                self.table.setItem(row, col, item)

        total = len(posts)
        pending = sum(1 for p in posts if p.get('status') == 'pending')
        self.count_label.setText(f'{total} total, {pending} pending')

    # ── Actions ──────────────────────────────────────────────────

    def _get_selected_ids(self) -> list[int]:
        ids = []
        for item in self.table.selectedItems():
            if item.column() == 0:
                try:
                    ids.append(int(item.text()))
                except ValueError:
                    pass
        return ids

    def _cancel_selected(self):
        ids = self._get_selected_ids()
        if not ids:
            QMessageBox.information(self, 'Cancel', 'Select row(s) to cancel.')
            return
        for post_id in ids:
            try:
                self.controller.db.update_scheduled_post_status(post_id, 'cancelled')
            except Exception:
                pass
        self.refresh()

    def _retry_failed(self):
        try:
            posts = self.controller.db.get_scheduled_posts()
        except Exception:
            return
        for post in posts:
            if post.get('status') == 'failed':
                try:
                    self.controller.db.update_scheduled_post_status(post['id'], 'pending')
                except Exception:
                    pass
        self.refresh()
        if self.controller.statusBar():
            self.controller.statusBar().showMessage('Failed posts set back to pending.', 3000)

    def _clear_sent(self):
        reply = QMessageBox.question(
            self, 'Clear Sent',
            'Remove all successfully sent posts from the queue?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            posts = self.controller.db.get_scheduled_posts()
            for post in posts:
                if post.get('status') == 'sent':
                    self.controller.db.delete_scheduled_post(post['id'])
        except Exception as e:
            QMessageBox.warning(self, 'Error', str(e))
        self.refresh()
