# -*- coding: utf-8 -*-

# Copyright © 2014-2017 Jean-Sebastien Gosselin
# email: jean-sebastien.gosselin@ete.inrs.ca
#
# This file is part of GWHAT (GroundWater Hydrograph Analysis Toolbox).
# Licensed under the terms of the GNU General Public License.

# ---- Imports: standard libraries

import os
import csv
from copy import copy
import sys

# ---- Imports: third parties

import numpy as np
import xlsxwriter
from PyQt5.QtCore import (Qt, QAbstractTableModel, QVariant, QEvent, QPoint,
                          QRect)
from PyQt5.QtWidgets import (QApplication, QTableView, QCheckBox, QStyle,
                             QWidget, QStyledItemDelegate, QItemDelegate,
                             QStyleOptionButton, QHeaderView)


# ---- Imports: local

from gwhat.common.utils import calc_dist_from_coord


class WeatherSationList(list):
    """
    The weather station list contains the following information:
    station names, station ID , year at which the data records begin and year
    at which the data records end, the provinces to which each station belongs,
    the climate ID and the Proximity value in km for the original search
    location. Note that the station ID is not the same as the Climate ID
    of the station.
    """

    HEADER = ['staName', 'stationId', 'StartYear', 'EndYear', 'Province',
              'ClimateID', 'Latitude (dd)', 'Longitude (dd)', 'Elevation (m)']

    KEYS = ['Name', 'Station ID', 'DLY First Year', 'DLY Last Year',
            'Province', 'ID', 'Latitude', 'Longitude', 'Elevation']
    DTYPES = [str, str, int, int, str, str, float, float, float]

    def __init__(self, filelist=None, *args, **kwargs):
        super(WeatherSationList, self).__init__(*args, **kwargs)
        self._list = []
        self._filename = None
        if filelist:
            self.load_stationlist_from_file(filelist)

    def __getitem__(self, key):
        if type(key) == str:
            try:
                idx = self.KEYS.index(key)
            except ValueError:
                return None
            else:
                return np.array(self)[:, idx].astype(self.DTYPES[idx])
        else:
            return super(WeatherSationList, self).__getitem__(key)

    def add_stations(self, stations):
        for station in stations:
            if type(station) == list and len(station) != len(self.HEADER):
                raise TypeError
            else:
                self.append(station)

    def remove_stations_at(self, index):
        return self.pop(index)

    def load_stationlist_from_file(self, filelist, overwrite=True):
        if overwrite:
            self.clear()

        if not os.path.exists(filelist):
            print("%s not found." % filelist)
            return

        for d in [',', '\t']:
            try:
                with open(filelist, 'r') as f:
                    reader = list(csv.reader(f, delimiter=d))
                    assert reader[0] == self.HEADER
            except (AssertionError, IndexError):
                continue
            else:
                self.extend(reader[1:])
        else:
            return

    def get_file_content(self):
        file_content = copy(self)
        file_content.insert(0, self.HEADER)
        return file_content

    def save_to_file(self, filename):
        if filename:
            root, ext = os.path.splitext(filename)
            if ext in ['.xlsx', '.xls']:
                with xlsxwriter.Workbook(filename) as wb:
                    ws = wb.add_worksheet()
                    for i, row in enumerate(self.get_file_content()):
                        ws.write_row(i, 0, row)
            else:
                with open(filename, 'w', encoding='utf8')as f:
                    writer = csv.writer(f, delimiter=',', lineterminator='\n')
                    writer.writerows(self.get_file_content())

            print('Station list saved successfully in %s' % filename)

    def format_list_in_html(self):
        """Format the content of the weather station list into a HTML table."""
        html = "<table>"
        html += "<tr>"
        for attrs in self.HEADER:
            html += '<th>%s</th>' % attrs
        html += "<tr>"
        for station in self:
            html += "<tr>"
            for attrs in station:
                html += '<td>%s</td>' % attrs
            html += "</tr>"
        html += "</table>"

        return html


if __name__ == '__main__':
    fname = ("C:\\Users\\jsgosselin\\OneDrive\\WHAT\\WHAT\\tests\\"
             "@ new-prô'jèt!\\weather_station_list.lst")
    stationlist = WeatherSationList(fname)
    filecontent = stationlist.get_file_content()
    stationlist.save_to_file("test.csv")
