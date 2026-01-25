"""
Instagram tab extracted from the monolithic main window.
"""
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QLineEdit,
    QTabWidget,
    QGroupBox,
    QMessageBox,
    QInputDialog,
)
from PyQt6.QtCore import Qt


class InstagramTab(QWidget):
    """Encapsulates Instagram posting UI and authentication."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.ig_selected_photo_id = None
        self._build_ui()
        self._check_credentials()
    
    def _check_credentials(self):
        """Check if credentials are saved and update UI."""
        try:
            if self.controller.db.has_api_credentials("instagram"):
                creds = self.controller.db.get_api_credentials("instagram")
                username = creds.get("username", "Unknown")
                self.ig_status_label.setText(f"Status: Connected as @{username}")
                self.ig_status_label.setStyleSheet("color: green;")
                self.ig_auth_btn.setEnabled(False)
                self.ig_logout_btn.setEnabled(True)
                self.ig_post_btn.setEnabled(True)
        except Exception as e:
            print(f"Error checking Instagram credentials: {e}")

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Header with info
        header = QLabel("<h3>📸 Instagram Direct Post</h3>")
        layout.addWidget(header)

        info = QLabel(
            "<small><b>Note:</b> This uses Instagram's unofficial API (instagrapi). "
            "Instagram actively blocks automation attempts. "
            "For more reliable integration, use Instagram's official Graph API (requires business account).</small>"
        )
        info.setObjectName("infoBanner")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Auth section
        auth_group = QGroupBox("Authentication")
        auth_group.setObjectName("igAuthGroup")
        auth_layout = QVBoxLayout()

        self.ig_status_label = QLabel("Status: Not connected")
        self.ig_status_label.setStyleSheet("color: red;")
        auth_layout.addWidget(self.ig_status_label)

        auth_button_layout = QHBoxLayout()
        self.ig_auth_btn = QPushButton("Connect Instagram Account")
        self.ig_auth_btn.clicked.connect(self.connect_instagram)
        auth_button_layout.addWidget(self.ig_auth_btn)

        self.ig_logout_btn = QPushButton("Disconnect")
        self.ig_logout_btn.setEnabled(False)
        self.ig_logout_btn.clicked.connect(self.disconnect_instagram)
        auth_button_layout.addWidget(self.ig_logout_btn)
        auth_button_layout.addStretch()
        auth_layout.addLayout(auth_button_layout)

        auth_group.setLayout(auth_layout)
        layout.addWidget(auth_group)

        # Content type tabs
        self.ig_content_tabs = QTabWidget()

        # Post tab
        post_tab = self._create_post_tab()
        self.ig_content_tabs.addTab(post_tab, "📷 Post")

        # Reel tab
        reel_tab = self._create_reel_tab()
        self.ig_content_tabs.addTab(reel_tab, "🎬 Reel")

        # Story tab
        story_tab = self._create_story_tab()
        self.ig_content_tabs.addTab(story_tab, "📖 Story")

        # Highlights tab
        highlights_tab = self._create_highlights_tab()
        self.ig_content_tabs.addTab(highlights_tab, "⭐ Highlights")

        layout.addWidget(self.ig_content_tabs)

    def _create_post_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        preview_layout = QHBoxLayout()

        self.ig_thumbnail_label = QLabel()
        self.ig_thumbnail_label.setObjectName("thumbnailPreview")
        self.ig_thumbnail_label.setFixedSize(200, 200)
        self.ig_thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ig_thumbnail_label.setText("No photo selected")
        preview_layout.addWidget(self.ig_thumbnail_label)

        info_layout = QVBoxLayout()

        self.ig_photo_label = QLabel("No photo selected")
        self.ig_photo_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.ig_photo_label)

        browse_btn = QPushButton("📂 Browse Photos")
        browse_btn.clicked.connect(self.ig_select_photo)
        info_layout.addWidget(browse_btn)

        self.ig_lightbox_btn = QPushButton("🔍 View in Lightbox")
        self.ig_lightbox_btn.setEnabled(False)
        info_layout.addWidget(self.ig_lightbox_btn)

        info_layout.addStretch()
        preview_layout.addLayout(info_layout)

        layout.addLayout(preview_layout)

        layout.addWidget(QLabel("Caption:"))
        self.ig_caption_edit = QTextEdit()
        self.ig_caption_edit.setPlaceholderText("Enter caption (max 2,200 characters)...")
        self.ig_caption_edit.setMaximumHeight(100)
        layout.addWidget(self.ig_caption_edit)

        layout.addWidget(QLabel("Hashtags:"))
        self.ig_hashtags_edit = QLineEdit()
        self.ig_hashtags_edit.setPlaceholderText("Separate with spaces")
        layout.addWidget(self.ig_hashtags_edit)

        button_layout = QHBoxLayout()
        self.ig_post_btn = QPushButton("📤 Post to Instagram")
        self.ig_post_btn.setEnabled(False)
        self.ig_post_btn.clicked.connect(self.post_to_instagram)
        button_layout.addWidget(self.ig_post_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        layout.addStretch()
        return widget

    def _create_reel_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("<b>Instagram Reels</b>"))
        layout.addWidget(QLabel("Coming soon: Video upload and Reel-specific features"))
        layout.addStretch()
        return widget

    def _create_story_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("<b>Instagram Stories</b>"))
        layout.addWidget(QLabel("Coming soon: Story-specific formatting and ephemeral content"))
        layout.addStretch()
        return widget

    def _create_highlights_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("<b>Instagram Highlights</b>"))
        layout.addWidget(QLabel("Coming soon: Archive Stories as Highlights"))
        layout.addStretch()
        return widget

    # API methods
    def connect_instagram(self):
        username, ok = QInputDialog.getText(self.controller, "Instagram Login", "Username:")
        if not ok or not username:
            return

        password, ok = QInputDialog.getText(self.controller, "Instagram Login", "Password:", QLineEdit.EchoMode.Password)
        if not ok or not password:
            return

        QMessageBox.information(
            self.controller,
            "Feature Not Implemented",
            "Instagram connection requires instagrapi library and authentication flow setup",
        )

    def disconnect_instagram(self):
        if self.controller.db.delete_api_credentials("instagram"):
            self.ig_status_label.setText("Status: Not connected")
            self.ig_status_label.setStyleSheet("color: red;")
            self.ig_auth_btn.setEnabled(True)
            self.ig_logout_btn.setEnabled(False)
            self.ig_post_btn.setEnabled(False)
            if self.controller.statusBar():
                self.controller.statusBar().showMessage("Instagram disconnected", 2000)

    def ig_select_photo(self):
        QMessageBox.information(self.controller, "Not Implemented", "Photo picker not yet implemented")

    def post_to_instagram(self):
        if not self.ig_selected_photo_id:
            QMessageBox.warning(self.controller, "No Photo", "Please select media first")
            return
        QMessageBox.information(self.controller, "Posted", "Post functionality not yet implemented")
