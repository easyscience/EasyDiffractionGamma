# SPDX-FileCopyrightText: 2023 EasyDiffraction contributors
# SPDX-License-Identifier: BSD-3-Clause
# © 2023 Contributors to the EasyDiffraction project <https://github.com/easyscience/EasyDiffraction>

from EasyApp.Logic.Logging import console
from PySide6.QtCore import Property
from PySide6.QtCore import QObject
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot

from Logic.Helpers import formatMsg


class Analysis(QObject):
    definedChanged = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self._proxy = parent
        self._defined = False

    # QML accessible properties

    @Property(bool, notify=definedChanged)
    def defined(self):
        return self._defined

    @defined.setter
    def defined(self, newValue):
        if self._defined == newValue:
            return
        self._defined = newValue
        console.debug(formatMsg('main', f'Analysis defined: {newValue}'))
        self.definedChanged.emit()

    @Slot()
    def resetAll(self):
        self.defined = False
        console.debug('All analysis removed')
