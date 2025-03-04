# SPDX-FileCopyrightText: 2023 EasyDiffraction contributors
# SPDX-License-Identifier: BSD-3-Clause
# © 2023 Contributors to the EasyDiffraction project <https://github.com/easyscience/EasyDiffraction>

import copy
import random
import re

import numpy as np
import periodictable as pt
from EasyApp.Logic.Logging import console
from easycrystallography.Components.AtomicDisplacement import AtomicDisplacement
from easycrystallography.Components.SpaceGroup import SpaceGroup
from easycrystallography.Symmetry.tools import SpacegroupInfo
from easydiffraction import Job
from easydiffraction.io.cif import dataBlockToCif
from PySide6.QtCore import Property
from PySide6.QtCore import QFile
from PySide6.QtCore import QIODevice
from PySide6.QtCore import QObject
from PySide6.QtCore import QTextStream
from PySide6.QtCore import QThreadPool
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot
from PySide6.QtQml import QJSValue

from Logic.Data import Data
from Logic.Helpers import formatMsg
from Logic.Tables import COLOR_TABLE
from Logic.Tables import PERIODIC_TABLE  # TODO CHANGE THIS TO PERIODICTABLE

_DEFAULT_CIF_BLOCK = """data_default

_space_group.name_H-M_alt "P n m a"
_space_group.IT_coordinate_system_code abc

_cell.length_a 10
_cell.length_b 6
_cell.length_c 5
_cell.angle_alpha 90
_cell.angle_beta 90
_cell.angle_gamma 90

loop_
_atom_site.label
_atom_site.type_symbol
_atom_site.fract_x
_atom_site.fract_y
_atom_site.fract_z
_atom_site.occupancy
_atom_site.adp_type
_atom_site.B_iso_or_equiv
O O 0 0 0 1 Biso 0
"""

BLOCK2PHASE = {
    '_cell': 'cell',
    '_space_group': 'space_group',
    '_atom_site': 'atoms',
    'label': 'name',
    'type_symbol': 'specie',
    'occupancy': 'occupancy',
    'fract_x': 'fract_x',
    'fract_y': 'fract_y',
    'fract_z': 'fract_z',
    'length_a': 'length_a',
    'length_b': 'length_b',
    'length_c': 'length_c',
    'angle_alpha': 'angle_alpha',
    'angle_beta': 'angle_beta',
    'angle_gamma': 'angle_gamma',
    'name_H-M_alt': 'space_group_HM_name',
    'crystal_system': 'crystal_system',
    'IT_number': 'int_number',
    'IT_coordinate_system_code': 'setting',
    'B_iso_or_equiv': 'b_iso_or_equiv',
    'U_iso_or_equiv': 'u_iso_or_equiv',
}
class Model(QObject):
    definedChanged = Signal()
    currentIndexChanged = Signal()
    dataBlocksChanged = Signal()
    dataBlocksCifChanged = Signal()

    structViewAtomsModelChanged = Signal()
    structViewCellModelChanged = Signal()
    structViewAxesModelChanged = Signal()

    def __init__(self, parent, interface=None):
        super().__init__(parent)
        self._proxy = parent
        self._interface = interface
        self._defined = False
        self._currentIndex = -1
        self._dataBlocks = []
        self._dataBlocksCif = []

        self._structureViewUpdater = StructureViewUpdater(self._proxy)

        self._structViewAtomsModel = []
        self._structViewCellModel = []
        self._structViewAxesModel = []

        self._spaceGroupDict = {}
        self._spaceGroupNames = self.createSpaceGroupNames()
        self._isotopesNames = self.createIsotopesNames()

        self.createJob()

        self.phases = self.job.phases #Phases()

    # QML accessible properties

    @Property('QVariant', constant=True)
    def spaceGroupNames(self):
        return self._spaceGroupNames

    @Property('QVariant', constant=True)
    def isotopesNames(self):
        return self._isotopesNames

    @Property(bool, notify=definedChanged)
    def defined(self):
        return self._defined

    @defined.setter
    def defined(self, newValue):
        if self._defined == newValue:
            return
        self._defined = newValue
        console.debug(formatMsg('main', f'Model defined: {newValue}'))
        self.definedChanged.emit()

    @Property(int, notify=currentIndexChanged)
    def currentIndex(self):
        return self._currentIndex

    @currentIndex.setter
    def currentIndex(self, newValue):
        if self._currentIndex == newValue:
            return
        self._currentIndex = newValue
        console.debug(f"Current model index: {newValue}")
        self.currentIndexChanged.emit()

    @Property('QVariant', notify=dataBlocksChanged)
    def dataBlocks(self):
        return self._dataBlocks

    @Property('QVariant', notify=dataBlocksCifChanged)
    def dataBlocksCif(self):
        return self._dataBlocksCif

    @Property('QVariant', notify=structViewAtomsModelChanged)
    def structViewAtomsModel(self):
        return self._structViewAtomsModel

    @Property('QVariant', notify=structViewCellModelChanged)
    def structViewCellModel(self):
        return self._structViewCellModel

    @Property('QVariant', notify=structViewAxesModelChanged)
    def structViewAxesModel(self):
        return self._structViewAxesModel

    def createJob(self):
        # Create default job, so basic operations can be performed even without
        # loading any models or experiments
        self._job = Job(interface=self._interface)
        self._interface = self.job.interface
        self.job._experiment._interface = self._interface

    @property
    def job(self):
        return self._job

    # QML accessible methods
    @Slot(str, str, result=str)
    def atomData(self, typeSymbol, key):
        if typeSymbol == '':
            return ''
        typeSymbol = re.sub(r'[0-9\+\-]', '', typeSymbol)  # '162Dy' -> 'Dy', 'Co2+' -> 'Co'
        if key == 'color':
            return COLOR_TABLE[typeSymbol]
        try:
            callable = getattr(pt, typeSymbol)
            r = getattr(callable, key)
            return r
        except AttributeError:
            pass
            # passing the color check to the internal database
        return PERIODIC_TABLE[typeSymbol][key]

    @Slot()
    def addDefaultModel(self):
        console.debug("Adding default model(s)")
        self.loadModelsFromEdCif(_DEFAULT_CIF_BLOCK)

    @Slot('QVariant')
    def loadModelsFromResources(self, fpaths):
        if isinstance(fpaths, QJSValue):
            fpaths = fpaths.toVariant()
        for fpath in fpaths:
            console.debug(f"Loading model(s) from: {fpath}")
            file = QFile(fpath)
            if not file.open(QIODevice.ReadOnly | QIODevice.Text):
                console.error('Not found in resources')
                return
            stream = QTextStream(file)
            edCif = stream.readAll()
            self.loadModelsFromEdCif(edCif)

    @Slot('QVariant')
    def loadModelsFromFiles(self, fpaths):
        if isinstance(fpaths, QJSValue):
            fpaths = fpaths.toVariant()
        for fpath in fpaths:
            fpath = fpath.toLocalFile()
            console.debug(f"Loading model(s) from: {fpath}")
            with open(fpath, 'r') as file:
                edCif = file.read()
            edCif = re.sub(r'data_(.*)', lambda m: m.group(0).lower(), edCif)  # Lowercase all data block names
            self.loadModelsFromEdCif(edCif)

    def loadModelsFromEdCif(self, edCif):
        # Update the Phases object
        self.job.add_sample_from_string(edCif)
        # self.phases is already updated by the job
        self._currentIndex = len(self.phases) - 1
        # convert phase into dataBlocks
        dataBlocks = self.phaseToBlocks(self.phases)
        self._dataBlocks.append(dataBlocks)
        self.defined = bool(len(self._dataBlocks))

        self.setDataBlocksCif()
        self.updateCifOnInterface()
        self.dataBlocksChanged.emit()

    def updateCifOnInterface(self):
        '''
        Update the CIF representation on the current interface
        '''
        cif = self._dataBlocksCif[self.currentIndex][0]
        self._interface.updateModelCif(cif)

    def phaseToBlocks(self, phases):
        """
        The Phase object needs casting into EDA centric dictionary.
        Most of the fields are present in the Phase object, but some need to be added manually.
        Most notably, `shortPrettyName` is added to each parameter
        Some fields which are simple types in the Phase object are converted to dictionaries as well.
        """
        phase = phases[self._currentIndex]
        blocks = {'name': {}, 'params': {}, 'loops': {}}
        blocks['name']['value'] = phase.name

        ###### CELL
        category = '_cell'
        params = 'params'
        blocks[params][category] = {}
        name = 'length_a'
        unit = 'Å'
        icon = 'ruler'
        categoryIcon = 'cube'
        absDelta = 0.1
        def addKeys():
            blocks[params][category][name]['category'] = category
            blocks[params][category][name]['name'] = name
            blocks[params][category][name]['unit'] = unit
            blocks[params][category][name]['icon'] = icon
            blocks[params][category][name]['categoryIcon'] = categoryIcon
            blocks[params][category][name]['absDelta'] = absDelta
        blocks[params][category][name] = self.fromParameterObject(phase.cell.length_a)
        blocks[params][category][name]['value'] = float(phase.cell.length_a.value)
        blocks[params][category][name]['shortPrettyName'] = "a"
        addKeys()
        name = 'length_b'
        blocks[params][category][name] = self.fromParameterObject(phase.cell.length_b)
        blocks[params][category][name]['shortPrettyName'] = "b"
        addKeys()
        name = 'length_c'
        blocks[params][category][name] = self.fromParameterObject(phase.cell.length_c)
        blocks[params][category][name]['shortPrettyName'] = "c"
        addKeys()
        name = 'angle_alpha'
        unit = '°'
        categoryIcon = 'less-than'
        absDelta = 1.0
        blocks[params][category][name] = self.fromParameterObject(phase.cell.angle_alpha)
        blocks[params][category][name]['shortPrettyName'] = "α"
        addKeys()
        name = 'angle_beta'
        blocks[params][category][name] = self.fromParameterObject(phase.cell.angle_beta)
        blocks[params][category][name]['shortPrettyName'] = "β"
        addKeys()
        name = 'angle_gamma'
        blocks[params][category][name] = self.fromParameterObject(phase.cell.angle_gamma)
        blocks[params][category][name]['shortPrettyName'] = "γ"
        addKeys()

        ###### SPACE GROUP
        category = '_space_group'
        blocks[params][category] = {}
        name = 'name_H-M_alt'
        blocks[params][category][name] = self.fromDescriptorObject(phase.space_group.space_group_HM_name)
        blocks[params][category][name]['shortPrettyName'] = "name"
        blocks[params][category][name]['enabled'] = True
        blocks[params][category][name]['category'] = category
        blocks[params][category][name]['name'] = name
        blocks[params][category][name]['fit'] = False
        name = 'crystal_system'
        blocks[params][category][name] = {}
        blocks[params][category][name]['value'] = phase.space_group.crystal_system
        blocks[params][category][name]['shortPrettyName'] = "crystal system"
        blocks[params][category][name]['name'] = name
        blocks[params][category][name]['category'] = category
        blocks[params][category][name]['url'] = blocks[params][category]['name_H-M_alt']['url']
        blocks[params][category][name]['optional'] = True
        name = 'IT_number'
        blocks[params][category][name] = {}
        blocks[params][category][name]['value'] = phase.space_group.int_number
        blocks[params][category][name]['shortPrettyName'] = "number"
        blocks[params][category][name]['name'] = name
        blocks[params][category][name]['category'] = category
        blocks[params][category][name]['error'] = 0.0
        blocks[params][category][name]['url'] = blocks[params][category]['name_H-M_alt']['url']
        blocks[params][category][name]['optional'] = True

        name = 'IT_coordinate_system_code'
        blocks[params][category][name] = {}
        setting = phase.space_group.setting.value if phase.space_group.setting is not None else ""
        blocks[params][category][name]['value'] = setting
        blocks[params][category][name]['permittedValues'] = SpaceGroup.find_settings_by_number(phase.space_group.int_number)
        blocks[params][category][name]['shortPrettyName'] = "code"
        blocks[params][category][name]['name'] = name
        blocks[params][category][name]['category'] = category
        blocks[params][category][name]['error'] = 0.0
        blocks[params][category][name]['url'] = blocks[params][category]['name_H-M_alt']['url']
        blocks[params][category][name]['fit'] = False

        ###### ATOMS
        blocks['loops']['_atom_site'] = []
        categoryIcon = 'atom'
        prettyCategory = 'atom'
        category = '_atom_site'
        absDelta = 0.05
        icon = 'map-marker-alt'
        unit = 'Å'
        def addKeys():
            atomDict[params]['category'] = category
            atomDict[params]['idx'] = idx
            atomDict[params]['categoryIcon'] = categoryIcon
            atomDict[params]['prettyCategory'] = prettyCategory
            atomDict[params]['absDelta'] = absDelta
            atomDict[params]['icon'] = icon
            atomDict[params]['rowName'] = atom.label.value
            atomDict[params]['min'] = -np.inf
            atomDict[params]['max'] = np.inf

        for idx, atom in enumerate(phase.atoms):
            atomDict = {}
            atomDict['type_symbol'] = {'shortPrettyName': 'type',
                                       'value': atom.specie.symbol,
                                       'name': 'type_symbol',
                                       'category': category,
                                       'idx': idx}
            atomDict['label'] = self.fromDescriptorObject(atom.label)
            atomDict['label']['idx'] = idx
            atomDict['label']['shortPrettyName'] = "label"
            atomDict['label']['name'] = 'label'
            atomDict['label']['category'] = category
            params = 'fract_x'
            atomDict[params] = self.fromParameterObject(atom.fract_x)
            atomDict[params]['shortPrettyName'] = "x"
            atomDict[params]['name'] = 'fract_x'
            addKeys()
            params = 'fract_y'
            atomDict[params] = self.fromParameterObject(atom.fract_y)
            atomDict[params]['shortPrettyName'] = "y"
            atomDict[params]['name'] = 'fract_y'
            addKeys()
            params = 'fract_z'
            atomDict[params] = self.fromParameterObject(atom.fract_z)
            atomDict[params]['shortPrettyName'] = "z"
            atomDict[params]['name'] = 'fract_z'
            addKeys()
            params = 'occupancy'
            atomDict[params] = self.fromParameterObject(atom.occupancy)
            atomDict[params]['shortPrettyName'] = "occ"
            atomDict[params]['name'] = 'occupancy'
            icon = 'fill'
            addKeys()

            atomDict['Wyckoff_symbol'] = {'shortPrettyName': 'WP',
                                       'value': self.getWyckoffSymbol(atom),
                                       'name': 'Wyckoff_symbol',
                                       'category': category,
                                       'idx': idx,
                                       'optional': True,
                                       'fittable': False}

            if hasattr(atom, 'adp') and isinstance(atom.adp, AtomicDisplacement):
                atomDict['ADP_type'] = {}
                atomDict['ADP_type']['display_name'] = 'type'
                atomDict['ADP_type']['shortPrettyName'] = 'type'
                atomDict['ADP_type']['name'] = 'ADP_type'
                absDelta = 0.1
                unit = 'Å²'
                if atom.adp.adp_type.value == 'Biso':
                    atomDict['ADP_type']['value'] = 'Biso'
                    params = 'B_iso_or_equiv'
                    icon = 'arrows-alt'
                    atomDict[params] = self.fromParameterObject(atom.adp.Biso)
                    atomDict[params]['shortPrettyName'] = "iso"
                    atomDict[params]['name'] = "B_iso_or_equiv"
                    atomDict[params]['unit'] = unit
                    addKeys()

                elif atom.adp.adp_type.value == 'Uiso':
                    atomDict['ADP_type']['value'] = 'Uiso'
                    params = 'U_iso_or_equiv'
                    atomDict[params] = self.fromParameterObject(atom.adp.Uiso)
                    atomDict[params]['shortPrettyName'] = "U_iso_or_equiv"
                    atomDict[params]['name'] = "U_iso_or_equiv"
                    atomDict[params]['unit'] = unit
                    addKeys()

            blocks['loops']['_atom_site'].append(atomDict)

        return blocks

    def fromParameterObject(self, coreObject):
        """
        Convert a Parameter object into a dictionary representation

        still not sure if these should be reimplemented:
            icon
            categoryIcon
            cifDict
            absDelta
        """
        dict_repr = {}
        dict_repr['value'] = float(coreObject.value)
        dict_repr['fit'] = not bool(coreObject.fixed)
        dict_repr['fittable'] = bool(coreObject.enabled)
        dict_repr['prettyName'] = coreObject.display_name
        dict_repr['error'] = float(coreObject.error)
        dict_repr['url'] = coreObject.url
        dict_repr['enabled'] = bool(coreObject.enabled)
        dict_repr['min'] = float(coreObject.min)
        dict_repr['max'] = float(coreObject.max)
        return dict_repr

    def fromDescriptorObject(self, coreObject):
        """
        Convert a Descriptor object into a dictionary representation
        """
        dict_repr = {}
        dict_repr['value'] = coreObject.value
        dict_repr['prettyName'] = coreObject.display_name
        dict_repr['url'] = coreObject.url
        dict_repr['fittable'] = False # none of the descriptors are fittables
        return dict_repr

    def blocksToPhase(self, blockIdx, category, name, field, value):
        """
        Update the phase object with new values defined
        by the data block key names.
        """
        # find the correct parameter in the phase object
        phase = self.phases[blockIdx]
        p_name = BLOCK2PHASE[name]
        p_category = BLOCK2PHASE[category]
        # get category
        phase_with_category = getattr(phase, p_category)
        if field == 'value':
            setattr(phase_with_category, p_name, value)
        elif field == 'error':
            getattr(phase_with_category, p_name).error = value
        elif field == 'fit':
            getattr(phase_with_category, p_name).fixed = not value
        pass

    def blocksToLoopPhase(self, blockIdx, category, name, rowIndex, field, value):
        """
        Update the phase loop object with new values defined
        by the data block key names.
        """
        # find the correct parameter in the phase object
        phase = self.phases[blockIdx]
        p_name = BLOCK2PHASE[name]
        p_category = BLOCK2PHASE[category]
        # get category
        phase_with_category = getattr(phase, p_category)[rowIndex]
        # get loop item
        phase_with_item = getattr(phase_with_category, p_name)
        # label and type_symbol accessors are different
        if name == 'label':
            phase_with_category.label = value
            return
        if name == 'type_symbol':
            phase_with_item = pt.elements.symbol(value)
            return
        if field == 'value':
            phase_with_item.value = value
        elif field == 'error':
            phase_with_item.error = value
        elif field == 'fit':
            phase_with_item.fixed = not value
        pass

    def removePhase(self, phase_name: str):
        if phase_name in self.phases.phase_names:
            del self.phases[phase_name]
            return True
        return False

    def getWyckoffSymbol(self, atom):
        """
        Query the calculator for the list of Wyckoff symbols.
        THIS IS NOT HOW IT SHOULD BE DONE!
        The method explicitly relies on Cryspy objects and therefore is not general.
        """
        if not hasattr(self._interface.data(), '_cryspyObj'):
            return ''
        c_obj = self._interface.data()._cryspyObj
        if c_obj is None:
            return ''

        current_phase_name = self.phases[self.currentIndex].name.lower()

        for crystal in c_obj:
            if crystal.data_name.lower() == current_phase_name:
                for a in crystal.atom_site:
                    if a.label == atom.label.value:
                        s = a.wyckoff_symbol
                        m = a.multiplicity
                        if s and m:
                            return f'{m}{s}'

        return ''

    @Slot(str)
    def replaceModel(self, edCif=''):
        """
        New CIF -> _dataBlocks ( -> _dataBlocksCif -> calcObj and calcDict)
        """
        console.debug("Calculator obj and dict need to be replaced")
        if edCif:
            self.removeModel(self.currentIndex)
            self.loadModelsFromEdCif(edCif)
        self.updateCifOnInterface()
        self.dataBlocksChanged.emit()

    @Slot(int)
    def removeModel(self, index):
        console.debug(f"Removing model no. {index + 1}")
        if len(self.dataBlocks) < index + 1:
            return
        currentDataBlock = self.dataBlocks[index]
        currentModelName = currentDataBlock['name']['value']

        # self._interface.remove_phase(currentModelName) # delete phase info on interface
        self._interface.remove_phase(phases_obj=self.phases, phase_obj=self.phases[self.currentIndex])
        self.removePhase(currentModelName) # delete phase locally
        del self._dataBlocks[index]

        self.defined = bool(len(self.dataBlocks))
        if not self.defined:
            self._currentIndex = -1

        # self.dataBlocksChanged.emit()
        console.debug(f"Model no. {index + 1} has been removed")

    @Slot()
    def resetAll(self):
        self.defined = False
        self.phases = self.job.phases
        self._currentIndex = -1
        self._dataBlocks = []
        self._dataBlocksCif = []
        for name in self.phases.phase_names:
            del self.phases[name]
        self.dataBlocksChanged.emit()
        console.debug("All models removed")

    @Slot(int, str, str, str, 'QVariant')
    def setMainParamWithFullUpdate(self, blockIdx, category, name, field, value):
        self.blocksToPhase(blockIdx, category, name, field, value)
        # we should do the proper phase -> datablocks conversion
        # self._dataBlocks[blockIdx] = self.phaseToBlocks(self.phases)

        # but it's easier to just update the existing dict
        if field == 'value':
            self._dataBlocks[blockIdx]['params'][category][name]['value'] = value
            # check dependencies for the given parameter
            self.setParamDependencies(blockIdx, category, name, value)
        elif field == 'error':
            self._dataBlocks[blockIdx]['params'][category][name]['error'] = value
        elif field == 'fit':
            self._dataBlocks[blockIdx]['params'][category][name]['fit'] = value

        self.setDataBlocksCif()
        # self.replaceModel(self._dataBlocksCif[0][0])
        self.replaceModel()

    def setParamDependencies(self, blockIdx, category, name, value):
        # changes to certain parameters trigger changes in other parameters
        # 1. space group code change -> change space group name
        if name == 'IT_coordinate_system_code':
            spaceGroup = self._dataBlocks[blockIdx]['params']['_space_group']
            group = self.job.phases[blockIdx].space_group
            spaceGroup['name_H-M_alt']['value'] = group.hermann_mauguin
        pass

    @Slot(int, str, str, str, 'QVariant')
    def setMainParam(self, blockIdx, category, name, field, value):
        changedIntern = self.editDataBlockMainParam(blockIdx, category, name, field, value)
        changedCalculator = self.editCalculatorDictByMainParam(blockIdx, category, name, field, value)
        self.blocksToPhase(blockIdx, category, name, field, value)
        self.setDataBlocksCif()
        if changedIntern and changedCalculator:
            self.dataBlocksChanged.emit()

    @Slot(int, str, str, int, str, 'QVariant')
    def setLoopParamWithFullUpdate(self, blockIdx, category, name, rowIndex, field, value):
        changedIntern = self.editDataBlockLoopParam(blockIdx, category, name, rowIndex, field, value)
        self.blocksToLoopPhase(blockIdx, category, name, rowIndex, field, value)
        self.setDataBlocksCif()
        if not changedIntern:
            return
        self.replaceModel()

    @Slot(int, str, str, int, str, 'QVariant')
    def setLoopParam(self, blockIdx, category, name, rowIndex, field, value):
        changedIntern = self.editDataBlockLoopParam(blockIdx, category, name, rowIndex, field, value)
        changedCalculator = self.editCalculatorDictByLoopParam(blockIdx, category, name, rowIndex, field, value)
        self.blocksToLoopPhase(blockIdx, category, name, rowIndex, field, value)
        self.setDataBlocksCif()
        if changedIntern and changedCalculator:
            self.dataBlocksChanged.emit()

    @Slot(str, int)
    def removeLoopRow(self, category, rowIndex):
        self.removeDataBlockLoopRow(category, rowIndex)
        self.replaceModel()

    @Slot(str)
    def appendLoopRow(self, category):
        self.appendDataBlockLoopRow(category)
        self.replaceModel()

    @Slot(str, int)
    def duplicateLoopRow(self, category, idx):
        self.duplicateDataBlockLoopRow(category, idx)
        self.replaceModel()

    # Private methods

    def createSpaceGroupNames(self):
        all_system_names = SpacegroupInfo.get_all_systems()
        names = []
        for system in all_system_names:
            numbers = SpacegroupInfo.get_ints_from_system(system)
            for n in numbers:
                names.extend(SpacegroupInfo.get_compatible_HM_from_int(n))
        return names

    def createIsotopesNames(self):
        elements = pt.elements
        isotopes = [element.symbol for element in elements][1:] # skip 'n'
        isotopes.extend([str(iso) + element.symbol for element in elements for iso in element.isotopes][1:]) # skip '1n'
        return isotopes

    def removeDataBlockLoopRow(self, category, rowIndex):
        block = 'model'
        blockIdx = self._currentIndex
        del self._dataBlocks[blockIdx]['loops'][category][rowIndex]
        self.setDataBlocksCif()
        console.debug(formatMsg('sub', 'Intern dict', 'removed', f'{block}[{blockIdx}].{category}[{rowIndex}]'))

    def appendDataBlockLoopRow(self, category):
        block = 'model'
        blockIdx = self._currentIndex

        lastAtom = self._dataBlocks[blockIdx]['loops'][category][-1]

        newAtom = copy.deepcopy(lastAtom)
        atom_type = random.choice(self.isotopesNames) # noqa: S311

        newAtom['label']['value'] = atom_type
        # type symbol is atom_type but with numerical prefix removed
        type_symbol = re.sub(r'[0-9]', '', atom_type)
        newAtom['type_symbol']['value'] = type_symbol
        newAtom['fract_x']['value'] = random.uniform(0, 1) # noqa: S311
        newAtom['fract_y']['value'] = random.uniform(0, 1) # noqa: S311
        newAtom['fract_z']['value'] = random.uniform(0, 1) # noqa: S311
        newAtom['occupancy']['value'] = 1
        newAtom['B_iso_or_equiv']['value'] = 0

        self._dataBlocks[blockIdx]['loops'][category].append(newAtom)
        atomsCount = len(self._dataBlocks[blockIdx]['loops'][category])
        self.setDataBlocksCif()
        self.dataBlocksChanged.emit()
        console.debug(formatMsg('sub', 'Intern dict', 'added', f'{block}[{blockIdx}].{category}[{atomsCount}]'))

    def duplicateDataBlockLoopRow(self, category, idx):
        block = 'model'
        blockIdx = self._currentIndex

        lastAtom = self._dataBlocks[blockIdx]['loops'][category][idx]

        self._dataBlocks[blockIdx]['loops'][category].append(lastAtom)
        atomsCount = len(self._dataBlocks[blockIdx]['loops'][category])
        self.setDataBlocksCif()
        self.dataBlocksChanged.emit()
        console.debug(formatMsg('sub', 'Intern dict', 'added', f'{block}[{blockIdx}].{category}[{atomsCount}]'))

    def editDataBlockMainParam(self, blockIdx, category, name, field, value):
        blockType = 'model'
        oldValue = self._dataBlocks[blockIdx]['params'][category][name][field]
        if oldValue == value:
            return False
        self._dataBlocks[blockIdx]['params'][category][name][field] = value
        if isinstance(value, float):
            console.debug(formatMsg(
                'sub', 'Intern dict', f'{oldValue} → {value:.6f}', f'{blockType}[{blockIdx}].{category}.{name}.{field}'))
        else:
            console.debug(formatMsg(
                'sub', 'Intern dict', f'{oldValue} → {value}', f'{blockType}[{blockIdx}].{category}.{name}.{field}'))
        return True

    def editDataBlockLoopParam(self, blockIdx, category, name, rowIndex, field, value):
        block = 'model'
        oldValue = self._dataBlocks[blockIdx]['loops'][category][rowIndex][name][field]
        if oldValue == value:
            return False
        self._dataBlocks[blockIdx]['loops'][category][rowIndex][name][field] = value
        if isinstance(value, float):
            console.debug(formatMsg(
            'sub', 'Intern dict', f'{oldValue} → {value:.6f}', f'{block}[{blockIdx}].{category}[{rowIndex}].{name}.{field}'))
        else:
            console.debug(formatMsg(
                'sub', 'Intern dict', f'{oldValue} → {value}', f'{block}[{blockIdx}].{category}[{rowIndex}].{name}.{field}'))
        return True

    def editCalculatorDictByMainParam(self, blockIdx, category, name, field, value):
        if field != 'value' and field != 'fit':
            return True

        path, value = self.calculatorDictPathByMainParam(blockIdx, category, name, value)
        if field == 'fit':
            path[1] = f'flags_{path[1]}'

        oldValue = self._interface.data()._cryspyDict[path[0]][path[1]][path[2]]
        if oldValue != value:
            self._interface.data()._cryspyDict[path[0]][path[1]][path[2]] = value

        console.debug(formatMsg('sub', 'Calculator dict', f'{oldValue} → {value}', f'{path}'))
        return True

    def editCalculatorDictByLoopParam(self, blockIdx, category, name, rowIndex, field, value):
        if field != 'value' and field != 'fit':
            return True

        path, value = self.calculatorDictPathByLoopParam(blockIdx, category, name, rowIndex, value)
        if field == 'fit':
            path[1] = f'flags_{path[1]}'

        oldValue = self._interface.data()._cryspyDict[path[0]][path[1]][path[2]]
        if oldValue == value:
            return False
        self._interface.data()._cryspyDict[path[0]][path[1]][path[2]] = value

        console.debug(formatMsg('sub', 'Calculator dict', f'{oldValue} → {value}', f'{path}'))
        return True

    def calculatorDictPathByMainParam(self, blockIdx, category, name, value):
        blockName = self._dataBlocks[blockIdx]['name']['value']
        path = ['','','']
        path[0] = f"crystal_{blockName}"

        # _cell
        if category == '_cell':
            if name == 'length_a':
                path[1] = 'unit_cell_parameters'
                path[2] = 0
            elif name == 'length_b':
                path[1] = 'unit_cell_parameters'
                path[2] = 1
            elif name == 'length_c':
                path[1] = 'unit_cell_parameters'
                path[2] = 2
            elif name == 'angle_alpha':
                path[1] = 'unit_cell_parameters'
                path[2] = 3
                value = np.deg2rad(value)
            elif name == 'angle_beta':
                path[1] = 'unit_cell_parameters'
                path[2] = 4
                value = np.deg2rad(value)
            elif name == 'angle_gamma':
                path[1] = 'unit_cell_parameters'
                path[2] = 5
                value = np.deg2rad(value)

        # undefined
        else:
            console.error(f"Undefined name '{category}.{name}'")

        return path, value

    def calculatorDictPathByLoopParam(self, blockIdx, category, name, rowIndex, value):
        blockName = self._dataBlocks[blockIdx]['name']['value']
        path = ['','','']
        path[0] = f"crystal_{blockName}"

        # _atom_site
        if category == '_atom_site':
            if name == 'fract_x':
                path[1] = 'atom_fract_xyz'
                path[2] = (0, rowIndex)
            elif name == 'fract_y':
                path[1] = 'atom_fract_xyz'
                path[2] = (1, rowIndex)
            elif name == 'fract_z':
                path[1] = 'atom_fract_xyz'
                path[2] = (2, rowIndex)
            elif name == 'occupancy':
                path[1] = 'atom_occupancy'
                path[2] = rowIndex
            elif name == 'B_iso_or_equiv':
                path[1] = 'atom_b_iso'
                path[2] = rowIndex

        # undefined
        else:
            console.error(f"Undefined name '{category}.{name}'")

        return path, value

    def paramValueByFieldAndCrypyParamPath(self, field, path):  # NEED FIX: code duplicate of editDataBlockByLmfitParams
        block, group, idx = path

        # crystal block
        if block.startswith('crystal_'):
            blockName = block[8:]
            category = None
            name = None
            rowIndex = -1

            # unit_cell_parameters
            if group == 'unit_cell_parameters':
                category = '_cell'
                if idx[0] == 0:
                    name = 'length_a'
                elif idx[0] == 1:
                    name = 'length_b'
                elif idx[0] == 2:
                    name = 'length_c'
                elif idx[0] == 3:
                    name = 'angle_alpha'
                elif idx[0] == 4:
                    name = 'angle_beta'
                elif idx[0] == 5:
                    name = 'angle_gamma'

            # atom_fract_xyz
            elif group == 'atom_fract_xyz':
                category = '_atom_site'
                rowIndex = idx[1]
                if idx[0] == 0:
                    name = 'fract_x'
                elif idx[0] == 1:
                    name = 'fract_y'
                elif idx[0] == 2:
                    name = 'fract_z'

            # atom_occupancy
            elif group == 'atom_occupancy':
                category = '_atom_site'
                rowIndex = idx[0]
                name = 'occupancy'

            # b_iso_or_equiv
            elif group == 'atom_b_iso':
                category = '_atom_site'
                rowIndex = idx[0]
                name = 'B_iso_or_equiv'

            blockIdx = [block['name']['value'] for block in self._dataBlocks].index(blockName)

            if rowIndex == -1:
                return self.dataBlocks[blockIdx]['params'][category][name][field]
            else:
                return self.dataBlocks[blockIdx]['loops'][category][rowIndex][name][field]

        return None

    def editDataBlockByLmfitParams(self, params):
        for param in params.values():
            block, group, idx = Data.strToCalcDictParamPath(param.name)

            # crystal block
            if block.startswith('crystal_'):
                blockName = block[8:]
                category = None
                name = None
                rowIndex = -1
                value = param.value
                error = 0
                if param.stderr is not None:
                    if param.stderr < 1e-6:
                        error = 1e-6  # Temporary solution to compensate for too small uncertanties after lmfit
                    else:
                        error = param.stderr

                # unit_cell_parameters
                if group == 'unit_cell_parameters':
                    category = '_cell'
                    if idx[0] == 0:
                        name = 'length_a'
                    elif idx[0] == 1:
                        name = 'length_b'
                    elif idx[0] == 2:
                        name = 'length_c'
                    elif idx[0] == 3:
                        name = 'angle_alpha'
                        value = np.rad2deg(value)
                    elif idx[0] == 4:
                        name = 'angle_beta'
                        value = np.rad2deg(value)
                    elif idx[0] == 5:
                        name = 'angle_gamma'
                        value = np.rad2deg(value)

                # atom_fract_xyz
                elif group == 'atom_fract_xyz':
                    category = '_atom_site'
                    rowIndex = idx[1]
                    if idx[0] == 0:
                        name = 'fract_x'
                    elif idx[0] == 1:
                        name = 'fract_y'
                    elif idx[0] == 2:
                        name = 'fract_z'

                # atom_occupancy
                elif group == 'atom_occupancy':
                    category = '_atom_site'
                    rowIndex = idx[0]
                    name = 'occupancy'

                # b_iso_or_equiv
                elif group == 'atom_b_iso':
                    category = '_atom_site'
                    rowIndex = idx[0]
                    name = 'B_iso_or_equiv'

                value = float(value)  # convert float64 to float (needed for QML access)
                error = float(error)  # convert float64 to float (needed for QML access)
                blockIdx = [block['name']['value'] for block in self._dataBlocks].index(blockName)

                if rowIndex == -1:
                    self.editDataBlockMainParam(blockIdx, category, name, 'value', value)
                    self.editDataBlockMainParam(blockIdx, category, name, 'error', error)
                else:
                    self.editDataBlockLoopParam(blockIdx, category, name, rowIndex, 'value', value)
                    self.editDataBlockLoopParam(blockIdx, category, name, rowIndex, 'error', error)

    def setDataBlocksCif(self):
        self._dataBlocksCif = [[dataBlockToCif(block)] for block in self._dataBlocks]
        console.debug(formatMsg('sub', f'{len(self._dataBlocksCif)} model(s)', '', 'to CIF string', 'converted'))
        self.dataBlocksCifChanged.emit()

    def updateCurrentModelStructView(self):
        self.setCurrentModelStructViewAtomsModel()
        #self.setCurrentModelStructViewCellModel()
        #self.setCurrentModelStructViewAxesModel()

    def setCurrentModelStructViewCellModel(self):
        params = self._dataBlocks[self._currentIndex]['params']
        a = params['_cell']['length_a']['value']
        b = params['_cell']['length_b']['value']
        c = params['_cell']['length_c']['value']
        self._structViewCellModel = [
            # x
            { "x": 0,     "y":-0.5*b, "z":-0.5*c, "rotx": 0, "roty": 0,  "rotz":-90, "len": a },
            { "x": 0,     "y": 0.5*b, "z":-0.5*c, "rotx": 0, "roty": 0,  "rotz":-90, "len": a },
            { "x": 0,     "y":-0.5*b, "z": 0.5*c, "rotx": 0, "roty": 0,  "rotz":-90, "len": a },
            { "x": 0,     "y": 0.5*b, "z": 0.5*c, "rotx": 0, "roty": 0,  "rotz":-90, "len": a },
            # y
            { "x":-0.5*a, "y": 0,     "z":-0.5*c, "rotx": 0, "roty": 0,  "rotz": 0,  "len": b },
            { "x": 0.5*a, "y": 0,     "z":-0.5*c, "rotx": 0, "roty": 0,  "rotz": 0,  "len": b },
            { "x":-0.5*a, "y": 0,     "z": 0.5*c, "rotx": 0, "roty": 0,  "rotz": 0,  "len": b },
            { "x": 0.5*a, "y": 0,     "z": 0.5*c, "rotx": 0, "roty": 0,  "rotz": 0,  "len": b },
            # z
            { "x":-0.5*a, "y":-0.5*b, "z": 0,     "rotx": 0, "roty": 90, "rotz": 90, "len": c },
            { "x": 0.5*a, "y":-0.5*b, "z": 0,     "rotx": 0, "roty": 90, "rotz": 90, "len": c },
            { "x":-0.5*a, "y": 0.5*b, "z": 0,     "rotx": 0, "roty": 90, "rotz": 90, "len": c },
            { "x": 0.5*a, "y": 0.5*b, "z": 0,     "rotx": 0, "roty": 90, "rotz": 90, "len": c },
        ]
        console.debug(
            f"Structure view cell  for model no. {self._currentIndex + 1} has been set. Cell lengths: ({a}, {b}, {c})")
        self.structViewCellModelChanged.emit()

    def setCurrentModelStructViewAxesModel(self):
        params = self._dataBlocks[self._currentIndex]['params']
        a = params['_cell']['length_a']['value']
        b = params['_cell']['length_b']['value']
        c = params['_cell']['length_c']['value']
        self._structViewAxesModel = [
            {"x": 0.5, "y": 0,   "z": 0,   "rotx": 0, "roty":  0, "rotz": -90, "len": a},
            {"x": 0,   "y": 0.5, "z": 0,   "rotx": 0, "roty":  0, "rotz":   0, "len": b},
            {"x": 0,   "y": 0,   "z": 0.5, "rotx": 0, "roty": 90, "rotz":  90, "len": c}
        ]
        console.debug(
            f"Structure view axes  for model no. {self._currentIndex + 1} has been set. Cell lengths: ({a}, {b}, {c})")
        self.structViewAxesModelChanged.emit()

    def setCurrentModelStructViewAtomsModel(self):
        '''
        Create a list of atoms for structure view, using easycrystallography to calculate equivalent positions
        '''
        print("\nsetCurrentModelStructViewAtomsModel\n")
        structViewModel = set()
        if self._currentIndex == -1:
            self._structViewAtomsModel = []
            self.structViewAtomsModelChanged.emit()
            return
        atoms = self._dataBlocks[self._currentIndex]['loops']['_atom_site']

        # Add all atoms in the cell, including those in equivalent positions
        for atom in atoms:
            symbol = atom['type_symbol']['value']
            xUnique = atom['fract_x']['value']
            yUnique = atom['fract_y']['value']
            zUnique = atom['fract_z']['value']

            # symmetry mappig using EasyDiffractionLib
            xArray, yArray, zArray = [], [], []
            spacegroup_str = self._dataBlocks[0]['params']['_space_group']['name_H-M_alt']['value']
            spacegroup = SpaceGroup(spacegroup_str)
            orbit_array = spacegroup.get_orbit(np.array([xUnique, yUnique, zUnique]))
            xArray = orbit_array[:, 0].tolist()
            yArray = orbit_array[:, 1].tolist()
            zArray = orbit_array[:, 2].tolist()

            # wrap into unit cell if required
            xArray = self.wrap_into_unit_cell(xArray)
            yArray = self.wrap_into_unit_cell(yArray)
            zArray = self.wrap_into_unit_cell(zArray)

            for x, y, z in zip(xArray, yArray, zArray):
                structViewModel.add((
                    float(x),
                    float(y),
                    float(z),
                    self.atomData(symbol, 'covalent_radius'),
                    self.atomData(symbol, 'color')
                ))
        # Add those atoms, which have 0 in xyz to be translated into 1
        structViewModelCopy = copy.copy(structViewModel)
        for item in structViewModelCopy:
            if item[0] == 0 and item[1] == 0 and item[2] == 0:
                structViewModel.add((1, 0, 0, item[3], item[4]))
                structViewModel.add((0, 1, 0, item[3], item[4]))
                structViewModel.add((0, 0, 1, item[3], item[4]))
                structViewModel.add((1, 1, 0, item[3], item[4]))
                structViewModel.add((1, 0, 1, item[3], item[4]))
                structViewModel.add((0, 1, 1, item[3], item[4]))
                structViewModel.add((1, 1, 1, item[3], item[4]))
            elif item[0] == 0 and item[1] == 0:
                structViewModel.add((1, 0, item[2], item[3], item[4]))
                structViewModel.add((0, 1, item[2], item[3], item[4]))
                structViewModel.add((1, 1, item[2], item[3], item[4]))
            elif item[0] == 0 and item[2] == 0:
                structViewModel.add((1, item[1], 0, item[3], item[4]))
                structViewModel.add((0, item[1], 1, item[3], item[4]))
                structViewModel.add((1, item[1], 1, item[3], item[4]))
            elif item[1] == 0 and item[2] == 0:
                structViewModel.add((item[0], 1, 0, item[3], item[4]))
                structViewModel.add((item[0], 0, 1, item[3], item[4]))
                structViewModel.add((item[0], 1, 1, item[3], item[4]))
            elif item[0] == 0:
                structViewModel.add((1, item[1], item[2], item[3], item[4]))
            elif item[1] == 0:
                structViewModel.add((item[0], 1, item[2], item[3], item[4]))
            elif item[2] == 0:
                structViewModel.add((item[0], item[1], 1, item[3], item[4]))
        # Create dict from set for GUI
        self._structViewAtomsModel = [{'x':x, 'y':y, 'z':z, 'diameter':diameter, 'color':color}
                                      for x, y, z, diameter, color in structViewModel]
        console.debug(formatMsg('sub',
                    f'{len(atoms)} atom(s)', f'model no. {self._currentIndex + 1}', 'for structure view', 'defined'))
        self.structViewAtomsModelChanged.emit()

    @staticmethod
    def wrap_into_unit_cell(position):
        """Wrap the atomic position into the conventional unit cell."""
        return [(coord % 1) for coord in position]

    def phaseToModel(self, phase):
        '''
        Convert the current phase to ED model representation
        '''
        pass

    def jobToModel(self, job):
        '''
        Convert the current job to ED model representation
        '''
        pass

class StructureViewWorker(QObject):
    finished = Signal()

    def __init__(self, proxy):
        super().__init__()
        self._proxy = proxy

    def run(self):
        self._proxy.model.updateCurrentModelStructView()
        self.finished.emit()


class StructureViewUpdater(QObject):
    finished = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self._proxy = parent
        self._threadpool = QThreadPool.globalInstance()
        self._worker = StructureViewWorker(self._proxy)

        self._worker.finished.connect(self.finished)

    def update(self):
        self._threadpool.start(self._worker.run)
        console.debug(formatMsg('main', '---------------'))
