# -*- coding: utf-8 -*-
"""
/***************************************************************************
                                 A QGIS plugin
 This plugin gives access to Israeli open spatial data sources
                             -------------------
        begin                : 2020-04-01
        copyright            : (C) 2020 by Kaplan Open Source Consulting Inc.
        email                : dror@kaplanopensource.co.il
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 3 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt5.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QUrl, QByteArray
from PyQt5.QtGui import QIcon, QPixmap, QDesktopServices
from PyQt5.QtWidgets import QAction, QTreeWidgetItem, QAbstractItemView, QTreeWidget
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkProxy
import requests as rq
import json
import zlib
import codecs
import os # This is is needed in the pyqgis console also
from qgis.core import QgsVectorLayer, QgsRasterLayer, Qgis, QgsProject, QgsLayerTreeLayer, QgsLayerTreeGroup, QgsSettings,QgsNetworkAccessManager,QgsError
# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .opendata_loader_dialog import opendata_loaderDialog, UserServiceDialog
#from .data_sources_list import *
import os.path
import io
import zipfile
import tempfile
from qgis.gui import *

class OpenDataLoader:
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
        self.mb = self.iface.messageBar()
        self.dlg = opendata_loaderDialog()
        # added form for adding user services
        self.formdlg = UserServiceDialog()
        self.populateExistingUserServices()
        self.curMode = 2
        self.headers = {"Agent":"QGIS"}
        
        #self.dlg.treeView.headerItem().setText(0, "Gov Orgs")
        
        
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        f = open(os.path.join(self.plugin_dir,"metadata.txt"), "r")
        lines = f.readlines()
        self.version = 'v'+ [line for line in lines if line.startswith("version")][0][:-1].split("=")[1]
        # initialize locale
        """
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'opendata_loader_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)
        """
        # Declare instance attributes
        self.actions = []
        
        self.menu = self.tr(u'&Israeli Open Data Sources')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

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
        return QCoreApplication.translate('opendata_loader', message)


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
            self.iface.addPluginToWebMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/israeli_opendata_loader/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Add Israeli open data'),
            callback=self.run,
            parent=self.iface.mainWindow())
        
        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginWebMenu(
                self.tr(u'&Israeli Open Data Sources'),
                action)
            self.iface.removeToolBarIcon(action)
            
    def openRegisterButton(self):
        QDesktopServices.openUrl(QUrl('https://kaplanopensource.co.il/services/qgis'))

    def clearSelection(self):
        
        selectedAll = []
        selectedAll.append(self.dlg.govTree.selectedItems())
        selectedAll.append(self.dlg.muniTree.selectedItems())
        selectedAll.append(self.dlg.orgTree.selectedItems())
        selectedAll.append(self.dlg.opendataTree.selectedItems())
        selectedAll.append(self.dlg.userServicesTree.selectedItems())
        selected = []
        for i in selectedAll:
            selected += i
        
        for item in selected:
            item.setSelected(False)

        self.dlg.govTree.clearSelection()
        self.dlg.muniTree.clearSelection()
        self.dlg.orgTree.clearSelection()
        self.dlg.opendataTree.clearSelection()
        self.dlg.userServicesTree.clearSelection()
            
        
    def setSelectionType(self):
        
        #self.dlg.selectionButton.setText("Single")
        if self.curMode == 2:
            self.dlg.govTree.setSelectionMode(QAbstractItemView.SingleSelection)
            self.dlg.muniTree.setSelectionMode(QAbstractItemView.SingleSelection)  
            self.dlg.orgTree.setSelectionMode(QAbstractItemView.SingleSelection)
            self.dlg.opendataTree.setSelectionMode(QAbstractItemView.SingleSelection)
            self.dlg.userServicesTree.setSelectionMode(QAbstractItemView.SingleSelection)
            self.dlg.selectionButton.setText("בחירה בודדת")
            self.curMode = 1
        elif self.curMode == 1:
            self.dlg.govTree.setSelectionMode(QAbstractItemView.MultiSelection)
            self.dlg.muniTree.setSelectionMode(QAbstractItemView.MultiSelection)  
            self.dlg.orgTree.setSelectionMode(QAbstractItemView.MultiSelection)
            self.dlg.opendataTree.setSelectionMode(QAbstractItemView.MultiSelection)
            self.dlg.userServicesTree.setSelectionMode(QAbstractItemView.MultiSelection)
            self.dlg.selectionButton.setText("בחירה מרובה")
            self.curMode = 2
        
    def getOrgs(self, root):
        baseObject = {}
        files = os.listdir(root)
        for file in files:
            if file.endswith('.json'):
                org = os.path.splitext(file)
                path = os.path.join(root, file)
                with open(path, encoding='utf-8') as json_file:
                    baseObject[org] = json.load(json_file)
        return baseObject   


    def buildDataList(self):
        
        try:
            dataList = json.loads(codecs.decode(self.checkCredentials().decode('utf-8'),'rot_13'))

            if dataList:
                if dataList['type'] == 'paid':
                    self.dlg.teaserGov.hide()
                    self.dlg.teaserMuni.hide()
                    self.dlg.versionLabel.setText('משתמש משלם')
                else:
                    self.dlg.versionLabel.setText('משתמש רשום (ללא תשלום)')

                if dataList['type'] == 'free':
                    self.dlg.teaserGov.hide()
                    self.dlg.teaserMuni.show()
                    self.dlg.teaserMuni.setText('זמין למשתמשים משלמים')

                if dataList['type'] == 'overLimit':
                    self.mb.pushWarning('אזהרה', 'הגעת למגבלת השימוש החודשית, ניתן ליצור קשר להרחבת השימוש')
                    self.dlg.teaserGov.show()
                    self.dlg.teaserGov.setText('עברת את מגבלת השימוש החודשית')
                    self.dlg.teaserMuni.show()
                    self.dlg.teaserMuni.setText('זמין למשתמשים משלמים')

                if dataList['type'] == 'notRegistered':
                    self.dlg.versionLabel.setText('משתמש לא רשום')
                    self.mb.pushInfo('לידיעתך', 'עליך להירשם על מנת לראות ארגונים ממשלתיים')
                    self.dlg.teaserGov.show()
                    self.dlg.teaserGov.setText('זמין למשתמשים רשומים')
                    self.dlg.teaserMuni.show()
                    self.dlg.teaserMuni.setText('זמין למשתמשים משלמים')
                    self.dlg.teaserUserServices.show()
                    self.dlg.teaserUserServices.setText('זמין למשתמשים רשומים')
                else:
                    self.dlg.loginsCounter.setText('החודש התחברת\n{} פעמים'.format(dataList['logins']))

                if 'orgName' in dataList:
                    if len(dataList['orgName']) > 0:
                        if 'userServices' in dataList['data'] and len(dataList['data']['userServices']) > 0:
                            self.dlg.teaserUserServices.hide()
                        else:
                            self.dlg.teaserUserServices.setText('יש להוסיף סרביס ראשון\n  על מנת לפתוח את הטאב')
                    else:
                        self.dlg.teaserUserServices.setText('מוזמנים לפנות אלינו \n על מנת לפתוח את האפשרות')

        except:
            self.mb.pushMessage('תקלת חיבור','נראה שיש תקלה בחיבור לשרת, נא לדווח על השגיאה',Qgis.Warning, 5)
            raise Exception
                
        return dataList['data']

    def getWithProxy(self, url, headers=None):
        s = QgsSettings()
        proxy = QNetworkProxy()
        proxyEnabled = s.value("proxy/proxyEnabled", "")
        proxyType = s.value("proxy/proxyType", "" )
        proxyHost = s.value("proxy/proxyHost", "" )
        proxyPort = s.value("proxy/proxyPort", "" )
        proxyUser = s.value("proxy/proxyUser", "" )
        proxyPassword = s.value("proxy/proxyPassword", "" )
        if not self.QNM:
            self.QNM = QgsNetworkAccessManager()
        self.QNM.setTimeout(20000)
        if proxyEnabled == "true":
            proxy.setType(QNetworkProxy.HttpProxy)
            proxy.setHostName(proxyHost)
            if proxyPort != "":
                proxy.setPort(int(proxyPort))
            proxy.setUser(proxyUser)
            proxy.setPassword(proxyPassword)
            QNetworkProxy.setApplicationProxy(proxy)
            self.QNM.setupDefaultProxyAndCache()
            self.QNM.setFallbackProxyAndExcludes(proxy,[""],[""])
        request = QNetworkRequest(QUrl(url))
        if headers:
            for header in headers.keys():
                request.setRawHeader(header, headers[header])
        reply = self.QNM.blockingGet(request)
        return reply.content().data()

    def postWithProxy(self, url, headers=None, data=None):
        s = QgsSettings()
        proxy = QNetworkProxy()
        proxyEnabled = s.value("proxy/proxyEnabled", "")
        proxyType = s.value("proxy/proxyType", "" )
        proxyHost = s.value("proxy/proxyHost", "" )
        proxyPort = s.value("proxy/proxyPort", "" )
        proxyUser = s.value("proxy/proxyUser", "" )
        proxyPassword = s.value("proxy/proxyPassword", "" )
        self.QNM = QgsNetworkAccessManager()
        self.QNM.setTimeout(20000)
        if proxyEnabled == "true":
            proxy.setType(QNetworkProxy.HttpProxy)
            proxy.setHostName(proxyHost)
            if proxyPort != "":
                proxy.setPort(int(proxyPort))
            proxy.setUser(proxyUser)
            proxy.setPassword(proxyPassword)
            QNetworkProxy.setApplicationProxy(proxy)
            self.QNM.setupDefaultProxyAndCache()
            self.QNM.setFallbackProxyAndExcludes(proxy,[""],[""])
        request = QNetworkRequest(QUrl(url))
        if headers:
            for header in headers.keys():
                headerKey = QByteArray()
                headerKey.append(header)
                headerVal = QByteArray()
                headerVal.append(headers[header])
                request.setRawHeader(headerKey, headerVal)
        postdata = QByteArray()
        if data:
            for key in data.keys():
                postdata.append(key).append('=').append(data[key]).append("&")
        return self.QNM.blockingPost(request, postdata)

    def loadLayers(self):
        """
        Initial list filling function
        """
        self.dlg.govTree.clear()
        self.dlg.muniTree.clear()
        self.dlg.orgTree.clear()
        self.dlg.opendataTree.clear()
        self.dlg.userServicesTree.clear()
        
        self.dlg.govTree.setSelectionMode(QAbstractItemView.MultiSelection)  
        self.dlg.muniTree.setSelectionMode(QAbstractItemView.MultiSelection)  
        self.dlg.orgTree.setSelectionMode(QAbstractItemView.MultiSelection)
        self.dlg.opendataTree.setSelectionMode(QAbstractItemView.MultiSelection)
        self.dataList = self.buildDataList()
        if "govOrgs" in self.dataList and len(self.dataList["govOrgs"]) > 0:
            orgI = -1
            for (orgI, org) in enumerate(self.dataList["govOrgs"].values()):
                orgItem = QTreeWidgetItem(None, [org["hebName"]])
                layers = org["layers"]
                for layer in layers:
                    TreeItemName = layer["layerHebName"]
                    layerItem = QTreeWidgetItem(orgItem,[TreeItemName])
                    self.defineLayerItemIcon(layer,layerItem)
                self.dlg.govTree.insertTopLevelItems(orgI, [orgItem])
                self.dlg.govTree.sortItems(0,Qt.AscendingOrder)
        
        if "municipalities" in self.dataList and len(self.dataList["municipalities"]) > 0:
            munisI = -1
            for (munisI, muni) in enumerate(self.dataList["municipalities"].values()):
                muniItem = QTreeWidgetItem(None, [muni["hebName"]])
                layers = muni["layers"]
                for layer in layers:
                    TreeItemName = layer["layerHebName"]
                    layerItem = QTreeWidgetItem(muniItem,[TreeItemName])
                    self.defineLayerItemIcon(layer,layerItem)

                self.dlg.muniTree.insertTopLevelItems(munisI, [muniItem])
                self.dlg.muniTree.sortItems(0,Qt.AscendingOrder)

        if "NGO" in self.dataList and len(self.dataList["NGO"]) > 0:
            NGOI = -1
            for (NGOI, ngo) in enumerate(self.dataList["NGO"].values()):
                NGOItem = QTreeWidgetItem(None, [ngo["hebName"]])
                layers = ngo["layers"]
                for layer in layers:
                    TreeItemName = layer["layerHebName"]
                    layerItem = QTreeWidgetItem(NGOItem,[TreeItemName])
                    self.defineLayerItemIcon(layer,layerItem)

                self.dlg.orgTree.insertTopLevelItems(NGOI, [NGOItem])
                self.dlg.orgTree.sortItems(0,Qt.AscendingOrder)

        if "ods" in self.dataList and len(self.dataList["ods"]) > 0:
            odsI = -1
            for (odsI, ods) in enumerate(self.dataList["ods"].values()):
                odsItem = QTreeWidgetItem(None, [ods["hebName"]])
                layers = ods["layers"]
                for layer in layers:
                    TreeItemName = layer["layerHebName"]
                    layerItem = QTreeWidgetItem(odsItem,[TreeItemName])
                    self.defineLayerItemIcon(layer,layerItem)
                self.dlg.opendataTree.insertTopLevelItems(odsI, [odsItem])
                self.dlg.opendataTree.sortItems(0,Qt.AscendingOrder)

        if "userServices" in self.dataList and len(self.dataList["userServices"]) > 0:
            self.dlg.tabWidget.setTabEnabled(4,True)
            for (LayerI, layer) in enumerate(self.dataList["userServices"]):
                layerItemName = layer['layerHebName']
                layerItem = QTreeWidgetItem(None,[layerItemName])
                self.defineLayerItemIcon(layer,layerItem)
                self.dlg.userServicesTree.insertTopLevelItems(LayerI, [layerItem])

    def checkCredentials(self):
        try:
            userEmail = self.dlg.emailInput.text()
            userKey = self.dlg.keyInput.text()
            userCreds = {'email':userEmail, 'key':userKey}
            self.reply = self.postWithProxy("https://qgis-plugin.kaplanopensource.co.il/json", self.headers, userCreds)
            obj = zlib.decompress(self.reply.content())
            self.storeCredentials()
        except Exception as e:
            error = QgsError("התרחשה תקלה בחיבור נא להעביר את ההודעה המצורפת","תקלה")
            error.append(str(e),"תקלת חיבור")
            QgsErrorDialog(error,"network error").show(error,"Israeli Open Data Loader Network Error")
            raise Exception
        return obj
        
    def storeCredentials(self):
        s = QgsSettings()
        userEmail = self.dlg.emailInput.text()
        userKey = self.dlg.keyInput.text()
        s.setValue('opendata_loader/email', userEmail)
        s.setValue('opendata_loader/key', userKey)
    
    def loadCredentials(self):
        s = QgsSettings()
        userEmail = s.value('opendata_loader/email','')
        userKey = s.value('opendata_loader/key','')
        self.dlg.emailInput.setText(userEmail)
        self.dlg.keyInput.setText(userKey)

    def addExisting(self):
        data = self.formdlg.ExistingLayers.currentData()
        data['layerUrl'] = bytearray(data['layerUrl'],'utf-8').hex()
        s = QgsSettings()
        userEmail = s.value('opendata_loader/email','')
        userKey = s.value('opendata_loader/key','')
        userCreds = {'email':userEmail, 'key':userKey, 'layer': json.dumps(data, ensure_ascii=False), 'type': 'insert'}
        self.reply = self.postWithProxy("https://qgis-plugin.kaplanopensource.co.il/service", self.headers, userCreds)
        if self.reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) == 200:
            self.loadLayers()
        else:
            self.mb.pushMessage('תקלה','התרחשה תקלה בהוספת השכבה',Qgis.Warning, 5)

    def defineLayerItemIcon(self,layer,layerItem):
        if layer["connectionType"] == 'GeoJSON' or layer["connectionType"] == 'shp':
            layerItem.setIcon(0,QIcon(":images/themes/default/mIconVector.svg"))
        if layer["connectionType"] == "connections-arcgismapserver" or layer["connectionType"] == "wms" or layer["connectionType"] == "connections-wms":
            layerItem.setIcon(0,QIcon(":images/themes/default/mIconWms.svg"))
        if layer["connectionType"] == "connections-arcgisfeatureserver" or layer["connectionType"] == "wfs" or layer["connectionType"] == "connections-wfs":
            layerItem.setIcon(0,QIcon(":images/themes/default/mIconWfs.svg"))

    def removeDuplicateUserServices(self, userServices):
        seen = set()
        result = []
        for layer in userServices:
            key = (layer['layerHebName'], layer['layerUrl'])
            if key in seen:
                continue

            result.append(layer)
            seen.add(key)
        return result

    def filterServices(self, layer):
        providerType = layer.providerType()
        acceptedTypes = ['wms','WFS', 'arcgismapserver', 'arcgisfeatureserver']
        if providerType in acceptedTypes:
            return True

    def populateExistingUserServices(self):
        self.formdlg.ExistingLayers.clear()
        self.formdlg.ExistingLayers.line_edit = self.formdlg.ExistingLayers.lineEdit()
        self.formdlg.ExistingLayers.line_edit.setAlignment(Qt.AlignCenter)
        self.formdlg.ExistingLayers.line_edit.setReadOnly(True)

        mapLayers = QgsProject.instance().mapLayers().values()
        mapServices = [{'layerHebName':layer.name(),'layerUrl':layer.source(),'tempLayerType':layer.providerType(),'layerCRS':layer.crs().authid() } for layer in mapLayers if self.filterServices(layer)]
        mapServices = sorted(mapServices, key=lambda k: k['layerHebName'])
        for layer in mapServices:
            if layer['tempLayerType'] == 'wms' or layer['tempLayerType'] == 'arcgismapserver':
                icon = QIcon(":images/themes/default/mIconWms.svg")
            else:
                icon = QIcon(":images/themes/default/mIconWfs.svg")
            name = layer['layerHebName']
            self.formdlg.ExistingLayers.addItem(icon,name, userData = layer)
        self.formdlg.ExistingLayers.insertSeparator(len(mapServices))
        s = QgsSettings()
        keys = s.allKeys()
        mapserverKeys = [key for key in keys if key.startswith('qgis/connections-arcgismapserver') or key.startswith('qgis/connections-wms')]
        featureserverKeys = [key for key in keys if key.startswith('qgis/connections-arcgisfeatureserver') or key.startswith('qgis/connections-wfs')]
        mapserverservices = list(set([key.split('/')[2] for key in mapserverKeys]))
        mapserverservices.sort()
        for service in mapserverservices:
            selectedKeys = [key for key in mapserverKeys if key.split('/')[2] == service]
            layerName = service
            layerUrl = ''
            for key in selectedKeys:
                if key.endswith('url'):
                    layerUrl = s.value(key,'')
                    continue
                else:
                    pass
            #layerUrl = s.value([key for key in selectedKeys if key.endswith('url')][0],'')
            tempLayerType = 'arcgismapserver'
            connectionType = 'connections-arcgismapserver'
            layer =  {
                        "connectionType": connectionType,
                        "layerEngName": layerName,
                        "layerHebName": layerName,
                        "layerUrl":layerUrl,
                        "tempLayerType": tempLayerType
                    }
            if len(layerUrl) > 1:
                self.formdlg.ExistingLayers.addItem(QIcon(":images/themes/default/mIconWms.svg"),service, userData = layer)

        featureserverservices = list(set([key.split('/')[2] for key in featureserverKeys]))
        featureserverservices.sort()
        for service in featureserverservices:
            selectedKeys = [key for key in featureserverKeys if key.split('/')[2] == service]
            layerName = service
            layerUrl = ''
            for key in selectedKeys:
                if key.endswith('url'):
                    layerUrl = s.value(key,'')
                    continue
                else:
                    pass
            #layerUrl = s.value([key for key in selectedKeys if key.endswith('url')][0],'')
            tempLayerType = 'arcgisfeatureserver'
            connectionType = 'connections-arcgisfeatureserver'
            layer =  {
                        "connectionType": connectionType,
                        "layerEngName": layerName,
                        "layerHebName": layerName,
                        "layerUrl":layerUrl,
                        "tempLayerType": tempLayerType
                    }
            if len(layerUrl) > 1:
                self.formdlg.ExistingLayers.addItem(QIcon(":images/themes/default/mIconWfs.svg"), service, userData = layer)

    def openUserServicesForm(self):
        self.populateExistingUserServices()
        self.formdlg.open()

    def addUserService(self):
        layerName = self.formdlg.UserLayerHebName.text()
        layerURL = bytearray(self.formdlg.UserLayerURL.text(),'utf-8').hex()
        layer = {"layerHebName": layerName,
            "layerUrl" : layerURL
            }
        s = QgsSettings()
        userEmail = s.value('opendata_loader/email','')
        userKey = s.value('opendata_loader/key','')
        userCreds = {'email':userEmail, 'key':userKey, 'layer': json.dumps(layer, ensure_ascii=False), 'type': 'insert'}
        self.reply = self.postWithProxy("https://qgis-plugin.kaplanopensource.co.il/service", self.headers, userCreds)
        if self.reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) == 200:
            self.loadLayers()
        else:
            self.mb.pushMessage('תקלה','התרחשה תקלה בהוספת השכבה',Qgis.Warning, 5)

    def addPluginServiceToUserServices(self):
        if self.curMode == 1:
            selectedItems = self.dlg.tabWidget.currentWidget().findChildren(QTreeWidget)[0].selectedItems()
            if len(selectedItems) > 0:
                selectedItem = self.dlg.tabWidget.currentWidget().findChildren(QTreeWidget)[0].selectedItems()[0]
            else:
                self.mb.pushInfo('',"יש לבצע בחירה על מנת להוסיף שירותים")
                return
        else:
            self.mb.pushInfo('', 'ניתן להוסיף רק שירות אחד בכל בחירה')
            return
        if self.dlg.tabWidget.currentWidget().objectName() != 'userServicesTab':
            if selectedItem.parent() is None:
                self.mb.pushWarning('Warning',"הוספה של ארגונים שלמים אינה נתמכת")
                return

            parent = selectedItem.parent()
            parent_text = parent.text(0)
            layers = []
            for muni in self.dataList["municipalities"].values():
                if parent_text == muni["hebName"]:
                    layers.extend(muni["layers"])

            for govOrg in self.dataList["govOrgs"].values():
                if parent_text == govOrg["hebName"]:
                    layers.extend(govOrg["layers"])

            for org in self.dataList["NGO"].values():
                if parent_text == org["hebName"]:
                    layers.extend(org["layers"])

            for ods in self.dataList["ods"].values():
                if parent_text == ods["hebName"]:
                    layers.extend(ods["layers"])

            for layer in layers:
                if selectedItem.text(0) == layer["layerHebName"]:
                    selectedLayer = layer

            layerName = parent_text + ' - ' + selectedLayer["layerHebName"]
            layerURL = bytearray(selectedLayer["layerUrl"],'utf-8').hex()

            layer = {
                "layerHebName": layerName,
                "layerUrl" : layerURL,
                "tempLayerType": selectedLayer['tempLayerType']
            }
            s = QgsSettings()
            userEmail = s.value('opendata_loader/email','')
            userKey = s.value('opendata_loader/key','')
            userCreds = {'email':userEmail, 'key':userKey, 'layer': json.dumps(layer, ensure_ascii=False), 'type': 'insert'}
            self.reply = self.postWithProxy("https://qgis-plugin.kaplanopensource.co.il/service", self.headers, userCreds)
            if self.reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) == 200:
                self.loadLayers()
            else:
                self.mb.pushMessage('תקלה','התרחשה תקלה בהוספת השכבה',Qgis.Warning, 5)

    def addTempArcgisFeature(self, layer, crs=None, group=False, allGroup=None):
        """
        :param crs: A coordinate reference system, preferebly using EPSG codes.
            for example: 'EPSG:3857'
        """
        url = layer["layerUrl"]
        metdataUrl = "{}?f=pjson".format(url)
        try:
            data = json.loads(self.getWithProxy(metdataUrl))
            if 'error' in data:
                self.mb.pushCritical('Error',"The layer is not available, please report layer: \"{}\" is not available".format(layer["layerHebName"]))
                return "error"
        except rq.exceptions.SSLError:
            self.mb.pushCritical('SSL Error'," could not get layers from url")
            return "error"
        else:
            if crs is None:
                spatialReference = data.get("spatialReference", {})
                latestWkid = spatialReference.get("latestWkid", 3857)
                crs = "EPSG:{}".format(latestWkid)
            if "layers" in data:
                layers = data["layers"]
                if len(layers) == 1:
                    l = layers[0]
                    layerUrl = "crs='{}' url='{}/{}'".format(crs, url,l["id"])
                    vlayer = QgsVectorLayer(layerUrl, l["name"], "arcgisfeatureserver")
                    if group:
                        QgsProject.instance().addMapLayer(vlayer, False)
                        allGroup.addLayer(vlayer)
                    else:
                        QgsProject.instance().addMapLayer(vlayer)
                else:
                    groupName=layer["layerHebName"]
                    #root = QgsProject.instance().layerTreeRoot()
                    layerTree = self.iface.layerTreeCanvasBridge().rootGroup()
                    group1 = QgsLayerTreeGroup(groupName, False)
                    group0 = group1
                    if group:
                        allGroup.insertChildNode(-1,group0)
                    else:
                        layerTree.insertChildNode(0, group1)
                    for l in layers:
                        if 'type' in l and l["type"] == 'Group Layer':
                            if l == layers[0]:
                                continue
                            else:
                                group1 = QgsLayerTreeGroup(l["name"], False)
                                group0.insertChildNode(-1,group1)
                        layerUrl = "crs='{}' url='{}/{}'".format(crs, url,l["id"])
                        vlayer = QgsVectorLayer(layerUrl, l["name"], "arcgisfeatureserver")
                        QgsProject.instance().addMapLayer(vlayer, False)
                        group0.addLayer(vlayer)
                    #group = root.addGroup(groupName)
            else:
                layerUrl = "crs='{}' url='{}'".format(crs, url)
                vlayer = QgsVectorLayer(layerUrl,  layer["layerHebName"], "arcgisfeatureserver")
                if group:
                    QgsProject.instance().addMapLayer(vlayer, False)
                    allGroup.addLayer(vlayer)
                else:
                    QgsProject.instance().addMapLayer(vlayer)
            return data

    def addTempArcgisMap(self, layer, crs=None, group=False, allGroup=None):
        """
        :param url: arcgis server mapserver address.
        
        :param crs: A coordinate reference system, preferebly using EPSG codes.
            for example: 'EPSG:3857'
        """
        url = layer["layerUrl"]
        metdataUrl = "{}?f=pjson".format(url)
        try:
            data = json.loads(self.getWithProxy(metdataUrl))
            if 'error' in data:
                self.mb.pushCritical('Error',"The layer is not available, please report layer: \"{}\" is not available".format(layer["layerHebName"]))
                return "error"
        except rq.exceptions.SSLError:
            self.mb.pushCritical('SSL Error'," could not get layers from url")
            return "error"
        else:
            if crs is None:
                spatialReference = data.get("spatialReference", {})
                latestWkid = spatialReference.get("latestWkid", 3857)
                crs = "EPSG:{}".format(latestWkid)
                
            if "layers" in data:
                layers = data["layers"]
                if len(layers) == 1:
                    l = layers[0]    
                    layerUrl = "crs='{}' format='PNG32' layer='{}' url='{}'".format(crs, l["id"], url)
                    rlayer = QgsRasterLayer(layerUrl, l["name"], "arcgismapserver")
                    if group:
                        QgsProject.instance().addMapLayer(rlayer, False)
                        allGroup.addLayer(rlayer)
                    else:
                        QgsProject.instance().addMapLayer(rlayer)
                else:
                    groupName=layer["layerHebName"]
                    #root = QgsProject.instance().layerTreeRoot()
                    layerTree = self.iface.layerTreeCanvasBridge().rootGroup()
                    groupLayer = QgsLayerTreeGroup(groupName, False)
                    group0 = groupLayer
                    if group:
                        allGroup.insertChildNode(-1,group0)
                    else:
                        layerTree.insertChildNode(0, group0)
                    for l in layers:
                        if 'type' in l and l["type"] == 'Group Layer':
                            if l == layers[0]:
                                continue
                            else:
                                group = QgsLayerTreeGroup(l["name"], False)
                                group0.insertChildNode(-1,group)
                        layerUrl = "crs='{}' format='PNG32' layer='{}' url='{}'".format(crs, l["id"], url)
                        rlayer = QgsRasterLayer(layerUrl, l["name"], "arcgismapserver")
                        QgsProject.instance().addMapLayer(rlayer, False)
                        group0.addLayer(rlayer)
            else:
                layerUrl = "crs='{}' format='PNG32' url='{}'".format(crs, url)
                rlayer = QgsRasterLayer(layerUrl,  layer["layerHebName"], "arcgismapserver")
                if group:
                    QgsProject.instance().addMapLayer(rlayer, False)
                    allGroup.addLayer(rlayer)
                else:
                    QgsProject.instance().addMapLayer(rlayer)

    def esriJsonToGeoJson(self, url):
        base_object = {'type': "FeatureCollection",'features':[]}
        r = json.load(self.getWithProxy(metdataUrl))
        esriJson = r.json()
        geomType = esriJson['geometryType']
        if 'spatialRefernce' in esriJson:
            wkid = esriJson['spatialReference']['wkid']
        else:
            wkid = False
        #wkid = esriJson.get('spatialReference'.{}).get('wkid', False)
        if wkid and wkid != 4326:
            base_object["crs"] = {"type": "link",
                          "properties": {
                            "href": "https://www.spatialreference.org\
                            /ref/esri/{}/proj4/".format(wkid),
                            "type": "proj4"}}
        if geomType == 'esriGeometryPolyline':
            for f in esriJson["features"]:
                feature = {'type' : 'Feature','properties' : {},'geometry' : {}}
                paths = f['geometry']['paths']
                #if any([len(p) > 1 for p in paths]):
                #    feature['geometry']['type'] = 'MultiLineString'
                #else:
                #    feature['geometry']['type'] = 'LineString'
                feature['geometry']['type'] = \
                    'MultiLineString' if any([len(p) > 1 for p in paths]) else 'LineString'
                feature['geometry']['coordinates'] = paths

        elif geomType == 'esriGeometryPoint':
            for f in esriJson["features"]:
                feature = {'type' : 'Feature','properties' : {},'geometry' : {}}
                feature['geometry']['type'] = 'Point'
                geom = [f['geometry']['x'],f['geometry']['y']]
                feature['geometry']['coordinates'] = geom

        elif geomType == 'esriGeometryMultipoint':
            for f in esriJson["features"]:
                feature = {'type' : 'Feature','properties' : {},'geometry' : {}}
                feature['geometry']['type'] = 'MultiPoint'
                geometries = f['geometries']
                points = []
                for geom in geometries:
                    points.extend(geom['points'])
                feature['geometry']['coordinates'] = points

        elif geomType == 'esriGeometryPolygon':
            for f in esriJson["features"]:
                feature = {'type' : 'Feature','properties' : {},'geometry' : {}}
                rings = f['geometry']['rings']
                #paths = f['geometry']['paths']
                #if any([len(r) > 1 for r in rings]):
                #    feature['geometry']['type'] = 'MultiPolygon'
                #else:
                #    feature['geometry']['type'] = 'Polygon'
                feature['geometry']['type'] = \
                    'MultiPolygon' if any([len(p) > 1 for p in rings]) else 'Polygon'
                feature['geometry']['coordinates'] = [rings]
                
        if 'attributes' in f:
                feature['properties'] = f['attributes']
                base_object['features'].append(feature)
        return base_object

    def addTempShapefile(self, layer, group=False, allGroup=None):
        url = layer["layerUrl"]
        request = QNetworkRequest(QUrl(url))
        if "header" in layer:
            request.setRawHeader("user-agent", layer["header"])
        response = self.QNM.blockingGet(request)
        with zipfile.ZipFile(io.BytesIO(response.content())) as thezip:
            f = tempfile.TemporaryDirectory()
            if not os.path.isdir(f.name):
                os.mkdir(f.name)
            thezip.extractall(path=f.name)
            filenames = os.listdir(f.name)
            for name in filenames:
                if name.endswith(".shp"):
                    file = os.path.join(f.name,name)
                    layerName = os.path.splitext(name)[0]
                    vlayer=QgsVectorLayer(file,layerName,layer["tempLayerType"])
                    if group:
                        QgsProject.instance().addMapLayer(vlayer, False)
                        allGroup.addLayer(vlayer)
                    else:
                        QgsProject.instance().addMapLayer(vlayer)

    def addWMSService(self, layer, group=False, allGroup=None):
        rlayer = QgsRasterLayer(layer["layerUrl"], layer["layerHebName"], layer["tempLayerType"])
        if group:
            QgsProject.instance().addMapLayer(rlayer, False)
            allGroup.addLayer(rlayer)
        else:
            QgsProject.instance().addMapLayer(rlayer)
            layerTree = self.iface.layerTreeCanvasBridge().rootGroup()
            layerTree.insertChildNode(0, QgsLayerTreeLayer(rlayer))

    def addWMSService(self, layer, group=False, allGroup=None):
        rlayer = QgsRasterLayer(layer["layerUrl"], layer["layerHebName"], layer["tempLayerType"])
        if group is not False:
            QgsProject.instance().addMapLayer(rlayer, False)
            allGroup.addLayer(rlayer)
        else:
            QgsProject.instance().addMapLayer(rlayer)

    def addGeoserverGeoJson(self, layer, group=False, allGroup=None):
        name = layer["layerHebName"]
        if "layerUrl2" in layer:
            url = layer["layerUrl2"]
            type = "ogr"
            vlayer = QgsVectorLayer(url,name,type)
            if group:
                QgsProject.instance().addMapLayer(vlayer, False)
                if allGroup:
                    allGroup.addLayer(vlayer)
            else:
                QgsProject.instance().addMapLayer(vlayer)
        else:
            self.mb.pushCritical('Error',"Unable to load WMS as vector layer")

    def addTempGeoJson(self, layer, group=False, allGroup=None):
        name = layer["layerHebName"]
        url = layer["layerUrl"]
        type = layer["tempLayerType"]
        vlayer = QgsVectorLayer(url,name,type)
        if group:
            QgsProject.instance().addMapLayer(vlayer, False)
            if allGroup:
                allGroup.addLayer(vlayer)
        else:
            QgsProject.instance().addMapLayer(vlayer)
    
    def loadTemps(self):
        """
        loading temporary layers to the project
        """
        sending_button = self.dlg.sender()
        group = self.dlg.addAsGroup.isChecked()
        
        self.selectedItemsAll = []
        self.selectedItemsAll.append(self.dlg.govTree.selectedItems())
        self.selectedItemsAll.append(self.dlg.muniTree.selectedItems())
        self.selectedItemsAll.append(self.dlg.orgTree.selectedItems())
        self.selectedItemsAll.append(self.dlg.opendataTree.selectedItems())
        if self.curMode == 1:
            self.selectedItemsAll = []
            self.selectedItemsAll.append(self.dlg.tabWidget.currentWidget().findChildren(QTreeWidget)[0].selectedItems())

        selectedItems = []
        for i in self.selectedItemsAll:
            selectedItems += i
        selectedLayers = []
        layers = []
        for item in selectedItems:
            if item.parent() is None:
                self.mb.pushWarning('Warning',"Adding entire organizations is not supported")
                continue
            else:
                parent = item.parent()

            parent_text = parent.text(0)

            for muni in self.dataList["municipalities"].values():
                if parent_text == muni["hebName"]:
                    layers.extend(muni["layers"])

            for govOrg in self.dataList["govOrgs"].values():
                if parent_text == govOrg["hebName"]:
                    layers.extend(govOrg["layers"])

            for org in self.dataList["NGO"].values():
                if parent_text == org["hebName"]:
                    layers.extend(org["layers"])

            for ods in self.dataList["ods"].values():
                if parent_text == ods["hebName"]:
                    layers.extend(ods["layers"])

            for layer in layers:
                    if item.text(0) == layer["layerHebName"]:
                        selectedLayers.append(layer)

        seen = set()
        new_l = []
        for d in selectedLayers:
            t = tuple(d.items())
            if t not in seen:
                seen.add(t)
                new_l.append(d)
        selectedLayers = new_l
        
        if "userServices" in self.dataList:
            s = QgsSettings()
            userServices = self.dataList["userServices"]
            for i in self.dlg.userServicesTree.selectedItems():
                for layer in userServices:
                    if i.text(0) == layer['layerHebName']:
                        selectedLayers.append(layer)
        
        allGroup = QgsLayerTreeGroup("Group", False)
        if group is not False:
            layerTree = self.iface.layerTreeCanvasBridge().rootGroup()
            layerTree.insertChildNode(0, allGroup)
        if sending_button.objectName() == "addToMapV":
            self.drawTempVLayer(selectedLayers, group, allGroup)
        elif sending_button.objectName() == "addToMapR":
            self.drawTempRLayer(selectedLayers, group, allGroup)
        selectedLayers =[]
        self.clearSelection()
        allGroup = None
    
    def drawTempVLayer(self, selectedLayers, group, allGroup):
        """
        Draw temporary vector layers
        """
        layersAdded = 0
        for layer in selectedLayers:
            layerUrl = layer["layerUrl"]
            layerCRS = layer["layerCRS"] if "layerCRS" in layer else None
            tempLayerType = layer["tempLayerType"]
            connectionType = layer["connectionType"]
            if connectionType == 'connections-arcgisfeatureserver':
                self.addTempArcgisFeature(layer,layerCRS, group, allGroup)
                layersAdded += 1
            elif connectionType == 'connections-arcgismapserver':
                self.mb.pushWarning('Warning', 'Rendering Arcgis MapServer layer as features might not work')
                self.addTempArcgisFeature(layer,layerCRS, group, allGroup)    
                layersAdded += 1
            elif connectionType == 'GeoJSON':
                self.addTempGeoJson(layer, group, allGroup)
                layersAdded += 1
            elif connectionType == 'shp':
                self.addTempShapefile(layer, group, allGroup)
                layersAdded += 1
            elif connectionType == 'esriJson':
                gj = self.esriJsonToGeoJson(layerUrl)
                layer['layerUrl'] = json.dumps(gj)
                self.addTempGeoJson(layer, group, allGroup)
                layersAdded += 1
            elif connectionType == 'wms':
                self.addGeoserverGeoJson(layer, group, allGroup)
                layersAdded += 1
            else:
                self.mb.pushCritical('Error',"Unrecognised layer type {}".format(tempLayerType))
                raise TypeError("Unrecognised layer type {}".format(tempLayerType))
        if layersAdded > 0:
            self.mb.pushInfo('{} Layers added'.format(str(layersAdded)),"")
        else:
            self.mb.pushInfo('No layers to add',"")
        self.clearSelection()
    
    def drawTempRLayer(self, selectedLayers, group, allGroup):
        """
        Draw temporary raster layers
        """
        layersAdded = 0
        for layer in selectedLayers:
            layerUrl = layer["layerUrl"]
            layerCRS = layer["layerCRS"] if "layerCRS" in layer else None
            tempLayerType = layer["tempLayerType"]
            if tempLayerType == 'arcgisfeatureserver':
                layersAdded += 1
                self.mb.pushWarning('Warning', 'Rendering Arcgis FeatureServer layer as raster might not work')
                self.addTempArcgisMap(layer,layerCRS, group, allGroup)
            elif tempLayerType == 'arcgismapserver':
                layersAdded += 1
                self.addTempArcgisMap(layer,layerCRS, group, allGroup)
            elif tempLayerType == 'ogr':
                self.mb.pushWarning('Error',"Unable to render layer type {} as raster".format(layer["connectionType"]))
            elif tempLayerType == 'wms':
                layersAdded += 1
                self.addWMSService(layer,group, allGroup)
            else:
                self.mb.pushCritical('Error',"Unrecognised layer type {}".format(tempLayerType))
                break
        if layersAdded > 0:
            self.mb.pushInfo('{} Layers added'.format(str(layersAdded)),"")
        else:
            self.mb.pushInfo('No layers to add',"")
        self.clearSelection()

    def closeFormDialog(self):
        self.formdlg.reject()

    def resizeTabWidget(self):
        self.dlg.tabWidget.setGeometry(self.dlg.tabWidget.x(),self.dlg.tabWidget.y(),self.dlg.width()-60,self.dlg.tabWidget.height())
        self.dlg.govTree.setGeometry(self.dlg.govTree.x(),self.dlg.govTree.y(),self.dlg.tabWidget.width()-5,self.dlg.govTree.height())
        self.dlg.teaserGov.setGeometry(self.dlg.teaserGov.x(),self.dlg.teaserGov.y(),self.dlg.tabWidget.width()-5,self.dlg.teaserGov.height())
        self.dlg.muniTree.setGeometry(self.dlg.muniTree.x(),self.dlg.muniTree.y(),self.dlg.tabWidget.width()-5,self.dlg.muniTree.height())
        self.dlg.teaserMuni.setGeometry(self.dlg.teaserMuni.x(),self.dlg.teaserMuni.y(),self.dlg.tabWidget.width()-5,self.dlg.teaserMuni.height())
        self.dlg.orgTree.setGeometry(self.dlg.orgTree.x(),self.dlg.orgTree.y(),self.dlg.tabWidget.width()-5,self.dlg.orgTree.height())
        self.dlg.opendataTree.setGeometry(self.dlg.opendataTree.x(),self.dlg.opendataTree.y(),self.dlg.tabWidget.width()-5,self.dlg.opendataTree.height())
        self.dlg.teaserUserServices.setGeometry(self.dlg.teaserUserServices.x(),self.dlg.teaserUserServices.y(),self.dlg.tabWidget.width()-5,self.dlg.teaserUserServices.height())
        self.dlg.userServicesTree.setGeometry(self.dlg.userServicesTree.x(),self.dlg.userServicesTree.y(),self.dlg.tabWidget.width()-5,self.dlg.userServicesTree.height())

    def run(self):
        """Run method that performs all the real work"""

        if self.first_start:
            self.first_start = False
            self.dlg = opendata_loaderDialog()
            self.setSelectionType()

        self.loadCredentials()
        self.loadLayers()

        self.dlg.resized.connect(self.resizeTabWidget)
        self.dlg.registerButton.clicked.connect(self.openRegisterButton)
        self.dlg.submitCredntials.clicked.connect(self.loadLayers)
        self.dlg.addToMapV.clicked.connect(self.loadTemps)
        self.dlg.addToMapR.clicked.connect(self.loadTemps)
        self.dlg.addToMyServices.clicked.connect(self.addPluginServiceToUserServices)
        self.dlg.addServiceButton.clicked.connect(self.openUserServicesForm)
        self.dlg.vLabel.setText(self.version)
        self.formdlg.AddUserLayer.clicked.connect(self.addUserService)
        self.formdlg.addExisting.clicked.connect(self.addExisting)
        self.formdlg.closeForm.clicked.connect(self.closeFormDialog)

        self.dlg.selectionButton.clicked.connect(self.setSelectionType)
        self.clearSelection()
        self.dlg.show()
        result = self.dlg.exec_()
        if result:
            self.clearSelection()
            
            

