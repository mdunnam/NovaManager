"""
Batch File Operations tab for PhotoFlow.
Rename by pattern, resize, convert, export to folder, watermark.
"""
import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QGroupBox, QFormLayout, QFileDialog,
    QProgressBar, QMessageBox, QCheckBox, QSpinBox, QScrollArea,
    QTextEdit,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from core.icons import icon as _icon


# ── Worker thread ────────────────────────────────────────────────

class _BatchWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int, int)   # done, errors
    log = pyqtSignal(str)

    def __init__(self, photos, operation, params):
        super().__init__()
        self.photos = photos
        self.operation = operation
        self.params = params
        self._running = True

    def run(self):
        done = errors = 0
        total = len(self.photos)
        for i, photo in enumerate(self.photos):
            if not self._running:
                break
            fp = photo.get('filepath', '')
            self.progress.emit(i + 1, total, Path(fp).name if fp else '?')
            try:
                if self.operation == 'rename':
                    self._rename(photo)
                elif self.operation == 'export':
                    self._export(photo)
                elif self.operation == 'zip':
                    self._zip_add(photo)
                elif self.operation == 'resize':
                    self._resize(photo)
                elif self.operation == 'watermark':
                    self._watermark(photo)
                done += 1
            except Exception as e:
                errors += 1
                self.log.emit(f'ERROR {Path(fp).name}: {e}')
        self.finished.emit(done, errors)

    def _rename(self, photo):
        fp = Path(photo.get('filepath', ''))
        if not fp.exists():
            raise FileNotFoundError(fp)
        pattern = self.params.get('pattern', '{filename}')
        dt = photo.get('exif_date_taken') or photo.get('date_created')
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt.split('.')[0])
            except Exception:
                dt = None
        replacements = {
            '{filename}':  fp.stem,
            '{date}':      dt.strftime('%Y-%m-%d') if dt else 'nodate',
            '{year}':      dt.strftime('%Y') if dt else 'XXXX',
            '{month}':     dt.strftime('%m') if dt else 'XX',
            '{scene}':     (photo.get('scene_type') or 'unknown').replace(' ', '_'),
            '{id}':        str(photo.get('id', 0)),
            '{status}':    (photo.get('status') or 'raw'),
        }
        new_stem = pattern
        for k, v in replacements.items():
            new_stem = new_stem.replace(k, v)
        # Sanitise
        for ch in r'\/:*?"<>|':
            new_stem = new_stem.replace(ch, '_')
        new_fp = fp.parent / (new_stem + fp.suffix)
        if new_fp != fp:
            fp.rename(new_fp)
            self.log.emit(f'Renamed: {fp.name} → {new_fp.name}')

    def _export(self, photo):
        fp = Path(photo.get('filepath', ''))
        if not fp.exists():
            raise FileNotFoundError(fp)
        dest_dir = Path(self.params.get('dest_dir', ''))
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / fp.name
        # Avoid overwrite
        if dest.exists():
            stem, suffix = fp.stem, fp.suffix
            dest = dest_dir / f'{stem}_copy{suffix}'
        shutil.copy2(fp, dest)
        self.log.emit(f'Exported: {fp.name} → {dest}')

    def _zip_add(self, photo):
        """Add this photo to the running zip archive stored in self.params['_zf']."""
        fp = Path(photo.get('filepath', ''))
        if not fp.exists():
            raise FileNotFoundError(fp)
        zf = self.params.get('_zf')
        if zf is not None:
            zf.write(fp, fp.name)
            self.log.emit(f'Zipped: {fp.name}')

    def _resize(self, photo):
        fp = Path(photo.get('filepath', ''))
        if not fp.exists():
            raise FileNotFoundError(fp)
        try:
            from PIL import Image
        except ImportError:
            raise RuntimeError('Pillow not installed')
        max_px = int(self.params.get('max_px', 1920))
        quality = int(self.params.get('quality', 85))
        dest_dir = self.params.get('dest_dir', '')
        overwrite = self.params.get('overwrite', False)

        img = Image.open(fp)
        w, h = img.size
        if max(w, h) > max_px:
            ratio = max_px / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

        if dest_dir:
            out = Path(dest_dir) / fp.name
            Path(dest_dir).mkdir(parents=True, exist_ok=True)
        elif overwrite:
            out = fp
        else:
            out = fp.parent / (fp.stem + '_resized' + fp.suffix)

        save_kwargs = {}
        if fp.suffix.lower() in ('.jpg', '.jpeg'):
            save_kwargs['quality'] = quality
            save_kwargs['optimize'] = True
        img.save(out, **save_kwargs)
        self.log.emit(f'Resized: {fp.name} ({w}×{h} → {img.size[0]}×{img.size[1]})')

    def _watermark(self, photo):
        fp = Path(photo.get('filepath', ''))
        if not fp.exists():
            raise FileNotFoundError(fp)
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            raise RuntimeError('Pillow not installed')
        text = self.params.get('text', '© PhotoFlow')
        opacity = int(self.params.get('opacity', 128))
        position = self.params.get('position', 'bottom-right')
        dest_dir = self.params.get('dest_dir', '')

        img = Image.open(fp).convert('RGBA')
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        try:
            font = ImageFont.truetype('arial.ttf', max(16, img.size[0] // 40))
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        margin = 20
        w, h = img.size
        positions = {
            'bottom-right': (w - tw - margin, h - th - margin),
            'bottom-left':  (margin, h - th - margin),
            'top-right':    (w - tw - margin, margin),
            'top-left':     (margin, margin),
            'center':       ((w - tw) // 2, (h - th) // 2),
        }
        x, y = positions.get(position, positions['bottom-right'])
        draw.text((x, y), text, font=font, fill=(255, 255, 255, opacity))
        out_img = Image.alpha_composite(img, overlay).convert('RGB')

        if dest_dir:
            Path(dest_dir).mkdir(parents=True, exist_ok=True)
            out = Path(dest_dir) / fp.name
        else:
            out = fp.parent / (fp.stem + '_wm' + fp.suffix)
        out_img.save(out)
        self.log.emit(f'Watermarked: {fp.name} → {out.name}')

    def stop(self):
        self._running = False


# ── UI ───────────────────────────────────────────────────────────

class BatchTab(QWidget):
    """Batch file operations: rename, resize, export, watermark."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)

        header = QLabel('<b>Batch File Operations</b>')
        header.setStyleSheet('font-size: 15px; padding: 4px;')
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)

        # ── Photo selection ──────────────────────────────────────
        sel_group = QGroupBox('Apply to')
        sel_layout = QHBoxLayout(sel_group)
        self.scope_combo = QComboBox()
        self.scope_combo.addItems([
            'All photos in library',
            'Selected photos in Library tab',
            'Current filter results',
        ])
        sel_layout.addWidget(self.scope_combo)
        layout.addWidget(sel_group)

        # ── Rename ───────────────────────────────────────────────
        rename_group = QGroupBox('Rename by Pattern')
        rename_form = QFormLayout(rename_group)
        self.rename_pattern = QLineEdit()
        self.rename_pattern.setText('{date}_{scene}_{id}')
        self.rename_pattern.setToolTip(
            'Variables: {filename} {date} {year} {month} {scene} {id} {status}'
        )
        rename_form.addRow('Pattern:', self.rename_pattern)
        rename_form.addRow('', QLabel('<span style="color:#888;font-size:10px;">Variables: {filename} {date} {year} {month} {scene} {id} {status}</span>'))
        rename_btn = QPushButton('Rename Files')
        rename_btn.setIcon(_icon('rename'))
        rename_btn.setIconSize(QSize(16, 16))
        rename_btn.clicked.connect(lambda: self._run('rename'))
        rename_form.addRow('', rename_btn)
        layout.addWidget(rename_group)

        # ── Export ───────────────────────────────────────────────
        export_group = QGroupBox('Export / Copy to Folder')
        export_form = QFormLayout(export_group)
        self.export_dir = QLineEdit()
        self.export_dir.setPlaceholderText('Destination folder...')
        browse_exp = QPushButton()
        browse_exp.setIcon(_icon('folder'))
        browse_exp.setIconSize(QSize(16, 16))
        browse_exp.setToolTip('Browse for output folder')
        browse_exp.clicked.connect(lambda: self._browse(self.export_dir))
        exp_row = QHBoxLayout()
        exp_row.addWidget(self.export_dir)
        exp_row.addWidget(browse_exp)
        export_form.addRow('Destination:', exp_row)
        export_btn = QPushButton('Export Files')
        export_btn.setIcon(_icon('export'))
        export_btn.setIconSize(QSize(16, 16))
        export_btn.clicked.connect(lambda: self._run('export'))
        export_form.addRow('', export_btn)
        layout.addWidget(export_group)

        # ── Zip export ───────────────────────────────────────────
        zip_group = QGroupBox('Export to Zip Archive')
        zip_form = QFormLayout(zip_group)
        self.zip_dest = QLineEdit()
        self.zip_dest.setPlaceholderText('Output folder for the .zip file...')
        browse_zip = QPushButton()
        browse_zip.setIcon(_icon('folder'))
        browse_zip.setIconSize(QSize(16, 16))
        browse_zip.setToolTip('Browse for output folder')
        browse_zip.clicked.connect(lambda: self._browse(self.zip_dest))
        zip_row = QHBoxLayout()
        zip_row.addWidget(self.zip_dest)
        zip_row.addWidget(browse_zip)
        zip_form.addRow('Output folder:', zip_row)
        self.zip_name = QLineEdit()
        self.zip_name.setPlaceholderText('export.zip')
        zip_form.addRow('Archive name:', self.zip_name)
        zip_btn = QPushButton('Create Zip Archive')
        zip_btn.setIcon(_icon('package'))
        zip_btn.setIconSize(QSize(16, 16))
        zip_btn.clicked.connect(lambda: self._run('zip'))
        zip_form.addRow('', zip_btn)
        layout.addWidget(zip_group)

        # ── Resize ───────────────────────────────────────────────
        resize_group = QGroupBox('Resize Images')
        resize_form = QFormLayout(resize_group)
        self.resize_max_px = QSpinBox()
        self.resize_max_px.setRange(100, 10000)
        self.resize_max_px.setValue(1920)
        self.resize_max_px.setSuffix(' px (longest side)')
        resize_form.addRow('Max size:', self.resize_max_px)
        self.resize_quality = QSpinBox()
        self.resize_quality.setRange(1, 100)
        self.resize_quality.setValue(85)
        self.resize_quality.setSuffix(' % (JPEG quality)')
        resize_form.addRow('Quality:', self.resize_quality)
        self.resize_dest = QLineEdit()
        self.resize_dest.setPlaceholderText('Output folder (blank = save alongside original with _resized suffix)')
        browse_rsz = QPushButton()
        browse_rsz.setIcon(_icon('folder'))
        browse_rsz.setIconSize(QSize(16, 16))
        browse_rsz.setToolTip('Browse for output folder')
        browse_rsz.clicked.connect(lambda: self._browse(self.resize_dest))
        rsz_row = QHBoxLayout()
        rsz_row.addWidget(self.resize_dest)
        rsz_row.addWidget(browse_rsz)
        resize_form.addRow('Output folder:', rsz_row)
        self.resize_overwrite = QCheckBox('Overwrite originals (no backup!)')
        resize_form.addRow('', self.resize_overwrite)
        resize_btn = QPushButton('Resize Files')
        resize_btn.setIcon(_icon('resize_image'))
        resize_btn.setIconSize(QSize(16, 16))
        resize_btn.clicked.connect(lambda: self._run('resize'))
        resize_form.addRow('', resize_btn)
        layout.addWidget(resize_group)

        # ── Watermark ────────────────────────────────────────────
        wm_group = QGroupBox('Apply Watermark Text')
        wm_form = QFormLayout(wm_group)
        self.wm_text = QLineEdit()
        self.wm_text.setText('© ' + datetime.now().strftime('%Y'))
        wm_form.addRow('Text:', self.wm_text)
        self.wm_position = QComboBox()
        self.wm_position.addItems(['bottom-right', 'bottom-left', 'top-right', 'top-left', 'center'])
        wm_form.addRow('Position:', self.wm_position)
        self.wm_opacity = QSpinBox()
        self.wm_opacity.setRange(10, 255)
        self.wm_opacity.setValue(128)
        wm_form.addRow('Opacity (0-255):', self.wm_opacity)
        self.wm_dest = QLineEdit()
        self.wm_dest.setPlaceholderText('Output folder (blank = save alongside with _wm suffix)')
        browse_wm = QPushButton()
        browse_wm.setIcon(_icon('folder'))
        browse_wm.setIconSize(QSize(16, 16))
        browse_wm.setToolTip('Browse for output folder')
        browse_wm.clicked.connect(lambda: self._browse(self.wm_dest))
        wm_row = QHBoxLayout()
        wm_row.addWidget(self.wm_dest)
        wm_row.addWidget(browse_wm)
        wm_form.addRow('Output folder:', wm_row)
        wm_btn = QPushButton('Apply Watermark')
        wm_btn.setIcon(_icon('watermark'))
        wm_btn.setIconSize(QSize(16, 16))
        wm_btn.clicked.connect(lambda: self._run('watermark'))
        wm_form.addRow('', wm_btn)
        layout.addWidget(wm_group)

        layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

        # ── Progress + log ───────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        outer.addWidget(self.progress_bar)

        self.cancel_btn = QPushButton('Cancel')
        self.cancel_btn.setIcon(_icon('stop'))
        self.cancel_btn.setIconSize(QSize(16, 16))
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel)
        outer.addWidget(self.cancel_btn)

        outer.addWidget(QLabel('Log:'))
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(120)
        self.log_edit.setStyleSheet('font-size: 10px; font-family: monospace;')
        outer.addWidget(self.log_edit)

    # ── Helpers ──────────────────────────────────────────────────

    def _browse(self, line_edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder')
        if folder:
            line_edit.setText(folder)

    def _get_photos(self) -> list:
        scope = self.scope_combo.currentText()
        if 'Selected' in scope:
            try:
                ids = list(self.controller.photos_tab.persistent_selected_ids)
                if ids:
                    return [self.controller.db.get_photo(i) for i in ids if self.controller.db.get_photo(i)]
            except Exception:
                pass
        if 'filter' in scope.lower():
            # Use whatever the gallery currently shows
            try:
                return list(self.controller.gallery_tab._all_photos)
            except Exception:
                pass
        return self.controller.db.get_all_photos()

    def _run(self, operation: str):
        photos = self._get_photos()
        if not photos:
            QMessageBox.information(self, 'Batch', 'No photos to process.')
            return

        params = self._build_params(operation)
        if params is None:
            return  # validation failed

        reply = QMessageBox.question(
            self, f'Batch {operation.title()}',
            f'Apply {operation} to {len(photos)} photo(s)?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.log_edit.clear()
        self.progress_bar.setMaximum(len(photos))
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.cancel_btn.setVisible(True)

        # For zip export: open the archive before the worker runs, close it after
        if operation == 'zip':
            zip_path = params.get('_zip_path', '')
            try:
                zf = zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED)
                params['_zf'] = zf
                self._zip_file = zf
                self._zip_path = zip_path
            except Exception as e:
                QMessageBox.critical(self, 'Zip Error', f'Cannot create zip: {e}')
                return
        else:
            self._zip_file = None

        self._worker = _BatchWorker(photos, operation, params)
        self._worker.progress.connect(lambda cur, tot, name: (
            self.progress_bar.setValue(cur),
            self.progress_bar.setFormat(f'{cur}/{tot}  {name}'),
        ))
        self._worker.log.connect(self.log_edit.append)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _build_params(self, operation: str) -> dict | None:
        if operation == 'rename':
            p = self.rename_pattern.text().strip()
            if not p:
                QMessageBox.warning(self, 'Rename', 'Enter a rename pattern.')
                return None
            return {'pattern': p}
        if operation == 'export':
            d = self.export_dir.text().strip()
            if not d:
                QMessageBox.warning(self, 'Export', 'Choose a destination folder.')
                return None
            return {'dest_dir': d}
        if operation == 'zip':
            d = self.zip_dest.text().strip()
            if not d:
                QMessageBox.warning(self, 'Zip Export', 'Choose an output folder.')
                return None
            archive_name = self.zip_name.text().strip() or 'export.zip'
            if not archive_name.lower().endswith('.zip'):
                archive_name += '.zip'
            zip_path = Path(d) / archive_name
            Path(d).mkdir(parents=True, exist_ok=True)
            return {'dest_dir': d, 'archive_name': archive_name, '_zip_path': str(zip_path)}
        if operation == 'resize':
            return {
                'max_px': self.resize_max_px.value(),
                'quality': self.resize_quality.value(),
                'dest_dir': self.resize_dest.text().strip(),
                'overwrite': self.resize_overwrite.isChecked(),
            }
        if operation == 'watermark':
            return {
                'text': self.wm_text.text() or '© PhotoFlow',
                'position': self.wm_position.currentText(),
                'opacity': self.wm_opacity.value(),
                'dest_dir': self.wm_dest.text().strip(),
            }
        return {}

    def _on_done(self, done: int, errors: int):
        # Close zip archive if one was open
        if getattr(self, '_zip_file', None):
            try:
                self._zip_file.close()
                self.log_edit.append(f'Zip saved: {self._zip_path}')
            except Exception as e:
                self.log_edit.append(f'Error closing zip: {e}')
            self._zip_file = None

        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        msg = f'Done: {done} file(s) processed.'
        if errors:
            msg += f' {errors} error(s) — see log.'
        self.log_edit.append(f'\n{msg}')
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(msg, 5000)

    def _cancel(self):
        if self._worker:
            self._worker.stop()
