# -*- coding: utf-8 -*-
"""
Copyright 2014-2015 Jean-Sebastien Gosselin

email: jnsebgosselin@gmail.com

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

#----- STANDARD LIBRARY IMPORTS -----

from os import path
from calendar import monthrange
import csv
from math import sin, cos, sqrt, atan2, radians
#from time import clock

#----- THIRD PARTY IMPORTS -----

import numpy as np
import matplotlib as mpl
mpl.use('Qt4Agg')
mpl.rcParams['backend.qt4'] = 'PySide'
#from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg
from matplotlib.backends.backend_agg import FigureCanvasAgg
import matplotlib.pyplot as plt

from PySide import QtGui

from xlrd.xldate import xldate_from_date_tuple
from xlrd import xldate_as_tuple, open_workbook
#from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT

#---- PERSONAL IMPORTS ----

import database as db
#import meteo

class LabelDatabase():
    
    def __init__(self, language): #------------------------------ English -----
        
        self.temperature = u'Tmax weekly (°C)'
        self.mbgs = 'Water Level at Well %s (mbgs)'
        self.masl = 'Water Level at Well %s (masl)'
        self.precip = 'Ptot weekly (mm)'
        self.station_meteo = 'Climatological Station = %s (located %0.1f km from the well)'
        self.month_names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                            "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
                            
        if language == 'French': #-------------------------------- French -----
            
            self.mbgs = "Niveau d'eau au puits %s (mbgs)"
            self.masl = "Niveau d'eau au puits %s (masl)"
            self.precip = 'Ptot hebdo (mm)'
            self.temperature = u'Tmax hebdo (°C)'
            self.station_meteo = u'Station climatologique = %s (située à %0.1f km du puits)'
            self.month_names = ["JAN", u"FÉV", "MAR", "AVR", "MAI", "JUN",
                                "JUL", u"AOÛ", "SEP", "OCT", "NOV", u"DÉC"]


class Hydrograph(mpl.figure.Figure):
    def __init__(self, *args, **kargs):
        super(Hydrograph, self).__init__(*args, **kargs)
        
        self.isHydrographExists = False
        
        #---- set canvas and renderer ----
        
        self.set_canvas(FigureCanvasAgg(self))
        
        #---- Fig Init ----        
        
        self.fwidth = 11.0
        self.fheight = 8.5
        self.patch.set_facecolor('white')
        
        #---- Database ----
        
        HeaderDB = db.FileHeaders()
        self.header = HeaderDB.graph_layout
        
        #---- Scales ----
        
        self.WLmin = 0
        self.WLscale = 0
        
        self.RAINscale = 20
                
        self.TIMEmin = 36526
        self.TIMEmax = 36526
        
        self.NZGrid = 20 # Dundurn: 17 # Old version: 26
        
        #---- Labels ----  
        
        self.title_state = 0 # 0: No title; 1: With Title
        self.title_text = 'Add A Title To The Figure Here'
        self.language = 'English'
                   
        #---- Layout Options
        
        self.WLdatum = 0 # 0: mbgs;  1: masl
        self.trend_line = 0
        self.isLegend = False
        self.meteoOn = True # controls wether meteo data are plotted or not
        self.gridLines = 2 # 0 -> None, 1 -> "-" 2 -> ":"
        self.datemode = 'month' # 'month' or 'year'
        
        #---- Waterlvl Obj ----
        
        self.WaterLvlObj = []
        
        #---- Daily Weather ----
        
        self.fmeteo = [] # path to the weather data file (.out)
        self.finfo = []  # path the the .log file associated with the .out file
        
        self.TIMEmeteo = np.array([])
        self.TMAX = np.array([])
        self.PTOT = np.array([])        
        self.RAIN = np.array([])
        
        #---- Bin Redistributed Weather ----
        
        self.bTIME = np.array([])
        self.bTMAX = np.array([])
        self.bPTOT = np.array([])
        self.bRAIN = np.array([])
        
        self.bwidth_indx = 1
        #   0: 1 day;
        #   1: 7 days;
        #   2: 15 days;
        #   3: 30 days;
        #   4: monthly;
        #   5: yearly
        
        self.NMissPtot = []
        
    def generate_hydrograph(self, MeteoObj): #================================

        #---- Reinit Figure ----
        
        self.clf()
        
        fheight = self.fheight # Figure height in inches
        fwidth = self.fwidth   # Figure width in inches
        
        if self.meteoOn == False:
            fheight /= 2

        self.set_size_inches(fwidth, fheight, forward=True) 
                        
        #---- Update Variables ----
        
        WaterLvlObj = self.WaterLvlObj 
        
        #---- Assign class values ----
        
        self.label_font_size = 14
        self.date_labels_display_pattern = 1
        
        if self.meteoOn == True:
        
            #---- Assign Weather Data ----
            
            self.name_meteo = MeteoObj.STA
            
            DATA = MeteoObj.DATA
            # DATA = [YEAR, MONTH, DAY, TMAX, TMIN, TMEAN, PTOT, ETP, RAIN]
            
            self.TIMEmeteo = MeteoObj.TIME # Time in numeric format (days)
            self.TMAX = DATA[:, 3] # Daily maximum temperature (deg C)
            self.PTOT = DATA[:, 6] # Daily total precipitation (mm)        
            self.RAIN = DATA[:, -1]
            
            #---- Resample Data in Bins ----
            
            self.resample_bin()
        
        #-------------------------------------------------- AXES CREATION ----        
        
        # http://stackoverflow.com/questions/15303284/
        # multiple-y-scales-but-only-one-enabled-for-pan-and-zoom
        
        # http://matplotlib.1069221.n5.nabble.com/Control-twinx-series-zorder-
        #        ax2-series-behind-ax1-series-or-place-ax2-on-left-ax1
        #        -on-right-td12994.html
        
        #--- Time (host) ---
        
        # Also holds the gridlines.
        
        self.ax1 = self.add_axes([0, 0, 1, 1], frameon=False)

        #--- Frame ---
        
        # Only used to display the frame so it is always on top.
        
        self.ax0 = self.add_axes(self.ax1.get_position(), frameon=True)
        self.ax0.patch.set_visible(False) 
        self.ax0.set_zorder(self.ax1.get_zorder() + 20)
        self.ax0.tick_params(bottom='off', top='off', left='off', right='off',
                             labelbottom='off', labelleft='off')
                                       
        #--- Water Levels ---
        
        self.ax2 = self.ax1.twinx()
        self.ax2.set_zorder(self.ax1.get_zorder() + 10)      
        self.ax2.yaxis.set_ticks_position('left')
        self.ax2.yaxis.set_label_position('left') 
        self.ax2.tick_params(axis='y', direction='out', labelsize=10)
        for loc in ['top', 'bottom', 'right', 'left']:
            self.ax2.spines[loc].set_visible(False)
            
        self.update_waterlvl_scale()
        
        if self.meteoOn == True:
                    
            #--- Precipitation ---
            
            self.ax3 = self.ax1.twinx()
            self.ax3.set_zorder(self.ax1.get_zorder() + 10)
            self.ax3.set_navigate(False)
            for loc in ['top', 'bottom', 'right', 'left']:
                self.ax3.spines[loc].set_visible(False) 
            
            #--- Air Temperature ---
        
            self.ax4 = self.ax1.twinx()
            self.ax4.set_zorder(self.ax1.get_zorder() - 10)
            self.ax4.set_navigate(False)
            for loc in ['top', 'bottom', 'right', 'left']:
                self.ax4.spines[loc].set_visible(False)
        
        #-------------------------------------------------- Update margins ---
        
        self.bottom_margin = 0.75
        self.set_margins() # set margins for all the axes
        
        #--------------------------------------------------- FIGURE TITLE ----
           
        self.dZGrid_inch = (fheight - 2 * self.bottom_margin) / self.NZGrid
            
        xTitle = (self.TIMEmin + self.TIMEmax) / 2.
        ytitle = self.NZGrid + (0.4 / self.dZGrid_inch)
        
        self.figTitle = self.ax1.text(xTitle, ytitle, self.title_text,
                                      fontsize=18 * fheight / 8.5,
                                      horizontalalignment='center', 
                                      verticalalignment='center')
                                      
        self.draw_figure_title()
                
        #------------------------------------------- WEATHER STATION TEXT ----
        
        # Calculate horizontal distance between weather station and
        # observation well.

        LAT1 = float(WaterLvlObj.LAT)
        LON1 = float(WaterLvlObj.LON)
        LAT2 = float(MeteoObj.LAT)
        LON2 = float(MeteoObj.LON)
            
        self.dist = LatLong2Dist(LAT1, LON1, LAT2, LON2)
         
        # display text on figure
         
        text1_ypos = self.NZGrid + 0.025 / self.dZGrid_inch
       
        self.text1 = self.ax1.text(self.TIMEmax, text1_ypos, '',
                                   rotation=0, verticalalignment='bottom',
                                   horizontalalignment='right', fontsize=10)
                   
        #---------------------------------------------------- TIME + GRID ----            
        
        self.xlab = [] # Initiate variable
        self.set_time_scale()
        
        self.ax1.xaxis.set_ticklabels([])
        self.ax1.xaxis.set_ticks_position('bottom')
        self.ax1.tick_params(axis='both',direction='out')
        
        self.ax1.set_yticks(np.arange(0, self.NZGrid, 2))
        self.ax1.yaxis.set_ticklabels([])
        self.ax1.tick_params(axis='y', length=0)
        self.ax1.patch.set_facecolor('none')
        
        self.set_gridLines()         
            
        #---------------------------------------------------- WATER LEVEL ----
        
        #---- Continuous Line Datalogger ----
        
        self.l1_ax2, = self.ax2.plot([], [], '-', zorder = 10, linewidth=1)
        
        #---- Data Point Datalogger ----
        
        self.l2_ax2, = self.ax2.plot([], [], '.', color=[0.65, 0.65, 1.],
                                     markersize=5)
                                     
        #---- Manual Mesures ----
                                     
        self.h_WLmes, = self.ax2.plot([], [], 'o', zorder = 15,
                                     label='Manual measures')
                                            
        plt.setp(self.h_WLmes, markerfacecolor='none', markersize=5,
                 markeredgecolor=(1, 0.25, 0.25), markeredgewidth=1.5)
        
        self.draw_waterlvl()
         
        #-------------------------------------------------------- WEATHER ----
        
        if self.meteoOn == True:
            
            #---------------------------------------------- PRECIPITATION ----
            
            self.update_precip_scale()
            
            self.ax3.yaxis.set_ticks_position('right')
            self.ax3.yaxis.set_label_position('right')
            self.ax3.tick_params(axis='y', direction='out', labelsize=10)
            
            #---- INIT ARTISTS ----
                
            self.PTOT_bar, = self.ax3.plot([], [])
            self.RAIN_bar, = self.ax3.plot([], [])
            self.baseline, = self.ax3.plot([self.TIMEmin, self.TIMEmax],
                                           [0, 0], 'k')
                 
            #-------------------------------------------- AIR TEMPERATURE ----
          
            TEMPmin = -40
            TEMPscale = 20
            TEMPmax = 40
            
            self.ax4.axis(ymin=TEMPmax-TEMPscale*self.NZGrid, 
                          ymax=TEMPmax)
               
            yticks_position = np.array([TEMPmin, 0, TEMPmax])
            self.ax4.set_yticks(yticks_position)
            self.ax4.yaxis.set_ticks_position('left')
            self.ax4.tick_params(axis='y', direction='out', labelsize=10)
            self.ax4.yaxis.set_label_position('left')

            #---- INIT ARTISTS ----
                
            self.l1_ax4, = self.ax4.plot([], [])                # fill shape
            self.l2_ax4, = self.ax4.plot([], [], color='black') # contour line
        
            #------------------------------------- MISSING VALUES MARKERS ----
    
            if self.finfo:
                
                #---- PRECIPITATION ----
                
                PTOTmiss_time, _ = load_weather_log(self.finfo,
                                                    'Total Precip (mm)', 
                                                    self.bTIME, self.bPTOT)
                                                        
                self.NMissPtot = len(PTOTmiss_time)
                
                y = np.ones(self.NMissPtot) * -5 * self.RAINscale / 20.
                
                self.PTOTmiss_dots, = self.ax3.plot(PTOTmiss_time, y, '.r')
                plt.setp(self.PTOTmiss_dots, markersize=3)
                
                #---- Air Temperature ----
            
                Temp_missing_time, _ = load_weather_log(self.finfo,
                                                        'Max Temp (deg C)',                                   
                                                        self.bTIME, self.bTMAX)
                                                        
                NMissTMAX = len(Temp_missing_time) 
                y = np.ones(NMissTMAX) * 35
                
                TMAXmiss_dots, = self.ax4.plot(Temp_missing_time, y, '.r')
                plt.setp(TMAXmiss_dots, markersize=3)                
                                          
            self.draw_weather()
                
        #--------------------------------------------------- DRAW YLABELS ----
                                                                 
        self.draw_ylabels()
        
        #--------------------------------------------------------- LEGEND ----

        if self.isLegend == True:
            
            #---- Water Level ----
            
            self.ax2.legend(loc=4, numpoints=1, fontsize=10, ncol=2)
            
            #---- Weather ----
    
            rec1 = plt.Rectangle((0, 0), 1, 1, fc=[0.65,0.65,0.65])
            rec2 = plt.Rectangle((0, 0), 1, 1, fc=[0, 0, 1])
            rec3 = plt.Rectangle((0, 0), 1, 1, fc=[1, 0.65, 0.65])
           
            labels = ['Snow', 'Rain', 'Air Temperature', 'Missing Data']
            
            self.ax4.legend([rec1, rec2, rec3, TMAXmiss_dots], labels,
                            loc=[0.01, 0.45], numpoints=1, fontsize=10)
        
        #---------------------------------------------------- UPDATE FLAG ----
        
        self.isHydrographExists = True
        
    def set_fig_size(self, fwidth, fheight): #================================
        
        self.fwidth = fwidth   # Figure width in inches   
        self.fheight = fheight # Figure height in inches
        
        self.set_size_inches(fwidth, fheight)
        self.set_margins()
        self.draw_ylabels()
        self.set_time_scale()
        
        self.canvas.draw()
        
    def set_margins(self): #==================================================
        
        #---- MARGINS (Inches / Fig. Dimension) ----
        
        left_margin  = 0.85 / self.fwidth
        right_margin = 0.85 / self.fwidth
        top_margin = 0.35 / self.fheight
        bottom_margin = 0.75 / self.fheight
        
        if self.title_state == 1:
            top_margin = 0.75 / self.fheight
            
        if self.meteoOn == False:
            right_margin = 0.35 / self.fwidth
        
        #---- MARGINS (% of figure) ----
        
        x0 = left_margin
        w = 1 - (left_margin + right_margin)
        if self.meteoOn == True:            
            y0 = bottom_margin          
            h = 1 - (bottom_margin + top_margin)
        else:
            y0 = bottom_margin / 2.
            h = 1 - (bottom_margin + top_margin) / 2.
        
        self.ax0.set_position([x0, y0, w, h])
        self.ax1.set_position([x0, y0, w, h])        
        self.ax2.set_position([x0, y0, w, h])
        if self.meteoOn == True:
            self.ax3.set_position([x0, y0, w, h])
            self.ax4.set_position([x0, y0, w, h])
            
            
    def draw_ylabels(self): #=================================================
        
        labelDB = LabelDatabase(self.language)
        
        #----------------------------------------- Calculate LabelPadding ----
        
        left_margin  = 0.85
        right_margin = 0.85
        if self.meteoOn == False:
            right_margin = 0.35
            
        axwidth = (self.fwidth - left_margin - right_margin)
        print(axwidth)
        labPad = 0.3 / 2.54 # in Inches       
        labPad /= axwidth   # relative coord.
        
        #-------------------------------- YLABELS LEFT (Temp. & Waterlvl) ----
        
        if self.WLdatum == 0:       
            lab_ax2 = labelDB.mbgs % self.WaterLvlObj.name_well
        elif self.WLdatum == 1:
            lab_ax2 = labelDB.masl % self.WaterLvlObj.name_well
         
        #---- Water Level ----
         
        self.ax2.set_ylabel(lab_ax2,rotation=90,
                            fontsize=self.label_font_size,
                            verticalalignment='bottom',
                            horizontalalignment='center')
                       
        # Get bounding box dimensions of yaxis ticklabels for ax2
        renderer = self.canvas.get_renderer() 
        bbox2_left, _ = self.ax2.yaxis.get_ticklabel_extents(renderer)
        
        # bbox are structured in the the following way:   [[ Left , Bottom ],
        #                                                  [ Right, Top    ]]
        
        # Transform coordinates in ax2 coordinate system.       
        bbox2_left = self.ax2.transAxes.inverted().transform(bbox2_left)
        
        # Calculate the labels positions in x and y.
        ylabel2_xpos = bbox2_left[0, 0] - labPad
        ylabel2_ypos = (bbox2_left[1, 1] + bbox2_left[0, 1]) / 2.
        
        if self.meteoOn == False:            
            self.ax2.yaxis.set_label_coords(ylabel2_xpos, ylabel2_ypos)
            return
            
        #---- Temperature ----
    
        self.ax4.set_ylabel(labelDB.temperature, rotation=90, va='bottom',
                            ha='center', fontsize=self.label_font_size)
                            
        # Get bounding box dimensions of yaxis ticklabels for ax4                    
        bbox4_left, _ = self.ax4.yaxis.get_ticklabel_extents(renderer)
        
        # Transform coordinates in ax4 coordinate system.
        bbox4_left = self.ax4.transAxes.inverted().transform(bbox4_left)        
        
        # Calculate the labels positions in x and y.
        ylabel4_xpos = bbox4_left[0, 0] - labPad
        ylabel4_ypos = (bbox4_left[1, 1] + bbox4_left[0, 1]) / 2.
        
        # Take the position which is farthest from the left y axis in order
        # to have both labels on the left aligned.
        ylabel_xpos = min(ylabel2_xpos, ylabel4_xpos)

        self.ax2.yaxis.set_label_coords(ylabel_xpos, ylabel2_ypos)
        self.ax4.yaxis.set_label_coords(ylabel_xpos, ylabel4_ypos)
                
        #---------------------------------------- ylabels : Precipitation ----
        
        self.ax3.set_ylabel(labelDB.precip, rotation=270, va='bottom', 
                            ha='center', fontsize=self.label_font_size)
                        
        # Get bounding box dimensions of yaxis ticklabels for ax3
        _, bbox3_right = self.ax3.yaxis.get_ticklabel_extents(renderer)
        
        # Transform coordinates in ax3 coordinate system and
        # calculate the labels positions in x and y.
        bbox3_right = self.ax3.transAxes.inverted().transform(bbox3_right)
        
        ylabel3_xpos = bbox3_right[1, 0] + labPad
        ylabel3_ypos = (bbox3_right[1, 1] + bbox3_right[0, 1]) / 2.
        
        # Take the position which is farthest from the left y axis in order
        # to have both labels on the left aligned.

        self.ax3.yaxis.set_label_coords(ylabel3_xpos, ylabel3_ypos)
        
        #------------------------------------------ WEATHER STATION LABEL ----
        
        text_top_margin = labelDB.station_meteo % (self.name_meteo,
                                                   self.dist)
        self.text1.set_text(text_top_margin)
        
        
    def set_waterLvlObj(self, WaterLvlObj): #=================================
        self.WaterLvlObj = WaterLvlObj
   
    
    def checkLayout(self, name_well, filename): #=============================
        
        with open(filename, 'r') as f:
            reader = list(csv.reader(f, delimiter='\t'))
            reader = np.array(reader)
       
        # Check if config file is from an old version of Hydroprint
        # and if yes, convert it to the new version.
       
        nCONFG, nPARA = np.shape(reader)

        if nPARA < len(self.header[0]):
            
            nMissing = len(self.header[0]) - nPARA
            
            col2add = np.zeros((nCONFG, nMissing)).astype(int)
            col2add = col2add.astype(str)
            
            reader = np.hstack((reader, col2add))
            reader[0] = self.header[0]
            
            if nPARA < 8:
                reader[1:, 7] = 'Add A Title To The Figure Here'
            if nPARA < 9:
                reader[1:, 8] = 20
            if nPARA < 10:
                reader[1:, 9] = 0
            if nPARA < 11:
                reader[1:, 10] = 0
            
            with open(filename, 'w') as f:
                writer = csv.writer(f, delimiter='\t')
                writer.writerows(reader)
             
            msg = ('The "graph_layout.lst" file is from an older version ' +
                   'of WHAT. The old file has been converted to the newer ' +
                   'version.') 
            print(msg)
        
        # Check if there is a layout stored for the current 
        # selected observation well.
        row = np.where(reader[:,0] == name_well)[0]
           
        if len(row) > 0:
            layoutExist = True
        else:
            layoutExist = False
           
        return layoutExist
        
                    
    def load_layout(self, name_well, filename): #=============================      
            
        # A <checkConfig> is supposed to have been carried before this method
        # is called. So it can be supposed at this point that everything is
        # fine with the graph layout for this well.
        
        with open(filename, 'r') as f:
            reader = list(csv.reader(f, delimiter='\t'))
            reader = np.array(reader)
     
        row = np.where(reader[:,0] == name_well)[0]
        
        reader = reader[row][0]
        
        self.fmeteo = reader[1]
        self.finfo = self.fmeteo[:-3] + 'log'
                          
        self.WLmin = reader[2].astype(float)
        self.WLscale = reader[3].astype(float)
            
        self.TIMEmin = reader[4].astype(float)
        self.TIMEmax = reader[5].astype(float)
        
        self.title_state = reader[6].astype(float)
        if self.title_state != 0:
            self.title_state = 1
        
        self.title_text = reader[7].astype(str)
        self.RAINscale = reader[8].astype(float)
        self.WLdatum = reader[9].astype(int)
        self.trend_line = reader[10].astype(int)

        
    def save_layout(self, name_well, filename): #=============================
        
        #---- load file ----
        
        with open(filename, 'r') as f:
            reader = list(csv.reader(f, delimiter='\t'))
            reader = np.array(reader)
        
        #---- update content ----
         
        rowx = np.where(reader[:,0] == name_well)[0]
        
        new = [name_well, self.fmeteo, self.WLmin, self.WLscale, 
               self.TIMEmin, self.TIMEmax,self.title_state, self.title_text,
               self.RAINscale, self.WLdatum, self.trend_line]
        
        if len(rowx) == 0:
            reader = np.vstack((reader, new))
        else:
            reader = np.delete(reader, rowx, 0)
            reader = np.vstack((reader, new))
        reader[0] = self.header[0]
        
        #---- save file ----
            
        with open(filename, 'w') as f:
            writer = csv.writer(f, delimiter='\t')
            writer.writerows(reader)
    
      
    def best_fit_waterlvl(self): #============================================
        
        WL = self.WaterLvlObj.lvl   
        if self.WLdatum == 1: # masl
            WL = self.WaterLvlObj.ALT - WL
        
        WL = WL[~np.isnan(WL)]
        dWL = np.max(WL) - np.min(WL)
        ygrid = self.NZGrid - 10
        
        #----- WL Scale -----
        
        SCALE = np.hstack((np.arange(0.05, 0.30, 0.05), 
                           np.arange(0.3, 5.1, 0.1)))
        dSCALE = np.abs(SCALE - dWL / ygrid)
        indx = np.where(dSCALE == np.min(dSCALE))[0][0]
        
        self.WLscale = SCALE[indx]
        
        #-----WL Min Value-----
        
        if self.WLdatum == 0: # mbgs
            N = np.ceil(np.max(WL) / self.WLscale)
        elif self.WLdatum == 1: # masl        
            #WL = self.WaterLvlObj.ALT - WL
            N = np.floor(np.min(WL) / self.WLscale)
        
        self.WLmin = self.WLscale * N
        
        return self.WLscale, self.WLmin
    
    
    def best_fit_time(self, TIME): #==========================================
        
        # ----- Data Start -----
        
        date0 = xldate_as_tuple(TIME[0], 0)
        date0 = (date0[0], date0[1], 1)
        
        self.TIMEmin = xldate_from_date_tuple(date0, 0)
        
        # ----- Date End -----
        
        date1 = xldate_as_tuple(TIME[-1], 0)
        
        year =  date1[0]
        month = date1[1] + 1
        if month > 12:
            month = 1
            year += 1
        
        date1 = (year, month, 1)
        
        self.TIMEmax = xldate_from_date_tuple(date1, 0)
        
        return date0, date1
        
        
    def resample_bin(self): #==================================================
   
        # 1 day; 7 days; 15 days; 30 days; monthly; yearly  
        self.bwidth = [1., 7., 15., 30., 30., 365.][self.bwidth_indx]
        bwidth = self.bwidth
        
        if self.bwidth_indx == 0: # daily
            
            self.bTIME = np.copy(self.TIMEmeteo)
            self.bTMAX = np.copy(self.TMAX)
            self.bPTOT = np.copy(self.PTOT)
            self.bRAIN = np.copy(self.RAIN)

        elif self.bwidth_indx in [1, 2, 3]: #7 days; 15 days; 30 days

            self.bTIME = self.bin_sum(self.TIMEmeteo, bwidth) / bwidth
            self.bTMAX = self.bin_sum(self.TMAX, bwidth) / bwidth
            self.bPTOT = self.bin_sum(self.PTOT, bwidth)
            self.bRAIN = self.bin_sum(self.RAIN, bwidth)            

        elif self.bwidth_indx == 4 : # monthly
            print('option not yet available, kept default of 1 day')

        elif self.bwidth_indx == 5 : # yearly
            print('option not yet available, kept default of 1 day')
            
    
    def bin_sum(self, x, bwidth): #============================================
       
        """
        Sum data x over bins of width "bwidth" starting at indice 0 of x.
        If there is residual data at the end because of the last bin being not
        complete, data are rejected and removed from the reshaped series.
        """
        
        nbin = np.floor(len(x) / bwidth)
        
        bheight = x[:nbin*bwidth].reshape(nbin, bwidth)
        bheight = np.sum(bheight, axis=1)
        
        # nres = len(x) - (nbin * bwidth)
        
        return bheight
            
    
    def draw_waterlvl(self): #=================================================
        
        """
        This method is called the first time the graph is plotted and each
        time water level datum is changed.
        """
        
        #------------------------------------------------- Logger Measures ----
        
        time = self.WaterLvlObj.time
        
        if self.WLdatum == 1: # masl
        
            water_lvl = self.WaterLvlObj.ALT - self.WaterLvlObj.lvl
                                                                
        else: # mbgs -> yaxis is inverted
        
            water_lvl = self.WaterLvlObj.lvl

        if self.trend_line == 1:
            
            tfilt, wlfilt = filt_data(time, water_lvl, 7)
            
            self.l1_ax2.set_data(tfilt, wlfilt)
            self.l1_ax2.set_label('WL Trend Line')
                          
            self.l2_ax2.set_data(time, water_lvl)
                          
        else:
            
            self.l1_ax2.set_data(time, water_lvl)
            self.l1_ax2.set_label('Water Level')
            
            self.l2_ax2.set_data([], [])
                        
        #------------------------------------------------ Manual Measures ----
        
        TIMEmes = self.WaterLvlObj.TIMEmes
        WLmes = self.WaterLvlObj.WLmes
        
        if len(WLmes) > 1:
            if self.WLdatum == 1:   # masl
            
                WLmes = self.WaterLvlObj.ALT - WLmes
               
            self.h_WLmes.set_data(TIMEmes, WLmes)
        
                                                           
    def draw_weather(self): #=================================================

        """
        This method is called the first time the graph is plotted and each
        time the time scale is changed by the user.
        """


        if self.meteoOn == False:
            print('meteoOn == False')
            return
        #--------------------------------- SUBSAMPLE WEATHER DATA TO PLOT ----
        
        istart = np.where(self.bTIME > self.TIMEmin)[0]
        if len(istart) == 0:
            istart = 0
        else:
            istart = istart[0]
            if istart > 0:
                istart -= 1
        
        iend = np.where(self.bTIME < self.TIMEmax)[0]
        if len(iend) == 0:
            iend = 0
        else:
            iend = iend[-1]
            if iend < len(self.bTIME):
                iend += 1

        time = self.bTIME[istart:iend]
        Tmax = self.bTMAX[istart:iend]
        Ptot = self.bPTOT[istart:iend]
        Rain = self.bRAIN[istart:iend]
        
        #---------------------------------------------------- PLOT PRECIP ----
        
        TIME2X = np.zeros(len(time) * 4)
        Ptot2X = np.zeros(len(time) * 4)
        Rain2X = np.zeros(len(time) * 4)
        
        n = self.bwidth / 2.
        f = 0.85 # Space between individual bar.
        
        TIME2X[0::4] = time - n * f
        TIME2X[1::4] = time - n * f
        TIME2X[2::4] = time + n * f
        TIME2X[3::4] = time + n * f
        
        Ptot2X[0::4] = 0
        Ptot2X[1::4] = Ptot
        Ptot2X[2::4] = Ptot
        Ptot2X[3::4] = 0
        
        Rain2X[0::4] = 0
        Rain2X[1::4] = Rain
        Rain2X[2::4] = Rain
        Rain2X[3::4] = 0
        
        
        self.PTOT_bar.remove()
        self.RAIN_bar.remove()
        
        self.PTOT_bar = self.ax3.fill_between(TIME2X, 0., Ptot2X, 
                                              color=(0.65,0.65,0.65),
                                              alpha=1., edgecolor='none')
                                            
        self.RAIN_bar = self.ax3.fill_between(TIME2X, 0., Rain2X, color='blue',
                                              alpha=1., edgecolor='none')
                                            
        self.baseline.set_data([self.TIMEmin, self.TIMEmax], [0, 0])
                                                    
        #--------------------------------------------------- PLOT AIR TEMP ----
        
        TIME2X = np.zeros(len(time)*2)
        Tmax2X = np.zeros(len(time)*2)
        
        n = self.bwidth / 2.
        TIME2X[0:2*len(time)-1:2] = time - n
        TIME2X[1:2*len(time):2] = time + n
        Tmax2X[0:2*len(time)-1:2] = Tmax
        Tmax2X[1:2*len(time):2] = Tmax

        color = [255./255, 204./255, 204./255]        
        
        self.l1_ax4.remove()
        self.l1_ax4 = self.ax4.fill_between(TIME2X, 0., Tmax2X, color=color,
                                            edgecolor='none')
        
        self.l2_ax4.set_xdata(TIME2X)
        self.l2_ax4.set_ydata(Tmax2X)
        
    def set_time_scale(self): #===============================================
        
        #----------------------------------------------- time min and max ----
        
        if self.datemode == 'year':
            
            year = xldate_as_tuple(self.TIMEmin, 0)[0]
            self.TIMEmin = xldate_from_date_tuple((year, 1, 1), 0)
            
            last_month = xldate_as_tuple(self.TIMEmax, 0)[1] == 1
            last_day = xldate_as_tuple(self.TIMEmax, 0)[2] == 1
            
            if last_month and last_day:
                pass
            else:                                
                year = xldate_as_tuple(self.TIMEmax, 0)[0] + 1
                self.TIMEmax = xldate_from_date_tuple((year, 1, 1), 0)
                
        #---------------------------------------------- xticks and labels ----
        
        #---- compute parameters ----
        
        xticks_info = self.make_xticks_info()
        
        #---- major ----
        
        self.ax1.set_xticks(xticks_info[0])

        #---- minor ----

        # labels are set using the minor ticks.
        
        self.ax1.set_xticks(xticks_info[1], minor=True)
        self.ax1.tick_params(which='minor', length=0)                             
        self.ax1.xaxis.set_ticklabels(xticks_info[2], minor=True, rotation=45,
                                      va='top', ha='right', fontsize=10)
        
        #------------------------------------------- text horiz. position ----
        
        # adjust "climatological station" label and 
        # title horizontal position
        
        self.text1.set_x(self.TIMEmax)
        self.figTitle.set_x((self.TIMEmin + self.TIMEmax) / 2.)
        
        #---------------------------------------------------- axis limits ----
           
        self.ax1.axis([self.TIMEmin, self.TIMEmax, 0, self.NZGrid])
       
    def draw_xlabels(self): #==================================================
        
        # Called when there is a change in language of the labels
        # of the graph
        
        _, _, xticks_labels = self.make_xticks_info()
        
        self.ax1.xaxis.set_ticklabels(xticks_labels, minor=True, rotation=45,
                                      va='top', ha='right', fontsize=10)
                                            
    def draw_figure_title(self): #=============================================
        
        if self.title_state == 1:

            self.figTitle.set_text(self.title_text)
            
        else:

            self.figTitle.set_text('')
            
    
                    
    def update_waterlvl_scale(self): #=========================================
        
        NZGrid = self.NZGrid
        dZGrid = 8
        if self.meteoOn == False:
            NZGrid = NZGrid/2+2
            dZGrid = 0
            
        if self.WLdatum == 1:   # masl
        
            WLmin = self.WLmin
            WLscale = self.WLscale
            WLmax = WLmin + NZGrid * WLscale
            
            yticks_position = np.arange(WLmin,
                                        WLmin + (NZGrid - dZGrid) * WLscale,
                                        WLscale * 2)
                                                                                
        else: # mbgs: Y axis is inverted
        
            WLmax = self.WLmin
            WLscale = self.WLscale    
            WLmin = WLmax - NZGrid * WLscale
            
            yticks_position = np.arange(WLmax, 
                                        WLmax - (NZGrid - dZGrid) * WLscale,
                                        WLscale * -2)
                                                
        self.ax2.axis(ymin=WLmin, ymax=WLmax)
        self.ax2.set_yticks(yticks_position)
                
        if self.WLdatum != 1:
            self.ax2.invert_yaxis()
            
    def update_precip_scale(self): #===========================================
        
        if self.meteoOn == False:
            return
        
        RAINscale = self.RAINscale
        
        RAINmin = 0
        RAINmax = RAINmin + RAINscale * 6
        
        self.ax3.axis(ymin=RAINmin - (RAINscale*4), 
                      ymax=RAINmin - (RAINscale*4) + self.NZGrid*RAINscale)
        
        yticks_position = np.arange(0, RAINmax + RAINscale, RAINscale*2)
        self.ax3.set_yticks(yticks_position)
        self.ax3.invert_yaxis()
        
        #---- Update position of missing markers ----
        
        if self.NMissPtot:
            y = np.ones(self.NMissPtot) * -5 * RAINscale / 20.
            self.PTOTmiss_dots.set_ydata(y)
            
    def set_gridLines(self): #=================================================
        
        # 0 -> None, 1 -> "-" 2 -> ":"
        
        if self.gridLines == 0:

            self.ax1.tick_params(gridOn=False)

        elif self.gridLines == 1:

            self.ax1.tick_params(gridOn=True)
            self.ax1.grid(axis='both', color=[0.35, 0.35, 0.35], linestyle='-',
                          linewidth=0.5)
                      
        else:

            self.ax1.tick_params(gridOn=True)
            self.ax1.grid(axis='both', color=[0.35, 0.35, 0.35], linestyle=':',
                          linewidth=0.5, dashes=[0.5, 5])
        
    def make_xticks_info(self): #==============================================
        
        #--------------------------------------- horizontal text alignment ----
        
        # The strategy here is to:
        # 1. render some random text ; 
        # 2. get the height of its bounding box ; 
        # 3. get the horizontal translation of the top-right corner after a
        #    rotation of the bbox of 45 degrees ;
        # 4. sclale the length calculated in step 3 to the height to width
        #    ratio of the axe ;
        # 5. convert the lenght calculated in axes coord. to the data coord.
        #    system ;
        # 6. remove the random text from the figure.
        
        #---- random text bbox height ----
        
        txt = self.ax1.text(0.5, 0.5, 'some_dummy_text', fontsize=10, 
                            ha='right', va='top', transform=self.ax1.transAxes)
        
        renderer = self.canvas.get_renderer()
        bbox = txt.get_window_extent(renderer)
        bbox = bbox.transformed(self.ax1.transAxes.inverted())
        
        #---- horiz. trans. of bbox top-right corner ----
        
        dx = bbox.height * np.sin(np.radians(45))
        
        #---- scale to axe dimension ----
                
        bbox = self.ax1.get_window_extent(renderer)
        bbox = bbox.transformed(self.dpi_scale_trans.inverted())
        
        sdx = dx * bbox.height / bbox.width
        sdx *= (self.TIMEmax - self.TIMEmin + 1)
        
        txt.remove()
        
        #---- transform to data coord ----
                
        n = self.date_labels_display_pattern
        month_names = LabelDatabase(self.language).month_names
       
        # xticks_labels_offset = 0.012 * (self.TIMEmax - self.TIMEmin + 1)
        xticks_labels_offset = sdx
        
        xticks_labels = []
        xticks_position = [self.TIMEmin]
        xticks_labels_position = []
        
        if self.datemode == 'month':
            
            i = 0
            while xticks_position[i] < self.TIMEmax:
                
                year = xldate_as_tuple(xticks_position[i], 0)[0]
                month = xldate_as_tuple(xticks_position[i], 0)[1]
                
                month_range = monthrange(year, month)[1]    
                
                xticks_position.append(xticks_position[i] + month_range)
                     
                if i % n == 0:         
    
                    xticks_labels_position.append(xticks_position[i] +
                                                  0.5 * month_range +
                                                  xticks_labels_offset)
                    
                    xticks_labels.append("%s '%s" % (month_names[month - 1], 
                                                     str(year)[-2:]))
                                                     
                i += 1
                
        elif self.datemode == 'year':
            
            i = 0
            year = xldate_as_tuple(xticks_position[i], 0)[0]
            while xticks_position[i] < self.TIMEmax:
                
                xticks_position.append(
                                     xldate_from_date_tuple((year+1, 1, 1), 0))
                year_range = xticks_position[i+1] - xticks_position[i]
                
                if i % n == 0:         
    
                    xticks_labels_position.append(xticks_position[i] +
                                                  0.5 * year_range +
                                                  xticks_labels_offset)
                    
                    xticks_labels.append("%d" % year)
                
                year += 1
                i += 1
                
                
        return xticks_position, xticks_labels_position, xticks_labels


#==============================================================================             
class WaterlvlData():
#==============================================================================

    def __init__(self):
        
        self.time = []
        self.lvl = []
        self.name_well = []
        self.well_info = [] # html table to display in the UI
                
        self.WLmes = []
        self.TIMEmes = []
        
        self.LAT = []
        self.LON = []
        self.ALT = []
        
        self.wlvlFilename = []
        self.soilFilename = []
        
    def load(self, fname):
        
        self.wlvlFilename = fname
        
        fileName, fileExtension = path.splitext(fname)
        
        self.soilFilename = fileName + '.sol'
        
        #---- Open First Sheet ----
        
        book = open_workbook(fname, on_demand=True)
        sheet = book.sheet_by_index(0)
        
        #---- Search for First Line With Data ----
        
        self.time = sheet.col_values(0, start_rowx=0, end_rowx=None)
        self.time = np.array(self.time)
       
        row = 0
        hit = False
        while hit == False:
            
            if self.time[row] == 'Date':
                hit = True
            else: 
                row += 1
            
            if row >= len(self.time):
                print('WARNING: Waterlvl data file is not formatted correctly')
                book.release_resources()
                return False
                
        start_rowx = row + 1
           
        #---- Load Data ----
        
        try:

            self.time = self.time[start_rowx:]
            self.time = np.array(self.time).astype(float)        
        
            header = sheet.col_values(1, start_rowx=0, end_rowx=5)
            self.name_well = header[0]
            self.LAT = header[1]
            self.LON = header[2]
            self.ALT = header[3]
            
            self.lvl = sheet.col_values(1, start_rowx=start_rowx, end_rowx=None)
            self.lvl = np.array(self.lvl).astype(float)
            
        except:

            print('WARNING: Waterlvl data file is not formatted correctly')
            book.release_resources()
            return False
        
        book.release_resources()
        
        print('Loading waterlvl time-series for well %s' % self.name_well)

        #------------------------------------------------------- WELL INFO ----
        
        FIELDS = ['Well Name', 'Latitude', 'Longitude', 'Altitude',
                  'Municipality']
                  
        well_info = '''
                    <table border="0" cellpadding="2" cellspacing="0" 
                    align="left">
                    '''
        
        for i in range(len(FIELDS)):
            
             try:                 
                 VAL = '%0.2f' % float(header[i])
             except:
                 VAL = header[i]
                 
             well_info += '''
                          <tr>
                            <td width=10></td>
                            <td align="left">%s</td>
                            <td align="left" width=20>:</td>
                            <td align="left">%s</td>
                          </tr>
                          ''' % (FIELDS[i], VAL)
        well_info += '</table>'
        
        self.well_info = well_info
        
        return True
        
        
    def load_waterlvl_measures(self, fname, name_well):
        
        print('Loading waterlvl manual measures for well %s' % name_well)
        
        WLmes = []
        TIMEmes = []
            
        if path.exists(fname):
            
            #---- Import Data ----
            
            reader = open_workbook(fname)
            
            NAME = reader.sheet_by_index(0).col_values(0, start_rowx=1,
                                                       end_rowx=None)
                                                                   
            TIME = reader.sheet_by_index(0).col_values(1, start_rowx=1,
                                                       end_rowx=None)
            
            OBS = reader.sheet_by_index(0).col_values(2, start_rowx=1,
                                                      end_rowx=None)
            #---- Convert to Numpy ----
                                                      
            NAME = np.array(NAME).astype('str')
            TIME = np.array(TIME).astype('float')
            OBS = np.array(OBS).astype('float')
                       
            if len(NAME) > 1:
                rowx = np.where(NAME == name_well)[0]
            
                if len(rowx) > 0:
                    WLmes = OBS[rowx]
                    TIMEmes = TIME[rowx]
            
        self.TIMEmes = TIMEmes
        self.WLmes = WLmes
                
        return TIMEmes, WLmes
        
#===============================================================================      
def load_weather_log(fname, varname, bintime, binvalue):
#===============================================================================

    print('Resampling missing data markers')
    
    bwidth = bintime[1] - bintime[0]
    
    #---- Load Data ----
    
    with open(fname, 'r') as f:
        reader = csv.reader(f, delimiter='\t')
        reader = list(reader)[36:]
    
    variable = np.zeros(len(reader)).astype('str') 
    time = np.zeros(len(reader))
    for i in range(len(reader)):
        variable[i] = reader[i][0]
        year = int(float(reader[i][1]))
        month = int(float(reader[i][2]))
        day = int(float(reader[i][3]))
        time[i] = xldate_from_date_tuple((year, month, day), 0)
    
    time = time[np.where(variable == varname)[0]]
    
    #---- Resample for Bins ----
    
    # Each missing value is assigned to a bin. At the end, if a bin has
    # received multiple hit, only one is kept by calling np.unique.
    
    time2 = np.array([])
    missing_value = np.array([])
    
    for t in time:
        if t >= bintime[0] and t <= bintime[-1]+bwidth:
            
            search = np.abs(bintime - t)
            hit = np.where(search == min(search))[0]

            time2 = np.append(time2, bintime[hit])
            missing_value = np.append(missing_value, binvalue[hit])
    
    time2, indices = np.unique(time2, return_index=True)
    missing_value = missing_value[indices]
    
    return time2, missing_value
    
#==============================================================================   
def filt_data(time, waterlvl, period):
    """
    period is in days
    """
#==============================================================================
    
    #------------- RESAMPLING 6H BASIS AND NAN ESTIMATION BY INTERPOLATION ----
    
    time6h_0 = np.floor(time[0]) + 1/24
    time6h_end = np.floor(time[-1]) + 1/24
    
    time6h = np.arange(time6h_0, time6h_end + 6/24., 6/24.)     

    # Remove times with nan values    
    index_nonan = np.where(~np.isnan(waterlvl))[0]
    
    # Resample data and interpolate missing values
    waterlvl = np.interp(time6h, time[index_nonan], waterlvl[index_nonan])
    
    #----------------------------------------------------------- FILT DATA ----
#    cuttoff_freq = 1. / period
#    samp_rate = 1. / (time[1] - time[0])
#    Wn = cuttoff_freq / (samp_rate / 2)
#    N = 3
#    
#    (b, a) = signal.butter(N, Wn, btype='low')
#    wlfilt = signal.lfilter(b, a, waterlvl)
    
    win = 4 * period
    
    wlfilt = np.zeros(len(waterlvl) - win)
    tfilt = time6h[win/2:-win/2]
    
    # Centered Moving Average Window        
    for i in range(len(wlfilt)):
        wlfilt[i] = np.mean(waterlvl[i:i+win+1])
    
    return tfilt, wlfilt

#==============================================================================
def LatLong2Dist(LAT1, LON1, LAT2, LON2):
    """
    Computes the horizontal distance in km between 2 points from geographic 
    coordinates given in decimal degrees.
 
    ---- INPUT ----
    
    LAT1 = latitute coordinate of first point
    LON1 = longitude coordinate of first point
    LAT2 = latitude coordinate of second point
    LON2 = longitude coordinate of second point
    
    ---- OUTPUT ----
    
    DIST = horizontal distance between the two points in km

    ---- SOURCE ----
    
    www.stackoverflow.com/questions/19412462 (last accessed on 17/01/2014)
    """
#============================================================================== 
  
    R = 6373.0 # R = Earth radius in km

    # Convert decimal degrees to radians.
    LAT1 = radians(LAT1)
    LON1 = radians(LON1)
    LAT2 = radians(LAT2)
    LON2 = radians(LON2)
    
    # Compute the horizontal distance between the two points in km.
    dLON = LON2 - LON1
    dLAT = LAT2 - LAT1
    a = (sin(dLAT/2))**2 + cos(LAT1) * cos(LAT2) * (sin(dLON/2))**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))    
    
    DIST = R * c 
    
    return DIST
    
if __name__ == '__main__':
    
    import sys
    from meteo import MeteoObj
    
    from imageviewer2 import ImageViewer
    

    app = QtGui.QApplication(sys.argv)
    
    fmeteo = 'Files4testing/AUTEUIL_2000-2013.out'
    fwaterlvl = 'Files4testing/PO16A.xls'
    
    import os
#    import datetime
    import time
    
    #---- load data ----
    
    t = os.path.getmtime(fmeteo)
    t = time.gmtime(t)
    
    waterLvlObj = WaterlvlData()
    waterLvlObj.load(fwaterlvl)
    
    fname = 'Files4testing/waterlvl_manual_measurements.xls'
    waterLvlObj.load_waterlvl_measures(fname, 'PO16A')
    
    meteoObj = MeteoObj()
    meteoObj.load_and_format(fmeteo)
    
    #---- set up hydrograph ----
    
    hydrograph = Hydrograph()
    
    hydrograph.WLdatum = 0 # 0 -> mbgs ; 1 -> masl
    hydrograph.gridLines = 2
    
    hydrograph.title_state = 0 # 1 -> title ; 0 -> no title
    hydrograph.title_text = "Title of the Graph"
    hydrograph.meteoOn = True # 0 -> no meteo ; 1 -> meteo
    
    hydrograph.set_waterLvlObj(waterLvlObj)
    hydrograph.best_fit_waterlvl()
    hydrograph.best_fit_time(waterLvlObj.time)
    hydrograph.finfo = 'Files4testing/AUTEUIL_2000-2013.log'
    
    hydrograph.generate_hydrograph(meteoObj) 
    hydrograph.savefig('../Projects/Project4Testing/hydrograph.pdf')
    
    #---- show figure on-screen ----
    
#    canvas = FigureCanvasQTAgg(hydrograph)
    
    imgview = ImageViewer()
    imgview.load_image(hydrograph)
    imgview.show()
    
#    canvas = FigureCanvasQTAgg(hydrograph2display.fig)
#    canvas.show()
#    canvas.setFixedSize(canvas.size())
#    
#    qr = canvas.frameGeometry()
#    cp = QtGui.QDesktopWidget().availableGeometry().center()
#    qr.moveCenter(cp)
#    canvas.move(qr.topLeft())
    
    sys.exit(app.exec_())
    