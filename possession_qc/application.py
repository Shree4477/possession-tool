"""Qt application bootstrap."""

import sys
from typing import Optional, Sequence

from PySide6.QtWidgets import QApplication

from possession_qc.ui.main_window import MainWindow


def run(arguments: Optional[Sequence[str]] = None) -> int:
    """Create the Qt application, show its main window, and run the event loop."""
    application = QApplication(list(arguments) if arguments is not None else sys.argv)
    application.setApplicationDisplayName("Possession QC Tool")
    application.setOrganizationName("Thelios")

    window = MainWindow()
    window.show()
    return application.exec()

