# -*- coding: utf-8 -*-
"""
Copyright 2014-2017 Jean-Sebastien Gosselin
email: jean-sebastien.gosselin@ete.inrs.ca

This file is part of WHAT (Well Hydrograph Analysis Toolbox).

WHAT is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>
"""

from __future__ import division, unicode_literals

# Standard library imports :

try:
    from urllib2 import urlopen, URLError
except ImportError:
    from urllib.request import URLError, urlopen

import sys
import os
from os import getcwd, path, makedirs
from time import gmtime, sleep
import csv

# Third party imports :

import numpy as np

from PyQt5.QtCore import Qt, QThread, QObject
from PyQt5.QtCore import pyqtSignal as QSignal
from PyQt5.QtWidgets import (QApplication, QDesktopWidget, QWidget, QMenu,
                             QToolButton, QGridLayout, QLabel, QCheckBox,
                             QFrame, QTextEdit, QPushButton, QFileDialog,
                             QMessageBox, QProgressBar)

# Local imports :

import common.database as db
from common import IconDB, QToolButtonNormal, QToolButtonSmall
import common.widgets as myqt
from meteo.search_weather_data import WeatherStationDisplayTable
from meteo.search_weather_data import Search4Stations


# =============================================================================


class DwnldWeatherWidget(QWidget):
    """
    Interface that allows to download daily weather data from the governement
    of Canada website (http://climate.weather.gc.ca/historical_data/
    search_historic_data_e.html).
    """

    ConsoleSignal = QSignal(str)
    sig_download_process_ended = QSignal()

    def __init__(self, parent=None):
        super(DwnldWeatherWidget, self).__init__(parent)

        self.set_workdir(getcwd())

        self.staList_fname = []
        self.staList_isNotSaved = False

        self.mergeHistoryLog = []
        self.mergeHistoryIndx = 0
        self.mergeHistoryFnames = []

        self.staList2dwnld = []
        self.dwnld_indx = 0

        # Setup child widgets and UI.

        self.search4stations = Search4Stations(self)
        self.station_table = WeatherStationDisplayTable(1, self)
        self.__initUI__()

        # Setup downloader worker and thread.

        self.dwnld_worker = RawDataDownloader()
        self.dwnld_thread = QThread()
        self.dwnld_worker.moveToThread(self.dwnld_thread)

        self.dwnld_worker.sig_download_finished.connect(
                self.process_station_data)
        self.dwnld_worker.sig_update_pbar.connect(self.pbar.setValue)
        self.dwnld_worker.ConsoleSignal.connect(self.ConsoleSignal.emit)

    def __initUI__(self):

        # ---- Main Window ----

        self.setWindowIcon(IconDB().master)

        # ---- TOOLBAR ----

        btn_save_menu = QMenu()
        btn_save_menu.addAction('Save As...',
                                self.btn_saveAs_staList_isClicked)

        self.btn_save_staList = QToolButtonNormal(IconDB().save)
        self.btn_save_staList.setToolTip('Save current station list.')
        self.btn_save_staList.setMenu(btn_save_menu)
        self.btn_save_staList.setPopupMode(QToolButton.MenuButtonPopup)

        btn_search4station = QToolButtonNormal(IconDB().search)
        btn_search4station.setToolTip('Search for weather stations in the ' +
                                      'Canadian Daily Climate Database (CDCD)')

        btn_browse_staList = QToolButtonNormal(IconDB().openFile)
        btn_browse_staList.setToolTip('Load an existing weather station list')

        btn_delSta = QToolButtonNormal(IconDB().erase)
        btn_delSta.setToolTip('Remove selected weather stations from the list')

        self.btn_get = QToolButtonNormal(IconDB().download)
        self.btn_get.setToolTip(
                "Download data for the selected weather stations.")
        self.btn_get.clicked.connect(self.btn_get_isClicked)

        tb = QGridLayout()
        col = 0
        buttons = [btn_search4station, btn_browse_staList,
                   self.btn_save_staList, btn_delSta, self.btn_get]
        for button in buttons:
            col += 1
            tb.addWidget(button, 0, col)

        tb.setColumnStretch(tb.columnCount(), 100)
        tb.setSpacing(5)
        tb.setContentsMargins(0, 0, 0, 0)  # [L, T, R, B]

        # ---- Progress Bar ----

        self.pbar = QProgressBar()
        self.pbar.setValue(0)
        self.pbar.hide()

        # ---- Right Panel ----

        display_label = QLabel('<b>Formatted Weather Data Info :</b>')

        self.saveAuto_checkbox = QCheckBox(
            'Automatically save formatted\nweather data')
        self.saveAuto_checkbox.setCheckState(Qt.Checked)
        self.saveAuto_checkbox.setStyleSheet(
                          'QCheckBox::indicator{subcontrol-position:top left}')

        # ---- Go Toolbar ----

        self.btn_goNext = QToolButtonSmall(IconDB().go_next)
        self.btn_goNext.setEnabled(False)

        self.btn_goPrevious = QToolButtonSmall(IconDB().go_previous)
        self.btn_goPrevious.setEnabled(False)

        self.btn_goLast = QToolButtonSmall(IconDB().go_last)
        self.btn_goLast.setEnabled(False)

        self.btn_goFirst = QToolButtonSmall(IconDB().go_first)
        self.btn_goFirst.setEnabled(False)

        goToolbar_grid = QGridLayout()
        goToolbar_widg = QFrame()

        col = 0
        goToolbar_grid.addWidget(self.btn_goFirst, 0, col)
        col += 1
        goToolbar_grid.addWidget(self.btn_goPrevious, 0, col)
        col += 1
        goToolbar_grid.addWidget(self.btn_goNext, 0, col)
        col += 1
        goToolbar_grid.addWidget(self.btn_goLast, 0, col)

        goToolbar_grid.setContentsMargins(0, 0, 0, 0)  # [L, T, R, B]
        goToolbar_grid.setSpacing(5)

        goToolbar_widg.setLayout(goToolbar_grid)

        # ---- Right Panel Assembly ----

        self.mergeDisplay = QTextEdit()
        self.mergeDisplay.setReadOnly(True)
        self.mergeDisplay.setMinimumHeight(250)

        btn_selectRaw = QPushButton('Select')
        btn_selectRaw.setIcon(IconDB().openFile)
        btn_selectRaw.setToolTip('Select and format raw weather data files')
        btn_selectRaw.setIconSize(IconDB().iconSize2)

        btn_saveMerge = QPushButton('Save')
        btn_saveMerge.setToolTip('Save formated weather data in a csv file')
        btn_saveMerge.setIcon(IconDB().save)
        btn_saveMerge.setIconSize(IconDB().iconSize2)

        rightPanel_grid = QGridLayout()
        rightPanel_widg = QFrame()

        row = 0

        rightPanel_grid.addWidget(btn_selectRaw, row, 0)
        rightPanel_grid.addWidget(btn_saveMerge, row, 1)
        row += 1
        rightPanel_grid.addWidget(self.mergeDisplay, row, 0, 1, 3)
        row += 1
        rightPanel_grid.addWidget(goToolbar_widg, row, 0, 1, 3)
        row += 1
        rightPanel_grid.addWidget(QLabel(''), row, 0, 1, 3)
        row += 1
        rightPanel_grid.addWidget(self.saveAuto_checkbox, row, 0, 1, 3)

        rightPanel_grid.setContentsMargins(0, 0, 0, 0)  # [L, T, R, B]
        rightPanel_grid.setRowStretch(row+1, 100)
        rightPanel_grid.setColumnStretch(2, 100)

        rightPanel_widg.setLayout(rightPanel_grid)

        # ------------------------------------------------------ Main Grid ----

        main_grid = QGridLayout()

        main_grid.addLayout(tb, 0, 0)
        main_grid.addWidget(self.station_table, 1, 0)
        main_grid.addWidget(myqt.VSep(), 0, 1, 2, 1)

        main_grid.addWidget(display_label, 0, 2)
        main_grid.addWidget(rightPanel_widg, 1, 2)

        main_grid.setContentsMargins(10, 10, 10, 10)  # [L, T, R, B]
        main_grid.setColumnStretch(0, 500)
        main_grid.setRowStretch(1, 500)
        main_grid.setVerticalSpacing(5)
        main_grid.setHorizontalSpacing(15)

        self.setLayout(main_grid)

        # --------------------------------------------------------- EVENTS ----

        # ---- concatenate raw data ----

        btn_selectRaw.clicked.connect(self.btn_selectRaw_isClicked)

        self.btn_goLast.clicked.connect(self.display_mergeHistory)
        self.btn_goFirst.clicked.connect(self.display_mergeHistory)
        self.btn_goNext.clicked.connect(self.display_mergeHistory)
        self.btn_goPrevious.clicked.connect(self.display_mergeHistory)

        btn_saveMerge.clicked.connect(self.btn_saveMerge_isClicked)

        # ---- weather station list ----

        btn_delSta.clicked.connect(self.btn_delSta_isClicked)
        btn_browse_staList.clicked.connect(self.btn_browse_staList_isClicked)
        self.btn_save_staList.clicked.connect(self.btn_save_staList_isClicked)

        # ---- search4stations ----

        btn_search4station.clicked.connect(self.search4stations.show)
        self.search4stations.staListSignal.connect(self.add_stations2list)
        self.search4stations.ConsoleSignal.connect(self.ConsoleSignal.emit)

    # =========================================================================

    @property
    def workdir(self):
        return self.__workdir

    def set_workdir(self, directory):
        self.__workdir = directory

    # =========================================================================

    def btn_delSta_isClicked(self):
        rows = self.station_table.get_checked_rows()
        if len(rows) > 0:
            self.station_table.delete_rows(rows)
            self.staList_isNotSaved = True
        else:
            print('No weather station selected')

        # Unckeck header ckbox if list is cleared :
        nrow = self.station_table.rowCount()
        if nrow == 0:
            self.station_table.chkbox_header.setCheckState(
                Qt.CheckState(False))

    def add_stations2list(self, staList2add):
        staList2grow = self.station_table.get_staList()

        if len(staList2grow) == 0:
            staList2grow = staList2add
        else:
            StationID = np.array(staList2grow)[:, 1].astype(str)
            for row in range(len(staList2add)):
                sta2add = staList2add[row]
                indx = np.where(StationID == sta2add[1])[0]
                if len(indx) > 0:
                    print('Station %s already in list and was not added.'
                          % sta2add[0])
                else:
                    print('Station %s added to list.' % sta2add[0])
                    staList2grow.append(sta2add)

                    self.staList_isNotSaved = True
                    self.staList_fname = []

        self.station_table.populate_table(staList2grow)

    def btn_browse_staList_isClicked(self):
        '''
        Allows the user to select a weather station list with
        a 'lst' extension.
        '''

        filename, _ = QFileDialog.getOpenFileName(
                          self, 'Select a valid station list',
                          self.workdir, '*.lst')

        if filename:
            QApplication.processEvents()
            self.load_stationList(filename)

    def load_stationList(self, filename):
        '''
        It loads the informations in the weather stations list file (.lst) that
        is located in "filename". The content is then displayed in a
        QTableWidget named "station_table".

        ----- weather_stations.lst -----

        The weather_station.lst is a csv file that contains the following
        information:  station names, station ID , date at which the data
        records begin and date at which the data records end, the provinces
        to which each station belongs, the climate ID and the Proximity
        value in km for the original search location.

        All these information can be found on the Government of Canada
        website in the address bar of the web browser when a station is
        selected. Note that the station ID is not the same as the Climate ID
        of the station. For example, the ID for the station Abercorn is 5308,
        as it can be found in the following address:

        "http://climate.weather.gc.ca/climateData/dailydata_e.html?timeframe=
         2&Prov=QUE&StationID=5308&dlyRange=1950-12-01|1985-01-31&Year=
         1985&Month=1&Day=01"
        '''

        # ----- Check if file exists ----

        # In case this method is not called from the UI.

        headerDB = db.FileHeaders()
        self.staList_isNotSaved = False

        if not path.exists(filename):
            msg = ('"%s" not found. Please select an existing weather station'
                   ' list or search for new stations on the CDCD.'
                   ) % filename
            print(msg)
            self.ConsoleSignal.emit('<font color=red>%s</font>' % msg)

            self.station_table.populate_table(staList=[])
            self.staList_fname = []

            return

        # ------------------------------------------------------ Open file ----

        with open(filename, 'r') as f:
            reader = list(csv.reader(f, delimiter=','))

        if reader[0] != db.FileHeaders().weather_stations[0]:
            with open(filename, 'r') as f:
                reader = list(csv.reader(f, delimiter='\t'))

        # -------------------------------------------------- Check version ----

        # Check if the list is from an older version, and update it if yes

        header = headerDB.weather_stations[0]

        nCONFG, nPARA = np.shape(reader)
        if nPARA < len(header):

            print('This list is from an older version of WHAT.')
            print('Converting to new format.')
            self.ConsoleSignal.emit('''<font color=#C83737>Converting weather
            station list to a more recent format. Please wait...</font>''')

            QApplication.processEvents()
            QApplication.processEvents()

            QApplication.setOverrideCursor(Qt.WaitCursor)

            reader[0] = headerDB.weather_stations[0]
            for i in range(nCONFG-1):
                Prov = reader[i+1][4]
                stationId = reader[i+1][1]
                reader[i+1] = self.search4stations.get_staInfo(Prov, stationId)

            # ---- Save Updated List ----

            with open(filename, 'w') as f:
                writer = csv.writer(f, delimiter=',')
                writer.writerows(reader)

            QApplication.restoreOverrideCursor()

        # ---- Load list in UI ----

        if len(reader) > 1:
            msg = 'Weather station list loaded successfully.'
            print(msg)
            self.ConsoleSignal.emit('<font color=black>%s</font>' % msg)
            staList = reader[1:]
        else:
            msg = 'Weather station list is empty.'
            print(msg)
            self.ConsoleSignal.emit('<font color=#C83737>%s</font>' % msg)
            staList = []

        self.station_table.populate_table(staList)
        self.staList_fname = filename

        return staList

    def btn_save_staList_isClicked(self):
        filename = self.staList_fname
        if filename:
            msg = 'Station list saved in %s' % filename
            print(msg)
            self.ConsoleSignal.emit('<font color=black>%s</font>' % msg)
            self.station_table.save_staList(filename)
            self.staList_isNotSaved = False
        else:
            self.btn_saveAs_staList_isClicked()

    def btn_saveAs_staList_isClicked(self):
        fname = os.path.join(self.workdir, 'weather_stations.lst')
        dialog = QFileDialog()
        dialog.setConfirmOverwrite(True)
        fname, ftype = dialog.getSaveFileName(
                           caption="Save Weather Stations List",
                           dir=fname, filter=('*.lst'))

        if fname:
            if fname[-4:] != ftype[1:]:
                # Add a file extension if there is none
                fname = fname + ftype[1:]

            self.station_table.save_staList(fname)
            self.staList_fname = fname
            self.staList_isNotSaved = False

            msg = 'Station list saved in %s' % fname
            print(msg)
            self.ConsoleSignal.emit('<font color=black>%s</font>' % msg)

    # =========================================================================

    def btn_get_isClicked(self):
        """
        This method starts or stop the downloading process of raw weather
        data files.
        """
        if self.dwnld_thread.isRunning():
            self.stop_download_process()
        else:
            self.start_download_process()

    def start_download_process(self):
        # Grab the info of the weather stations that are selected.
        rows = self.station_table.get_checked_rows()
        self.staList2dwnld = self.station_table.get_content4rows(rows)
        if len(self.staList2dwnld) == 0:
            msg = ('No weather station currently selected.')
            btn = QMessageBox.Ok
            QMessageBox.warning(self, 'Warning', msg, btn)
            return

        # Update the UI.
        self.pbar.show()
        self.btn_get.setIcon(IconDB().stop)

        # Set thread working directory.
        self.dwnld_worker.dirname = os.path.join(self.workdir, 'Meteo', 'Raw')

        # Start downloading data.
        self.download_next_station()

    def stop_download_process(self):
        print('Stopping the download process.')
        self.btn_get.setIcon(IconDB().download)
        self.btn_get.setEnabled(False)
        self.dwnld_worker.stop_download()
        self.wait_for_thread_to_quit()
        self.btn_get.setEnabled(True)
        self.sig_download_process_ended.emit()

    def download_next_station(self):
        self.wait_for_thread_to_quit()
        try:
            sta2dwnl = self.staList2dwnld.pop(0)
        except IndexError:
            # There is no more data to download.
            print('Raw weather data downloaded for all selected stations.')
            self.btn_get.setIcon(IconDB().download)
            self.pbar.hide()
            self.sig_download_process_ended.emit()
            return

        # Set worker sttributes.
        self.dwnld_worker.StaName = sta2dwnl[0]
        self.dwnld_worker.stationID = sta2dwnl[1]
        self.dwnld_worker.yr_start = sta2dwnl[2]
        self.dwnld_worker.yr_end = sta2dwnl[3]
        self.dwnld_worker.climateID = sta2dwnl[5]

        # Highlight the row of the next station to download data from.
        current_row = self.station_table.get_row_from_climateid(sta2dwnl[5])
        self.station_table.selectRow(current_row)

        # Start the downloading process.
        try:
            self.dwnld_thread.started.disconnect(
                    self.dwnld_worker.download_data)
        except TypeError:
            # The method self.dwnld_worker.download_data is not connected.
            pass
        finally:
            self.dwnld_thread.started.connect(self.dwnld_worker.download_data)
            self.dwnld_thread.start()

    def process_station_data(self, file_list=None):
        if file_list:
            self.concatenate_and_display(file_list)
        self.download_next_station()

    def wait_for_thread_to_quit(self):
        self.dwnld_thread.quit()
        waittime = 0
        while self.dwnld_thread.isRunning():
            print('Waiting for the downloading thread to close')
            sleep(0.1)
            waittime += 0.1
            if waittime > 15:
                msg = ('This function is not working as intended.'
                       ' Please report a bug.')
                print(msg)
                self.ConsoleSignal.emit('<font color=red>%s</font>' % msg)
                return

    def display_mergeHistory(self):

        # ---------------------------- Respond to UI event (if applicable) ----

        button = self.sender()
        if button == self.btn_goFirst:
            self.mergeHistoryIndx = 0
        elif button == self.btn_goLast:
            self.mergeHistoryIndx = len(self.mergeHistoryLog) - 1
        elif button == self.btn_goPrevious:
            self.mergeHistoryIndx += -1
        elif button == self.btn_goNext:
            self.mergeHistoryIndx += 1

        # ------------------------------------------------------ Update UI ----

        self.mergeDisplay.setText(self.mergeHistoryLog[self.mergeHistoryIndx])
        if len(self.mergeHistoryLog) > 1:
            if self.mergeHistoryIndx == (len(self.mergeHistoryLog) - 1):
                self.btn_goLast.setEnabled(False)
                self.btn_goNext.setEnabled(False)
                self.btn_goFirst.setEnabled(True)
                self.btn_goPrevious.setEnabled(True)
            elif self.mergeHistoryIndx == 0:
                self.btn_goLast.setEnabled(True)
                self.btn_goNext.setEnabled(True)
                self.btn_goFirst.setEnabled(False)
                self.btn_goPrevious.setEnabled(False)
            else:
                self.btn_goLast.setEnabled(True)
                self.btn_goNext.setEnabled(True)
                self.btn_goFirst.setEnabled(True)
                self.btn_goPrevious.setEnabled(True)

    def btn_selectRaw_isClicked(self):  # =====================================
        """
        This method is called by the event <btn_select.clicked.connect>.
        It allows the user to select a group of raw data files belonging to a
        given meteorological station in order to concatenate them into a single
        file with the method <concatenate_and_display>.
        """

        dialog_fir = os.path.join(self.workdir, 'Meteo', 'Raw')
        fname, _ = QFileDialog.getOpenFileNames(
                self, 'Open files', dialog_fir, '*.csv')
        if fname:
            self.concatenate_and_display(fname)

    def concatenate_and_display(self, filenames):
        """
        Handles the concatenation process of individual yearly raw data files
        and display the results in the <mergeDisplay> widget.

        ---- CALLED BY----

        (1) Method: select_raw_files
        (2) Event:  self.dwnl_rawfiles.sig_merge_rawdata.connect
        """

        if len(filenames) == 0:
            print('No raw data file selected.')
            return

        mergeOutput, LOG = self.concatenate(filenames)

        StaName = mergeOutput[0, 1]
        YearStart = mergeOutput[8, 0][:4]
        YearEnd = mergeOutput[-1, 0][:4]
        climateID = mergeOutput[5, 1]

        self.ConsoleSignal.emit("""<font color=black>Raw data files concatened
        successfully for station %s.</font>""" % StaName)

        # ---- Update history variables and UI ----

        self.mergeHistoryLog.append(LOG)
        self.mergeHistoryIndx = len(self.mergeHistoryLog) - 1
        self.display_mergeHistory()
        self.mergeHistoryFnames.append(filenames)

        if self.saveAuto_checkbox.isChecked():

            # Check if the characters "/" or "\" are present in the station
            # name and replace these characters by "_" if applicable.

            StaName = StaName.replace('\\', '_')
            StaName = StaName.replace('/', '_')

            save_dir = os.path.join(self.workdir, 'Meteo', 'Input')
            if not path.exists(save_dir):
                makedirs(save_dir)

            filename = '%s (%s)_%s-%s.csv' % (StaName, climateID,
                                              YearStart, YearEnd)
            fname = os.path.join(save_dir, filename)
            self.save_concatened_data(fname, mergeOutput)

    def btn_saveMerge_isClicked(self):  # =====================================
        '''
        This method allows the user to select a path for the file in which the
        concatened data are going to be saved.

        ---- CALLED BY----

        (1) Event: btn_saveMerge.clicked.connect
        '''

        if len(self.mergeHistoryLog) == 0:
            print('There is no concatenated data file to save yet.')
            return

        filenames = self.mergeHistoryFnames[self.mergeHistoryIndx]
        mergeOutput, _ = self.concatenate(filenames)

        if np.size(mergeOutput) != 0:
            StaName = mergeOutput[0, 1]
            YearStart = mergeOutput[8, 0][:4]
            YearEnd = mergeOutput[-1, 0][:4]
            climateID = mergeOutput[5, 1]

            # Check if the characters "/" or "\" are present in the station
            # name and replace these characters by "_" if applicable.

            StaName = StaName.replace('\\', '_')
            StaName = StaName.replace('/', '_')

            filename = '%s (%s)_%s-%s.csv' % (StaName, climateID,
                                              YearStart, YearEnd)
            dialog_dir = os.path.join(self.workdir, 'Meteo, Input', filename)
            fname, _ = QFileDialog.getSaveFileName(
                           self, 'Save file', dialog_dir, '*.csv')

            if fname:
                self.save_concatened_data(fname, mergeOutput)

    def concatenate(self, fname):
        fname = np.sort(fname)  # list of the raw data file paths

        COLN = (1, 2, 3, 5, 7, 9, 19)
        # columns of the raw data files to extract :
        # year, month, day, Tmax, Tmin, Tmean, Ptot

        ALLDATA = np.zeros((0, len(COLN)))  # matrix containing all the data
        StaName = np.zeros(len(fname)).astype(str)    # station names
        StaMatch = np.zeros(len(fname)).astype(bool)  # station match
        ClimateID = np.zeros(len(fname)).astype(str)  # climate ID

        for i in range(len(fname)):
            enc = ['utf-8', 'utf-8-sig', 'utf-16', 'iso-8859-1']
            j = 0
            while True:
                # This while loop is in case EnviroCan decides to change the
                # encoding format of the raw data file like they did in 2016
                # when they changed it from iso-8859-1 to utf-8-sig.

                if j >= len(enc):
                    print('There is a compatibility problem with the data.')
                    print('Please, write at jnsebgosselin@gmail.com')
                    break

                try:
                    with open(fname[i], 'r', encoding=enc[j]) as f:
                        reader = list(csv.reader(f, delimiter=','))

                    if reader[0][0] == 'Station Name':
                        break
                    else:
                        f.close()
                        j = j + 1
                except IndexError:
                    j = i + 1

            StaName[i] = reader[0][1]
            ClimateID[i] = reader[5][1]
            StaMatch[i] = (ClimateID[0] == ClimateID[i])

            row_data_start = 0
            fieldSearch = 'None'
            while fieldSearch != 'Date/Time':
                try:
                    fieldSearch = reader[row_data_start][0]
                except IndexError:
                    pass

                row_data_start += 1
                if row_data_start > 50:
                    print('There is a compatibility problem with the data.')
                    print('Please, write at jnsebgosselin@gmail.com')
                    break

            DATA = np.array(reader[row_data_start:])
            DATA = DATA[:, COLN]
            DATA[DATA == ''] = 'nan'
            DATA = DATA.astype('float')

            ALLDATA = np.vstack((ALLDATA, DATA))

        # ---------------------------------------- Produce a Summary Table ----

        FIELDS = ['T<sub>max<\sub>', 'T<sub>min<\sub>', 'T<sub>mean<\sub>',
                  'P<sub>tot<\sub>']

        ndata = float(len(ALLDATA[:, 0]))
        province = reader[1][1]

#        style="border-bottom:1px solid black"
#        <td align="left" width=15>:</td>
        LOG = '''
              <p align='center'>
                <b><font color=#C83737>%s</font></b><br>%s<br>(%d - %d)
              </p>
              <table border="0" cellpadding="1" cellspacing="0" align="center">
              <tr><td colspan="4"><hr><\td><\tr>
              <tr>
                <td align="left">Weather<\td>
                <td align="left" width=25></td>
                <td colspan="2" align="right">Days with<\td>
              <\tr>
              <tr>
                <td align="left">Variables<\td>
                <td align="left" width=25></td>
                <td colspan="2" align="right">Missing Data<\td>
              <\tr>
              <tr><td colspan="4"><hr><\td><\tr>
              ''' % (StaName[0], province,
                     np.min(ALLDATA[:, 0]), np.max(ALLDATA[:, 0]))
        for i in range(0, len(FIELDS)):
            nonan = sum(np.isnan(ALLDATA[:, i+3]))
            LOG += '''
                   <tr>
                     <td align="left">%s</td>
                     <td align="left" width=25></td>
                     <td align="right">%d</td>
                     <td align="right">&nbsp;(%d%%)</td>
                   </tr>
                   ''' % (FIELDS[i], nonan, nonan/ndata*100)
        LOG += '<tr><td colspan="4"><hr><\td><\tr>'

        # ----------------------------------------------- Restructure Data ----

        HEADER = np.zeros((8, len(COLN))).astype('str')
        HEADER[:] = ''
        HEADER[0:6, 0:2] = np.array(reader[0:6])
        HEADER[7, :] = ['Year', 'Month', 'Day',
                        'Max Temp (deg C)', 'Min Temp (deg C)',
                        'Mean Temp (deg C)', 'Total Precip (mm)']

        MergeOutput = np.vstack((HEADER, ALLDATA.astype('str')))

        # ----------------------- Check if files are from the same station ----

        if min(StaMatch) == 1:
            pass  # everything is fine
        else:
            msg = ('WARNING: All the data files do not belong to' +
                   ' station %s') % StaName[0]
            print(msg)
            self.ConsoleSignal.emit('<font color=#C83737>%s</font>' % msg)

        return MergeOutput, LOG

    def save_concatened_data(self, fname, fcontent):

        """
        This method saves the concatened data into a single csv file.

        ---- CALLED BY----

        (1) Method: btn_saveMerge_isClicked
        (2) Method: concatenate_and_display if self.saveAuto_checkbox.isChecked
        """

        with open(fname, 'w', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter='\t', lineterminator='\n')
            writer.writerows(fcontent)

        msg = 'Concatened data saved in: %s.' % fname
        print(msg)
        self.ConsoleSignal.emit('<font color=black>%s</font>' % msg)


# =============================================================================


class RawDataDownloader(QObject):
    '''
    This thread is used to download the raw data files from
    www.climate.weather.gc.ca and saves them automatically in
    <Project_directory>/Meteo/Raw/<station_name (Climate ID)>.

    New in 4.0.6: Raw data files that already exists in the Raw directory
                  won't be downloaded again from the server.

    ---- Input ----

    self.__stop_dwnld = Flag that is used to stop the thread from the UI side.

    ---- Output ----

    self.ERRFLAG = Flag for the download of files - np.arrays
                   0 -> File downloaded successfully
                   1 -> Problem downloading the file
                   3 -> File NOT downloaded because it already exists
    '''

    sig_download_finished = QSignal(list)
    sig_update_pbar = QSignal(int)
    ConsoleSignal = QSignal(str)

    def __init__(self):
        super(RawDataDownloader, self).__init__(parent=None)

        self.__stop_dwnld = False

        self.ERRFLAG = []

        # These values need to be pushed from the parent.

        self.dirname = []    # Directory where the downloaded files are saved
        self.stationID = []
        # Unique identifier for the station used for downloading the
        # data from the server
        self.climateID = []  # Unique identifier for the station
        self.yr_start = []
        self.yr_end = []
        self.StaName = []  # Common name given to the station (not unique)

    def stop_download(self):
        self.__stop_dwnld = True

    def download_data(self):

        # ---------------------------------------------------------- INIT -----

        staID = self.stationID
        yr_start = int(self.yr_start)
        yr_end = int(self.yr_end)
        StaName = self.StaName
        climateID = self.climateID

        self.ERRFLAG = np.ones(yr_end - yr_start + 1)

        self.ConsoleSignal.emit(
            '''<font color=black>Downloading data from </font>
               <font color=blue>www.climate.weather.gc.ca</font>
               <font color=black> for station %s</font>''' % StaName)
        self.sig_update_pbar.emit(0)

        StaName = StaName.replace('\\', '_')
        StaName = StaName.replace('/', '_')
        dirname = os.path.join(self.dirname, '%s (%s)' % (StaName, climateID))
        if not path.exists(dirname):
            makedirs(dirname)

        # ------------------------------------------------------- DOWNLOAD ----

        # Data are downloaded on a yearly basis from yStart to yEnd

        # list of paths of the yearly raw data files that will be pass to
        # contatenate and merge function.
        fname4merge = []
        for i, year in enumerate(range(yr_start, yr_end+1)):
            if self.__stop_dwnld:
                # Stop the downloading process.
                self.__stop_dwnld = False
                msg = "Downloading process for station %s stopped." % StaName
                print(msg)
                self.ConsoleSignal.emit("<font color=red>%s</font>" % msg)
                return

            # Define file and URL paths.
            fname = os.path.join(
                    dirname, "eng-daily-0101%s-1231%s.csv" % (year, year))
            url = ('http://climate.weather.gc.ca/climate_data/' +
                   'bulk_data_e.html?format=csv&stationID=' + str(staID) +
                   '&Year=' + str(year) + '&Month=1&Day=1&timeframe=2' +
                   '&submit=Download+Data')

            # Download data for that year.
            if path.exists(fname):
                # If the file was downloaded in the same year that of the data
                # record, data will be downloaded again in case the data series
                # was not complete.

                # Get year of file last modification
                myear = path.getmtime(fname)
                myear = gmtime(myear)[0]
                if myear == year:
                    self.ERRFLAG[i] = self.dwnldfile(url, fname)
                else:
                    self.ERRFLAG[i] = 3
                    print('Not downloading: Raw Data File already exists.')
            else:
                self.ERRFLAG[i] = self.dwnldfile(url, fname)

            # Update UI :

            progress = (year - yr_start+1) / (yr_end+1 - yr_start) * 100
            self.sig_update_pbar.emit(int(progress))

            if self.ERRFLAG[i] == 1:                         # pragma: no cover
                self.ConsoleSignal.emit(
                    '''<font color=red>There was a problem downloading the
                         data of station %s for year %d.
                       </font>''' % (StaName, year))
            elif self.ERRFLAG[i] == 0:
                self.ConsoleSignal.emit(
                    '''<font color=black>Weather data for station %s
                         downloaded successfully for year %d.
                       </font>''' % (StaName, year))
                fname4merge.append(fname)
            elif self.ERRFLAG[i] == 3:
                sleep(0.1)
                self.ConsoleSignal.emit(
                    '''<font color=green>A weather data file already existed
                         for station %s for year %d. Downloading is skipped.
                       </font>''' % (StaName, year))
                fname4merge.append(fname)

        # ---------------------------------------------------- End of Task ----

        cmt = ("All raw  data files downloaded sucessfully for "
               "station %s.") % StaName
        print(cmt)
        self.ConsoleSignal.emit('<font color=black>%s</font>' % cmt)

        self.sig_update_pbar.emit(0)
        self.sig_download_finished.emit(fname4merge)

    def dwnldfile(self, url, fname):
        try:
            ERRFLAG = 0
            f = urlopen(url)
            print('downloading %s' % fname)

            # Write downloaded content to local file.
            with open(fname, 'wb') as local_file:
                local_file.write(f.read())
        except URLError as e:                                # pragma: no cover
            ERRFLAG = 1
            if hasattr(e, 'reason'):
                print('Failed to reach a server.')
                print('Reason: ', e.reason)
            elif hasattr(e, 'code'):
                print('The server couldn\'t fulfill the request.')
                print('Error code: ', e.code)

        return ERRFLAG


if __name__ == '__main__':                                   # pragma: no cover

    app = QApplication(sys.argv)

    ft = app.font()
    ft.setFamily('Segoe UI')
    ft.setPointSize(10)
    app.setFont(ft)

    w = DwnldWeatherWidget()

    testpath = "../tests/@ new-prô'jèt!"
    w.set_workdir(testpath)
    w.search4stations.lat_spinBox.setValue(45.4)
    w.search4stations.lon_spinBox.setValue(73.13)
    w.search4stations.isOffline = True
    w.load_stationList(os.path.join(testpath, "weather_station_list.lst"))

    w.station_table.set_fromyear(2000)
    w.station_table.set_toyear(2017)

    # ---- SHOW ----

    w.show()

    qr = w.frameGeometry()
    cp = QDesktopWidget().availableGeometry().center()
    qr.moveCenter(cp)
    w.move(qr.topLeft())

    sys.exit(app.exec_())
