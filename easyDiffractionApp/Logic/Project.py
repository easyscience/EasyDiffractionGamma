# SPDX-FileCopyrightText: 2023 EasyDiffraction contributors
# SPDX-License-Identifier: BSD-3-Clause
# © 2023 Contributors to the EasyDiffraction project <https://github.com/easyscience/EasyDiffractionApp>

import os
import time
from pathlib import Path
from gemmi import cif
from PySide6.QtCore import QObject, Signal, Slot, Property, QUrl
from PySide6.QtCore import QFile, QTextStream, QIODevice

from easydiffraction.calculators.cryspy.parser import Parameter
from easydiffraction.io.cif import dataBlockToCif
# from easydiffraction.io.cif import cifV2ToV1
from EasyApp.Logic.Logging import console
from Logic.Helpers import formatMsg


_EMPTY_DATA = {
    'name': '',
    'params': {},
    'loops': {}
}

_EMPTY_DESCRIPTION = dict(Parameter(
                        '.',
                        category = '_project',
                        name = 'description',
                        prettyName = 'Description',
                        url = 'https://easydiffraction.org'
                    ))
_EXAMPLES = [
    {
        'name': 'La0.5Ba0.5CoO3 (HRPT)',
        'description': 'neutrons, powder, constant wavelength, HRPT@PSI',
        'path': ':/Examples/La0.5Ba0.5CoO3_HRPT@PSI/project.cif'

     },
     {
         'name': 'La0.5Ba0.5CoO3-Raw (HRPT)',
         'description': 'neutrons, powder, constant wavelength, HRPT@PSI',
         'path': ':/Examples/La0.5Ba0.5CoO3-Raw_HRPT@PSI/project.cif'

      },
      {
          'name': 'La0.5Ba0.5CoO3-Mult-Phases (HRPT)',
          'description': 'neutrons, powder, constant wavelength, HRPT@PSI, 2 phases',
          'path': ':/Examples/La0.5Ba0.5CoO3-Mult-Phases_HRPT@PSI/project.cif'
      },
    {
        'name': 'Co2SiO4 (D20)',
        'description': 'neutrons, powder, constant wavelength, D20@ILL',
        'path': ':/Examples/Co2SiO4_D20@ILL/project.cif'

     },
    {
        'name': 'Dy3Al5O12 (G41)',
        'description': 'neutrons, powder, constant wavelength, G41@LLB',
        'path': ':/Examples/Dy3Al5O12_G41@LLB/project.cif'

     },
     {
        'name': 'PbSO4 (D1A)',
        'description': 'neutrons, powder, constant wavelength, D1A@ILL',
        'path': ':/Examples/PbSO4_D1A@ILL/project.cif'

     },
     {
        'name': 'LaMnO3 (3T2)',
        'description': 'neutrons, powder, constant wavelength, 3T2@LLB',
        'path': ':/Examples/LaMnO3_3T2@LLB/project.cif'
     },

     {
        'name': 'Si (SEPD)',
        'description': 'neutrons, powder, time-of-flight, SEPD@Argonne',
        'path': ':/Examples/Si_SEPD@Argonne/project.cif'
     },
     #{
     #   'name': 'CeCuAl3 (Polaris)',
     #   'description': 'neutrons, powder, time-of-flight, Polaris@ISIS',
     #   'path': ':/Examples/CeCuAl3_Polaris@ISIS/project.cif'
     #},
     {
        'name': 'Na2Ca3Al2F14 (Osiris)',
        'description': 'neutrons, powder, time-of-flight, Osiris@ISIS',
        'path': ':/Examples/Na2Ca3Al2F14_Osiris@ISIS/project.cif'
     },
     {
        'name': 'Na2Ca3Al2F14 (WISH)',
        'description': 'neutrons, powder, time-of-flight, WISH@ISIS',
        'path': ':/Examples/Na2Ca3Al2F14_WISH@ISIS/project.cif'
     },
     {
        'name': 'CeO2 (iMATERIA)',
        'description': 'neutrons, powder, time-of-flight, iMATERIA@J-PARC',
        'path': ':/Examples/CeO2_iMATERIA@J-PARC/project.cif'
     },
    #  {
    #     'name': 'Tb2Ti2O7 (HEiDi)',
    #     'description': 'neutrons, single crystal, constant wavelength, HEiDi@MLZ',
    #     'path': ':/Examples/Tb2Ti2O7_HEiDi@MLZ/project.cif'
    #  },
     #{
     #    'name': 'Co2SiO4-Mult-Phases',
     #    'description': 'neutrons, powder, constant wavelength, D20@ILL, 2 phases',
     #    'path': ':/Examples/Co2SiO4-Mult-Phases/project.cif'
     #},
     #{
     #    'name': 'Si3N4',
     #    'description': 'neutrons, powder, constant wavelength, multi-phase, 3T2@LLB',
     #    'path': ':/Examples/Si3N4/project.cif'
     #}
]

_DEFAULT_CIF = """data_DefaultProject
_project.description 'Default project description'
"""


class Project(QObject):
    createdChanged = Signal()
    needSaveChanged = Signal()
    dataBlockChanged = Signal()
    dataBlockCifChanged = Signal()
    recentChanged = Signal()
    locationChanged = Signal()
    dateCreatedChanged = Signal()
    dateLastModifiedChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proxy = parent
        self._recent = []
        self.resetAll()

    @Slot()
    def resetAll(self):
        self._dataBlock = self.createDataBlockFromCif(_DEFAULT_CIF)
        self._dataBlockCif = _DEFAULT_CIF
        self._examples = _EXAMPLES
        self._created = False
        self._needSave = False
        self._isExample = False

        self._location = str(Path.home())
        self._dateCreated = ''
        self._dateLastModified = ''
        self._dirNames = {
            'models': 'models',
            'experiments': 'experiments',
            'analysis': 'analysis',
            'summary': 'summary'
        }

    @Property('QVariant', notify=dataBlockChanged)
    def dataBlock(self):
        return self._dataBlock

    @Property(str, notify=dataBlockCifChanged)
    def dataBlockCif(self):
        return self._dataBlockCif

    @Property('QVariant', constant=True)
    def examples(self):
        return self._examples

    @Property(bool, notify=createdChanged)
    def created(self):
        return self._created

    @created.setter
    def created(self, newValue):
        if self._created == newValue:
            return
        self._created = newValue
        self.createdChanged.emit()

    @Property(bool, notify=needSaveChanged)
    def needSave(self):
        return self._needSave and not self._isExample

    @needSave.setter
    def needSave(self, newValue):
        if self._needSave == newValue:
            return
        self._needSave = newValue
        self.needSaveChanged.emit()

    @Slot()
    def setNeedSaveToTrue(self):
        self.needSave = True

    @Property('QVariant', notify=recentChanged)
    def recent(self):
        return self._recent

    @recent.setter
    def recent(self, newFilePaths):
        newFilePaths = newFilePaths.toVariant()
        existingFilePaths = [fpath for fpath in newFilePaths if os.path.isfile(fpath)]
        if self._recent == existingFilePaths:
            return
        self._recent = existingFilePaths
        self.recentChanged.emit()

    @Property(str, notify=locationChanged)
    def location(self):
        return self._location

    @location.setter
    def location(self, newValue):
        if self._location == newValue:
            return
        self._location = newValue
        self.locationChanged.emit()

    @Property(str, notify=dateCreatedChanged)
    def dateCreated(self):
        return self._dateCreated

    @dateCreated.setter
    def dateCreated(self, newValue):
        if self._dateCreated == newValue:
            return
        self._dateCreated = newValue
        self.dateCreatedChanged.emit()

    @Property(str, notify=dateLastModifiedChanged)
    def dateLastModified(self):
        return self._dateLastModified

    @dateLastModified.setter
    def dateLastModified(self, newValue):
        if self._dateLastModified == newValue:
            return
        self._dateLastModified = newValue
        self.dateLastModifiedChanged.emit()

    @Property('QVariant', constant=True)
    def dirNames(self):
        return self._dirNames

    def createDataBlockFromCif(self, edCif):
        block = cif.read_string(edCif).sole_block()
        dataBlock = gemmiObjToEdProject(block)
        return dataBlock

    @Slot('QVariant')
    def loadRecentFromFile(self, fpath):
        self.loadProjectFromFile(fpath)

    @Slot(str)
    def loadExampleFromSoure(self, fpath):
        self._isExample = True
        self.loadProjectFromSource(fpath)

    @Slot('QVariant')
    def loadProject(self, fpath):
        fpath = fpath.toLocalFile()

        if fpath in self._recent:
            self._recent.remove(fpath)
        self._recent.insert(0, fpath)
        self._recent = self._recent[:10]
        self.recentChanged.emit()

        self.loadProjectFromFile(fpath)

    def loadProjectFromSource(self, fpath):
        console.debug(f"Loading project from: {fpath}")
        file = QFile(fpath)
        if not file.open(QIODevice.ReadOnly | QIODevice.Text):
            console.error('Not found in resources')
            return

        stream = QTextStream(file)
        edCif = stream.readAll()
        ## cryspyCif = cifV2ToV1(edCif)

        block = cif.read_string(edCif).sole_block()
        self._dataBlock = gemmiObjToEdProject(block)


        self.location = os.path.dirname(fpath)

        modelFileNames = [item['cif_file_name']['value'] for item in self._dataBlock['loops']['_model']]
        modelFilePaths = [os.path.join(self._location, self._dirNames['models'], fileName) for fileName in modelFileNames]
        self._proxy.model.loadModelsFromResources(modelFilePaths)

        if '_experiment' in self._dataBlock['loops']:
            experimentFileNames = [item['cif_file_name']['value'] for item in self._dataBlock['loops']['_experiment']]
            experimentFilePaths = [os.path.join(self._location, self._dirNames['experiments'], fileName) for fileName in experimentFileNames]
            self._proxy.experiment.loadExperimentsFromResources(experimentFilePaths)

        reportFileName = 'report.cif'
        reportFilePath = os.path.join(self._location, self._dirNames['summary'], reportFileName)
        self._proxy.summary.loadReportFromResources(reportFilePath)

        if 'description' not in self._dataBlock['params']['_project']:
            self._dataBlock['params']['_project']['description'] = _EMPTY_DESCRIPTION

        self.dataBlockChanged.emit()
        self.created = True
        self.needSave = False

    def loadProjectFromFile(self, fpath):
        console.debug(f"Loading project from: {fpath}")

        if fpath in self._recent:
            self._recent.remove(fpath)
        self._recent.insert(0, fpath)
        self._recent = self._recent[:10]
        self.recentChanged.emit()

        with open(fpath, 'r') as file:
            edCif = file.read()

        block = cif.read_string(edCif).sole_block()
        self._dataBlock = gemmiObjToEdProject(block)

        st = os.stat(fpath)
        fmt = "%d %b %Y %H:%M"
        #self.dateCreated = time.strftime(fmt, time.localtime(st.st_birthtime))
        self.dateLastModified = time.strftime(fmt, time.localtime(st.st_mtime))

        self.location = os.path.dirname(fpath)

        modelFileNames = [item['cif_file_name']['value'] for item in self._dataBlock['loops']['_model']]
        modelFilePaths = [os.path.join(self._location, self._dirNames['models'], fileName) for fileName in modelFileNames]
        modelFilePaths = [QUrl.fromLocalFile(path) for path in modelFilePaths]
        self._proxy.model.loadModelsFromFiles(modelFilePaths)

        if '_experiment' in self._dataBlock['loops']:
            experimentFileNames = [item['cif_file_name']['value'] for item in self._dataBlock['loops']['_experiment']]
            experimentFilePaths = [os.path.join(self._location, self._dirNames['experiments'], fileName) for fileName in experimentFileNames]
            experimentFilePaths = [QUrl.fromLocalFile(path) for path in experimentFilePaths]
            self._proxy.experiment.loadExperimentsFromFiles(experimentFilePaths)

        reportFileName = 'report.cif'
        reportFilePath = os.path.join(self._location, self._dirNames['summary'], reportFileName)
        reportFilePath = QUrl.fromLocalFile(reportFilePath)
        self._proxy.summary.loadReportFromFile(reportFilePath)

        if 'description' not in self._dataBlock['params']['_project']:
            self._dataBlock['params']['_project']['description'] = _EMPTY_DESCRIPTION

        self.dataBlockChanged.emit()
        self.created = True
        self.needSave = True

    @Slot(str)
    def setName(self, value):
        oldValue = self._dataBlock['name']['value']
        if oldValue == value:
            return
        self._dataBlock['name']['value'] = value
        console.debug(formatMsg('sub', 'Intern dict', f'{oldValue} → {value}', 'project.name'))
        self.dataBlockChanged.emit()

    def setModels(self):
        names = [f"{block['name']['value']}" for block in self._proxy.model.dataBlocks]
        oldNames = []
        if '_model' in self._dataBlock['loops']:
            oldNames = [os.path.splitext(item['cif_file_name']['value'])[0] for item in self._dataBlock['loops']['_model']]
        if oldNames == names:
            return

        self._dataBlock['loops']['_model'] = []
        for name in names:
            edModel = {}
            edModel['cif_file_name'] = dict(Parameter(
                f'{name}.cif',
                name='cif_file_name',
                prettyName='Model file(s)',
                url='https://easydiffraction.org'
            ))
            self._dataBlock['loops']['_model'].append(edModel)

        console.debug(formatMsg('sub', 'Intern dict', f'{oldNames} → {names}'))
        self.dataBlockChanged.emit()

    def setExperiments(self):
        names = [f"{block['name']['value']}" for block in self._proxy.experiment.dataBlocksNoMeas]
        oldNames = []
        if '_experiment' in self._dataBlock['loops']:
            oldNames = [os.path.splitext(item['cif_file_name']['value'])[0] for item in self._dataBlock['loops']['_experiment']]
        if oldNames == names:
            return

        self._dataBlock['loops']['_experiment'] = []
        for name in names:
            edExperiment = {}
            edExperiment['cif_file_name'] = dict(Parameter(
                f'{name}.cif',
                name='cif_file_name',
                prettyName='Experiment file(s)',
                url='https://easydiffraction.org'
            ))
            self._dataBlock['loops']['_experiment'].append(edExperiment)

        console.debug(formatMsg('sub', 'Intern dict', f'{oldNames} → {names}'))
        self.dataBlockChanged.emit()

    @Slot(str, str, str, 'QVariant')
    def setMainParam(self, category, name, field, value):
        changedIntern = self.editDataBlockMainParam(category, name, field, value)
        if changedIntern:
            self.dataBlockChanged.emit()

    def editDataBlockMainParam(self, category, name, field, value):
        blockType = 'project'
        oldValue = self._dataBlock['params'][category][name][field]
        if oldValue == value:
            return False
        self._dataBlock['params'][category][name][field] = value
        if isinstance(value, float):
            console.debug(formatMsg('sub', 'Intern dict', f'{oldValue} → {value:.6f}', f'{blockType}.{category}.{name}.{field}'))
        else:
            console.debug(formatMsg('sub', 'Intern dict', f'{oldValue} → {value}', f'{blockType}.{category}.{name}.{field}'))
        return True

    @Slot()
    def create(self):
        self.save()

        fpath = os.path.join(self.location, 'project.cif')
        st = os.stat(fpath)
        fmt = "%d %b %Y %H:%M"
        #self.dateCreated = time.strftime(fmt, time.localtime(st.st_birthtime))
        self.dateLastModified = time.strftime(fmt, time.localtime(st.st_mtime))

        self.created = True

    @Slot()
    def save(self):
        console.debug(formatMsg('main', 'Saving project...'))

        projectDirPath = self.location
        projectFileName = 'project.cif'
        projectFilePath = os.path.join(projectDirPath, projectFileName)
        os.makedirs(projectDirPath, exist_ok=True)
        with open(projectFilePath, 'w') as file:
            file.write(self.dataBlockCif)
            console.debug(formatMsg('sub', f'saved to: {projectFilePath}'))

        if self._proxy.model.defined:
            modelFileNames = [item['cif_file_name']['value'] for item in self._dataBlock['loops']['_model']]
            modelFilePaths = [os.path.join(projectDirPath, self._dirNames['models'], fileName) for fileName in modelFileNames]
            for (modelFilePath, dataBlockCif) in zip(modelFilePaths, self._proxy.model.dataBlocksCif):
                dataBlockCif = dataBlockCif[0]
                os.makedirs(os.path.dirname(modelFilePath), exist_ok=True)
                with open(modelFilePath, 'w') as file:
                    file.write(dataBlockCif)
                    console.debug(formatMsg('sub', f'saved to: {modelFilePath}'))

        if self._proxy.experiment.defined:
            experimentFileNames = [item['cif_file_name']['value'] for item in self._dataBlock['loops']['_experiment']]
            experimentFilePaths = [os.path.join(projectDirPath, self._dirNames['experiments'], fileName) for fileName in experimentFileNames]
            for (experimentFilePath, dataBlockCifNoMeas, dataBlockCifMeasOnly) in zip(experimentFilePaths, self._proxy.experiment.dataBlocksCifNoMeas, self._proxy.experiment.dataBlocksCifMeasOnly):
                os.makedirs(os.path.dirname(experimentFilePath), exist_ok=True)
                dataBlockCif = dataBlockCifNoMeas + '\n\n' + dataBlockCifMeasOnly
                with open(experimentFilePath, 'w') as file:
                    file.write(dataBlockCif)
                    console.debug(formatMsg('sub', f'saved to: {experimentFilePath}'))

        if self._proxy.summary.isCreated:
            fileName = 'report.cif'
            reportFilePath = os.path.join(projectDirPath, self._dirNames['summary'], fileName)
            os.makedirs(os.path.dirname(reportFilePath), exist_ok=True)
            with open(reportFilePath, 'w') as file:
                dataBlockCif = self._proxy.summary.dataBlocksCif
                file.write(dataBlockCif)
                console.debug(formatMsg('sub', f'saved to: {reportFilePath}'))

        self.needSave = False

    def setDataBlockCif(self):
        self._dataBlockCif = dataBlockToCif(self._dataBlock)
        console.debug(formatMsg('sub', 'Project', '', 'to CIF string', 'converted'))
        self.dataBlockCifChanged.emit()


def gemmiObjToEdProject(starObj):
    edProject = {'name': '', 'params': {}, 'loops': {}}

    # DATABLOCK ID

    edProject['name'] = dict(Parameter(
        starObj.name,
        icon = 'archive',
        url = 'https://docs.easydiffraction.org/app/project/dictionaries/',
    ))

    # DATABLOCK SINGLES

    for param in starObj:
        if param.pair is not None and param.pair[0] == '_project.description':
            category, name = param.pair[0].split('.')
            if category not in edProject['params']:
                edProject['params'][category] = {}
            # remove double quotes from param.pair[1]
            value = param.pair[1]
            if '"' in value:
                value = value[1:-1]
            edProject['params'][category][name] = dict(Parameter(
                value,
                category = category,
                name = name,
                prettyName = 'Description',
                url = 'https://docs.easydiffraction.org/app/project/dictionaries/',
            ))

    # DATABLOCK TABLES

    for loop in starObj:
        if loop.loop is None:
            continue
        category = loop.loop.tags[0]

        if '_model' in category:
            edModels = []
            for rowItem in loop.loop.values:
                edModel = {}
                edModel['cif_file_name'] = dict(Parameter(
                    rowItem,
                    category = '_model',
                    name = 'cif_file_name',
                    prettyName = 'Model file',
                    url = 'https://easydiffraction.org'
                ))
                edModels.append(edModel)
            edProject['loops']['_model'] = edModels

        elif '_experiment' in category:
            edExperiments = []
            for rowItem in loop.loop.values:
                edExperiment = {}
                edExperiment['cif_file_name'] = dict(Parameter(
                    rowItem,
                    category = '_experiment',
                    name = 'cif_file_name',
                    prettyName = 'Experiment file',
                    url = 'https://easydiffraction.org'
                ))
                edExperiments.append(edExperiment)
            edProject['loops']['_experiment'] = edExperiments

    return edProject
