# SPDX-FileCopyrightText: 2023 EasyDiffraction contributors
# SPDX-License-Identifier: BSD-3-Clause
# © © 2023 Contributors to the EasyDiffraction project <https://github.com/easyscience/EasyDiffractionApp>

from easydiffraction.calculators.cryspy.calculator import Data as CalcData  # TODO: make non-cryspy specific
from PySide6.QtCore import QObject
from PySide6.QtCore import Slot


class Data(QObject):
    def __init__(self, parent, interface=None):
        super().__init__(parent)
        self._interface = interface
        self._data = self._interface.data()
        self._calcDict = self._data._cryspyDict
        self._calcObj = self._data._cryspyObj
        self._calcInOutDict = self._data._inOutDict

    @Slot()
    def resetAll(self):
        self._data.reset()

    def calcDictParamPathToStr(p):
        return CalcData.cryspyDictParamPathToStr(p)

    def strToCalcDictParamPath(s):
        return CalcData.strToCryspyDictParamPath(s)
