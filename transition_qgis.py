# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Transition
                                 A QGIS plugin
 truc
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2024-02-03
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Transition
        email                : Transition
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QDialog, QSpinBox
from PyQt5.QtWidgets import QWidget, QMessageBox
from PyQt5 import QtTest


from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand, QgsProjectionSelectionDialog
from qgis.core import QgsUnitTypes, QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsPointXY, QgsVectorLayer, QgsProject, QgsLayerTreeGroup, Qgis
# Initialize Qt resources from file resources.py
from .resources import *

# Import the code for the DockWidget
from .transition_qgis_dockwidget import TransitionDockWidget
from .create_login import Login
from .coordinate_capture_map_tool import CoordinateCaptureMapTool
import os.path

import sys
import geojson
import configparser

from .import_path import return_lib_path
sys.path.append(return_lib_path())
from transition_api_lib import Transition

from .create_route import CreateRouteDialog
from .create_accessibility import CreateAccessibilityForm
from .create_settings import CreateSettingsForm


class TransitionWidget:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        self.settings = QSettings()
        # initialize locale
        locale = self.settings.value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'transition_qgis_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Transition')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'Transition')
        self.toolbar.setObjectName(u'Transition')

        #print "** INITIALIZING Transition"
        self.pluginIsActive = False
        self.dockwidget = None
        self.loginPopup = None
        self.transition_paths = None
        self.validLogin = False

        self.crs = QgsCoordinateReferenceSystem("EPSG:4326")
        self.transform = QgsCoordinateTransform()
        self.transform.setDestinationCrs(self.crs)
        if self.crs.mapUnits() == QgsUnitTypes.DistanceDegrees:
            self.userCrsDisplayPrecision = 5
        else:
            self.userCrsDisplayPrecision = 3
        self.canvasCrsDisplayPrecision = None
        self.iface.mapCanvas().destinationCrsChanged.connect(self.setSourceCrs)
        self.setSourceCrs()

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('Transition', message)
    
    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action


    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/transition_qgis/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Transition'),
            callback=self.run,
            parent=self.iface.mainWindow())

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        #print "** CLOSING Transition"

        # disconnects
        if self.dockwidget is not None:
            self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)
            self.dockwidget = None
        print("closing")

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None

        self.pluginIsActive = False


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        #print "** UNLOAD Transition"

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Transition'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar


    #--------------------------------------------------------------------------

    def run(self):
        """Run method that loads and starts the plugin"""

        if not self.pluginIsActive:
            self.pluginIsActive = True
            print("Transition plugin is active")

            self.checkValidLogin()
            print(f"Valid login: {self.validLogin}")

            if self.validLogin:
                self.show_dockwidget()

            else:
                self.loginPopup = Login(self.iface, self.settings)
                self.loginPopup.finished.connect(self.onLoginFinished)

    def checkValidLogin(self):
        token = self.settings.value("token")
        if token:
            self.validLogin = True
            Transition.set_token(self.settings.value("token"))
            Transition.set_url(self.settings.value("url"))


    def onLoginFinished(self, result):
        if result == QDialog.Accepted:
            print("Login successful")
            self.validLogin = True
            self.show_dockwidget()

            #print "** STARTING Transition"

            # dockwidget may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if self.dockwidget == None and self.validLogin:
                self.show_dockwidget()

        else:
            print("Login canceled")

            # Close the plugin's dock widget if it was created
            if self.dockwidget:
                self.iface.removeDockWidget(self.dockwidget)
                self.dockwidget.close()
            self.onClosePlugin()

    def show_dockwidget(self):
        if self.dockwidget == None and self.validLogin:
            print("Creating new dockwidget")
            # Create the dockwidget (after translation) and keep reference
            self.dockwidget = TransitionDockWidget()

            self.selectedCoords = { 'routeOriginPoint': None, 'routeDestinationPoint': None, 'accessibilityMapPoint': None }

            self.createRouteForm = CreateRouteDialog()
            self.dockwidget.routeVerticalLayout.addWidget(self.createRouteForm)
            self.createAccessibilityForm = CreateAccessibilityForm()
            self.dockwidget.accessibilityVerticalLayout.addWidget(self.createAccessibilityForm)
            self.dockwidget.createSettingsForm = CreateSettingsForm(self.settings)
            self.dockwidget.settingsVerticalLayout.addWidget(self.dockwidget.createSettingsForm)

            self.dockwidget.pathButton.clicked.connect(self.onPathButtonClicked)
            self.dockwidget.nodeButton.clicked.connect(self.onNodeButtonClicked)
            self.dockwidget.accessibilityButton.clicked.connect(self.onAccessibilityButtonClicked)
            self.dockwidget.routeButton.clicked.connect(self.onNewRouteButtonClicked)
            self.dockwidget.disconnectButton.clicked.connect(self.onDisconnectUser)
            self.mapToolFrom = CoordinateCaptureMapTool(self.iface, self.iface.mapCanvas(), Qt.darkGreen, "Starting point")
            self.mapToolFrom.mouseClicked.connect(lambda event: self.mouseClickedCapture(event, self.dockwidget.userCrsEditFrom, 'routeOriginPoint'))
            self.mapToolFrom.endSelection.connect(self.stopCapturing)

            self.mapToolTo = CoordinateCaptureMapTool(self.iface, self.iface.mapCanvas(), Qt.blue, "Destination point")
            self.mapToolTo.mouseClicked.connect(lambda event: self.mouseClickedCapture(event, self.dockwidget.userCrsEditTo, 'routeDestinationPoint'))
            self.mapToolTo.endSelection.connect(self.stopCapturing)

            self.mapToolAccessibility = CoordinateCaptureMapTool(self.iface, self.iface.mapCanvas(), Qt.blue, "Accessibility map center")
            self.mapToolAccessibility.mouseClicked.connect(lambda event: self.mouseClickedCapture(event, self.dockwidget.userCrsEditAccessibility, 'accessibilityMapPoint'))
            self.mapToolAccessibility.endSelection.connect(self.stopCapturing)

            self.dockwidget.routeCaptureButtonFrom.clicked.connect(lambda: self.startCapturing(self.mapToolFrom))
            self.dockwidget.routeCaptureButtonTo.clicked.connect(lambda: self.startCapturing(self.mapToolTo))
            self.dockwidget.accessibilityCaptureButton.clicked.connect(lambda: self.startCapturing(self.mapToolAccessibility))

            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)

            # Determine the order in which the layers are shown on the map (point, line, polygon)
            QgsProject.instance().layerTreeRegistryBridge().setLayerInsertionMethod(Qgis.LayerTreeInsertionMethod.OptimalInInsertionGroup)

        # show the dockwidget
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
        self.dockwidget.show()

    def onPathButtonClicked(self):
        try:
            geojson_data = Transition.get_paths()
            layer = QgsVectorLayer(geojson.dumps(geojson_data), "transition_paths", "ogr")
            
            if not layer.isValid():
                raise Exception("Layer failed to load!")
    
            QgsProject.instance().addMapLayer(layer)

        except Exception as error:
            self.iface.messageBar().pushCritical('Error', str(error))


    def onNodeButtonClicked(self):
        try:
            geojson_data = Transition.get_nodes()
            layer = QgsVectorLayer(geojson.dumps(geojson_data), "transition_nodes", "ogr")
            
            if not layer.isValid():
                raise Exception("Layer failed to load!")

            QgsProject.instance().addMapLayer(layer)

        except Exception as error:
            self.iface.messageBar().pushCritical('Error', str(error))

    def onNewRouteButtonClicked(self):
        try:
            modes = self.createRouteForm.modeChoice.checkedItems()
            if not modes:
                QMessageBox.warning(self.dockwidget, "No modes selected", "Please select at least one mode.")
                return
            
            originCoord = [self.selectedCoords['routeOriginPoint'].x(), self.selectedCoords['routeOriginPoint'].y()]
            destCoord = [self.selectedCoords['routeDestinationPoint'].x(), self.selectedCoords['routeDestinationPoint'].y()]
            departureOrArrivalChoice = "Departure" if self.createRouteForm.departureRadioButton.isChecked() else "Arrival"
            departureOrArrivalTime = self.createRouteForm.departureOrArrivalTime.time().toPyTime()
            maxParcoursTime = self.createRouteForm.maxParcoursTimeChoice.value()
            minWaitTime = self.createRouteForm.minWaitTimeChoice.value()
            maxAccessTimeOrigDest = self.createRouteForm.maxAccessTimeOrigDestChoice.value()
            maxTransferWaitTime = self.createRouteForm.maxTransferWaitTimeChoice.value()
            maxWaitTimeFisrstStopChoice = self.createRouteForm.maxWaitTimeFisrstStopChoice.value()
            scenarioId = self.createRouteForm.scenarios.json()['collection'][self.createRouteForm.scenarioChoice.currentIndex()]['id']

            result = Transition.request_routing_result(modes=modes, 
                                                origin=originCoord, 
                                                destination=destCoord, 
                                                scenario_id=scenarioId, 
                                                max_travel_time=maxParcoursTime, 
                                                min_waiting_time=minWaitTime,
                                                max_transfer_time=maxTransferWaitTime, 
                                                max_access_time=maxAccessTimeOrigDest, 
                                                departure_or_arrival_time=departureOrArrivalTime, 
                                                departure_or_arrival_choice=departureOrArrivalChoice, 
                                                max_first_waiting_time=maxWaitTimeFisrstStopChoice,
                                                with_geojson=True)
            
            # Remove the existing "Routing results" group if it exists
            existing_group = QgsProject.instance().layerTreeRoot().findGroup("Routing results")
            if existing_group:
                QgsProject.instance().layerTreeRoot().removeChildNode(existing_group)
            
            # Create a new group layer for the routing results, it will contain all the routing modes in separate layers
            root = QgsProject.instance().layerTreeRoot()
            group = root.addGroup("Routing results")
            for key, value in result.items():  
                geojsonPath = value["pathsGeojson"]
                mode = key
                for i in range(len(geojsonPath)):
                    geojson_data = geojsonPath[i]
                    layer = QgsVectorLayer(geojson.dumps(geojson_data), mode, "ogr")
                    if not layer.isValid():
                        raise Exception("Layer failed to load!")
                    QgsProject.instance().addMapLayer(layer, False)
                    group.addLayer(layer)

        except Exception as error:
            self.iface.messageBar().pushCritical('Error', str(error))

    def onAccessibilityButtonClicked(self):
        try:
            geojson_data = Transition.request_accessibility_map(
                with_geojson=True,
                departure_or_arrival_choice="Departure" if self.createAccessibilityForm.departureRadioButton.isChecked() else "Arrival",
                departure_or_arrival_time=self.createAccessibilityForm.departureOrArrivalTime.time().toPyTime(),
                n_polygons=self.createAccessibilityForm.nPolygons.value(),
                delta_minutes=self.createAccessibilityForm.delta.value(),
                delta_interval_minutes=self.createAccessibilityForm.deltaInterval.value(),
                scenario_id=self.createAccessibilityForm.scenarios.json()['collection'][self.createAccessibilityForm.scenarioChoice.currentIndex()]['id'],
                place_name=self.createAccessibilityForm.placeName.text(),
                max_total_travel_time_minutes=self.createAccessibilityForm.maxTotalTravelTime.value(),
                min_waiting_time_minutes=self.createAccessibilityForm.minWaitTime.value(),
                max_access_egress_travel_time_minutes=self.createAccessibilityForm.maxAccessTimeOrigDest.value(),
                max_transfer_travel_time_minutes=self.createAccessibilityForm.maxTransferWaitTime.value(),
                max_first_waiting_time_minutes=self.createAccessibilityForm.maxFirstWaitTime.value(),
                walking_speed_kmh=self.createAccessibilityForm.walkingSpeed.value(),
                coord_latitude=self.selectedCoords['accessibilityMapPoint'].y(),
                coord_longitude=self.selectedCoords['accessibilityMapPoint'].x()
            )
            geojson_data = geojson.dumps(geojson_data['polygons'])

            if geojson_data:
                # Remove the existing "Accessibility map" layer if it exists
                existing_layers = QgsProject.instance().mapLayersByName("Accessibility map")
                if existing_layers:
                    QgsProject.instance().removeMapLayer(existing_layers[0].id())

                # Add the new "Accessibility map" layer
                layer = QgsVectorLayer(geojson_data, "Accessibility map", "ogr")
                if not layer.isValid():
                    raise Exception("Layer failed to load!")
                QgsProject.instance().addMapLayer(layer)

                # Set layer opacity to 60%
                single_symbol_renderer = layer.renderer()
                symbol = single_symbol_renderer.symbol()
                symbol.setOpacity(0.6)
                layer.triggerRepaint()
        
        except Exception as error:
            self.iface.messageBar().pushCritical('Error', str(error))

    def setCrs(self):
        selector = QgsProjectionSelectionDialog(self.iface.mainWindow())
        selector.setCrs(self.crs)
        if selector.exec():
            self.crs = selector.crs()
            self.transform.setDestinationCrs(self.crs)
            if self.crs.mapUnits() == QgsUnitTypes.DistanceDegrees:
                self.userCrsDisplayPrecision = 5
            else:
                self.userCrsDisplayPrecision = 3

    def setSourceCrs(self):
        self.transform.setSourceCrs(self.iface.mapCanvas().mapSettings().destinationCrs())
        if self.iface.mapCanvas().mapSettings().destinationCrs().mapUnits() == QgsUnitTypes.DistanceDegrees:
            self.canvasCrsDisplayPrecision = 5
        else:
            self.canvasCrsDisplayPrecision = 3

    def mouseClickedCapture(self, point: QgsPointXY, displayField, selectedCoordKey):
        userCrsPoint = self.transform.transform(point)
        displayField.setText('{0:.{2}f},{1:.{2}f}'.format(userCrsPoint.x(),
                                                          userCrsPoint.y(),
                                                          self.userCrsDisplayPrecision))
        self.selectedCoords[selectedCoordKey] = userCrsPoint

    def startCapturing(self, mapTool):
        self.iface.mapCanvas().setMapTool(mapTool)

    def stopCapturing(self):
        # Set mouse cursor back to pan mode
        self.iface.actionPan().trigger()
        self.mapToolFrom.deactivate()

    def onDisconnectUser(self):
        # Remove all layers
        for layer in QgsProject.instance().mapLayers().values():
            QgsProject.instance().removeMapLayer(layer)

        # Remove all groups
        root = QgsProject.instance().layerTreeRoot()
        for group in root.children():
            root.removeChildNode(group)

        # Remove all user settings
        self.settings.remove("token")
        self.settings.remove("url")
        self.settings.remove("username")
        self.validLogin = False
        self.dockwidget.close()

        # add a delay to allow the layers to be removed before the login popup is shown
        QtTest.QTest.qWait(1000)
        self.loginPopup = Login(self.iface, self.settings)
        self.loginPopup.finished.connect(self.onLoginFinished)
        self.loginPopup.show()
