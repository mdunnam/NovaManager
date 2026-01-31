"""
Minimal Nova Manager to isolate the issue
"""
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLineEdit, QLabel)

class SimpleWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nova Photo Manager - Simple Test")
        self.setGeometry(100, 100, 800, 600)
        
        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Simple controls
        layout.addWidget(QLabel("Nova Photo Manager"))
        
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Folder:"))
        self.folder_input = QLineEdit()
        folder_row.addWidget(self.folder_input)
        
        browse_btn = QPushButton("Browse")
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)
        
        analyze_btn = QPushButton("Analyze Images")
        layout.addWidget(analyze_btn)
        
        layout.addStretch()

def main():
    try:
        print("Starting app...")
        app = QApplication(sys.argv)
        
        print("Creating window...")
        window = SimpleWindow()
        
        print("Showing window...")
        window.show()
        
        print("Running event loop...")
        result = app.exec()
        print(f"App closed with code: {result}")
        sys.exit(result)
        
    except Exception as e:
        print(f"CRASH: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")

if __name__ == '__main__':
    main()
