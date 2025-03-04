# SPDX-FileCopyrightText: 2023 easyDiffraction contributors <support@easydiffraction.org>
# SPDX-License-Identifier: BSD-3-Clause
# © 2021-2023 Contributors to the easyDiffraction project <https://github.com/easyScience/easyDiffractionApp>

# from easyscience import globad_object as borg
from distutils.util import strtobool
from threading import Thread
from typing import Callable
from typing import List

import numpy as np
from EasyApp.Logic.Logging import console
from easyscience.Constraints import NumericConstraint
from easyscience.Constraints import ObjConstraint
from easyscience.fitting.fitter import Fitter as CoreFitter
from easyscience.Utils.io.xml import XMLSerializer
from PySide6.QtCore import Property
from PySide6.QtCore import QObject
from PySide6.QtCore import QThread
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot


def _defaultFitResults():
    return {
        "success": None,
        "nvarys":  None,
        # "GOF":     None,
        "redchi2": None
    }

class BackendBridge(QObject):
    # Signal to send data to the GUI
    intermediate_data_ready = Signal(int, object)

# class FittingLogic(QObject):
class Fitting(QObject):
    """
    Logic related to the fitter setup
    """
    fitFinished = Signal()
    fitStarted = Signal()
    currentMinimizerChanged = Signal()
    minimizerMethodChanged = Signal()
    currentCalculatorChanged = Signal()
    finished = Signal()
    failed = Signal(str)
    constraintsRemoved = Signal()
    jobToDataBlocks = Signal()

    def __init__(self, proxy=None, interface=None):
        super().__init__(proxy)

        self.parent = proxy
        self.interface = interface
        self.fitter = CoreFitter(self.parent.experiment.job, self.interface.fit_func)
        self.bridge = BackendBridge()

        # Multithreading
        self.use_threading = True # change to False to disable threading for testing
        self._fit_finished = True
        self._fit_results = _defaultFitResults()
        self.data = None
        self.res = None
        self.is_fitting_now = False
        self._current_minimizer_method_index = 0
        # self._current_minimizer_method_name = self.fitter.available_interfaces()[0]  # noqa: E501
        self._current_minimizer_method_name = "least_squares"
        self.currentMinimizerChanged.connect(self.onCurrentMinimizerChanged)

        self.fit_thread = Thread(target=self.fit_threading, args=(self.bridge,))
        self.finished.connect(self.onSuccess)
        self.failed.connect(self.onFailed)

    def fit_nonpolar(self, *args):

        method = self._current_minimizer_method_name
        self._fit_finished = False
        # reset the iter counter
        self.interface._InterfaceFactoryTemplate__interface_obj._iteration = 0
        self.fitStarted.emit()

        kwargs = {'method' : method}

        # add the bridge info from args
        if len(args) > 0:
            kwargs['bridge'] = args[0]

        if method == 'least_squares':
            kwargs['minimizer_kwargs'] = {'diff_step': 1e-5}

        try:
            self.parent.job.fit(**kwargs)
            self.res = self.parent.job.fitting_results

        except Exception as ex:
            self.failed.emit(str(ex))
            return
        self.finished.emit()

    def fit_polar(self):
        data = self.data
        method = self._current_minimizer_method_name
        self._fit_finished = False
        self.fitStarted.emit()
        exp_data = data.experiments[0]
        x = exp_data.x

        refinement = self.parent.refinementMethods()
        targets = [component for component in refinement if refinement[component]]
        try:
            x_, y_, fit_func = self.generate_pol_fit_func(x, exp_data.y, exp_data.yb, targets)
        except Exception:
            raise NotImplementedError('This is not implemented for this calculator yet')
        weights = 1/exp_data.e
        weights = np.tile(weights, len(targets))

        kwargs = {
            'weights': weights,
            'method': method
        }

        #local_kwargs = {}
        if method == 'least_squares':
            kwargs['minimizer_kwargs'] = {'diff_step': 1e-5}

        # save some kwargs on the interface object for use in the calculator
        # TODO FIX THIS THIS IS NOT THE WAY TO DO IT :-/
        #self.interface._InterfaceFactoryTemplate__interface_obj.saved_kwargs = local_kwargs
        try:
            obj = self.fitter.fit_object
            fitter = CoreFitter(obj, fit_func)
            _ = fitter.fit(x_, y_, **kwargs)
        except Exception as ex:
            self.failed.emit(str(ex))
            return
        self.finished.emit()

    def generate_pol_fit_func(
        self,
        x_array: np.ndarray,
        spin_up: np.ndarray,
        spin_down: np.ndarray,
        components: List[Callable],
    ) -> Callable:
        num_components = len(components)
        dummy_x = np.repeat(x_array[..., np.newaxis], num_components, axis=x_array.ndim)
        calculated_y = np.array(
            [fun(spin_up, spin_down) for fun in components]
        ).swapaxes(0, x_array.ndim)

        def pol_fit_fuction(dummy_x: np.ndarray, **kwargs) -> np.ndarray:
            results, results_dict = self.interface().full_callback(
                x_array, pol_fn=components[0], **kwargs
            )
            phases = list(results_dict["phases"].keys())[0]
            up, down = (
                results_dict["phases"][phases]["components"]["up"],
                results_dict["phases"][phases]["components"]["down"],
            )
            bg = results_dict["f_background"]
            sim_y = np.array(
                [fun(up, down) + fun(bg, bg) for fun in components]
            ).swapaxes(0, x_array.ndim)
            return sim_y.flatten()

        return dummy_x.flatten(), calculated_y.flatten(), pol_fit_fuction

    def fit_threading(self, *args):
        if self.parent.experiment.isSpinPolarized():
            self.fit_polar()
        else:
            self.fit_nonpolar(*args)

    def setFailedFitResults(self):
        self._fit_results = _defaultFitResults()
        console.info('Optimization failed')
        self.parent.status.fitStatus = 'Failure'
        self._fit_results['success'] = 'Failure'  # not None but a string

    def setSuccessFitResults(self):
        self._fit_results = {
            "success": self.res.success,
            "nvarys":  self.res.n_pars,
            "redchi2": float(self.res.reduced_chi)
        }
        console.info('Optimization successfully finished')
        self.parent.status.fitStatus = 'Success'
        self.jobToDataBlocks.emit()
        pass

    @Slot()
    def resetAll(self):
        self.resetErrors()
        self._fit_results = _defaultFitResults()
        self.fitter = CoreFitter(self.parent.experiment.job, self.interface.fit_func)

    def resetErrors(self):
        # Reset all errors to zero
        # all_pars = set(self.parent.sample().get_parameters())
        all_pars = set(self.fitter.fit_object.get_parameters())
        fit_pars = {par for par in all_pars if par.enabled and not par.fixed}
        to_zero = all_pars.difference(fit_pars)
        # borg.stack.beginMacro('reset errors')
        for par in to_zero:
            par.error = 0.
        # borg.stack.endMacro()
        # macro = borg.stack.history.popleft()
        # for command in macro._commands:
        #    borg.stack.history[0]._commands.appendleft(command)

    def joinFitThread(self):
        if self.fit_thread.is_alive():
            self.fit_thread.join()

    def finishFit(self):
        self._fit_finished = True
        if 'redchi2' in self._fit_results:
            self.parent.status.goodnessOfFit = str(self._fit_results['redchi2'])
        else:
            self.parent.status.goodnessOfFit = 'N/A'

        self.fitFinished.emit()
        # TODO: remove once background is correctly implemented in polarized
        if self.parent.experiment.isSpinPolarized():
            self.parent.setSpinComponent()
        # must re-instantiate the thread object
        self.fit_thread = Thread(target=self.fit_threading, args=(self.bridge,))

    def onSuccess(self):
        self.joinFitThread()
        self.resetErrors()
        self.setSuccessFitResults()
        self.finishFit()

    def onFailed(self, ex):
        print("**** onFailed: fit FAILED with:\n {}".format(str(ex)))
        self.joinFitThread()
        self.setFailedFitResults()
        self.finishFit()

    @Slot()
    def startStop(self):
        # name = 'pd_' + self.parent.experiment.job.experiment.name
        self.parent.status.fitStatus = ''
        if self.parent.fittables._freeParamsCount <= 0:
            self.parent.status.fitStatus = 'No free params'
            console.debug('Minimization process has not been started. No free parameters found.')
            return

        if self.use_threading:
            if not self.fit_thread.is_alive():
                self.is_fitting_now = True
                self.fit_thread.start()
        else:
            # non-threaded version
            self.fit_threading()

    @Property(str, notify=minimizerMethodChanged)
    def minimizerMethod(self):
        return self._current_minimizer_method_name

    @minimizerMethod.setter
    def minimizerMethod(self, newValue):
        if self._current_minimizer_method_name == newValue:
            return
        self._current_minimizer_method_name = newValue
        self.minimizerMethodChanged.emit()

    def currentMinimizerIndex(self):
        current_name = self.fitter.minimizer.name
        index = self.fitter.available_engines.index(current_name)
        return index

    def setCurrentMinimizerIndex(self, new_index: int):
        if self.currentMinimizerIndex() == new_index:
            return
        new_name = self.fitter.available_engines[new_index]
        self.fitter.switch_engine(new_name)

    def onCurrentMinimizerChanged(self):
        idx = 0
        minimizer_name = self.fitter.current_engine.name
        if minimizer_name == 'lmfit':
            idx = self.minimizerMethodNames().index('least_squares')
        elif minimizer_name == 'bumps':
            idx = self.minimizerMethodNames().index('lm')
        if -1 < idx != self._current_minimizer_method_index:
            # Bypass the property as it would be added to the stack.
            self._current_minimizer_method_index = idx
            self._current_minimizer_method_name = self.minimizerMethodNames()[idx]  # noqa: E501
        return

    def minimizerMethodNames(self):
        current_minimizer = self.fitter.available_engines[self.currentMinimizerIndex()]  # noqa: E501
        tested_methods = {
            'lmfit': ['least_squares', 'leastsq'], # 'least_squares', 'powell', 'cobyla', 'leastsq'
            'bumps': ['lm'], # 'newton', 'lm'
            'DFO_LS': ['leastsq']
        }
        return tested_methods[current_minimizer]

    def currentMinimizerMethodIndex(self, new_index: int):
        if self._current_minimizer_method_index == new_index:
            return

        self._current_minimizer_method_index = new_index
        self._current_minimizer_method_name = self.minimizerMethodNames()[new_index]  # noqa: E501

    def setNewEngine(self, engine=None, method=None):
        new_engine_index = self.fitter.available_engines.index(engine)
        self.setCurrentMinimizerIndex(new_engine_index)
        new_method_index = self.minimizerMethodNames().index(method)
        self.currentMinimizerMethodIndex(new_method_index)

    def fittingNamesDict(self):
        return {
            'engine': self.fitter.current_engine.name,
            'method': self._current_minimizer_method_name
            }

    ####################################################################################################################
    # Calculator
    ####################################################################################################################

    def calculatorNames(self):
        interfaces = self.interface.interface_compatability("Npowder1DCWunp")     ## (self.parent.sample().exp_type_str)
        return interfaces

    def currentCalculatorIndex(self):
        interfaces = self.interface.interface_compatability("Npowder1DCWunp")    #(self.parent.sample().exp_type_str)
        return interfaces.index(self.interface.current_interface_name)

    def setCurrentCalculatorIndex(self, new_index: int):
        if self.currentCalculatorIndex == new_index:
            return
        interfaces = self.interface.interface_compatability("Npowder1DCWunp")
        new_name = interfaces[new_index]

        self.interface.switch(new_name, fitter=self.fitter)

        # recreate the fitter with the new interface
        self.fitter = CoreFitter(self.parent.sample(), self.parent.sample().create_simulation)

        print("***** _onCurrentCalculatorChanged")
        data = self.parent.pdata().simulations[0]
        data.name = f'{self.interface.current_interface_name} engine'
        # update interface on job
        job = self.parent.sample()
        job.interface = self.interface
        self.parent.updateCalculatedData()

    # Constraints
    def addConstraint(self, dependent_par_idx, relational_operator,
                      value, arithmetic_operator, independent_par_idx):
        if dependent_par_idx == -1 or value == "":
            print("Failed to add constraint: Unsupported type")
            return
        # if independent_par_idx == -1:
        #    print(f"Add constraint: {self.fitablesList()[dependent_par_idx]['label']}{relational_operator}{value}")
        # else:
        #    print(f"Add constraint: {self.fitablesList()[dependent_par_idx]['label']}{relational_operator}{value}"
        #    "{arithmetic_operator}{self.fitablesList()[independent_par_idx]['label']}")
        pars = [par for par in self.fitter.fit_object.get_parameters() if par.enabled]
        if arithmetic_operator != "" and independent_par_idx > -1:
            c = ObjConstraint(pars[dependent_par_idx],
                              str(float(value)) + arithmetic_operator,
                              pars[independent_par_idx])
        elif arithmetic_operator == "" and independent_par_idx == -1:
            c = NumericConstraint(pars[dependent_par_idx],
                                  relational_operator.replace("=", "=="),
                                  float(value))
        else:
            print("Failed to add constraint: Unsupported type")
            return
        # print(c)
        c()
        self.fitter.add_fit_constraint(c)

    def constraintsList(self):
        constraint_list = []
        for index, constraint in enumerate(self.fitter.fit_constraints()):
            if type(constraint) is ObjConstraint:
                independent_name = constraint.get_obj(constraint.independent_obj_ids).name
                relational_operator = "="
                value = float(constraint.operator[:-1])
                arithmetic_operator = constraint.operator[-1]
            elif type(constraint) is NumericConstraint:
                independent_name = ""
                relational_operator = constraint.operator.replace("==", "=")
                value = constraint.value
                arithmetic_operator = ""
            else:
                print(f"Failed to get constraint: Unsupported type {type(constraint)}")
                return
            number = index + 1
            dependent_name = constraint.get_obj(constraint.dependent_obj_ids).name
            enabled = int(constraint.enabled)
            constraint_list.append(
                {"number": number,
                 "dependentName": dependent_name,
                 "relationalOperator": relational_operator,
                 "value": value,
                 "arithmeticOperator": arithmetic_operator,
                 "independentName": independent_name,
                 "enabled": enabled}
            )
        return constraint_list

    def constraintsAsXml(self):
        xml = XMLSerializer().encode(self.constraintsList())
        return xml

    def removeConstraintByIndex(self, index: int):
        self.fitter.remove_fit_constraint(index)

    def toggleConstraintByIndex(self, index, enabled):
        constraint = self.fitter.fit_constraints()[index]
        constraint.enabled = bool(strtobool(enabled))

    def removeAllConstraints(self):
        for _ in range(len(self.fitter.fit_constraints())):
            self.removeConstraintByIndex(0)
        self.constraintsRemoved.emit()


class Fitter(QThread):
    """
    Simple wrapper for calling a function in separate thread
    """
    failed = Signal(str)
    finished = Signal()

    def __init__(self, parent, obj, method_name, *args, **kwargs):
        QThread.__init__(self, parent)
        self._obj = obj
        self.method_name = method_name
        self.args = args
        self.kwargs = kwargs

    def run(self):
        res = {}
        if hasattr(self._obj, self.method_name):
            func = getattr(self._obj, self.method_name)
            try:
                res = func(*self.args, **self.kwargs)
            except Exception as ex:
                self.failed.emit(str(ex))
                return str(ex)
            self.finished.emit()
        return res

    def stop(self):
        self.terminate()
        self.wait()  # to assure proper termination

