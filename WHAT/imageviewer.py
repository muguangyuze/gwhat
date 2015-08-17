# -*- coding: utf-8 -*-
"""
Copyright 2015 Jean-Sebastien Gosselin

email: jnsebgosselin@gmail.com

This file is part of WHAT (Well Hydrograph Analysis Toolbox). This code was
forked from a code provided in the example classes of the Qt Tookit by
Trolltech AS. Original license is provided below. I removed from the original
code most of the UI elements, added a zooming capability with the mouse wheel, 
and I added the capability to display matplotlib figures.

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

------------------------------------------------------------------------------

Copyright (C) 2005-2005 Trolltech AS. All rights reserved.

This file is part of the example classes of the Qt Toolkit.
This file may be used under the terms of the GNU General Public
License version 2.0 as published by the Free Software Foundation
and appearing in the file LICENSE.GPL included in the packaging of
this file.  Please review the following information to ensure GNU
General Public Licensing requirements will be met:
http://www.trolltech.com/products/qt/opensource.html

If you are unsure which license is appropriate for your use, please
review the following information:
http://www.trolltech.com/products/qt/licensing.html or contact the
sales department at sales@trolltech.com.

This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
"""

#---- THIRD PARTY IMPORTS ----

from PySide import QtGui, QtCore

import matplotlib
matplotlib.use('Qt4Agg')
matplotlib.rcParams['backend.qt4']='PySide'
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg
import matplotlib.pyplot as plt

#=============================================================================
class ImageViewer(QtGui.QWidget):
    """
    This is a PySide widget class to display a bitmap image in a QScrollArea 
    with zooming and panning capability with CTRL + Mouse_wheel and 
    Left-click event.
    """
#=============================================================================

    def __init__(self, parent=None): #========================================
        super(ImageViewer, self).__init__(parent)
        
        self.scaleFactor = 0
        self.scaleStep = 1.2
        self.pan = False
        
        #---- image container Set Up ----
        
        self.imageLabel = QtGui.QLabel()
        self.imageLabel.setBackgroundRole(QtGui.QPalette.Base)
        self.imageLabel.setSizePolicy(QtGui.QSizePolicy.Ignored,
                                      QtGui.QSizePolicy.Ignored)
        self.imageLabel.setScaledContents(True)
        self.imageLabel.installEventFilter(self)
        
        self.imageLabel.setFrameStyle(QtGui.QFrame.Panel | QtGui.QFrame.Raised)
        self.imageLabel.setLineWidth(2)
        self.imageLabel.setMidLineWidth(1)        
        
        #---- Scroll Area Set Up ----
        
        self.scrollArea = QtGui.QScrollArea(self)
        self.scrollArea.setWidget(self.imageLabel)
        self.scrollArea.setAlignment(QtCore.Qt.AlignCenter)
                
        #---- Grid Set Up ----
                
        grid = QtGui.QGridLayout()
               
        grid.addWidget(self.scrollArea, 0, 0)
                
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0) # (Left,Top, Right, Bottom)
        
        self.setLayout(grid)
        self.setWindowTitle("Image Viewer")
              
        #---- Create Initial Image with Matplotlib ----
        
        # http://stackoverflow.com/questions/17676373/
        # python-matplotlib-pyqt-copy-image-to-clipboard
        
        # http://stackoverflow.com/questions/21939658/
        # matplotlib-render-into-buffer-access-pixel-data
        
        figure = plt.figure()
        figure.patch.set_facecolor('white')

        figure_canvas = FigureCanvasQTAgg(figure)
        figure_canvas.draw()
                
        size = figure_canvas.size()
        width, height = size.width(), size.height()
        
        imgbuffer = figure_canvas.buffer_rgba()
        image = QtGui.QImage(imgbuffer, width, height,
                             QtGui.QImage.Format_ARGB32)
                             
        # Reference for the RGB to BGR swap:
        # http://sourceforge.net/p/matplotlib/mailman/message/5194542/
          
        image = QtGui.QImage.rgbSwapped(image)
        
        self.load_image(image, 0)
    
    def load_image(self, image, scaleFactor=0): #=============================
        
        self.scaleFactor = scaleFactor
                
        self.imageLabel.setPixmap(QtGui.QPixmap.fromImage(image))
        self.imageLabel.adjustSize()
        
        size = self.imageLabel.size()
        self.width = size.width()
        self.height = size.height()
        
        self.scaleImage()
        
    def refresh_image(self, image):
        
        self.imageLabel.setPixmap(QtGui.QPixmap.fromImage(image))
        
    def eventFilter(self, widget, event):
        
        # http://stackoverflow.com/questions/17525608/
        # event-filter-cannot-intercept-wheel-event-from-qscrollarea
        
        # http://stackoverflow.com/questions/20420072/
        # pyside-keypressevent-catching-enter-or-return
        
        # http://stackoverflow.com/questions/19113532/
        # qgraphicsview-zooming-in-and-out-under-mouse-position
        # -using-mouse-wheel

        #----------------------------------------------------------- ZOOM ----
        
        if event.type() == QtCore.QEvent.Type.Wheel:
                               
            # http://stackoverflow.com/questions/8772595/
            # how-to-check-if-a-key-modifier-is-pressed-shift-ctrl-alt
            
            modifiers = QtGui.QApplication.keyboardModifiers()
                      
            if modifiers == QtCore.Qt.ControlModifier:                
                if event.delta() > 0:
                    self.zoomIn()
                else:
                    self.zoomOut()
                return True
            else:
                return False
        
        #------------------------------------------------------------ PAN ----
        
        #---- Set ClosedHandCursor ----
        
        elif event.type() == QtCore.QEvent.Type.MouseButtonPress:
                  
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                
                QtGui.QApplication.setOverrideCursor(
                                                    QtCore.Qt.ClosedHandCursor)
                self.pan = True
                self.xclick = event.globalX()
                self.yclick = event.globalY()
        
        #---- Reset Cursor ----

        elif event.type() == QtCore.QEvent.Type.MouseButtonRelease:
            
            QtGui.QApplication.restoreOverrideCursor()
            self.pan = False
        
        #---- Move  ScrollBar----
        
        elif event.type() == QtCore.QEvent.Type.MouseMove:
            
            if self.pan == True:
                
                dx = self.xclick - event.globalX()
                self.xclick = event.globalX()
                
                dy = self.yclick - event.globalY()
                self.yclick = event.globalY()
                
                scrollBarH = self.scrollArea.horizontalScrollBar()
                scrollBarH.setValue(scrollBarH.value() + dx)
    
                scrollBarV = self.scrollArea.verticalScrollBar()
                scrollBarV.setValue(scrollBarV.value() + dy)

        return QtGui.QWidget.eventFilter(self, widget, event)

    def zoomIn(self):
        if self.scaleFactor < 5:
            self.scaleFactor += 1
            self.scaleImage()
            self.adjust_scrollbar(self.scaleStep)

    def zoomOut(self):
        if self.scaleFactor > -3:
            self.scaleFactor -= 1
            self.scaleImage()
            self.adjust_scrollbar(1/self.scaleStep)
                
    def scaleImage(self):
        
        new_width = int(self.width * self.scaleStep ** self.scaleFactor)
        new_height = int(self.height * self.scaleStep ** self.scaleFactor)
                
        self.imageLabel.resize(new_width, new_height)
        
#        pixmap = QtGui.QPixmap.fromImage(self.origImage)
#        transform = QtGui.QTransform().scale(self.scaleStep ** self.scaleFactor, 
#                                             self.scaleStep ** self.scaleFactor)
#        pixmap = pixmap.transformed(transform, QtCore.Qt.SmoothTransformation)
#        
#        self.imageLabel.setPixmap(pixmap)

    def adjust_scrollbar(self, factor):
        
        #---- Adjust HScrollBar ----
        
        scrollBar = self.scrollArea.horizontalScrollBar()
        scrollBar.setValue(int(factor * scrollBar.value()
                                + ((factor - 1) * scrollBar.pageStep()/2)))
                                
        #---- Adjust VScrollBar ----
                                
        scrollBar = self.scrollArea.verticalScrollBar()                        
        scrollBar.setValue(int(factor * scrollBar.value()
                                + ((factor - 1) * scrollBar.pageStep()/2)))
                                
#    def normalSize(self):
#        self.imageLabel.adjustSize()
#        self.scaleFactor = 1.0
#
#    def fitToWindow(self):
#        fitToWindow = self.fitToWindowAct.isChecked()
#        self.scrollArea.setWidgetResizable(fitToWindow)
#        if not fitToWindow:
#            self.normalSize()
#
#        self.updateActions()
                                
if __name__ == '__main__':

    import sys

    app = QtGui.QApplication(sys.argv)
    imageViewer = ImageViewer()
    imageViewer.show()
    
    figure = plt.figure()
    figure.set_size_inches(11, 8.5)
    figure.patch.set_facecolor('white')
    plt.plot([1, 2, 3, 4], [1, 2, 3, 4], '-b')

    figure_canvas = FigureCanvasQTAgg(figure)
    figure_canvas.draw()
            
    size = figure_canvas.size()
    width, height = size.width(), size.height()
    
    imgbuffer = figure_canvas.buffer_rgba()
    image = QtGui.QImage(imgbuffer, width, height,
                         QtGui.QImage.Format_ARGB32)
                         
    # Reference for the RGB to BGR swap:
    # http://sourceforge.net/p/matplotlib/mailman/message/5194542/
      
    image = QtGui.QImage.rgbSwapped(image)    
    imageViewer.load_image(image, 0)
    
    
    sys.exit(app.exec_())
