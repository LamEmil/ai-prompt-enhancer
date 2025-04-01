# run_app.py
import sys
from PySide6 import QtWidgets
from qt_material import apply_stylesheet # Import the theme application function

# Import the main window class from your module
from main_window import MainWindow

if __name__ == "__main__":
    # Create the Qt Application
    app = QtWidgets.QApplication(sys.argv)

    # Apply the qt-material theme
    apply_stylesheet(app, theme='dark_amber.xml') # Or your preferred theme

    # Create and show the main window
    window = MainWindow()
    window.show()

    # Run the application event loop
    sys.exit(app.exec())
