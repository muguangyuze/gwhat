# -*- coding: utf-8 -*-
"""
Copyright 2014 Jean-Sebastien Gosselin

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
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
       
#----- STANDARD LIBRARY IMPORTS -----
       
import csv
from calendar import monthrange

#----- THIRD PARTY IMPORTS -----

import matplotlib.pyplot as plt
import numpy as np
from xlrd.xldate import xldate_from_date_tuple
from xlrd import xldate_as_tuple

class LabelDataBase():  
    
    
    def __init__(self, language):
        
        self.ANPRECIP = 'Annual Total Precipitation (mm)'
        self.ANTEMP = u'Average Annual Air Temperature (°C)'
        
        self.month_names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                            "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        
        if language == 'French':
            'Option not available at the moment'
            
#===============================================================================        
class MeteoObj():
#===============================================================================    

    def __init__(self):
        
        self.TIME = []  # Time in numeric format (days)
        self.TMAX = []  # Daily maximum temperature (deg C)
        self.TAVG = []  # Daily mean temperature (deg C)
        self.PTOT = []  # Daily total precipitation (mm)
        self.RAIN = []  # Daily total liquid precipitation (mm)
        
        self.YEAR = []
        self.MONTH = []
        
        self.TIMEwk = []
        self.TMAXwk = []
        self.PTOTwk = []
        self.RAINwk = []
        
        self.info = []
        self.station_name = []
        self.LAT = []
        self.LON = []
        
    def load(self, fname):
        
        reader = open(fname, 'rb')
        reader = csv.reader(reader, delimiter='\t')
        reader = list(reader)
        
        self.station_name = reader[0][1]
        self.LAT = reader[2][1]
        self.LON = reader[3][1]
        
        DATA = np.array(reader[11:]).astype('float')
        
    #---------------------------------------------------------- REMOVE NAN -----
        
        # Remove nan rows at the beginning of the record if any
        for i in range(len(DATA[:, 0])):
            if np.all(np.isnan(DATA[i, 3:])):
                DATA = np.delete(DATA, i, axis=0)
            else:
                break
            
         # Remove nan rows at the end of the record if any
        for i in range(len(DATA[:, 0])):
            if np.all(np.isnan(DATA[-i, 3:])):
                DATA = np.delete(DATA, -i, axis=0)
            else:
                break   
            
    #----------------------------------------------- CHECK TIME CONTINUITY -----
        
        #Check if data are continuous over time.
        time_start = xldate_from_date_tuple((DATA[0, 0].astype('int'),
                                             DATA[0, 1].astype('int'),
                                             DATA[0, 2].astype('int')), 0)

        time_end = xldate_from_date_tuple((DATA[-1, 0].astype('int'),
                                           DATA[-1, 1].astype('int'),
                                           DATA[-1, 2].astype('int')), 0)
        
        # Check if the data series is continuous over time and 
        # correct it if not
        if time_end - time_start + 1 != len(DATA[:,0]):
            print reader[0][1], ' is not continuous, correcting...'
            DATA = make_timeserie_continuous(DATA)        
        
        #Generate a 1D array with date in numeric format
        TIME = np.arange(time_start, time_end + 1)
        
    #-------------------------------------------------- REASSIGN VARIABLES -----
                                            
        TMAX = DATA[:, 3]
        TAVG = DATA[:, 5]
        PTOT = DATA[:, 6]        

    #-------------------------------------------------------- ESTIMATE NAN -----

        PTOT[np.isnan(PTOT)] = 0
        
        nonanindx = np.where(~np.isnan(TMAX))[0]
        if len(nonanindx) < len(TMAX):
            TMAX = np.interp(TIME, TIME[nonanindx], TMAX[nonanindx])
    
    #------------------------------------------------------- ESTIMATE RAIN -----
        
        RAIN = np.copy(PTOT)
        RAIN[np.where(TAVG < 0)[0]] = 0
        
    #---------------------------------------------------- UPDATE CLASS VAR -----
    
        self.TIME = TIME
        self.TMAX = TMAX
        self.TAVG = TAVG
        self.PTOT = PTOT
        self.RAIN = RAIN
        
        self.YEAR = DATA[:, 0].astype(int)
        self.MONTH = DATA[:, 1].astype(int)
                
    #------------------------------------------ DAILY TO WEEKLY CONVERSION -----        
              
        Nbr_week = np.floor(len(TIME) / 7.)
        TIMEwk = TIME[0] + np.arange(7/2. - 1, 7 * Nbr_week - 7/2., 7)
        
        TMAXwk = np.zeros(Nbr_week)
        PTOTwk = np.zeros(Nbr_week)
        RAINwk = np.zeros(Nbr_week)
        for i in range(7):   
            TMAXwk = TMAXwk + TMAX[i:7*Nbr_week + i:7] / 7.
            PTOTwk = PTOTwk + PTOT[i:7*Nbr_week + i:7]
            RAINwk = RAINwk + RAIN[i:7*Nbr_week + i:7]
    
    #---------------------------------------------------- UPDATE CLASS VAR -----

        self.TIMEwk = TIMEwk
        self.TMAXwk = TMAXwk
        self.PTOTwk = PTOTwk
        self.RAINwk = RAINwk
        
    #-------------------------------------------------------- STATION INFO -----        
        
        FIELDS = ['Station', 'Province', 'Latitude', 'Longitude', 
                  'Altitude']
                  
        info = '''<table border="0" cellpadding="2" cellspacing="0" 
                   align="left">'''
        for i in range(len(FIELDS)):
            
            try:                 
                VAL = '%0.2f' % float(reader[i][1])
            except:
                VAL = reader[i][1]
                 
            info += '''<tr>
                         <td width=10></td>
                         <td align="left">%s</td>
                         <td align="left" width=20>:</td>
                         <td align="left">%s</td>
                       </tr>''' % (FIELDS[i], VAL)
        info += '</table>'
        
        self.info = info
        

#===============================================================================
def make_timeserie_continuous(DATA):
#
# This function is called when a time serie of a daily meteorological record
# is found to be discontinuous over time.
#
# <make_timeserie_continuous> will scan the entire time serie and will insert
# a row with nan values whenever there is a gap in the data and will return
# the continuous data set.
#
# DATA = [YEAR, MONTH, DAY, VAR1, VAR2 ... VARn]
#
#        2D matrix containing the dates and the corresponding daily 
#        meteorological data of a given weather station arranged in 
#        chronological order. 
#
#===============================================================================    
    
    nVAR = len(DATA[0,:]) - 3 # nVAR = number of meteorological variables
    nan2insert = np.zeros(nVAR) * np.nan    
    
    i = 0
    date1 = xldate_from_date_tuple((DATA[i, 0].astype('int'),
                                    DATA[i, 1].astype('int'),
                                    DATA[i, 2].astype('int')), 0)
    
                                   
    while i < len(DATA[:, 0]) - 1:
        
        date2 = xldate_from_date_tuple((DATA[i+1, 0].astype('int'),
                                        DATA[i+1, 1].astype('int'),
                                        DATA[i+1, 2].astype('int')), 0)
        
        # If dates 1 and 2 are not consecutive, add a nan row to DATA
        # after date 1.                                
        if date2 - date1 > 1:            
            date2insert = np.array(xldate_as_tuple(date1 + 1, 0))[:3]
            row2insert = np.append(date2insert, nan2insert)          
            DATA = np.insert(DATA, i + 1, row2insert, 0)
        
        date1 += 1            
        i += 1

    return DATA
    
            
#===============================================================================
def plot_monthly_normals(fig, TNORM, PNORM, RNORM, TSTD):
# Plot monthly normals
#===============================================================================
    
    SNORM = PNORM - RNORM
    
    fig.clf()
    
    label_font_size = 14
    labelDB = LabelDataBase('English')
    
    month_names = labelDB.month_names
     
    fig.patch.set_facecolor('white')
    
    fheight = fig.get_figheight()
    fwidth = fig.get_figwidth()
    
    left_margin  = 1
    right_margin = 1
    bottom_margin = 0.5
    top_margin = 0.25
    
    x0 = left_margin / fwidth
    y0 = bottom_margin / fheight
    w0 = 1 - (left_margin + right_margin) / fwidth
    h0 = 1 - (bottom_margin + top_margin) / fheight
   
    #---------------------------------------------------------AXES CREATION-----

    ax0  = fig.add_axes([x0, y0, w0, h0])
    ax0.patch.set_visible(False)
    ax1 = fig.add_axes(ax0.get_position(), frameon=False, zorder=1)
    ax1.patch.set_visible(False)
    
    #------------------------------------------------------XTICKS FORMATING----- 
    
    Xmin0 = 0
    Xmax0 = 12.001
    
    ax0.xaxis.set_ticks_position('bottom')
    ax0.tick_params(axis='x',direction='out', gridOn=False)
    ax0.xaxis.set_ticklabels([])
    ax0.set_xticks(np.arange(Xmin0, Xmax0))
    
    ax0.set_xticks(np.arange(Xmin0+0.5, Xmax0+0.49, 1), minor=True)
    ax0.tick_params(axis='x', which='minor', direction='out', gridOn=False,
                    length=0,)
    ax0.xaxis.set_ticklabels(month_names, minor=True)
    
    ax1.tick_params(axis='x', which='both', bottom='off', top='off',
                    labelbottom='off')
    
    #--------------------------------------------------- DEFINE AXIS RANGE -----
    
    if np.sum(PNORM) < 500:
        Yscale0 = 10 # Precipitation (mm)
    else:
        Yscale0 = 20
        
    Yscale1 = 5 # Temperature (deg C)
    
    SCA0 = np.arange(0, 10000, Yscale0)
    SCA1 = np.arange(-100, 100, Yscale1)
    
    #----- Precipitation -----
    
    indx = np.where(SCA0 > np.max(PNORM))[0][0]   
    Ymax0 = SCA0[indx+1]
    
    indx = np.where(SCA0 <= np.min(SNORM))[0][-1]
    Ymin0 = SCA0[indx]
    
    NZGrid0 = (Ymax0 - Ymin0) / Yscale0
    
    #----- Temperature -----
    
    indx = np.where(SCA1 > np.max(TNORM+TSTD))[0][0] 
    Ymax1 = SCA1[indx]
    
    indx = np.where(SCA1 < np.min(TNORM-TSTD))[0][-1] 
    Ymin1 = SCA1[indx]
    
    NZGrid1 = (Ymax1 - Ymin1) / Yscale1
    
    #----- Uniformization Of The Grids -----
    
    if NZGrid0 > NZGrid1:    
        Ymin1 = Ymax1 - NZGrid0 * Yscale1
    elif NZGrid0 < NZGrid1:
        Ymax0 = Ymin0 + NZGrid1 * Yscale0
    elif NZGrid0 == NZGrid1:
        pass
    
    #----- Adjust Space For Text -----
    
    reqheight = 0.12
    Ymax0 += (Ymax0 - Ymin0) * reqheight 
    Ymax1 += (Ymax1 - Ymin1) * reqheight
    
#    height4text = (Ymax1 - np.max(TNORM+TSTD)) / (Ymax1 - Ymin1)
        
#    Ymax0 += (Ymax0 - Ymin0) * (reqheight - height4text) 
#    Ymax1 += (Ymax1 - Ymin1) * (reqheight - height4text) 
    
#    Ymax0 += (Ymax0 - Ymin0) * (reqheight - height4text) 
#    Ymax1 += (Ymax1 - Ymin1) * (reqheight - height4text)
    
    #------------------------------------------------------YTICKS FORMATING-----
    
    #----- Precip (host) -----
    
    ax0.yaxis.set_ticks_position('left')
    yticks0_position = np.arange(Ymin0, Ymax0 - (Ymax0 - Ymin0) * 0.1,
                                 Yscale0)
    ax0.set_yticks(yticks0_position)
    ax0.tick_params(axis='y', direction='out', labelcolor='blue', gridOn=True)
    
    #----- Air Temp -----
    
    yticks1_position = np.arange(Ymin1, Ymax1 - (Ymax1 - Ymin1) * 0.1 ,
                                 Yscale1)    
    ax1.yaxis.set_ticks_position('right')
    ax1.set_yticks(yticks1_position)
    ax1.tick_params(axis='y', direction='out', labelcolor='red', gridOn=True)
    
    #------------------------------------------------------ SET AXIS RANGE ----- 

    ax0.axis([Xmin0, Xmax0, Ymin0, Ymax0])
    ax1.axis([Xmin0, Xmax0, Ymin1, Ymax1])
    
    #----------------------------------------------------------------LABELS-----
    
    ax0.set_ylabel('Monthly Total Precipication (mm)', fontsize=label_font_size,
                   verticalalignment='bottom', color='blue')
    ax0.yaxis.set_label_coords(-0.09, 0.5)
    
    ax1.set_ylabel(u'Monthly Mean Air Temperature (°C)', color='red',
                   fontsize=label_font_size, verticalalignment='bottom',
                   rotation=270)
    ax1.yaxis.set_label_coords(1.09, 0.5)

#---------------------------------------------------------------- PLOTTING -----
    
    SNOWcolor = [0.85, 0.85, 0.85]
    RAINcolor = [0, 0, 1]
    
    TNORM = np.hstack((TNORM[-1], TNORM, TNORM[0]))
    TSTD = np.hstack((TSTD[-1], TSTD, TSTD[0]))    
            
    XPOS = np.arange(0.5, 12.5, 1)
    
    ax0.bar(XPOS, PNORM, align='center', width=0.5, color=RAINcolor,
            edgecolor='k', linewidth=0.5)            
    ax0.bar(XPOS, SNORM, align='center', width=0.5, color=SNOWcolor,
            edgecolor='k', linewidth=0.5)    

    XPOS = np.arange(-0.5, Xmax0+0.5) 
    h1_ax1, = ax1.plot(XPOS, TNORM, color='red', clip_on=True, zorder=100,
                       marker='o', linestyle='--')
                         
    ax1.errorbar(XPOS, TNORM, yerr=TSTD, color='red', fmt='o', ecolor='black',
                 capthick=1.2, elinewidth=1.2, clip_on=True, zorder=100)
                 
    ax1.text(0.01, 0.95, 
             u'Mean Annual Air Temperature = %0.1f °C' % np.mean(TNORM[1:-1]),
             fontsize=12, verticalalignment='bottom', transform=ax1.transAxes)
    ax1.text(0.01, 0.9,
             u'Mean Annual Precipitation = %0.1f mm' % np.sum(PNORM),
             fontsize=12, verticalalignment='bottom', transform=ax1.transAxes)
             
#------------------------------------------------------------------ LEGEND -----        

    rec1 = plt.Rectangle((0, 0), 1, 1, fc=SNOWcolor)
    rec2 = plt.Rectangle((0, 0), 1, 1, fc=RAINcolor)
   
    labels = ['Air Temperature', 'Snow', 'Rain']
    
    ax1.legend([h1_ax1, rec1, rec2], labels, loc=1,
               numpoints=1, fontsize=10)
    
#===============================================================================    
def calculate_normals(fmeteo):
#===============================================================================
    
    METEO = MeteoObj()
    METEO.load(fmeteo)
    
    YEAR = METEO.YEAR
    MONTH = METEO.MONTH
    TAVG = METEO.TAVG
    PTOT = METEO.PTOT
    RAIN = METEO.RAIN
    
#---------------------------------------------------------- MONTHLY VALUES -----
    
    nYEAR = YEAR[-1] - YEAR[0] + 1
   
    TMONTH = np.zeros((nYEAR, 12))
    PMONTH = np.zeros((nYEAR, 12))
    RMONTH = np.zeros((nYEAR, 12))
    for j in range(nYEAR):
        for i in range(12):
            
            indx = np.where((YEAR == j+YEAR[0]) & (MONTH == i+1))[0]
            Nday = monthrange(j+YEAR[0], i+1)[1] 
            
            if len(indx) < Nday:
                print 'Month', i+1, 'of year', j+YEAR[0], 'is imcomplete'
                TMONTH[j, i] = np.nan
                PMONTH[j, i] = np.nan
                RMONTH[j, i] = np.nan
            else:
                TMONTH[j, i] = np.mean(TAVG[indx])
                PMONTH[j, i] = np.sum(PTOT[indx])
                RMONTH[j, i] = np.sum(RAIN[indx])

#--------------------------------------------------------- MONTHLY NORMALS -----
    
    TNORM = np.zeros(12)
    PNORM = np.zeros(12)
    RNORM = np.zeros(12)
    TSTD = np.zeros(12)
    for i in range(12):
        indx = np.where(~np.isnan(TMONTH[:, i]))[0]
        
        if len(indx) > 0:
            TNORM[i] = np.mean(TMONTH[indx, i])
            PNORM[i] = np.mean(PMONTH[indx, i])
            RNORM[i] = np.mean(RMONTH[indx, i])            
            TSTD[i] = (np.mean((TMONTH[indx, i] - TNORM[i])**2))**0.5            
        else:
            
            print 'WARNING, some months are empty because of lack of data'
            
            TNORM[i] = np.nan
            PNORM[i] = np.nan
            RNORM[i] = np.nan
            TSTD[i] = np.nan
    
    return TNORM, PNORM, RNORM, TSTD

if __name__ == '__main__':
    
    global label_font_size
    label_font_size = 14
    
    global labelDB
    labelDB = LabelDataBase('English')
                
    plt.close("all")
    
    fmeteo = 'Files4testing/AUTEUIL_2000-2013.out'
    TNORM, PNORM, RNORM, TSTD = calculate_normals(fmeteo)
    
    fig = plt.figure(figsize=(8.5, 5))        
#    fig.set_size_inches(8.5, 5)
    plot_monthly_normals(fig, TNORM, PNORM, RNORM, TSTD)
    
    fmeteo = 'Files4testing/Daily - SASKATOON DIEFENBAKER & RCS_1980-2014.out'
    TNORM, PNORM, RNORM, TSTD = calculate_normals(fmeteo)
    
    fig = plt.figure(figsize=(8.5, 5))        
    plot_monthly_normals(fig, TNORM, PNORM, RNORM, TSTD)