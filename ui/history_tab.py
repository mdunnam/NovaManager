"""
Posting History tab for PhotoFlow.
Shows a thumbnail grid of everything that's been posted, with platform, date, caption, and link.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QComboBox, QGridLayout, QSizePolicy,
    QApplication, QMessageBox,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QDesktopServices
from PyQt6.QtCore import QUrl
from core.icons import icon as _icon

_PLATFORM_COLOR = {
    'instagram': '#c13584',
    'twitter':   '#1da1f2',
    'facebook':  '#1877f2',
    'pinterest': '#e60023',
    'threads':   '#000000',
    'tiktok':    '#010101',
}


class _PostCard(QFrame):
    def __init__(self, post: dict, photo, controller, parent=None, delete_fn=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setMaximumWidth(200)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self._delete_fn = delete_fn
        self._build(post, photo, controller)

    def _build(self, post, photo, controller):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Thumbnail
        img = QLabel()
        img.setFixedSize(180, 140)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setStyleSheet('background: #1e1e1e;')
        if photo:
            fp = photo.get('filepath', '')
            if fp and os.path.exists(fp):
                pix = controller.get_cached_thumbnail(fp, 180)
                if pix and not pix.isNull():
                    img.setPixmap(pix)
                else:
                    img.setText(photo.get('filename', '?')[:16])
        layout.addWidget(img)

        # Platform badge
        platform = post.get('platform', '')
        color = _PLATFORM_COLOR.get(platform.lower(), '#555')
        badge = QLabel(platform.capitalize())
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f'background: {color}; color: white; font-size: 10px; '
            f'font-weight: bold; border-radius: 3px; padding: 2px 6px;'
        )
        layout.addWidget(badge)

        # Date
        dt = str(post.get('date_posted') or '')[:16]
        date_lbl = QLabel(dt)
        date_lbl.setStyleSheet('font-size: 9px; color: #888;')
        date_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(date_lbl)

        # Caption preview
        cap = (post.get('caption') or '')[:60]
        if cap:
            cap_lbl = QLabel(cap + ('…' if len(post.get('caption', '')) > 60 else ''))
            cap_lbl.setWordWrap(True)
            cap_lbl.setStyleSheet('font-size: 9px; color: #ccc;')
            layout.addWidget(cap_lbl)

        # Open link button
        url = post.get('post_url', '')
        if url:
            link_btn = QPushButton('View Post')
            link_btn.setIcon(_icon('link_external'))
            link_btn.setIconSize(QSize(14, 14))
            link_btn.setStyleSheet('font-size: 9px; padding: 2px;')
            link_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
            layout.addWidget(link_btn)

        # Copy caption
        if post.get('caption'):
            copy_btn = QPushButton('Copy Caption')
            copy_btn.setIcon(_icon('copy'))
            copy_btn.setIconSize(QSize(14, 14))
            copy_btn.setStyleSheet('font-size: 9px; padding: 2px;')
            copy_btn.clicked.connect(
                lambda: QApplication.clipboard().setText(post.get('caption', ''))
            )
            layout.addWidget(copy_btn)

        # Remove from history
        entry_id = post.get('id')
        if entry_id:
            del_btn = QPushButton('Remove')
            del_btn.setIcon(_icon('trash'))
            del_btn.setIconSize(QSize(14, 14))
            del_btn.setStyleSheet('font-size: 9px; padding: 2px; color: #e57373;')
            del_btn.clicked.connect(lambda: self._on_delete(entry_id, controller))
            layout.addWidget(del_btn)

    def _on_delete(self, entry_id: int, controller):
        """Remove this entry from posting_history and refresh the parent tab."""
        reply = QMessageBox.question(
            self, 'Remove Entry',
            'Remove this post from history?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            controller.db.delete_posting_history_entry(entry_id)
        except Exception as e:
            QMessageBox.warning(self, 'Error', str(e))
            return
        if self._delete_fn:
            self._delete_fn()


class HistoryTab(QWidget):
    """Posting history: thumbnail grid of sent posts."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header_row = QHBoxLayout()
        header = QLabel('<b>Posting History</b>')
        header.setStyleSheet('font-size: 15px; padding: 4px;')
        header_row.addWidget(header)
        header_row.addStretch()

        header_row.addWidget(QLabel('Platform:'))
        self.platform_filter = QComboBox()
        self.platform_filter.addItems(['All', 'Instagram', 'Twitter', 'Facebook', 'Pinterest', 'Threads', 'TikTok'])
        self.platform_filter.currentTextChanged.connect(self.refresh)
        header_row.addWidget(self.platform_filter)

        refresh_btn = QPushButton()
        refresh_btn.setIcon(_icon('refresh'))
        refresh_btn.setIconSize(QSize(18, 18))
        refresh_btn.setToolTip('Refresh posting history')
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        self.count_label = QLabel('')
        self.count_label.setStyleSheet('color: #aaa; font-size: 11px; padding: 2px 4px;')
        layout.addWidget(self.count_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.grid_container)
        layout.addWidget(self.scroll)

    def refresh(self):
        # Clear grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            posts = self.controller.db.get_posting_history()
        except Exception:
            posts = []

        platform_f = self.platform_filter.currentText().lower()
        if platform_f != 'all':
            posts = [p for p in posts if p.get('platform', '').lower() == platform_f]

        # Sort newest first
        posts = sorted(posts, key=lambda p: str(p.get('date_posted') or ''), reverse=True)

        cols = 5
        for idx, post in enumerate(posts):
            photo = None
            if post.get('photo_id'):
                try:
                    photo = self.controller.db.get_photo(post['photo_id'])
                except Exception:
                    pass
            card = _PostCard(post, photo, self.controller, self, delete_fn=self.refresh)
            self.grid_layout.addWidget(card, idx // cols, idx % cols)

        self.count_label.setText(f'{len(posts)} post{"s" if len(posts) != 1 else ""} sent')
