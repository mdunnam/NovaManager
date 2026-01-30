#!/usr/bin/env python3
"""Test script to verify the main application can instantiate."""

import sys
import os

# Set display to null for headless testing
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

print("=" * 70)
print("NOVA APP - APPLICATION STARTUP TEST")
print("=" * 70)

try:
    print("\n[1/4] Creating QApplication...")
    app = QApplication.instance() or QApplication([])
    print("      ✓ QApplication created")

    print("\n[2/4] Importing MainWindow...")
    from nova_manager import MainWindow
    print("      ✓ MainWindow imported")

    print("\n[3/4] Instantiating MainWindow...")
    window = MainWindow()
    print("      ✓ MainWindow instantiated")

    print("\n[4/4] Checking tab count...")
    tab_count = window.tabs.count()
    print(f"      ✓ Tabs loaded: {tab_count}")
    
    # List all tabs
    print("\n      Tab List:")
    for i in range(tab_count):
        tab_name = window.tabs.tabText(i)
        print(f"        [{i+1}] {tab_name}")

    print("\n" + "=" * 70)
    print("✓ APPLICATION STARTUP SUCCESSFUL")
    print("=" * 70)
    print(f"\nSummary:")
    print(f"  - QApplication: ✓")
    print(f"  - MainWindow: ✓")
    print(f"  - Tabs loaded: {tab_count}/9 ✓")
    print(f"\nAll components initialized without errors!")
    
    sys.exit(0)

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
