"""
TikTok tab extracted from the monolithic main window.
"""
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QLineEdit,
    QGroupBox,
    QMessageBox,
    QInputDialog,
)


class TikTokTab(QWidget):
    """Encapsulates TikTok posting UI and authentication."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.tt_media_selected_id = None
        self._build_ui()
        self._check_credentials()
    
    def _check_credentials(self):
        """Check if credentials are saved and update UI."""
        try:
            if self.controller.db.has_api_credentials("tiktok"):
                creds = self.controller.db.get_api_credentials("tiktok")
                username = creds.get("username", "Unknown")
                self.tt_status_label.setText(f"Status: Connected as @{username}")
                self.tt_status_label.setStyleSheet("color: green;")
                self.tt_auth_btn.setEnabled(False)
                self.tt_logout_btn.setEnabled(True)
                self.tt_post_btn.setEnabled(True)
        except Exception as e:
            print(f"Error checking TikTok credentials: {e}")

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("<h3>🎵 TikTok Direct Post</h3>")
        layout.addWidget(header)

        # Auth section
        auth_group = QGroupBox("Authentication")
        auth_group.setObjectName("ttAuthGroup")
        auth_layout = QVBoxLayout()

        self.tt_status_label = QLabel("Status: Not connected")
        self.tt_status_label.setStyleSheet("color: red;")
        auth_layout.addWidget(self.tt_status_label)

        auth_button_layout = QHBoxLayout()
        self.tt_auth_btn = QPushButton("Connect TikTok Account")
        self.tt_auth_btn.clicked.connect(self.connect_tiktok)
        auth_button_layout.addWidget(self.tt_auth_btn)

        self.tt_logout_btn = QPushButton("Disconnect")
        self.tt_logout_btn.setEnabled(False)
        self.tt_logout_btn.clicked.connect(self.disconnect_tiktok)
        auth_button_layout.addWidget(self.tt_logout_btn)
        auth_button_layout.addStretch()
        auth_layout.addLayout(auth_button_layout)

        auth_group.setLayout(auth_layout)
        layout.addWidget(auth_group)

        # Post section
        post_group = QGroupBox("Create Post")
        post_layout = QVBoxLayout()

        post_layout.addWidget(QLabel("Select Video or Photo:"))
        media_layout = QHBoxLayout()
        self.tt_media_label = QLabel("No media selected")
        media_layout.addWidget(self.tt_media_label)
        self.tt_browse_media_btn = QPushButton("Browse")
        self.tt_browse_media_btn.clicked.connect(self.tt_select_media)
        media_layout.addWidget(self.tt_browse_media_btn)
        post_layout.addLayout(media_layout)

        post_layout.addWidget(QLabel("Caption:"))
        self.tt_caption_edit = QTextEdit()
        self.tt_caption_edit.setPlaceholderText("Enter caption (max 2,200 characters)...")
        self.tt_caption_edit.setMaximumHeight(100)
        post_layout.addWidget(self.tt_caption_edit)

        post_layout.addWidget(QLabel("Hashtags:"))
        self.tt_hashtags_edit = QLineEdit()
        self.tt_hashtags_edit.setPlaceholderText("Separate with spaces")
        post_layout.addWidget(self.tt_hashtags_edit)

        button_layout = QHBoxLayout()
        self.tt_post_btn = QPushButton("📤 Post to TikTok")
        self.tt_post_btn.setEnabled(False)
        self.tt_post_btn.clicked.connect(self.post_to_tiktok)
        button_layout.addWidget(self.tt_post_btn)
        button_layout.addStretch()
        post_layout.addLayout(button_layout)

        post_group.setLayout(post_layout)
        layout.addWidget(post_group)

        layout.addStretch()

    # API methods
    def connect_tiktok(self):
        username, ok = QInputDialog.getText(self.controller, "TikTok Login", "Username:")
        if not ok or not username:
            return

        password, ok = QInputDialog.getText(self.controller, "TikTok Login", "Password:", QLineEdit.EchoMode.Password)
        if not ok or not password:
            return

        QMessageBox.information(
            self.controller,
            "Feature Not Implemented",
            "TikTok connection requires authentication flow setup",
        )

    def disconnect_tiktok(self):
        if self.controller.db.delete_api_credentials("tiktok"):
            self.tt_status_label.setText("Status: Not connected")
            self.tt_status_label.setStyleSheet("color: red;")
            self.tt_auth_btn.setEnabled(True)
            self.tt_logout_btn.setEnabled(False)
            self.tt_post_btn.setEnabled(False)
            if self.controller.statusBar():
                self.controller.statusBar().showMessage("TikTok disconnected", 2000)

    def tt_select_media(self):
        QMessageBox.information(self.controller, "Not Implemented", "Media picker not yet implemented")

    def post_to_tiktok(self):
        if not self.tt_media_selected_id:
            QMessageBox.warning(self.controller, "No Media", "Please select media first")
            return
        QMessageBox.information(self.controller, "Posted", "Post functionality not yet implemented")
