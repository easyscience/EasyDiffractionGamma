# SPDX-FileCopyrightText: 2023 EasyDiffraction contributors
# SPDX-License-Identifier: BSD-3-Clause
# © 2023 Contributors to the EasyDiffraction project <https://github.com/easyscience/EasyDiffraction>

from EasyApp.Logic.Logging import LoggerLevelHandler
from easydiffraction.calculators.wrapper_factory import WrapperFactory  # noqa: F401
from PySide6.QtCore import Property
from PySide6.QtCore import QObject
from PySide6.QtCore import Slot

from Logic.Analysis import Analysis
from Logic.Connections import Connections
from Logic.Data import Data
from Logic.Experiment import Experiment
from Logic.Fittables import Fittables
from Logic.Fitting2 import Fitting
from Logic.Helpers import BackendHelpers
from Logic.Model import Model
from Logic.Plotting import Plotting
from Logic.Project import Project
from Logic.Status import Status
from Logic.Summary import Summary


class PyProxy(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._logger = LoggerLevelHandler(self)
        self._project = Project(self)
        self._model = Model(self)  # Model assigns a default job and interface
        self.interface = self._model._interface
        # Now we have the default job so the subsequent modules can be initialized
        self._experiment = Experiment(self, interface=self.interface)
        self._data = Data(self, interface=self.interface)
        self._analysis = Analysis(self)
        self._fittables = Fittables(self)
        self._fitting = Fitting(self, interface=self.interface)
        self._summary = Summary(self, interface=self.interface)
        self._status = Status(self)
        self._plotting = Plotting(self)
        self._connections = Connections(self)
        self._backendHelpers = BackendHelpers(self)

    @Property('QVariant', constant=True)
    def job(self):
        return self._model.job

    @Property('QVariant', constant=True)
    def logger(self):
        return self._logger

    @Property('QVariant', constant=True)
    def connections(self):
        return self._connections

    @Property('QVariant', constant=True)
    def project(self):
        return self._project

    @Property('QVariant', constant=True)
    def experiment(self):
        return self._experiment

    @Property('QVariant', constant=True)
    def model(self):
        return self._model

    @Property('QVariant', constant=True)
    def data(self):
        return self._data

    @Property('QVariant', constant=True)
    def analysis(self):
        return self._analysis

    @Property('QVariant', constant=True)
    def fitting(self):
        return self._fitting

    @Property('QVariant', constant=True)
    def fittables(self):
        return self._fittables

    @Property('QVariant', constant=True)
    def summary(self):
        return self._summary

    @Property('QVariant', constant=True)
    def status(self):
        return self._status

    @Property('QVariant', constant=True)
    def plotting(self):
        return self._plotting

    @Property('QVariant', constant=True)
    def backendHelpers(self):
        return self._backendHelpers

    @Slot()
    def resetAll(self):
        self._connections.resetAll()  # Needs to be reset FIRST to disconnect all the signals
        self._model = Model(self)  # Model assigns a default job and interface
        self.interface = self._model._interface
        self._experiment.resetAll()
        self._experiment._interface = self.interface
        self._experiment._job = self._model.job
        self._data.resetAll()
        self._data._interface = self.interface
        self._analysis.resetAll()
        self._fitting.interface = self.interface
        self._fittables.resetAll()
        self._fitting.resetAll()
        self._summary.resetAll()
        self._summary._interface = self.interface
        self._project.resetAll()
        self._status.resetAll()
        # redo the slots
        self._connections = Connections(self)
