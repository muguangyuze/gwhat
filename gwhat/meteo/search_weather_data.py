# -*- coding: utf-8 -*-

# Copyright © 2014-2018 GWHAT Project Contributors
# https://github.com/jnsebgosselin/gwhat
#
# This file is part of GWHAT (Ground-Water Hydrograph Analysis Toolbox).
# Licensed under the terms of the GNU General Public License.

# ---- Imports: Standard Libraries

from datetime import datetime
import sys
import os
from time import sleep

# ---- Imports: Third Parties

from PyQt5.QtCore import pyqtSignal as QSignal
from PyQt5.QtCore import pyqtSlot as QSlot
from PyQt5.QtCore import Qt, QPoint, QThread, QSize
from PyQt5.QtWidgets import (QWidget, QLabel, QDoubleSpinBox, QComboBox,
                             QFrame, QGridLayout, QSpinBox, QPushButton,
                             QDesktopWidget, QApplication,
                             QFileDialog, QGroupBox, QStyle)

# ---- Imports: Local

from gwhat.common import StyleDB
from gwhat.common import icons
from gwhat.widgets.waitingspinner import QWaitingSpinner
from gwhat.meteo.weather_stationlist import WeatherSationView
from gwhat.meteo.weather_station_finder import (WeatherStationFinder,
                                                PROV_NAME_ABB)


class WaitSpinnerBar(QWidget):

    def __init__(self, parent=None):
        super(WaitSpinnerBar, self).__init__(parent)

        self._layout = QGridLayout(self)

        self._label = QLabel()
        self._label.setAlignment(Qt.AlignCenter)
        self._spinner = QWaitingSpinner(self, centerOnParent=False)

        icon = QWidget().style().standardIcon(QStyle.SP_MessageBoxCritical)
        pixmap = icon.pixmap(QSize(64, 64))
        self._failed_icon = QLabel()
        self._failed_icon.setPixmap(pixmap)
        self._failed_icon.hide()

        self._layout.addWidget(self._spinner, 1, 1)
        self._layout.addWidget(self._failed_icon, 1, 1)
        self._layout.addWidget(self._label, 2, 0, 1, 3)

        self._layout.setRowStretch(0, 100)
        self._layout.setRowStretch(3, 100)
        self._layout.setColumnStretch(0, 100)
        self._layout.setColumnStretch(2, 100)

    def set_label(self, text):
        """Set the text that is displayed next to the spinner."""
        self._label.setText(text)

    def show_warning_icon(self):
        """Stop and hide the spinner and show a critical icon instead."""
        self._spinner.hide()
        self._spinner.stop()
        self._failed_icon.show()

    def show(self):
        """Override Qt show to start waiting spinner."""
        self._spinner.show()
        self._failed_icon.hide()
        super(WaitSpinnerBar, self).show()
        self._spinner.start()

    def hide(self):
        """Override Qt hide to stop waiting spinner."""
        super(WaitSpinnerBar, self).hide()
        self._spinner.stop()


class WeatherStationBrowser(QWidget):
    """
    Widget that allows the user to browse and select ECCC climate stations.
    """

    ConsoleSignal = QSignal(str)
    staListSignal = QSignal(list)

    PROV_NAME = [x[0].title() for x in PROV_NAME_ABB]
    PROV_ABB = [x[1] for x in PROV_NAME_ABB]

    def __init__(self, parent=None):
        super(WeatherStationBrowser, self).__init__(parent)
        self.stn_finder_worker = WeatherStationFinder()
        self.stn_finder_worker.sig_load_database_finished.connect(
                self.receive_load_database)
        self.stn_finder_thread = QThread()
        self.stn_finder_worker.moveToThread(self.stn_finder_thread)

        self.station_table = WeatherSationView()
        self.waitspinnerbar = WaitSpinnerBar()
        self.stn_finder_worker.sig_progress_msg.connect(
                self.waitspinnerbar.set_label)
        self.__initUI__()

        self.start_load_database()

    def __initUI__(self):
        self.setWindowTitle('Weather Stations Browser')
        self.setWindowIcon(icons.get_icon('master'))
        self.setWindowFlags(Qt.Window)

        now = datetime.now()

        # ---- Tab Widget Search

        # ---- Proximity filter groupbox

        label_Lat = QLabel('Latitude :')
        label_Lat2 = QLabel('North')

        self.lat_spinBox = QDoubleSpinBox()
        self.lat_spinBox.setAlignment(Qt.AlignCenter)
        self.lat_spinBox.setSingleStep(0.1)
        self.lat_spinBox.setValue(0)
        self.lat_spinBox.setMinimum(0)
        self.lat_spinBox.setMaximum(180)
        self.lat_spinBox.setSuffix(u' °')
        self.lat_spinBox.valueChanged.connect(self.proximity_grpbox_toggled)

        label_Lon = QLabel('Longitude :')
        label_Lon2 = QLabel('West')

        self.lon_spinBox = QDoubleSpinBox()
        self.lon_spinBox.setAlignment(Qt.AlignCenter)
        self.lon_spinBox.setSingleStep(0.1)
        self.lon_spinBox.setValue(0)
        self.lon_spinBox.setMinimum(0)
        self.lon_spinBox.setMaximum(180)
        self.lon_spinBox.setSuffix(u' °')
        self.lon_spinBox.valueChanged.connect(self.proximity_grpbox_toggled)

        self.radius_SpinBox = QComboBox()
        self.radius_SpinBox.addItems(['25 km', '50 km', '100 km', '200 km'])
        self.radius_SpinBox.currentIndexChanged.connect(
                self.search_filters_changed)

        prox_search_grid = QGridLayout()
        row = 0
        prox_search_grid.addWidget(label_Lat, row, 1)
        prox_search_grid.addWidget(self.lat_spinBox, row, 2)
        prox_search_grid.addWidget(label_Lat2, row, 3)
        row += 1
        prox_search_grid.addWidget(label_Lon, row, 1)
        prox_search_grid.addWidget(self.lon_spinBox, row, 2)
        prox_search_grid.addWidget(label_Lon2, row, 3)
        row += 1
        prox_search_grid.addWidget(QLabel('Search Radius :'), row, 1)
        prox_search_grid.addWidget(self.radius_SpinBox, row, 2)

        prox_search_grid.setColumnStretch(0, 100)
        prox_search_grid.setColumnStretch(4, 100)
        prox_search_grid.setRowStretch(row+1, 100)
        prox_search_grid.setHorizontalSpacing(20)
        prox_search_grid.setContentsMargins(10, 10, 10, 10)  # (L, T, R, B)

        self.prox_grpbox = QGroupBox("Proximity filter :")
        self.prox_grpbox.setCheckable(True)
        self.prox_grpbox.setChecked(False)
        self.prox_grpbox.toggled.connect(self.proximity_grpbox_toggled)
        self.prox_grpbox.setLayout(prox_search_grid)

        # ---- Province filter

        prov_names = ['All']
        prov_names.extend(self.PROV_NAME)
        self.prov_widg = QComboBox()
        self.prov_widg.addItems(prov_names)
        self.prov_widg.setCurrentIndex(0)
        self.prov_widg.currentIndexChanged.connect(self.search_filters_changed)

        layout = QGridLayout()
        layout.addWidget(self.prov_widg, 2, 1)
        layout.setColumnStretch(2, 100)
        layout.setVerticalSpacing(10)

        prov_grpbox = QGroupBox("Province filter :")
        prov_grpbox.setLayout(layout)

        # ---- Data availability filter

        # Number of years with data

        self.nbrYear = QSpinBox()
        self.nbrYear.setAlignment(Qt.AlignCenter)
        self.nbrYear.setSingleStep(1)
        self.nbrYear.setMinimum(0)
        self.nbrYear.setValue(3)
        self.nbrYear.valueChanged.connect(self.search_filters_changed)

        subgrid1 = QGridLayout()
        subgrid1.addWidget(self.nbrYear, 0, 0)
        subgrid1.addWidget(QLabel('years of data between'), 0, 1)

        subgrid1.setHorizontalSpacing(10)
        subgrid1.setContentsMargins(0, 0, 0, 0)  # (L, T, R, B)
        subgrid1.setColumnStretch(2, 100)

        # Year range

        self.minYear = QSpinBox()
        self.minYear.setAlignment(Qt.AlignCenter)
        self.minYear.setSingleStep(1)
        self.minYear.setMinimum(1840)
        self.minYear.setMaximum(now.year)
        self.minYear.setValue(1840)
        self.minYear.valueChanged.connect(self.minYear_changed)

        label_and = QLabel('and')
        label_and.setAlignment(Qt.AlignCenter)

        self.maxYear = QSpinBox()
        self.maxYear.setAlignment(Qt.AlignCenter)
        self.maxYear.setSingleStep(1)
        self.maxYear.setMinimum(1840)
        self.maxYear.setMaximum(now.year)
        self.maxYear.setValue(now.year)
        self.maxYear.valueChanged.connect(self.maxYear_changed)

        subgrid2 = QGridLayout()
        subgrid2.addWidget(self.minYear, 0, 0)
        subgrid2.addWidget(label_and, 0, 1)
        subgrid2.addWidget(self.maxYear, 0, 2)

        subgrid2.setHorizontalSpacing(10)
        subgrid2.setContentsMargins(0, 0, 0, 0)  # (L, T, R, B)
        subgrid2.setColumnStretch(4, 100)

        # Subgridgrid assembly

        grid = QGridLayout()

        grid.addWidget(QLabel('Search for stations with at least'), 0, 0)
        grid.addLayout(subgrid1, 1, 0)
        grid.addLayout(subgrid2, 2, 0)

        grid.setVerticalSpacing(5)
        grid.setRowStretch(0, 100)
        # grid.setContentsMargins(0, 0, 0, 0)  # (L, T, R, B)

        self.year_widg = QGroupBox("Data Availability filter :")
        self.year_widg.setLayout(grid)

        # ---- Toolbar

        self.btn_addSta = btn_addSta = QPushButton('Add')
        btn_addSta.setIcon(icons.get_icon('add2list'))
        btn_addSta.setIconSize(icons.get_iconsize('small'))
        btn_addSta.setToolTip('Add selected found weather stations to the '
                              'current list of weather stations.')
        btn_addSta.clicked.connect(self.btn_addSta_isClicked)

        btn_save = QPushButton('Save')
        btn_save.setIcon(icons.get_icon('save'))
        btn_save.setIconSize(icons.get_iconsize('small'))
        btn_save.setToolTip('Save current found stations info in a csv file.')
        btn_save.clicked.connect(self.btn_save_isClicked)

        self.btn_fetch = btn_fetch = QPushButton('Fetch')
        btn_fetch.setIcon(icons.get_icon('refresh'))
        btn_fetch.setIconSize(icons.get_iconsize('small'))
        btn_fetch.setToolTip("Updates the climate station database by"
                             " fetching it again from the ECCC ftp server.")
        btn_fetch.clicked.connect(self.btn_fetch_isClicked)

        toolbar_grid = QGridLayout()
        toolbar_widg = QWidget()

        for col, btn in enumerate([btn_addSta, btn_save, btn_fetch]):
            toolbar_grid.addWidget(btn, 0, col+1)

        toolbar_grid.setColumnStretch(toolbar_grid.columnCount(), 100)
        toolbar_grid.setSpacing(5)
        toolbar_grid.setContentsMargins(0, 30, 0, 0)  # (L, T, R, B)

        toolbar_widg.setLayout(toolbar_grid)

        # ---- Left Panel

        panel_title = QLabel('<b>Weather Station Search Criteria :</b>')

        left_panel = QFrame()
        left_panel_grid = QGridLayout()

        left_panel_grid.addWidget(panel_title, 0, 0)
        left_panel_grid.addWidget(self.prox_grpbox, 1, 0)
        left_panel_grid.addWidget(prov_grpbox, 2, 0)
        left_panel_grid.addWidget(self.year_widg, 3, 0)
        left_panel_grid.setRowStretch(4, 100)
        left_panel_grid.addWidget(toolbar_widg, 5, 0)

        left_panel_grid.setVerticalSpacing(20)
        left_panel_grid.setContentsMargins(0, 0, 0, 0)   # (L, T, R, B)
        left_panel.setLayout(left_panel_grid)

        # ----- Main grid

        # Widgets

        vLine1 = QFrame()
        vLine1.setFrameStyle(StyleDB().VLine)

        # Grid

        main_layout = QGridLayout(self)

        main_layout.addWidget(left_panel, 0, 0)
        main_layout.addWidget(vLine1, 0, 1)
        main_layout.addWidget(self.station_table, 0, 2)
        main_layout.addWidget(self.waitspinnerbar, 0, 2)

        main_layout.setContentsMargins(10, 10, 10, 10)  # (L,T,R,B)
        main_layout.setRowStretch(0, 100)
        main_layout.setHorizontalSpacing(15)
        main_layout.setVerticalSpacing(5)
        main_layout.setColumnStretch(col, 100)

    @property
    def stationlist(self):
        return self.station_table.get_stationlist()

    @property
    def search_by(self):
        return ['proximity', 'province'][self.tab_widg.currentIndex()]

    @property
    def prov(self):
        if self.prov_widg.currentIndex() == 0:
            return self.PROV_ABB
        else:
            return self.PROV_ABB[self.prov_widg.currentIndex()-1]

    @property
    def lat(self):
        return self.lat_spinBox.value()

    def set_lat(self, x, silent=True):
        if silent:
            self.lat_spinBox.blockSignals(True)
        self.lat_spinBox.setValue(x)
        self.lat_spinBox.blockSignals(False)
        self.proximity_grpbox_toggled()

    @property
    def lon(self):
        return self.lon_spinBox.value()

    def set_lon(self, x, silent=True):
        if silent:
            self.lon_spinBox.blockSignals(True)
        self.lon_spinBox.setValue(x)
        self.lon_spinBox.blockSignals(False)
        self.proximity_grpbox_toggled()

    @property
    def rad(self):
        return int(self.radius_SpinBox.currentText()[:-3])

    @property
    def prox(self):
        if self.prox_grpbox.isChecked():
            return (self.lat, -self.lon, self.rad)
        else:
            return None

    @property
    def year_min(self):
        return int(self.minYear.value())

    def set_yearmin(self, x, silent=True):
        if silent:
            self.minYear.blockSignals(True)
        self.minYear.setValue(x)
        self.minYear.blockSignals(False)

    @property
    def year_max(self):
        return int(self.maxYear.value())

    def set_yearmax(self, x, silent=True):
        if silent:
            self.maxYear.blockSignals(True)
        self.maxYear.setValue(x)
        self.maxYear.blockSignals(False)

    @property
    def nbr_of_years(self):
        return int(self.nbrYear.value())

    def set_yearnbr(self, x, silent=True):
        if silent:
            self.nbrYear.blockSignals(True)
        self.nbrYear.setValue(x)
        self.nbrYear.blockSignals(False)

    # ---- Weather Station Finder Handlers

    def start_load_database(self, force_fetch=False):
        """Start the process of loading the climate station database."""
        if self.stn_finder_thread.isRunning():
            return

        self.station_table.clear()
        self.waitspinnerbar.show()

        # Start the downloading process.
        if force_fetch:
            self.stn_finder_thread.started.connect(
                    self.stn_finder_worker.fetch_database)
        else:
            self.stn_finder_thread.started.connect(
                    self.stn_finder_worker.load_database)
        self.stn_finder_thread.start()

    @QSlot()
    def receive_load_database(self):
        """Handles when loading the database is finished."""
        # Disconnect the thread.
        self.stn_finder_thread.started.disconnect()

        # Quit the thread.
        self.stn_finder_thread.quit()
        waittime = 0
        while self.stn_finder_thread.isRunning():
            sleep(0.1)
            waittime += 0.1
            if waittime > 15:                                # pragma: no cover
                print("Unable to quit the thread.")
                break
        # Force an update of the GUI.
        self.proximity_grpbox_toggled()
        if self.stn_finder_worker.data is None:
            self.waitspinnerbar.show_warning_icon()
        else:
            self.waitspinnerbar.hide()

    # ---- GUI handlers

    def show(self):
        super(WeatherStationBrowser, self).show()
        qr = self.frameGeometry()
        if self.parent():
            parent = self.parent()
            wp = parent.frameGeometry().width()
            hp = parent.frameGeometry().height()
            cp = parent.mapToGlobal(QPoint(wp/2, hp/2))
        else:
            cp = QDesktopWidget().availableGeometry().center()

        qr.moveCenter(cp)
        self.move(qr.topLeft())

    # -------------------------------------------------------------------------

    def minYear_changed(self):
        min_yr = min_yr = max(self.minYear.value(), 1840)

        now = datetime.now()
        max_yr = now.year

        self.maxYear.setRange(min_yr, max_yr)
        self.search_filters_changed()

    def maxYear_changed(self):
        min_yr = 1840

        now = datetime.now()
        max_yr = min(self.maxYear.value(), now.year)

        self.minYear.setRange(min_yr, max_yr)
        self.search_filters_changed()

    # ---- Toolbar Buttons Handlers

    def btn_save_isClicked(self):
        ddir = os.path.join(os.getcwd(), 'weather_station_list.csv')
        filename, ftype = QFileDialog().getSaveFileName(
                self, 'Save normals', ddir, '*.csv;;*.xlsx;;*.xls')
        self.station_table.save_stationlist(filename)

    def btn_addSta_isClicked(self):
        rows = self.station_table.get_checked_rows()
        if len(rows) > 0:
            staList = self.station_table.get_content4rows(rows)
            self.staListSignal.emit(staList)
            print('Selected stations sent to list')
        else:
            print('No station currently selected')

    def btn_fetch_isClicked(self):
        """Handles when the button fetch is clicked."""
        self.start_load_database(force_fetch=True)

    # ---- Search Filters Handlers

    def proximity_grpbox_toggled(self):
        """
        Set the values for the reference geo coordinates that are used in the
        WeatherSationView to calculate the proximity values and forces a
        refresh of the content of the table.
        """
        if self.prox_grpbox.isChecked():
            self.station_table.set_geocoord((self.lat, -self.lon))
        else:
            self.station_table.set_geocoord(None)
        self.search_filters_changed()

    def search_filters_changed(self):
        """
        Search for weather stations with the current filter values and forces
        an update of the station table content.
        """
        if self.stn_finder_worker.data is not None:
            stnlist = self.stn_finder_worker.get_stationlist(
                    prov=self.prov, prox=self.prox,
                    yrange=(self.year_min, self.year_max, self.nbr_of_years))
            self.station_table.populate_table(stnlist)


# %% if __name__ == '__main__'

if __name__ == '__main__':

    app = QApplication(sys.argv)

    ft = app.font()
    ft.setFamily('Segoe UI')
    ft.setPointSize(10)
    app.setFont(ft)

    stn_browser = WeatherStationBrowser()
    stn_browser.show()

    stn_browser.set_lat(45.40)
    stn_browser.set_lon(73.15)
    stn_browser.set_yearmin(1980)
    stn_browser.set_yearmax(2015)
    stn_browser.set_yearnbr(20)
    stn_browser.search_filters_changed()

    sys.exit(app.exec_())
