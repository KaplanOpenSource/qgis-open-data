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
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load opendata_loader class from file opendata_loader.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .opendata_loader import OpenDataLoader
    return OpenDataLoader(iface)
