"""
PhotoFlow - Entry Point
A desktop application for organizing photos and publishing to social media.
A BlinQ, LLC product.
"""
# This is the new entry point. Delegates to nova_manager until full refactor is complete.
from nova_manager import main

if __name__ == '__main__':
    main()
