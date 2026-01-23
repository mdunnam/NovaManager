"""
Minimal test of PyQt6
"""
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget

def main():
    try:
        print("Creating app...")
        app = QApplication(sys.argv)
        
        print("Creating window...")
        window = QMainWindow()
        window.setWindowTitle("Test Window")
        window.setGeometry(100, 100, 400, 300)
        
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel("If you see this, PyQt6 is working!"))
        window.setCentralWidget(central)
        
        print("Showing window...")
        window.show()
        
        print("Starting event loop...")
        sys.exit(app.exec())
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter...")

if __name__ == '__main__':
    main()
