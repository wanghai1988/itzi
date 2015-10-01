# coding=utf8
"""
Copyright (C) 2015  Laurent Courty

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
"""
from __future__ import division
from grass.gunittest.case import TestCase
from grass.gunittest.main import test

import grass.script as grass
import grass.temporal as tgis
from grass.pygrass import raster
from grass.pygrass.gis.region import Region
from grass.pygrass.messages import Messenger
import numpy as np
from gis import Igis

class TestIgis(TestCase):

    @classmethod
    def setUpClass(cls):
        """create test data"""
        # instantiate the class to be tested
        cls.gis = Igis()

    @classmethod
    def tearDownClass(cls):
        pass

    def test_init(self):
        """Test if the initialization is done properly
        """
        pass

    def test_unit_convert(self):
        self.assertEqual(self.gis.to_s("minutes", 2), 120)
        self.assertEqual(self.gis.to_s("hours", 1.5), 5400)
        self.assertEqual(self.gis.to_s("days", 2), 172800)

        self.assertEqual(self.gis.from_s("minutes", 300), 5)
        self.assertEqual(self.gis.from_s("hours", 9000), 2.5)
        self.assertEqual(self.gis.from_s("days", 129600), 1.5)

if __name__ == '__main__':
    test()