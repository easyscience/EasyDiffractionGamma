# SPDX-FileCopyrightText: 2023 EasyDiffraction contributors
# SPDX-License-Identifier: BSD-3-Clause
# © 2023 Contributors to the EasyDiffraction project <https://github.com/easyscience/EasyDiffraction>

import os

from EasyApp.Logic.Logging import console
from PySide6.QtCore import Property
from PySide6.QtCore import QFile
from PySide6.QtCore import QIODevice
from PySide6.QtCore import QObject
from PySide6.QtCore import QTextStream
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot

from Logic.Helpers import formatMsg

try:
    import cryspy

    console.debug('CrysPy module imported')
except ImportError:
    console.error('No CrysPy module found')


_HTML_TEMPLATE = """<!DOCTYPE html>

<html>

<style>
    th, td {
        padding-right: 18px;
    }
    th {
        text-align: left;
    }
</style>

<body>

    <table>

    <tr></tr>

    <!-- Summary title -->

    <tr>
        <td><h1>Summary</h1></td>
    </tr>

    <tr></tr>

    <!-- Project -->

    project_information_section

    <!-- Phases -->

    <tr>
        <td><h3>Crystal data</h3></td>
    </tr>

    <tr></tr>

    crystal_data_section

    <!-- Experiments -->

    <tr>
        <td><h3>Data collection</h3></td>
    </tr>

    <tr></tr>

    data_collection_section

    <!-- Analysis -->

    <tr>
        <td><h3>Refinement</h3></td>
    </tr>

    <tr></tr>

    <tr>
        <td>Calculation engine</td>
        <td>calculation_engine &mdash; https://www.cryspy.fr</td>
    </tr>
    <tr>
        <td>Minimization engine</td>
        <td>minimization_engine &mdash; https://lmfit.github.io/lmfit-py</td>
    </tr>
    <tr>
        <td>Goodness-of-fit: reduced <i>&chi;</i><sup>2</sup></td>
        <td>goodness_of_fit</td>
    </tr>
    <tr>
        <td>No. of parameters: total, free, fixed</td>
        <td>num_total_params,&nbsp;&nbsp;num_free_params,&nbsp;&nbsp;num_fixed_params</td>
    </tr>
    <tr>
        <td>No. of constraints</td>
        <td>0</td>
    </tr>

    <tr></tr>

    </table>

</body>

</html>"""


_HTML_PROJECT_INFORMATION_TEMPLATE = """
<tr>
    <td><h3>Project information</h3></td>
</tr>

<tr></tr>

<tr>
    <th>Title</th>
    <th>project_title</th>
</tr>
<tr>
    <td>Description</td>
    <td>project_description</td>
</tr>
<tr>
    <td>No. of phases</td>
    <td>num_phases</td>
</tr>
<tr>
    <td>No. of experiments</td>
    <td>num_experiments</td>
</tr>

<tr></tr>
"""

_HTML_CRYSTAL_DATA_TEMPLATE = """
<tr>
    <th>Phase datablock</th>
    <th>phase_name</th>
</tr>
<tr>
    <td>Crystal system, space group</td>
    <td>crystal_system,&nbsp;&nbsp;<i>name_H_M_alt</i></td>
</tr>
<tr>
    <td>Cell lengths: <i>a</i>, <i>b</i>, <i>c</i> (&#8491;)</td>
    <td>length_a,&nbsp;&nbsp;length_b,&nbsp;&nbsp;length_c</td>
</tr>
<tr>
    <td>Cell angles: <i>&#593;</i>, <i>&beta;</i>, <i>&#611;</i> (&deg;)</td>
    <td>angle_alpha,&nbsp;&nbsp;angle_beta,&nbsp;&nbsp;angle_gamma</td>
</tr>

<tr></tr>
"""

_HTML_DATA_COLLECTION_TEMPLATE = """
<tr>
    <th>Experiment datablock</th>
    <th>experiment_name</th>
</tr>
<tr>
    <td>Radiation probe</td>
    <td>radiation_probe</td>
</tr>
<tr>
    <td>Radiation type</td>
    <td>radiation_type</td>
</tr>
<tr>
    <td>Measured range: min, max, inc (range_units)</td>
    <td>range_min,&nbsp;&nbsp;range_max,&nbsp;&nbsp;range_inc</td>
</tr>
<tr>
    <td>No. of data points</td>
    <td>num_data_points</td>
</tr>

<tr></tr>
"""


class Summary(QObject):
    isCreatedChanged = Signal()
    dataBlocksCifChanged = Signal()
    asHtmlChanged = Signal()

    def __init__(self, parent, interface=None):
        super().__init__(parent)
        self._proxy = parent
        self._interface = interface
        self._isCreated = False
        self._dataBlocksCif = ''
        self._asHtml = ''

    @Slot()
    def resetAll(self):
        self.isCreated = False
        self._dataBlocksCif = ''
        console.debug('All summary removed')

    @Property(bool, notify=isCreatedChanged)
    def isCreated(self):
        return self._isCreated

    @isCreated.setter
    def isCreated(self, newValue):
        if self._isCreated == newValue:
            return
        self._isCreated = newValue
        self.isCreatedChanged.emit()

    @Property(str, notify=dataBlocksCifChanged)
    def dataBlocksCif(self):
        return self._dataBlocksCif

    @Property(str, notify=asHtmlChanged)
    def asHtml(self):
        return self._asHtml

    @asHtml.setter
    def asHtml(self, newValue):
        if self._asHtml == newValue:
            return
        self._asHtml = newValue
        self.asHtmlChanged.emit()

    @Slot(str, str)
    def saveAsHtml(self, location, name):
        fpath = os.path.join(location, f'{name}.html')
        with open(fpath, 'w') as file:
            file.write(self.asHtml)
        console.debug(formatMsg('sub', f'saved to: {fpath}'))

    def setDataBlocksCif(self):
        dataBlocksCifList = []
        cryspyDict = self._interface.data()._cryspyDict
        # cryspyInOutDict = self._proxy.data._calcInOutDict
        cryspyInOutDict = self._interface.data()._inOutDict
        cryspyObj = self._interface.data()._cryspyObj
        cryspyObj.take_parameters_from_dictionary(cryspyDict, l_parameter_name=None, l_sigma=None)
        cryspyObj.take_parameters_from_dictionary(cryspyInOutDict, l_parameter_name=None, l_sigma=None)

        # Models
        for blockCif in self._proxy.model._dataBlocksCif:
            dataBlocksCifList.append(blockCif[0])

        # Experiments without raw measured data, but with processed data and hkl lists
        for idx, block in enumerate(self._proxy.experiment._dataBlocksNoMeas):
            blockCifNoMeas = self._proxy.experiment._dataBlocksCifNoMeas[idx]
            dataBlocksCifList.append(blockCifNoMeas)
            for dataBlock in cryspyObj.items:
                if dataBlock.data_name == block['name']['value']:
                    if isinstance(dataBlock, cryspy.E_data_classes.cl_2_pd.Pd):
                        for subBlock in dataBlock.items:
                            if isinstance(subBlock, cryspy.C_item_loop_classes.cl_1_pd_peak.PdPeakL):
                                cif = subBlock.to_cif()
                                dataBlocksCifList.append(cif)
                            elif isinstance(subBlock, cryspy.C_item_loop_classes.cl_1_pd_proc.PdProcL):
                                cif = subBlock.to_cif()
                                dataBlocksCifList.append(cif)
                            elif isinstance(subBlock, cryspy.C_item_loop_classes.cl_1_pd_meas.PdMeasL):
                                cif = subBlock.to_cif()
                                dataBlocksCifList.append(cif)
                    elif isinstance(dataBlock, cryspy.E_data_classes.cl_2_tof.TOF):
                        for subBlock in dataBlock.items:
                            if isinstance(subBlock, cryspy.C_item_loop_classes.cl_1_tof_peak.TOFPeakL):
                                cif = subBlock.to_cif()
                                dataBlocksCifList.append(cif)
                            elif isinstance(subBlock, cryspy.C_item_loop_classes.cl_1_tof_proc.TOFProcL):
                                cif = subBlock.to_cif()
                                dataBlocksCifList.append(cif)
                            elif isinstance(subBlock, cryspy.C_item_loop_classes.cl_1_tof_meas.TOFMeasL):
                                cif = subBlock.to_cif()
                                dataBlocksCifList.append(cif)

        console.debug(formatMsg('sub', f'{len(dataBlocksCifList)} item(s)', '', 'to CIF string', 'converted'))
        self._dataBlocksCif = '\n\n'.join(dataBlocksCifList)
        self.dataBlocksCifChanged.emit()

    def setAsHtml(self):
        proxy = self._proxy
        if proxy.model.dataBlocks == [] or proxy.experiment.dataBlocksNoMeas == [] or proxy.experiment._yMeasArrays == []:
            return

        html = _HTML_TEMPLATE

        # Project information section

        html_project = ''
        if proxy.project.created:
            project_title = proxy.project.dataBlock['name']['value']
            project_description = proxy.project.dataBlock['params']['_project']['description']['value']

            html_project = _HTML_PROJECT_INFORMATION_TEMPLATE
            html_project = html_project.replace('project_title', f'{project_title}')
            html_project = html_project.replace('project_description', f'{project_description}')
            html_project = html_project.replace('num_phases', f'{proxy.status.phaseCount}')
            html_project = html_project.replace('num_experiments', f'{proxy.status.experimentsCount}')

        html = html.replace('project_information_section', html_project)

        # Crystal data section

        html_phases = []

        for phase in proxy.model.dataBlocks:
            phase_name = phase['name']['value']
            crystal_system = phase['params']['_space_group']['crystal_system']['value']
            name_H_M_alt = phase['params']['_space_group']['name_H-M_alt']['value']
            length_a = phase['params']['_cell']['length_a']['value']
            length_b = phase['params']['_cell']['length_b']['value']
            length_c = phase['params']['_cell']['length_c']['value']
            angle_alpha = phase['params']['_cell']['angle_alpha']['value']
            angle_beta = phase['params']['_cell']['angle_beta']['value']
            angle_gamma = phase['params']['_cell']['angle_gamma']['value']

            html_phase = _HTML_CRYSTAL_DATA_TEMPLATE
            html_phase = html_phase.replace('phase_name', f'{phase_name}')
            html_phase = html_phase.replace('crystal_system', f'{crystal_system}')
            html_phase = html_phase.replace('name_H_M_alt', f'{name_H_M_alt}')
            html_phase = html_phase.replace('length_a', f'{length_a}')
            html_phase = html_phase.replace('length_b', f'{length_b}')
            html_phase = html_phase.replace('length_c', f'{length_c}')
            html_phase = html_phase.replace('angle_alpha', f'{angle_alpha}')
            html_phase = html_phase.replace('angle_beta', f'{angle_beta}')
            html_phase = html_phase.replace('angle_gamma', f'{angle_gamma}')
            html_phases.append(html_phase)

        html = html.replace('crystal_data_section', '\n'.join(html_phases))

        # Data collection

        html_experiments = []

        for idx, experiment in enumerate(proxy.experiment.dataBlocksNoMeas):
            experiment_name = experiment['name']['value']
            radiation_probe = experiment['params']['_diffrn_radiation']['probe']['value']
            radiation_type = experiment['params']['_diffrn_radiation']['type']['value']
            radiation_type = radiation_type.replace('cwl', 'constant wavelength')
            radiation_type = radiation_type.replace('tof', 'time-of-flight')
            num_data_points = len(proxy.experiment._yMeasArrays[idx])
            if 'tof_range_min' in experiment['params']['_pd_meas']:
                range_min = experiment['params']['_pd_meas']['tof_range_min']['value']
                range_max = experiment['params']['_pd_meas']['tof_range_max']['value']
                range_inc = experiment['params']['_pd_meas']['tof_range_inc']['value']
                range_units = '&micro;s'
            else:
                range_min = experiment['params']['_pd_meas']['2theta_range_min']['value']
                range_max = experiment['params']['_pd_meas']['2theta_range_max']['value']
                range_inc = experiment['params']['_pd_meas']['2theta_range_inc']['value']
                range_units = '&deg;'

            html_experiment = _HTML_DATA_COLLECTION_TEMPLATE
            html_experiment = html_experiment.replace('experiment_name', f'{experiment_name}')
            html_experiment = html_experiment.replace('radiation_probe', f'{radiation_probe}')
            html_experiment = html_experiment.replace('radiation_type', f'{radiation_type}')
            html_experiment = html_experiment.replace('range_min', f'{range_min}')
            html_experiment = html_experiment.replace('range_max', f'{range_max}')
            html_experiment = html_experiment.replace('range_inc', f'{range_inc}')
            html_experiment = html_experiment.replace('range_units', f'{range_units}')
            html_experiment = html_experiment.replace('num_data_points', f'{num_data_points}')
            html_experiments.append(html_experiment)

        html = html.replace('data_collection_section', '\n'.join(html_experiments))

        # Refinement section

        num_free_params = proxy.fittables.freeParamsCount
        num_fixed_params = proxy.fittables.fixedParamsCount
        # num_params = num_free_params + num_fixed_params
        goodness_of_fit = proxy.status.goodnessOfFit
        goodness_of_fit = goodness_of_fit.split(' → ')[-1]

        html = html.replace('calculation_engine', f'{proxy.status.calculator}')
        html = html.replace('minimization_engine', f'{proxy.status.minimizer}')
        html = html.replace('goodness_of_fit', f'{goodness_of_fit}')
        html = html.replace('num_total_params', f'{num_free_params + num_fixed_params}')
        html = html.replace('num_free_params', f'{num_free_params}')
        html = html.replace('num_fixed_params', f'{num_fixed_params}')

        self.asHtml = html

    def loadReportFromResources(self, fpath):
        console.debug(f'Loading model(s) from: {fpath}')
        file = QFile(fpath)
        if not file.open(QIODevice.ReadOnly | QIODevice.Text):
            console.error('Not found in resources')
            return
        stream = QTextStream(file)
        edCif = stream.readAll()
        self._dataBlocksCif = edCif
        self.isCreated = True
        self.dataBlocksCifChanged.emit()

    def loadReportFromFile(self, fpath):
        fpath = fpath.toLocalFile()
        console.debug(f'Loading report from: {fpath}')
        if not os.path.isfile(fpath):
            console.error(f'File not found: {fpath}')
            return
        with open(fpath, 'r') as file:
            edCif = file.read()
        self._dataBlocksCif = edCif
        self.isCreated = True
        self.dataBlocksCifChanged.emit()
