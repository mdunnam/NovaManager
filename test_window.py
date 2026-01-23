import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel

app = QApplication(sys.argv)
window = QMainWindow()
window.setWindowTitle("Test")
window.setCentralWidget(QLabel("Test Window"))
window.show()
print("Window shown, starting event loop")
sys.exit(app.exec())
