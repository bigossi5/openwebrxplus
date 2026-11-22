from unittest import TestCase
from owrx import geo


class GeoTest(TestCase):
    def testHaversineWarsawBerlin(self):
        d = geo.haversineKm(52.2297, 21.0122, 52.52, 13.405)
        self.assertAlmostEqual(d, 517, delta=5)

    def testHaversineZero(self):
        self.assertAlmostEqual(geo.haversineKm(10, 20, 10, 20), 0.0)

    def testBearingCardinal(self):
        self.assertAlmostEqual(geo.bearingDeg(0, 0, 1, 0), 0.0, places=3)
        self.assertAlmostEqual(geo.bearingDeg(0, 0, 0, 1), 90.0, places=3)
        self.assertAlmostEqual(geo.bearingDeg(0, 0, -1, 0), 180.0, places=3)
        self.assertAlmostEqual(geo.bearingDeg(0, 0, 0, -1), 270.0, places=3)

    def testDestinationRoundTrip(self):
        lat, lon = geo.destinationPoint(52.0, 21.0, 75.0, 120.0)
        self.assertAlmostEqual(geo.haversineKm(52.0, 21.0, lat, lon), 120.0, places=3)
        self.assertAlmostEqual(geo.bearingDeg(52.0, 21.0, lat, lon), 75.0, delta=0.5)

    def testDestinationNorthOneDegree(self):
        lat, lon = geo.destinationPoint(0, 10, 0, 111.195)
        self.assertAlmostEqual(lat, 1.0, places=2)
        self.assertAlmostEqual(lon, 10.0, places=3)

    def testDestinationLongitudeWraps(self):
        lat, lon = geo.destinationPoint(0, 179.5, 90, 111.195)
        self.assertAlmostEqual(lon, -179.5, places=2)
