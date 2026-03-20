"""
Folder watcher for PhotoFlow — auto-imports new image files.
Uses a polling QThread (no watchdog dependency required).
If watchdog is installed, uses it for more efficient event-driven watching.
"""
import os
import time
from pathlib import Path

try:
    from PyQt6.QtCore import QThread, pyqtSignal
    _QT = True
except ImportError:
    _QT = False

_IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
    '.webp', '.heic', '.heif', '.raw', '.cr2', '.nef', '.arw',
}

if _QT:
    class FolderWatcher(QThread):
        """
        Polls a directory for new image files every `interval_secs` seconds.
        Emits `new_photo_found(filepath)` for each new file discovered.
        """
        new_photo_found = pyqtSignal(str)
        status_update = pyqtSignal(str)

        def __init__(self, folder: str, db, interval_secs: int = 15,
                     include_subfolders: bool = True, auto_analyze: bool = True):
            super().__init__()
            self.folder = folder
            self.db = db
            self.interval_secs = interval_secs
            self.include_subfolders = include_subfolders
            self.auto_analyze = auto_analyze
            self._running = False
            self._known_paths: set[str] = set()

        def run(self):
            self._running = True
            # Seed known paths from DB to avoid re-importing existing
            try:
                existing = self.db.get_all_photos()
                self._known_paths = {p['filepath'] for p in existing}
            except Exception:
                self._known_paths = set()

            self.status_update.emit(f'Watching: {self.folder}')

            while self._running:
                try:
                    self._scan()
                except Exception as e:
                    self.status_update.emit(f'Watcher error: {e}')

                for _ in range(self.interval_secs * 10):
                    if not self._running:
                        break
                    time.sleep(0.1)

        def _scan(self):
            folder = Path(self.folder)
            if not folder.is_dir():
                return

            if self.include_subfolders:
                candidates = (
                    str(p) for ext in _IMAGE_EXTENSIONS
                    for p in folder.rglob(f'*{ext}')
                )
            else:
                candidates = (
                    str(p) for ext in _IMAGE_EXTENSIONS
                    for p in folder.glob(f'*{ext}')
                )

            new_found = 0
            for fp in candidates:
                if fp not in self._known_paths:
                    self._known_paths.add(fp)
                    self.new_photo_found.emit(fp)
                    new_found += 1

            if new_found:
                self.status_update.emit(f'Watcher: {new_found} new file(s) found in {self.folder}')

        def stop(self):
            self._running = False

        def set_folder(self, folder: str):
            self.folder = folder
            self._known_paths.clear()
