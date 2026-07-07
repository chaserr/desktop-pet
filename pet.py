#!/usr/bin/env python3
import sys

from PyQt5.QtWidgets import QApplication

import config
import macos_bridge
from pet_window import PetWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    macos_bridge.hide_dock_icon()
    cfg = config.load()
    window = PetWindow(cfg)
    macos_bridge.float_over_everything(window)
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
