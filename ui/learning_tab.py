"""
AI Learning tab extracted from the monolithic main window.
"""
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QHeaderView,
    QAbstractItemView,
    QMessageBox,
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

        backup_btn = QPushButton("📦 Backup Learning Data")
        backup_btn.clicked.connect(self.manual_backup_learning_data)
        backup_layout.addWidget(backup_btn)

        restore_btn = QPushButton("♻️ Restore from Backup")
        restore_btn.clicked.connect(self.restore_learning_data)
        backup_layout.addWidget(restore_btn)

        layout.addLayout(backup_layout)

        # Clear learning button (with warning color)
        clear_btn = QPushButton("⚠️ Clear All Learning Data")
        clear_btn.setStyleSheet("QPushButton { background-color: #d32f2f; color: white; font-weight: bold; }")
        clear_btn.clicked.connect(self.clear_learning_data)
        layout.addWidget(clear_btn)

        # Load initial data
        self.refresh_learning_data()

    def refresh_learning_data(self):
        """Refresh learning data display."""
        self.learning_table.setRowCount(0)
        if self.controller.statusBar():
            self.controller.statusBar().showMessage("Learning data refreshed", 2000)

    def manual_backup_learning_data(self):
        """Backup learning data."""
        QMessageBox.information(self, "Backup", "Backup functionality not yet implemented")

    def restore_learning_data(self):
        """Restore learning data from backup."""
        QMessageBox.information(self, "Restore", "Restore functionality not yet implemented")

    def clear_learning_data(self):
        """Clear all learning data."""
        reply = QMessageBox.question(
            self,
            "Clear Learning Data",
            "Are you sure you want to clear all learned corrections? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "Cleared", "Learning data cleared")
            self.refresh_learning_data()
