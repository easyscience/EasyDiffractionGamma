# SPDX-FileCopyrightText: 2023 EasyDiffraction contributors
# SPDX-License-Identifier: BSD-3-Clause
# © 2023 Contributors to the EasyDiffraction project <https://github.com/easyscience/EasyDiffraction>

import numpy as np
from EasyApp.Logic.Logging import console
from PySide6.QtCore import Property
from PySide6.QtCore import QObject
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot

from Logic.Helpers import Converter
from Logic.Helpers import formatMsg

_EMPTY_DATA = [
    {
        "error": 0,
        "fit": True,
        "group": "",
        "max": 1,
        "min": -1,
        "name": "",
        "parentIndex": 0,
        "parentName": "",
        "unit": "",
        "value": 0,
        "enabeld": True
    }
]


class Fittables(QObject):
    dataChanged = Signal()
    dataJsonChanged = Signal()
    modelChangedSilently = Signal()
    experimentChangedSilently = Signal()
    nameFilterCriteriaChanged = Signal()
    variabilityFilterCriteriaChanged = Signal()
    paramsCountChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proxy = parent
        self._data = _EMPTY_DATA
        self._dataJson = ''
        self._nameFilterCriteria = ''
        self._variabilityFilterCriteria = ''
        self._freeParamsCount = 0
        self._fixedParamsCount = 0
        self._modelParamsCount = 0
        self._experimentParamsCount = 0

    @Slot()
    def resetAll(self):
        self._data = _EMPTY_DATA
        self._dataJson = ''
        self._nameFilterCriteria = ''
        self._variabilityFilterCriteria = ''
        self._freeParamsCount = 0
        self._fixedParamsCount = 0
        self._modelParamsCount = 0
        self._experimentParamsCount = 0
        #self.dataChanged.emit()
        console.debug("All fittables removed")

    @Property('QVariant', notify=dataChanged)
    def data(self):
        #console.error('FITTABLES DATA GETTER')
        return self._data

    @Property(str, notify=dataJsonChanged)
    def dataJson(self):
        return self._dataJson

    @Property(str, notify=nameFilterCriteriaChanged)
    def nameFilterCriteria(self):
        return self._nameFilterCriteria

    @nameFilterCriteria.setter
    def nameFilterCriteria(self, newValue):
        if self._nameFilterCriteria == newValue:
            return
        self._nameFilterCriteria = newValue
        console.debug(f"Fittables table filter criteria changed to {newValue}")
        self.nameFilterCriteriaChanged.emit()

    @Property(str, notify=variabilityFilterCriteriaChanged)
    def variabilityFilterCriteria(self):
        return self._variabilityFilterCriteria

    @variabilityFilterCriteria.setter
    def variabilityFilterCriteria(self, newValue):
        if self._variabilityFilterCriteria == newValue:
            return
        self._variabilityFilterCriteria = newValue
        console.debug(f"Fittables table variability filter criteria changed to {newValue}")
        self.variabilityFilterCriteriaChanged.emit()

    @Property(float, notify=paramsCountChanged)
    def freeParamsCount(self):
        return self._freeParamsCount

    @Property(float, notify=paramsCountChanged)
    def fixedParamsCount(self):
        return self._fixedParamsCount

    @Property(float, notify=paramsCountChanged)
    def modelParamsCount(self):
        return self._modelParamsCount

    @Property(float, notify=paramsCountChanged)
    def experimentParamsCount(self):
        return self._experimentParamsCount

    @Slot(str, int, str, int, str, str, float)
    def edit(self, blockType, blockIdx, category, rowIndex, name, field, value):
        if rowIndex == -1:
            console.debug(formatMsg('main',
                        'Changing fittable', f'{blockType}[{blockIdx}].{category}.{name}.{field} to {value}'))
            if blockType == 'experiment':
                self._proxy.experiment.setMainParam(blockIdx, category, name, field, value)
                # Update the job object
                self._proxy.experiment.blocksToJob(blockIdx, category, name, field, value)
            elif blockType == 'model':
                self._proxy.model.setMainParam(blockIdx, category, name, field, value)
                # Update the job object
                self._proxy.model.blocksToPhase(blockIdx, category, name, field, value)
        else:
            console.debug(formatMsg('main', 'Changing fittable',
                        f'{blockType}[{blockIdx}].{category}[{rowIndex}].{name}.{field} to {value}'))
            if blockType == 'experiment':
                self._proxy.experiment.setLoopParam(blockIdx, category, name, rowIndex, field, value)
                self._proxy.experiment.blocksToLoopJob(blockIdx, category, name, rowIndex, field, value)
            elif blockType == 'model':
                self._proxy.model.setLoopParam(blockIdx, category, name, rowIndex, field, value)
                self._proxy.model.blocksToLoopPhase(blockIdx, category, name, rowIndex, field, value)

    @Slot(str, int, str, int, str, str, float)
    def editSilently(self, blockType, blockIdx, category, rowIndex, name, field, value):  # NEED FIX: Move to connections
        changedIntern = False
        changedCryspy = False
        if rowIndex == -1:
            console.debug(formatMsg('main', 'Changing fittable',
                        f'{blockType}[{blockIdx}].{category}.{name}.{field} to {value}'))
            if blockType == 'experiment':
                # update exp model and job object
                # NEED FIX. Temp solution to reset su
                self._proxy.experiment.editDataBlockMainParam(blockIdx, category, name, 'error', 0)
                changedIntern = self._proxy.experiment.editDataBlockMainParam(blockIdx, category, name, field, value)
                # update cryspy model
                changedCryspy = self._proxy.experiment.editCalcDictByMainParam(blockIdx, category, name, field, value)
            elif blockType == 'model':
                # NEED FIX. Temp solution to reset su
                self._proxy.model.editDataBlockMainParam(blockIdx, category, name, 'error', 0)
                changedIntern = self._proxy.model.editDataBlockMainParam(blockIdx, category, name, field, value)
                self._proxy.model.blocksToPhase(blockIdx, category, name, field, value)
                # update cryspy model
                changedCryspy = self._proxy.model.editCalculatorDictByMainParam(blockIdx, category, name, field, value)
        else:
            console.debug(formatMsg('main', 'Changing fittable',
                        f'{blockType}[{blockIdx}].{category}[{rowIndex}].{name}.{field} to {value}'))
            if blockType == 'experiment':
                # NEED FIX. Temp solution to reset su
                self._proxy.experiment.editDataBlockLoopParam(blockIdx, category, name, rowIndex, 'error', 0)
                changedIntern = self._proxy.experiment.editDataBlockLoopParam(
                    blockIdx, category, name, rowIndex, field, value)
                changedCryspy = self._proxy.experiment.editCalcDictByLoopParam(
                    blockIdx, category, name, rowIndex, field, value)
            elif blockType == 'model':
                # NEED FIX. Temp solution to reset su
                self._proxy.model.editDataBlockLoopParam(blockIdx, category, name, rowIndex, 'error', 0)
                changedIntern = self._proxy.model.editDataBlockLoopParam(blockIdx, category, name, rowIndex, field, value)
                self._proxy.model.blocksToLoopPhase(blockIdx, category, name, rowIndex, field, value)
                changedCryspy = self._proxy.model.editCalculatorDictByLoopParam(
                    blockIdx, category, name, rowIndex, field, value)
        if changedIntern and changedCryspy:
            if blockType == 'model':
                self.modelChangedSilently.emit()
            elif blockType == 'experiment':
                self.experimentChangedSilently.emit()

    def set(self):
        _data = []
        _freeParamsCount = 0
        _fixedParamsCount = 0
        _modelParamsCount = 0
        _experimentParamsCount = 0

        # Model params
        for i in range(len(self._proxy.model.dataBlocks)):
            block = self._proxy.model.dataBlocks[i]

            # Model singles
            for categoryContent in block['params'].values():
                for paramName, paramContent in categoryContent.items():
                    if 'fittable' in paramContent and paramContent['fittable']:
                        fittable = {}
                        fittable['blockType'] = 'model'
                        fittable['blockIdx'] = i
                        fittable['blockName'] = block['name'] #['value']
                        # fittable['blockIcon'] = block['name']['icon']
                        fittable['blockIcon'] = "layer-group"
                        fittable['category'] = paramContent['category']
                        fittable['prettyCategory'] = paramContent['prettyCategory'] \
                            if 'prettyCategory' in paramContent else ''
                        fittable['name'] = paramContent['name']
                        fittable['prettyName'] = paramContent['prettyName'] if 'prettyName' in paramContent else ''
                        fittable['shortPrettyName'] = paramContent['shortPrettyName'] \
                            if 'shortPrettyName' in paramContent else ''
                        fittable['icon'] = paramContent['icon'] if 'icon' in paramContent else "map-marker-alt"
                        fittable['categoryIcon'] = paramContent['categoryIcon'] \
                            if 'categoryIcon' in paramContent else "layer-group"
                        fittable['enabled'] = paramContent['enabled']
                        fittable['value'] = paramContent['value']
                        fittable['error'] = paramContent['error']
                        fittable['min'] = paramContent['min'] if 'min' in paramContent else -np.inf
                        fittable['max'] = paramContent['max'] if 'max' in paramContent else np.inf
                        fittable['unit'] = paramContent['unit']
                        fittable['fit'] = paramContent['fit']

                        absDelta = paramContent['absDelta'] if 'absDelta' in paramContent else None
                        pctDelta = paramContent['pctDelta'] if 'pctDelta' in paramContent else None
                        if absDelta is not None:
                            fittable['from'] = max(fittable['value'] - absDelta, fittable['min'])
                            fittable['to'] = min(fittable['value'] + absDelta, fittable['max'])
                        elif pctDelta is not None:
                            fittable['from'] = max(fittable['value'] * (100 - pctDelta) / 100, fittable['min'])
                            fittable['to'] = min(fittable['value'] * (100 + pctDelta) / 100, fittable['max'])

                        fullName = \
                            f"{fittable['blockType']}.{fittable['blockName']}.{fittable['category']}.{fittable['name']}"
                        if fittable['enabled']:
                            _modelParamsCount += 1
                            if fittable['fit']:
                                _freeParamsCount += 1
                            else:
                                _fixedParamsCount += 1
                            if self.nameFilterCriteria in fullName:
                                if self.variabilityFilterCriteria == 'free' and fittable['fit']:
                                    _data.append(fittable)
                                elif self.variabilityFilterCriteria == 'fixed' and not fittable['fit']:
                                    _data.append(fittable)
                                elif self.variabilityFilterCriteria == 'all':
                                    _data.append(fittable)
                                elif self.variabilityFilterCriteria == '':
                                    _data.append(fittable)

            # Model tables
            for category, loopRows in block['loops'].items():
                for rowIndex, param in enumerate(loopRows):
                    for paramName, paramContent in param.items():
                        if 'fittable' in paramContent and paramContent['fittable']:
                            fittable = {}
                            fittable['blockType'] = 'model'
                            fittable['blockIdx'] = i
                            fittable['blockName'] = block['name']# ['value']
                            # fittable['blockIcon'] = block['name']['icon']
                            fittable['blockIcon'] = "layer-group"
                            fittable['category'] = category
                            fittable['prettyCategory'] = paramContent['prettyCategory'] \
                                if 'prettyCategory' in paramContent else ''
                            fittable['rowName'] = paramContent['rowName'] if 'rowName' in paramContent else ''
                            fittable['rowIndex'] = rowIndex
                            fittable['name'] = paramContent['name']
                            fittable['prettyName'] = paramContent['prettyName'] if 'prettyName' in paramContent else ''
                            fittable['shortPrettyName'] = paramContent['shortPrettyName'] \
                                if 'shortPrettyName' in paramContent else ''
                            fittable['icon'] = paramContent['icon'] if 'icon' in paramContent else "map-marker-alt"
                            fittable['categoryIcon'] = paramContent['categoryIcon'] \
                                if 'categoryIcon' in paramContent else "layer-group"
                            fittable['enabled'] = paramContent['enabled']
                            fittable['value'] = paramContent['value']
                            fittable['error'] = paramContent['error']
                            fittable['min'] = paramContent['min'] if 'min' in paramContent else -np.inf
                            fittable['max'] = paramContent['max'] if 'max' in paramContent else np.inf
                            fittable['unit'] = paramContent['unit'] if 'unit' in paramContent else ''
                            fittable['fit'] = paramContent['fit']

                            absDelta = paramContent['absDelta'] if 'absDelta' in paramContent else None
                            pctDelta = paramContent['pctDelta'] if 'pctDelta' in paramContent else None
                            if absDelta is not None:
                                fittable['from'] = max(fittable['value'] - absDelta, fittable['min'])
                                fittable['to'] = min(fittable['value'] + absDelta, fittable['max'])
                            elif pctDelta is not None:
                                fittable['from'] = max(fittable['value'] * (100 - pctDelta) / 100, fittable['min'])
                                fittable['to'] = min(fittable['value'] * (100 + pctDelta) / 100, fittable['max'])

                                fullName = (
                                f"{fittable['blockType']}.{fittable['blockName']}.{fittable['category']}"
                                f".{fittable['rowName']}.{fittable['name']}"
                            )
                            if fittable['enabled']:
                                _modelParamsCount += 1
                                if fittable['fit']:
                                    _freeParamsCount += 1
                                else:
                                    _fixedParamsCount += 1
                                if self.nameFilterCriteria in fullName:
                                    if self.variabilityFilterCriteria == 'free' and fittable['fit']:
                                        _data.append(fittable)
                                    elif self.variabilityFilterCriteria == 'fixed' and not fittable['fit']:
                                        _data.append(fittable)
                                    elif self.variabilityFilterCriteria == 'all':
                                        _data.append(fittable)
                                    elif self.variabilityFilterCriteria == '':
                                        _data.append(fittable)

        # Experiment params
        for i in range(len(self._proxy.experiment.dataBlocksNoMeas)):
            block = self._proxy.experiment.dataBlocksNoMeas[i]

            # Experiment singles
            for categoryContent in block['params'].values():
                for paramName, paramContent in categoryContent.items():
                    if paramContent['fittable']:
                        fittable = {}
                        fittable['blockType'] = 'experiment'
                        fittable['blockIdx'] = i
                        fittable['blockName'] = block['name']['value']
                        fittable['blockIcon'] = block['name']['icon']
                        fittable['category'] = paramContent['category']
                        fittable['prettyCategory'] = paramContent['prettyCategory']
                        fittable['name'] = paramContent['name']
                        fittable['prettyName'] = paramContent['prettyName']
                        fittable['shortPrettyName'] = paramContent['shortPrettyName']
                        fittable['icon'] = paramContent['icon']
                        fittable['categoryIcon'] = paramContent['categoryIcon']
                        fittable['enabled'] = paramContent['enabled']
                        fittable['value'] = paramContent['value']
                        fittable['error'] = paramContent['error']
                        fittable['min'] = paramContent['min']
                        fittable['max'] = paramContent['max']
                        fittable['unit'] = paramContent['unit']
                        fittable['fit'] = paramContent['fit']

                        absDelta = paramContent['absDelta']
                        pctDelta = paramContent['pctDelta']
                        if absDelta is not None:
                            fittable['from'] = max(fittable['value'] - absDelta, fittable['min'])
                            fittable['to'] = min(fittable['value'] + absDelta, fittable['max'])
                        elif pctDelta is not None:
                            fittable['from'] = max(fittable['value'] * (100 - pctDelta) / 100, fittable['min'])
                            fittable['to'] = min(fittable['value'] * (100 + pctDelta) / 100, fittable['max'])

                        fullName = \
                            f"{fittable['blockType']}.{fittable['blockName']}.{fittable['category']}.{fittable['name']}"
                        if fittable['enabled']:
                            _experimentParamsCount += 1
                            if fittable['fit']:
                                _freeParamsCount += 1
                            else:
                                _fixedParamsCount += 1
                            if self.nameFilterCriteria in fullName:
                                if self.variabilityFilterCriteria == 'free' and fittable['fit']:
                                    _data.append(fittable)
                                elif self.variabilityFilterCriteria == 'fixed' and not fittable['fit']:
                                    _data.append(fittable)
                                elif self.variabilityFilterCriteria == 'all':
                                    _data.append(fittable)
                                elif self.variabilityFilterCriteria == '':
                                    _data.append(fittable)

            # Experiment tables
            for category, loopRows in block['loops'].items():
                for rowIndex, param in enumerate(loopRows):
                    for paramName, paramContent in param.items():
                        if paramContent['fittable']:
                            fittable = {}
                            fittable['blockType'] = 'experiment'
                            fittable['blockIdx'] = i
                            fittable['blockName'] = block['name']['value']
                            fittable['blockIcon'] = block['name']['icon']
                            fittable['category'] = category
                            fittable['prettyCategory'] = paramContent['prettyCategory']
                            fittable['rowName'] = paramContent['rowName']
                            fittable['rowIndex'] = rowIndex
                            fittable['name'] = paramContent['name']
                            fittable['prettyName'] = paramContent['prettyName']
                            fittable['shortPrettyName'] = paramContent['shortPrettyName']
                            fittable['icon'] = paramContent['icon']
                            fittable['categoryIcon'] = paramContent['categoryIcon']
                            fittable['enabled'] = paramContent['enabled']
                            fittable['value'] = paramContent['value']
                            fittable['error'] = paramContent['error']
                            fittable['min'] = paramContent['min']
                            fittable['max'] = paramContent['max']
                            fittable['unit'] = paramContent['unit']
                            fittable['fit'] = paramContent['fit']

                            absDelta = paramContent['absDelta']
                            pctDelta = paramContent['pctDelta']
                            if absDelta is not None:
                                fittable['from'] = max(fittable['value'] - absDelta, fittable['min'])
                                fittable['to'] = min(fittable['value'] + absDelta, fittable['max'])
                            elif pctDelta is not None:
                                fittable['from'] = max(fittable['value'] * (100 - pctDelta) / 100, fittable['min'])
                                fittable['to'] = min(fittable['value'] * (100 + pctDelta) / 100, fittable['max'])

                            fullName = (
                                f"{fittable['blockType']}.{fittable['blockName']}.{fittable['category']}"
                                f".{fittable['rowName']}.{fittable['name']}"
                            )
                            if fittable['enabled']:
                                _experimentParamsCount += 1
                                if fittable['fit']:
                                    _freeParamsCount += 1
                                else:
                                    _fixedParamsCount += 1
                                if self.nameFilterCriteria in fullName:
                                    if self.variabilityFilterCriteria == 'free' and fittable['fit']:
                                        _data.append(fittable)
                                    elif self.variabilityFilterCriteria == 'fixed' and not fittable['fit']:
                                        _data.append(fittable)
                                    elif self.variabilityFilterCriteria == 'all':
                                        _data.append(fittable)
                                    elif self.variabilityFilterCriteria == '':
                                        _data.append(fittable)

        if True:  # len(_data):
            self._data = _data
            console.debug(formatMsg('sub', 'Fittables changed'))
            self.dataChanged.emit()
            self._freeParamsCount = _freeParamsCount
            self._fixedParamsCount = _fixedParamsCount
            self._modelParamsCount = _modelParamsCount
            self._experimentParamsCount = _experimentParamsCount
            self.paramsCountChanged.emit()

    def setDataJson(self):
        self._dataJson = Converter.dictToJson(self._data)
        console.debug(" - Fittables converted to JSON string")
        self.dataJsonChanged.emit()
