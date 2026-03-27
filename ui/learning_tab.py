"""
AI Learning tab extracted from the monolithic main window.
"""
from PyQt6.QtCore import QSize
from core.icons import icon as _icon
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QHeaderView,
    QAbstractItemView,
)


class AILearningTab(QWidget):
    """Encapsulates AI learning tracking and management."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Info label
        info = QLabel(
            "This shows the patterns AI has learned from your corrections.\n"
            "The more you correct, the smarter it gets!"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Refresh button
        refresh_btn = QPushButton("Refresh Learning Data")
        refresh_btn.setIcon(_icon('refresh'))
        refresh_btn.setIconSize(QSize(16, 16))
        refresh_btn.clicked.connect(self.refresh_learning_data)
        layout.addWidget(refresh_btn)

        # Table to show corrections
        self.learning_table = QTableWidget()
        self.learning_table.setColumnCount(5)
        self.learning_table.setHorizontalHeaderLabels([
            "Field", "AI Said", "You Corrected To", "Times", "Last Correction"
        ])
        self.learning_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.learning_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.learning_table.setSortingEnabled(True)
        layout.addWidget(self.learning_table)

        # Backup/Restore buttons
        backup_layout = QHBoxLayout()

        backup_btn = QPushButton("Backup Learning Data")
        backup_btn.setIcon(_icon('package'))
        backup_btn.setIconSize(QSize(16, 16))
        backup_btn.clicked.connect(self.manual_backup_learning_data)
        backup_layout.addWidget(backup_btn)

        restore_btn = QPushButton("Restore from Backup")
        restore_btn.setIcon(_icon('revert'))
        restore_btn.setIconSize(QSize(16, 16))
        restore_btn.clicked.connect(self.restore_learning_data)
        backup_layout.addWidget(restore_btn)

        layout.addLayout(backup_layout)

        # Clear learning button (with warning color)
        clear_btn = QPushButton("Clear All Learning Data")
        clear_btn.setIcon(_icon('trash', 16, '#ffffff'))
        clear_btn.setIconSize(QSize(16, 16))
        clear_btn.setStyleSheet("QPushButton { background-color: #d32f2f; color: white; font-weight: bold; }")
        clear_btn.clicked.connect(self.clear_learning_data)
        layout.addWidget(clear_btn)

        # Load initial data
        self.refresh_learning_data()

    def refresh_learning_data(self):
        """Query the DB for AI correction patterns and populate the table."""
        self.learning_table.setSortingEnabled(False)
        self.learning_table.setRowCount(0)
        try:
            corrections = self.controller.db.cursor.execute('''
                SELECT
                    field_name,
                    original_value,
                    corrected_value,
                    COUNT(*) AS count,
                    MAX(correction_date) AS last_date
                FROM ai_corrections
                WHERE original_value IS NOT NULL
                  AND corrected_value IS NOT NULL
                  AND original_value != corrected_value
                GROUP BY field_name, original_value, corrected_value
                ORDER BY count DESC, last_date DESC
            ''').fetchall()

            for field, orig, corrected, count, last_date in corrections:
                row = self.learning_table.rowCount()
                self.learning_table.insertRow(row)
                from PyQt6.QtWidgets import QTableWidgetItem
                self.learning_table.setItem(row, 0, QTableWidgetItem(field.replace('_', ' ').title()))
                self.learning_table.setItem(row, 1, QTableWidgetItem(orig or 'unknown'))
                self.learning_table.setItem(row, 2, QTableWidgetItem(corrected or ''))
                self.learning_table.setItem(row, 3, QTableWidgetItem(str(count)))
                self.learning_table.setItem(row, 4, QTableWidgetItem(last_date or ''))

            if self.controller.statusBar():
                self.controller.statusBar().showMessage(
                    f'Loaded {len(corrections)} learned patterns', 2000
                )
        except Exception as e:
            print(f'[AILearningTab] Error loading learning data: {e}')
        finally:
            self.learning_table.setSortingEnabled(True)

    def manual_backup_learning_data(self):
        """Delegate to MainWindow's full backup implementation."""
        self.controller.manual_backup_learning_data()

    def restore_learning_data(self):
        """Delegate to MainWindow's full restore implementation."""
        self.controller.restore_learning_data()

    def clear_learning_data(self):
        """Delegate to MainWindow's full clear implementation."""
        self.controller.clear_learning_data()
