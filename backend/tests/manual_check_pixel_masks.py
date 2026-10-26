"""Online scientific regression: run explicitly against Earth Engine."""
import ee
from services.gee_service import gee_service
assert gee_service.initialize()
g=ee.Geometry.Rectangle([78.455515,17.404373,78.492937,17.439588])
full=ee.Image.constant([1000,1500,2000,4000]).rename(['B2','B3','B4','B8'])
# Complete coverage of a small non-grid-aligned AOI must not lose edge pixels.
r=gee_service.compare_composites({'type':'rectangle','coordinates':[[78.455515,17.404373],[78.492937,17.439588]]},full,full)
assert r['commonCoveragePercent']==100,r
assert abs(r['ndviChange'])<1e-9,r
# Missing RGB pixels must also be excluded from comparison, despite valid NDVI bands.
half=ee.Image.pixelLonLat().select('longitude').lt(78.474226)
partial=full.addBands(full.select('B2').updateMask(half),overwrite=True)
r=gee_service.compare_composites({'type':'rectangle','coordinates':[[78.455515,17.404373],[78.492937,17.439588]]},full,partial)
assert 45<r['commonCoveragePercent']<55,r
assert abs(r['ndviChange'])<1e-9,r
print('PASS: full coverage 100%; RGB/NDVI intersection half coverage',r['commonCoveragePercent'],'%; identical-data change zero.')
