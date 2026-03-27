"""
TikTok tab for PhotoFlow.
Credential status display + redirect to unified Composer tab for posting.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFrame,
)
from PyQt6.QtCore import Qt, QSize
from core.icons import icon as _icon


class TikTokTab(QWidget):
    """TikTok credential status + link to Composer."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._build_ui()
        self._check_credentials()

    def _check_credentials(self):
        try:
            if self.controller.db.has_api_credentials('tiktok'):
                creds = self.controller.db.get_api_credentials('tiktok')
                username = creds.get('username') or creds.get('open_id', 'Unknown')
                self.status_label.setText(f'Connected as @{username}')
                self.status_label.setStyleSheet('color: #4caf50; font-weight: bold;')
            else:
                self.status_label.setText('Not connected — add credentials in Settings')
                self.status_label.setStyleSheet('color: #e53935;')
        except Exception as e:
            self.status_label.setText(f'Error: {e}')

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = QLabel('<b style="font-size:15px;">TikTok</b>')
        header.setStyleSheet('padding: 4px;')
        layout.addWidget(header)

        # Auth status card
        auth_group = QGroupBox('Connection Status')
        auth_layout = QHBoxLayout(auth_group)
        self.status_label = QLabel('Checking…')
        auth_layout.addWidget(self.status_label)
        auth_layout.addStretch()
        settings_btn = QPushButton('Manage Credentials')
        settings_btn.setIcon(_icon('settings'))
        settings_btn.setIconSize(QSize(16, 16))
        settings_btn.clicked.connect(self._open_settings)
        auth_layout.addWidget(settings_btn)
        layout.addWidget(auth_group)

        # Redirect banner
        banner = QFrame()
        banner.setFrameStyle(QFrame.Shape.StyledPanel)
        banner.setStyleSheet('background: #1a1a2e; border-radius: 6px; padding: 8px;')
        bl = QVBoxLayout(banner)

        info = QLabel(
            '<b>Posting is handled by the unified Composer tab.</b><br>'
            'Select a photo from the Gallery, then use the Composer to write your caption, '
            'add hashtags, and post directly to TikTok or schedule for later.'
        )
        info.setWordWrap(True)
        info.setStyleSheet('color: #ccc; font-size: 11px;')
        bl.addWidget(info)

        open_btn = QPushButton('Open Composer \u2192')
        open_btn.setIcon(_icon('arrow_right', 16, '#ffffff'))
        open_btn.setIconSize(QSize(16, 16))
        open_btn.setStyleSheet(
            'background: #010101; color: white; font-weight: bold; '
            'padding: 6px 18px; border-radius: 4px; border: 1px solid #69c9d0;'
        )
        open_btn.clicked.connect(self._open_composer)
        bl.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(banner)

        # Platform info
        info_group = QGroupBox('TikTok API Notes')
        il = QVBoxLayout(info_group)
        notes = QLabel(
            '• Requires TikTok for Developers account + approved app\n'
            '• Uses TikTok Content Posting API (v2)\n'
            '• Supports photo posts and video uploads\n'
            '• Set your Access Token and Open ID in Settings → TikTok'
        )
        notes.setStyleSheet('font-size: 10px; color: #aaa;')
        il.addWidget(notes)
        layout.addWidget(info_group)

        layout.addStretch()

    def _open_composer(self):
        try:
            tabs = self.controller.tabs
            for i in range(tabs.count()):
                if tabs.tabText(i).lower().startswith('compos'):
                    tabs.setCurrentIndex(i)
                    return
        except Exception:
            pass

    def _open_settings(self):
        try:
            tabs = self.controller.tabs
            for i in range(tabs.count()):
                if tabs.tabText(i).lower().startswith('setting'):
                    tabs.setCurrentIndex(i)
                    return
        except Exception:
            pass

    def refresh(self):
        self._check_credentials()
