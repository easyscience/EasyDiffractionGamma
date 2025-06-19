// SPDX-FileCopyrightText: 2023 EasyDiffraction contributors <support@easydiffraction.org>
// SPDX-License-Identifier: BSD-3-Clause
// © 2023 Contributors to the EasyDiffraction project <https://github.com/easyscience/EasyDiffraction>

import QtQuick
import QtQuick.Controls

import EasyApp.Gui.Style as EaStyle
import EasyApp.Gui.Globals as EaGlobals
import EasyApp.Gui.Elements as EaElements
import EasyApp.Gui.Components as EaComponents

import Gui.Globals as Globals
import Gui.Tests as Tests


EaElements.RemoteController {
    id: rc

    property int exitCode: 0
    property var res: []
    property string savedLoggingLevel

    Timer {
        running: true
        interval: 1000
        onTriggered: {
            savedLoggingLevel = EaGlobals.Vars.loggingLevel
            EaGlobals.Vars.loggingLevel = "Debug"
            startGuiTest()
        }
    }

    Timer {
        id: exitTimer

        interval: 3000
        onTriggered: {
            console.debug(`Starting forced exit timer`)
            console.debug(`Calling python exit app helper from within QML with code ${exitCode}`)
            EaGlobals.Vars.loggingLevel = savedLoggingLevel
            Globals.Proxies.main.backendHelpers.exitApp(exitCode)
        }
    }

    Timer {
        running: Globals.Proxies.main.status.fitStatus
        interval: 3000
        onTriggered: {
            finishGuiTest()
            processTestResults()
        }
    }

    // Tests

    function saveImage(fileName, path='tests/gui/screenshots/actual') {
        saveScreenshot(parent, `${path}/${fileName}`)
    }

    function startGuiTest() {
        console.debug('Start basic suit of GUI tests (step 1 of 2)')

        /////////////////////////
        // Set up testing process
        /////////////////////////


        rc.posToCenter()
        rc.showPointer()

        ////////////
        // Home Page
        ////////////

        res.push( rc.compare(Globals.Refs.app.appbar.homeButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.appbar.projectButton.enabled, false) )
        res.push( rc.compare(Globals.Refs.app.appbar.modelButton.enabled, false) )
        res.push( rc.compare(Globals.Refs.app.appbar.experimentButton.enabled, false) )
        res.push( rc.compare(Globals.Refs.app.appbar.analysisButton.enabled, false) )
        res.push( rc.compare(Globals.Refs.app.appbar.summaryButton.enabled, false) )

        res.push( rc.compare(Globals.Refs.app.homePage.startButton.text, 'Start') )
        res.push( rc.compare(Globals.Refs.app.homePage.startButton.enabled, true) )

        saveImage('HomePage.png')
        rc.mouseClick(Globals.Refs.app.homePage.startButton)
        //rc.wait(2000)

        ///////////////
        // Project Page
        ///////////////

        res.push( rc.compare(Globals.Refs.app.appbar.homeButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.appbar.projectButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.appbar.modelButton.enabled, false) )
        res.push( rc.compare(Globals.Refs.app.appbar.experimentButton.enabled, false) )
        res.push( rc.compare(Globals.Refs.app.appbar.analysisButton.enabled, false) )
        res.push( rc.compare(Globals.Refs.app.appbar.summaryButton.enabled, false) )

        res.push( rc.compare(Globals.Refs.app.projectPage.continueButton.text, 'Continue without project') )
        res.push( rc.compare(Globals.Refs.app.projectPage.continueButton.enabled, true) )

        res.push( rc.compare(Globals.Proxies.main.status.project, 'Undefined') )

        saveImage('ProjectPage.png')
        rc.mouseClick(Globals.Refs.app.projectPage.continueButton)

        /////////////
        // Model Page
        /////////////

        res.push( rc.compare(Globals.Refs.app.appbar.homeButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.appbar.projectButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.appbar.modelButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.appbar.experimentButton.enabled, false) )
        res.push( rc.compare(Globals.Refs.app.appbar.analysisButton.enabled, false) )
        res.push( rc.compare(Globals.Refs.app.appbar.summaryButton.enabled, false) )

        res.push( rc.compare(Globals.Refs.app.modelPage.loadNewModelFromFileButton.text, 'Load model(s) from file(s)') )
        res.push( rc.compare(Globals.Refs.app.modelPage.loadNewModelFromFileButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.modelPage.addNewModelManuallyButton.text, 'Define model manually') )
        res.push( rc.compare(Globals.Refs.app.modelPage.addNewModelManuallyButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.modelPage.continueButton.text, 'Continue') )
        res.push( rc.compare(Globals.Refs.app.modelPage.continueButton.enabled, false) )

        rc.mouseClick(Globals.Refs.app.modelPage.loadNewModelFromFileButton)
        //rc.mouseClick(Globals.Refs.app.modelPage.addNewModelManuallyButton)
        rc.wait(2000)

        //res.push( rc.compare(Globals.Refs.app.modelPage.loadNewModelFromFileButton.enabled, true) )
        //res.push( rc.compare(Globals.Refs.app.modelPage.addNewModelManuallyButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.modelPage.continueButton.enabled, true) )

        //res.push( rc.compare(parseFloat(Globals.Refs.app.modelPage.shiftParameter.text), Tests.NoProjectCreated.expected.model[0].params.shift.value) )
        //res.push( rc.compare(parseFloat(Globals.Refs.app.modelPage.widthParameter.text), Tests.NoProjectCreated.expected.model[0].params.width.value) )
        //res.push( rc.compare(parseFloat(Globals.Refs.app.modelPage.scaleParameter.text), Tests.NoProjectCreated.expected.model[0].params.scale.value) )

        //res.push( rc.compare(Globals.Refs.app.modelPage.plotView.xData, Globals.Tests.expected.created.experiment.xData) )
        //res.push( rc.compare(Globals.Refs.app.modelPage.plotView.calculatedYData, Globals.Tests.expected.created.model.yData) )

        res.push( rc.compare(Globals.Proxies.main.status.phaseCount, '2') )

        saveImage('ModelPage.png')
        rc.mouseClick(Globals.Refs.app.modelPage.continueButton)

        //////////////////
        // Experiment page
        //////////////////

        res.push( rc.compare(Globals.Refs.app.appbar.homeButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.appbar.projectButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.appbar.modelButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.appbar.experimentButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.appbar.analysisButton.enabled, false) )
        res.push( rc.compare(Globals.Refs.app.appbar.summaryButton.enabled, false) )

        res.push( rc.compare(Globals.Refs.app.experimentPage.importDataFromLocalDriveButton.text, 'Load experiment(s) from file(s)') )
        res.push( rc.compare(Globals.Refs.app.experimentPage.importDataFromLocalDriveButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.experimentPage.addDefaultExperimentDataButton.text, 'Define experiment manually') )
        res.push( rc.compare(Globals.Refs.app.experimentPage.addDefaultExperimentDataButton.enabled, false) )
        res.push( rc.compare(Globals.Refs.app.experimentPage.continueButton.text, 'Continue') )
        res.push( rc.compare(Globals.Refs.app.experimentPage.continueButton.enabled, false) )

        rc.mouseClick(Globals.Refs.app.experimentPage.importDataFromLocalDriveButton)
        rc.wait(2000)

        res.push( rc.compare(Globals.Refs.app.experimentPage.importDataFromLocalDriveButton.enabled, false) )
        res.push( rc.compare(Globals.Refs.app.experimentPage.addDefaultExperimentDataButton.enabled, false) )
        res.push( rc.compare(Globals.Refs.app.experimentPage.continueButton.text, 'Continue') )

        //res.push( rc.compare(Globals.Refs.app.modelPage.plotView.xData, Globals.Tests.expected.created.experiment.xData) )
        //res.push( rc.compare(Globals.Refs.app.experimentPage.plotView.measuredYData, Globals.Tests.expected.created.experiment.yData) )

        res.push( rc.compare(Globals.Proxies.main.status.experimentsCount, '1') )

        saveImage('ExperimentPage.png')
        rc.mouseClick(Globals.Refs.app.experimentPage.continueButton)

        ////////////////
        // Analysis page
        ////////////////

        res.push( rc.compare(Globals.Refs.app.appbar.homeButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.appbar.projectButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.appbar.modelButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.appbar.experimentButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.appbar.analysisButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.appbar.summaryButton.enabled, false) )

        res.push( rc.compare(Globals.Refs.app.analysisPage.startFittingButton.text, 'Start fitting') )
        res.push( rc.compare(Globals.Refs.app.analysisPage.startFittingButton.enabled, true) )
        res.push( rc.compare(Globals.Refs.app.analysisPage.continueButton.text, 'Continue') )
        res.push( rc.compare(Globals.Refs.app.analysisPage.continueButton.enabled, false) )

        res.push( rc.compare(Globals.Proxies.main.status.calculator, 'CrysPy') )
        res.push( rc.compare(Globals.Proxies.main.status.minimizer, 'Lmfit (leastsq)') )

        rc.wait(2000)

        //res.push( rc.compare(Globals.Refs.app.analysisPage.plotView.xData, Globals.Tests.expected.created.experiment.xData) )
        //res.push( rc.compare(Globals.Refs.app.analysisPage.plotView.measuredYData, Globals.Tests.expected.created.experiment.yData) )
        //res.push( rc.compare(Globals.Refs.app.analysisPage.plotView.calculatedYData, Globals.Tests.expected.created.model.yData) )

        saveImage('AnalysisPage.png')
        rc.mouseClick(Globals.Refs.app.analysisPage.startFittingButton)
    }

    function finishGuiTest() {
        console.debug('Finish basic suit of GUI tests (step 2 of 2)')

        ////////////////
        // Analysis page
        ////////////////

        //res.push( rc.compare(Globals.Refs.app.modelPage.slopeParameter.text, Globals.Tests.expected.fitted.model.parameters.slope.value) )
        //res.push( rc.compare(Globals.Refs.app.modelPage.yInterceptParameter.text, Globals.Tests.expected.fitted.model.parameters.yIntercept.value) )

        //res.push( rc.compare(Globals.Refs.app.analysisPage.plotView.xData, Globals.Tests.expected.created.experiment.xData) )
        //res.push( rc.compare(Globals.Refs.app.analysisPage.plotView.measuredYData, Globals.Tests.expected.created.experiment.yData) )
        //res.push( rc.compare(Globals.Refs.app.analysisPage.plotView.calculatedYData, Globals.Tests.expected.fitted.model.yData) )

        rc.mouseClick(Globals.Refs.app.analysisPage.fitStatusDialogOkButton)

        // default values from EDB 0.9.9 TODO: check the new code against the original EDB
        // res.push( rc.compare(Globals.Proxies.main.status.variables, '58 (6 free, 52 fixed)') )
        // //res.push( rc.compare(Globals.Proxies.main.status.fitIteration, '197') )
        // res.push( rc.compare(Globals.Proxies.main.status.goodnessOfFit, '341.99 → 4.41') )
        // res.push( rc.compare(Globals.Proxies.main.status.fitStatus, 'Success') )

        // res.push( rc.compare(Globals.Proxies.main.status.variables, '69 (6 free, 63 fixed)') )
        // //res.push( rc.compare(Globals.Proxies.main.status.fitIteration, '197') )
        // res.push( rc.compare(Globals.Proxies.main.status.goodnessOfFit, '0.81603') )
        // res.push( rc.compare(Globals.Proxies.main.status.fitStatus, 'Success') )
        rc.mouseClick(Globals.Refs.app.analysisPage.continueButton)
        //rc.wait(2000)

        ///////////////
        // Summary page
        ///////////////

        saveImage('SummaryPage.png')

        ///////////////////////////
        // Complete testing process
        ///////////////////////////

        //rc.mouseClick(Globals.Refs.app.appbar.resetStateButton)
        rc.wait(2000)

        rc.hidePointer()
    }

    function processTestResults() {
        let okTests = 0
        let failedTests = 0

        console.info("============================ GUI TEST REPORT START =============================")

        for (let i in res) {
            if (res[i].startsWith('FAIL')) {
                exitCode = 1
                failedTests += 1
                console.error(res[i])
            } else {
                okTests +=1
            }
        }

        console.info("--------------------------------------------------------------------------------")
        console.info(`${res.length} total, ${res.length - failedTests} passed, ${failedTests} failed`)
        console.info("============================= GUI TEST REPORT END ==============================")

        console.debug(`Exiting application from QML with code ${exitCode}`)
        //applicationWindow.close()
        //Qt.callLater(Qt.exit, exitCode)  // Doesn't work on GH Windows if running app via `python main.py`
        Qt.exit(exitCode)  // Doesn't work on GH Windows if running app via `python main.py`

        // Start timer to force python exit if normal way above doesn't work
        exitTimer.start()
    }

}
