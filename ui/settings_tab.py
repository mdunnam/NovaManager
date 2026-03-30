"""
Settings & Connections tab for PhotoFlow.
Manages social media API credentials (stored encrypted via the DB).
"""
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGroupBox, QFormLayout, QMessageBox, QScrollArea,
    QTabWidget, QCheckBox, QSpinBox, QFileDialog,
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from core.icons import icon as _icon
from PyQt6.QtGui import QFont


def _field(placeholder='', echo_mode=None):
    w = QLineEdit()
    w.setPlaceholderText(placeholder)
    if echo_mode:
        w.setEchoMode(echo_mode)
    return w


class _InstagramOAuthWorker(QThread):
    """Run the Meta OAuth browser flow off the UI thread."""

    completed = pyqtSignal(bool, dict, str)

    def __init__(self, app_id: str, app_secret: str, redirect_uri: str):
        super().__init__()
        self.app_id = app_id
        self.app_secret = app_secret
        self.redirect_uri = redirect_uri

    def _wait_for_code(self, redirect_uri: str, state: str) -> tuple[str, str]:
        """Listen on the redirect URI and capture the OAuth code."""
        parsed = urlparse(redirect_uri)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost'):
            return '', 'Redirect URI must be a local http://127.0.0.1/... or http://localhost/... address.'

        host = parsed.hostname or '127.0.0.1'
        port = parsed.port or 80
        path = parsed.path or '/'
        result: dict[str, str] = {}

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                req = urlparse(self.path)
                if req.path != path:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'Not found')
                    return

                query = parse_qs(req.query)
                if query.get('state', [''])[0] != state:
                    result['error'] = 'OAuth state mismatch.'
                elif 'error' in query:
                    result['error'] = query.get('error_description', query['error'])[0]
                elif 'code' in query:
                    result['code'] = query['code'][0]
                else:
                    result['error'] = 'OAuth callback received without a code.'

                html = (
                    '<html><body style="font-family:Segoe UI,Arial,sans-serif;padding:24px;">'
                    '<h2>PhotoFlow</h2>'
                    '<p>Instagram authorization received. You can close this browser tab.</p>'
                    '</body></html>'
                ).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(html)))
                self.end_headers()
                self.wfile.write(html)

            def log_message(self, format, *args):
                return

        try:
            server = HTTPServer((host, port), _Handler)
        except OSError as exc:
            return '', f'Could not bind local redirect server on {host}:{port}: {exc}'

        server.timeout = 0.5
        deadline = time.time() + 300
        while time.time() < deadline and 'code' not in result and 'error' not in result:
            server.handle_request()
        server.server_close()

        if 'code' in result:
            return result['code'], ''
        if 'error' in result:
            return '', result['error']
        return '', 'Timed out waiting for the Instagram OAuth callback.'

    def run(self):
        from core.social.instagram_api import InstagramAPI

        if not self.app_id or not self.app_secret:
            self.completed.emit(False, {}, 'Instagram OAuth requires both app_id and app_secret.')
            return

        state = uuid.uuid4().hex
        auth_url = InstagramAPI.build_auth_url(self.app_id, self.redirect_uri, state)
        webbrowser.open(auth_url)

        code, err = self._wait_for_code(self.redirect_uri, state)
        if err:
            self.completed.emit(False, {}, err)
            return

        ok, short_data = InstagramAPI.exchange_code_for_short_lived_token(
            self.app_id,
            self.app_secret,
            self.redirect_uri,
            code,
        )
        if not ok:
            self.completed.emit(
                False,
                {},
                (short_data.get('error') or {}).get('message', 'Code exchange failed.'),
            )
            return

        access_token = short_data.get('access_token', '')
        expires_in = short_data.get('expires_in', 0)

        ok, long_data = InstagramAPI.exchange_for_long_lived_token(
            self.app_id,
            self.app_secret,
            access_token,
        )
        if ok and long_data.get('access_token'):
            access_token = long_data.get('access_token', access_token)
            expires_in = long_data.get('expires_in', expires_in)

        ok, account_data = InstagramAPI.discover_connected_instagram_account(access_token)
        if not ok:
            self.completed.emit(
                False,
                {},
                (account_data.get('error') or {}).get('message', 'Could not resolve Instagram account.'),
            )
            return

        creds = {
            'app_id': self.app_id,
            'app_secret': self.app_secret,
            'redirect_uri': self.redirect_uri,
            'access_token': access_token,
            'ig_user_id': account_data.get('ig_user_id', ''),
            'page_id': account_data.get('page_id', ''),
            'page_name': account_data.get('page_name', ''),
            'ig_username': account_data.get('ig_username', ''),
            'expires_in': str(expires_in or ''),
        }
        msg = f"Connected Instagram account @{creds.get('ig_username') or creds['ig_user_id']}"
        self.completed.emit(True, creds, msg)


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
            if key == 'redirect_uri':
                w.setPlaceholderText('http://127.0.0.1:8765/callback')
            elif key == 'local_media_root':
                w.setPlaceholderText('e.g. C:/inetpub/wwwroot/photoflow')
            elif key == 'public_image_base_url':
                w.setPlaceholderText('https://cdn.example.com/photoflow')
            else:
                w.setPlaceholderText(f'Enter {label}')
            if is_secret:
                w.setEchoMode(QLineEdit.EchoMode.Password)
            if key == 'local_media_root':
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.addWidget(w)
                browse_btn = QPushButton('Browse...')
                browse_btn.setIcon(_icon('folder'))
                browse_btn.setIconSize(QSize(14, 14))
                browse_btn.clicked.connect(lambda checked=False, field=w: self._browse_folder(field))
                row_layout.addWidget(browse_btn)
                layout.addRow(label + ':', row_widget)
            else:
                layout.addRow(label + ':', w)
            self._fields[key] = w

    def _browse_folder(self, field: QLineEdit):
        """Browse for a local folder and assign it to the given line edit."""
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder')
        if folder:
            field.setText(folder)

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
                ('page_id', 'Facebook Page ID', False),
                ('app_id', 'App ID', False),
                ('app_secret', 'App Secret', True),
                ('redirect_uri', 'Redirect URI', False),
                ('local_media_root', 'Local Media Root', False),
                ('public_image_base_url', 'Public Image Base URL', False),
            ],
            'help': (
                'Requires a Meta app with instagram_basic, instagram_content_publish, '
                'pages_read_engagement, and pages_show_list scopes. Use Connect in Browser '
                'to fetch the token and linked Instagram business account. For local files, '
                'configure Local Media Root + Public Image Base URL so PhotoFlow can '
                'auto-stage a copy into a publicly served folder before posting.'
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
                ('local_media_root', 'Local Media Root', False),
                ('public_image_base_url', 'Public Image Base URL', False),
            ],
            'help': (
                'Create an app at developers.pinterest.com. '
                'Generate an OAuth2 token with boards:read and pins:write scopes. '
                'For local files, configure Local Media Root + Public Image Base URL so '
                'PhotoFlow can auto-stage a copy into a publicly served folder before posting.'
            ),
        },
        'threads': {
            'title': 'Threads (Meta)',
            'fields': [
                ('access_token', 'User Access Token', True),
                ('user_id', 'Threads User ID', False),
                ('local_media_root', 'Local Media Root', False),
                ('public_image_base_url', 'Public Image Base URL', False),
            ],
            'help': (
                'Uses the Threads API (graph.threads.net). '
                'Requires threads_basic and threads_content_publish scopes. '
                'For local files, configure Local Media Root + Public Image Base URL so '
                'PhotoFlow can auto-stage a copy into a publicly served folder before posting.'
            ),
        },
    }

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._cards: dict[str, PlatformCard] = {}
        self._instagram_oauth_worker = None
        self._instagram_oauth_btn = None
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

            if platform_key == 'instagram':
                oauth_btn = QPushButton('Connect in Browser')
                oauth_btn.setIcon(_icon('link_external'))
                oauth_btn.setIconSize(QSize(16, 16))
                oauth_btn.clicked.connect(self._start_instagram_oauth)
                self._instagram_oauth_btn = oauth_btn
                btn_row.addWidget(oauth_btn)

            if platform_key in ('instagram', 'pinterest', 'threads'):
                bridge_btn = QPushButton('Test Media Bridge')
                bridge_btn.setIcon(_icon('folder'))
                bridge_btn.setIconSize(QSize(16, 16))
                bridge_btn.clicked.connect(
                    lambda checked=False, p=platform_key: self._test_media_bridge(p)
                )
                btn_row.addWidget(bridge_btn)

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
        # Watch folder settings
        try:
            folder = self.controller.db.get_app_setting('watch_folder', '')
            interval = self.controller.db.get_app_setting('watcher_interval', '30')
            self.watch_folder_edit.setText(folder)
            self.watcher_interval_spin.setValue(int(interval) if interval.isdigit() else 30)
        except Exception:
            pass

    def _save(self, platform_key: str):
        card = self._cards[platform_key]
        creds = card.get_credentials()
        if platform_key == 'instagram' and not creds.get('redirect_uri'):
            creds['redirect_uri'] = 'http://127.0.0.1:8765/callback'
            card.set_credentials(creds)
        try:
            self.controller.db.save_credentials(platform_key, creds)
            if self.controller.statusBar():
                self.controller.statusBar().showMessage(
                    f'{self._PLATFORMS[platform_key]["title"]} credentials saved.', 3000
                )
        except Exception as e:
            QMessageBox.warning(self, 'Save Error', str(e))

    def _start_instagram_oauth(self):
        """Start the browser-based Meta OAuth flow for Instagram Graph API."""
        card = self._cards['instagram']
        creds = card.get_credentials()
        app_id = creds.get('app_id', '').strip()
        app_secret = creds.get('app_secret', '').strip()
        redirect_uri = creds.get('redirect_uri', '').strip() or 'http://127.0.0.1:8765/callback'

        if not app_id or not app_secret:
            QMessageBox.warning(
                self,
                'Instagram OAuth',
                'Enter your Meta app_id and app_secret first, then retry Connect in Browser.',
            )
            return

        self._instagram_oauth_worker = _InstagramOAuthWorker(app_id, app_secret, redirect_uri)
        self._instagram_oauth_worker.completed.connect(self._finish_instagram_oauth)
        if self._instagram_oauth_btn:
            self._instagram_oauth_btn.setEnabled(False)
            self._instagram_oauth_btn.setText('Waiting for Browser…')
        if self.controller.statusBar():
            self.controller.statusBar().showMessage('Opening Meta login in your browser…', 5000)
        self._instagram_oauth_worker.start()

    def _finish_instagram_oauth(self, success: bool, new_creds: dict, message: str):
        """Handle completion of the Instagram OAuth browser flow."""
        if self._instagram_oauth_btn:
            self._instagram_oauth_btn.setEnabled(True)
            self._instagram_oauth_btn.setText('Connect in Browser')

        if not success:
            QMessageBox.warning(self, 'Instagram OAuth', message)
            return

        card = self._cards['instagram']
        merged = card.get_credentials()
        merged.update(new_creds)
        card.set_credentials(merged)
        try:
            self.controller.db.save_credentials('instagram', merged)
        except Exception:
            pass

        QMessageBox.information(self, 'Instagram Connected', message)
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(message, 5000)

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

    def _test_media_bridge(self, platform_key: str):
        """Stage a sample image into the media bridge and show the resulting public URL."""
        from core.social.media_bridge import describe_media_bridge, ensure_public_image

        creds = self._cards[platform_key].get_credentials()
        ok, msg = describe_media_bridge(creds)
        if not ok:
            QMessageBox.warning(self, 'Media Bridge', msg)
            return

        start_dir = creds.get('local_media_root', '').strip()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f'Select Image for {self._PLATFORMS[platform_key]["title"]}',
            start_dir,
            'Images (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff);;All Files (*)',
        )
        if not file_path:
            return

        result = ensure_public_image(file_path, creds, platform_key)
        if not result.success:
            QMessageBox.warning(self, 'Media Bridge', result.message)
            return

        QMessageBox.information(
            self,
            'Media Bridge Ready',
            (
                f'Staged file:\n{result.staged_path}\n\n'
                f'Public URL:\n{result.public_url}'
            ),
        )
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(
                f'{self._PLATFORMS[platform_key]["title"]} media bridge verified.', 4000
            )

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

        # Persist settings so they survive restart
        try:
            self.controller.db.save_app_setting('watch_folder', folder)
            self.controller.db.save_app_setting(
                'watcher_interval', str(self.watcher_interval_spin.value())
            )
        except Exception:
            pass

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
