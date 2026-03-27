"""
Settings & Connections tab for PhotoFlow.
Manages social media API credentials (stored encrypted via the DB).
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGroupBox, QFormLayout, QMessageBox, QScrollArea,
    QTabWidget, QCheckBox, QSpinBox,
)
from PyQt6.QtCore import Qt, QSize
from core.icons import icon as _icon
from PyQt6.QtGui import QFont


def _field(placeholder='', echo_mode=None):
    w = QLineEdit()
    w.setPlaceholderText(placeholder)
    if echo_mode:
        w.setEchoMode(echo_mode)
    return w


class PlatformCard(QGroupBox):
    """Collapsible credential card for a single platform."""

    def __init__(self, title: str, fields: list[tuple[str, str, bool]], parent=None):
        """
        fields: list of (key, label, is_secret)
        """
        super().__init__(title, parent)
        self._fields: dict[str, QLineEdit] = {}
        self._build(fields)

    def _build(self, fields):
        layout = QFormLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        for key, label, is_secret in fields:
            w = QLineEdit()
            w.setPlaceholderText(f'Enter {label}')
            if is_secret:
                w.setEchoMode(QLineEdit.EchoMode.Password)
            layout.addRow(label + ':', w)
            self._fields[key] = w

    def get_credentials(self) -> dict:
        return {k: w.text().strip() for k, w in self._fields.items()}

    def set_credentials(self, creds: dict):
        for k, w in self._fields.items():
            w.setText(creds.get(k, ''))

    def clear(self):
        for w in self._fields.values():
            w.clear()


class SettingsTab(QWidget):
    """Settings & Connections UI."""

    # Credential definitions per platform
    _PLATFORMS = {
        'instagram': {
            'title': 'Instagram (Graph API)',
            'fields': [
                ('access_token', 'Access Token', True),
                ('ig_user_id', 'Instagram User ID', False),
                ('app_id', 'App ID (optional)', False),
                ('app_secret', 'App Secret (optional)', True),
            ],
            'help': (
                'Requires a Facebook Developer App with instagram_basic and '
                'instagram_content_publish permissions. The account must be a '
                'Business or Creator account linked to a Facebook Page.'
            ),
        },
        'twitter': {
            'title': 'Twitter / X',
            'fields': [
                ('api_key', 'API Key', True),
                ('api_secret', 'API Secret', True),
                ('access_token', 'Access Token', True),
                ('access_token_secret', 'Access Token Secret', True),
            ],
            'help': (
                'Create a project/app at developer.twitter.com. '
                'Enable OAuth 1.0a with Read and Write permissions.'
            ),
        },
        'facebook': {
            'title': 'Facebook (Page)',
            'fields': [
                ('page_access_token', 'Page Access Token', True),
                ('page_id', 'Page ID', False),
            ],
            'help': (
                'Use the Graph API Explorer to generate a Page Access Token '
                'with pages_manage_posts permission.'
            ),
        },
        'pinterest': {
            'title': 'Pinterest',
            'fields': [
                ('access_token', 'Access Token', True),
                ('board_id', 'Default Board ID', False),
            ],
            'help': (
                'Create an app at developers.pinterest.com. '
                'Generate an OAuth2 token with boards:read and pins:write scopes.'
            ),
        },
        'threads': {
            'title': 'Threads (Meta)',
            'fields': [
                ('access_token', 'User Access Token', True),
                ('user_id', 'Threads User ID', False),
            ],
            'help': (
                'Uses the Threads API (graph.threads.net). '
                'Requires threads_basic and threads_content_publish scopes. '
                'Images must be publicly accessible URLs.'
            ),
        },
    }

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._cards: dict[str, PlatformCard] = {}
        self._build_ui()
        self._load_all_credentials()

    def _build_ui(self):
        outer = QVBoxLayout(self)

        header = QLabel('<b>Settings & Connections</b>')
        header.setStyleSheet('font-size: 15px; padding: 4px;')
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        for platform_key, cfg in self._PLATFORMS.items():
            card = PlatformCard(cfg['title'], cfg['fields'])
            self._cards[platform_key] = card
            layout.addWidget(card)

            # Help text
            help_lbl = QLabel(cfg['help'])
            help_lbl.setWordWrap(True)
            help_lbl.setStyleSheet('color: #888; font-size: 11px; padding: 0 8px 4px 8px;')
            layout.addWidget(help_lbl)

            # Buttons row
            btn_row = QHBoxLayout()
            save_btn = QPushButton(f'Save {cfg["title"].split()[0]}')
            save_btn.setIcon(_icon('save'))
            save_btn.setIconSize(QSize(16, 16))
            save_btn.clicked.connect(lambda checked, p=platform_key: self._save(p))
            test_btn = QPushButton('Test Connection')
            test_btn.setIcon(_icon('broadcast'))
            test_btn.setIconSize(QSize(16, 16))
            test_btn.clicked.connect(lambda checked, p=platform_key: self._test(p))
            clear_btn = QPushButton('Clear')
            clear_btn.setIcon(_icon('trash'))
            clear_btn.setIconSize(QSize(16, 16))
            clear_btn.clicked.connect(lambda checked, p=platform_key: self._clear(p))
            btn_row.addWidget(save_btn)
            btn_row.addWidget(test_btn)
            btn_row.addWidget(clear_btn)
            btn_row.addStretch()
            layout.addLayout(btn_row)

            # Divider
            from PyQt6.QtWidgets import QFrame
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet('color: #444;')
            layout.addWidget(line)

        # AI / Ollama section
        ai_group = QGroupBox('AI Analysis (Ollama / LLaVA)')
        ai_layout = QFormLayout(ai_group)
        self.ollama_url = QLineEdit()
        self.ollama_url.setPlaceholderText('http://localhost:11434 (default)')
        ai_layout.addRow('Ollama URL:', self.ollama_url)
        self.ollama_model = QLineEdit()
        self.ollama_model.setPlaceholderText('llava:latest (default)')
        ai_layout.addRow('Model:', self.ollama_model)
        layout.addWidget(ai_group)

        ai_btn_row = QHBoxLayout()
        save_ai_btn = QPushButton('Save AI Settings')
        save_ai_btn.setIcon(_icon('save'))
        save_ai_btn.setIconSize(QSize(16, 16))
        save_ai_btn.clicked.connect(self._save_ai)
        test_ai_btn = QPushButton('Test Ollama')
        test_ai_btn.setIcon(_icon('broadcast'))
        test_ai_btn.setIconSize(QSize(16, 16))
        test_ai_btn.clicked.connect(self._test_ollama)
        ai_btn_row.addWidget(save_ai_btn)
        ai_btn_row.addWidget(test_ai_btn)
        ai_btn_row.addStretch()
        layout.addLayout(ai_btn_row)

        # Folder Watcher section
        from PyQt6.QtWidgets import QFrame
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet('color: #444;')
        layout.addWidget(line2)

        fw_group = QGroupBox('Auto-Import Folder Watcher')
        fw_form = QFormLayout(fw_group)
        self.watch_folder_edit = QLineEdit()
        self.watch_folder_edit.setPlaceholderText('e.g. C:/Photos/Import')
        fw_form.addRow('Watch folder:', self.watch_folder_edit)

        self.watch_subfolders_cb = QCheckBox('Include subfolders')
        self.watch_subfolders_cb.setChecked(True)
        fw_form.addRow('', self.watch_subfolders_cb)

        self.watcher_interval_spin = QSpinBox()
        self.watcher_interval_spin.setRange(5, 3600)
        self.watcher_interval_spin.setValue(30)
        self.watcher_interval_spin.setSuffix(' s')
        self.watcher_interval_spin.setToolTip('How often the watcher scans for new files (seconds)')
        fw_form.addRow('Scan interval:', self.watcher_interval_spin)

        layout.addWidget(fw_group)

        fw_btn_row = QHBoxLayout()
        browse_fw_btn = QPushButton('Browse...')
        browse_fw_btn.setIcon(_icon('folder'))
        browse_fw_btn.setIconSize(QSize(16, 16))
        browse_fw_btn.clicked.connect(self._browse_watch_folder)
        self.start_watcher_btn = QPushButton('Start Watcher')
        self.start_watcher_btn.setIcon(_icon('eye'))
        self.start_watcher_btn.setIconSize(QSize(16, 16))
        self.start_watcher_btn.clicked.connect(self._toggle_watcher)
        self.watcher_status = QLabel('Watcher: not running')
        self.watcher_status.setStyleSheet('color: #aaa; font-size: 11px;')
        fw_btn_row.addWidget(browse_fw_btn)
        fw_btn_row.addWidget(self.start_watcher_btn)
        fw_btn_row.addWidget(self.watcher_status)
        fw_btn_row.addStretch()
        layout.addLayout(fw_btn_row)

        layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

    # ── Credential persistence ───────────────────────────────────

    def _load_all_credentials(self):
        for platform_key, card in self._cards.items():
            try:
                creds = self.controller.db.get_credentials(platform_key)
                if creds:
                    card.set_credentials(creds)
            except Exception:
                pass
        # AI settings
        try:
            ai = self.controller.db.get_credentials('ollama') or {}
            self.ollama_url.setText(ai.get('url', ''))
            self.ollama_model.setText(ai.get('model', ''))
        except Exception:
            pass

    def _save(self, platform_key: str):
        card = self._cards[platform_key]
        creds = card.get_credentials()
        try:
            self.controller.db.save_credentials(platform_key, creds)
            if self.controller.statusBar():
                self.controller.statusBar().showMessage(
                    f'{self._PLATFORMS[platform_key]["title"]} credentials saved.', 3000
                )
        except Exception as e:
            QMessageBox.warning(self, 'Save Error', str(e))

    def _clear(self, platform_key: str):
        reply = QMessageBox.question(
            self, 'Clear Credentials',
            f'Remove saved {self._PLATFORMS[platform_key]["title"]} credentials?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._cards[platform_key].clear()
            try:
                self.controller.db.save_credentials(platform_key, {})
            except Exception:
                pass

    # ── Connection testing ───────────────────────────────────────

    def _test(self, platform_key: str):
        creds = self._cards[platform_key].get_credentials()
        try:
            if platform_key == 'instagram':
                from core.social.instagram_api import InstagramAPI
                api = InstagramAPI(creds)
            elif platform_key == 'twitter':
                from core.social.twitter_api import TwitterAPI
                api = TwitterAPI(creds)
            elif platform_key == 'facebook':
                from core.social.facebook_api import FacebookAPI
                api = FacebookAPI(creds)
            elif platform_key == 'pinterest':
                from core.social.pinterest_api import PinterestAPI
                api = PinterestAPI(creds)
            elif platform_key == 'threads':
                from core.social.threads_api import ThreadsAPI
                api = ThreadsAPI(creds)
            else:
                QMessageBox.information(self, 'Test', f'{platform_key} test not yet implemented.')
                return

            ok, msg = api.verify_credentials()
            if ok:
                QMessageBox.information(self, 'Connection OK', msg)
            else:
                QMessageBox.warning(self, 'Connection Failed', msg)
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))

    def _save_ai(self):
        ai = {'url': self.ollama_url.text().strip(), 'model': self.ollama_model.text().strip()}
        try:
            self.controller.db.save_credentials('ollama', ai)
            if self.controller.statusBar():
                self.controller.statusBar().showMessage('AI settings saved.', 3000)
        except Exception as e:
            QMessageBox.warning(self, 'Save Error', str(e))

    def _test_ollama(self):
        try:
            import ollama
            models = ollama.list()
            names = [m['model'] for m in models.get('models', [])]
            QMessageBox.information(self, 'Ollama Connected',
                                    f'Available models:\n' + '\n'.join(names or ['(none)']))
        except ImportError:
            QMessageBox.warning(self, 'Ollama', 'ollama Python package not installed.')
        except Exception as e:
            QMessageBox.warning(self, 'Ollama Unreachable', str(e))

    # ── Folder watcher ───────────────────────────────────────────

    def _browse_watch_folder(self):
        from PyQt6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, 'Select Watch Folder')
        if folder:
            self.watch_folder_edit.setText(folder)

    def _toggle_watcher(self):
        controller = self.controller
        fw = getattr(controller, '_folder_watcher', None)

        if fw and getattr(fw, '_running', False):
            # Stop
            fw.stop()
            fw.wait(1000)
            controller._folder_watcher = None
            self.start_watcher_btn.setText('Start Watcher')
            self.watcher_status.setText('Watcher: stopped')
            return

        folder = self.watch_folder_edit.text().strip()
        if not folder:
            QMessageBox.warning(self, 'Folder Watcher', 'Enter a folder path first.')
            return

        try:
            from core.folder_watcher import FolderWatcher
            watcher = FolderWatcher(
                folder=folder,
                db=controller.db,
                interval_secs=self.watcher_interval_spin.value(),
                include_subfolders=self.watch_subfolders_cb.isChecked(),
            )
            watcher.new_photo_found.connect(self._on_new_photo)
            watcher.status_update.connect(self.watcher_status.setText)
            watcher.start()
            controller._folder_watcher = watcher
            self.start_watcher_btn.setText('Stop Watcher')
            self.watcher_status.setText(f'Watching: {folder}')
        except Exception as e:
            QMessageBox.warning(self, 'Watcher Error', str(e))

    def _on_new_photo(self, filepath: str):
        """Handle a newly discovered file from the folder watcher."""
        try:
            from pathlib import Path
            db = self.controller.db
            if db.get_photo_by_path(filepath):
                return  # Already in DB
            db.add_photo(filepath, {})
            if self.controller.statusBar():
                self.controller.statusBar().showMessage(
                    f'Auto-imported: {Path(filepath).name}', 3000
                )
            # Refresh gallery if available
            try:
                self.controller.gallery_tab.refresh()
            except Exception:
                pass
        except Exception as e:
            print(f'[Watcher] Import error: {e}')

    # ── Public helpers used by other tabs ────────────────────────

    def get_credentials(self, platform_key: str) -> dict:
        """Return saved (possibly in-memory) credentials for a platform."""
        try:
            return self.controller.db.get_credentials(platform_key) or {}
        except Exception:
            return {}
