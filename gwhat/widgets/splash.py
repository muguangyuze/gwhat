# -*- coding: utf-8 -*-
"""
Copyright 2014-2017 Jean-Sebastien Gosselin
email: jean-sebastien.gosselin@ete.inrs.ca

This file is part of GWHAT (GroundWater Hydrograph Analysis Toolbox).

GWHAT is free software: you can redistribute it and/or modify
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

# ---- Third parties imports

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QSplashScreen

# ---- Local imports

SPLASH_IMG = 'ressources/splash.png'


class SplashScrn(QSplashScreen):
    def __init__(self):
        super(SplashScrn, self).__init__(QPixmap(SPLASH_IMG),
                                         Qt.WindowStaysOnTopHint)
        self.show()

    def showMessage(self, msg):
        """Override Qt method."""
        super(SplashScrn, self).showMessage(
                msg, Qt.AlignBottom | Qt.AlignCenter)
