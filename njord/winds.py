import os.path
from datetime import datetime as dtm
import ftplib

import scipy
import numpy as np
import pylab as pl
from scipy.stats import nanmean
from scipy.io import netcdf_file

import base
import gmtgrid
try:
    import bln
    HAS_BLN= True
except:
    HAS_BLN= False
    
class Seawinds(base.Grid):
    """Read jpl Seawinds fields"""
    def __init__(self, **kwargs):
        """Initialize the class with stuff from base.Grid"""
	super(Seawinds, self).__init__(**kwargs)
	
    def setup_grid(self):
	"""Setup lat-lon matrices for Seawinds"""
        if not os.path.isfile(self.gridfile):
            self.retrive_file(self.dataurl, self.gridfile)
        try:
            n = netcdf_file(self.gridfile, 'r')
        except:
            print 'Error opening the gridfile %s' % self.gridfile
            raise
        self.lat = n.variables['lat'][:]
        self.gmt = gmtgrid.Shift(n.variables['lon'][:].copy())
        self.lon = self.gmt.lonvec 
        self.llon,self.llat = np.meshgrid(self.lon,self.lat)

    def load(self, fld="nwnd", **kwargs):
	"""Load field for a given julian date. Returns u,v, or nwnd(windnorm)"""
        self._timeparams(**kwargs)
        filename = os.path.join(self.datadir,
                            "uv%04i%02i%02i.nc" % (self.yr, self.mn, self.dy))
        if not os.path.isfile(filename):
            self.download(filename)
        try:
            nc = netcdf_file(filename)
        except:
            os.remove(filename)
            self.download(filename)
            try:
                nc = netcdf_file(filename)
            except:
                filename = filename.rstrip(".nc") + "rt.nc"
                if not os.path.isfile(filename):
                    self.download(filename)
                try:
                    nc = netcdf_file(filename)
                except TypeError:
                    os.remove(filename)
                    self.download(filename)
                    nc = netcdf_file(filename)
                    
        u = nc.variables['u'][:].copy()
        v = nc.variables['v'][:].copy()
        u[u<-999] = np.nan
        v[v<-999] = np.nan
        if (fld=="u") | (fld=="uvel"):
            self.uvel = self.gmt.field(np.squeeze(u))
        elif (fld=="v") | (fld=="vvel"):
            self.vvel = self.gmt.field(np.squeeze(v))
        else:
            self.nwnd = self.gmt.field(np.squeeze(np.sqrt(u**2 + v**2)))

    def download(self, filename):
        try:
            self.retrive_file(self.dataurl, filename)
        except ftplib.error_perm:
            return False


class CCMP(base.Grid):
    """Read jpl CCMP fields
    http://podaac.jpl.nasa.gov/dataset/CCMP_MEASURES_ATLAS_L4_OW_L3_0_WIND_VECTORS_FLK
     ftp://podaac-ftp.jpl.nasa.gov/allData/ccmp/

    """
    def __init__(self, **kwargs):
        """Initialize the class with stuff from base.Grid"""
	super(CCMP, self).__init__(**kwargs)
	
    def setup_grid(self):
	"""Setup lat-lon matrices for CCMP"""
	try:
	    gc = netcdf_file(self.gridfile, 'r')
        except:
            print 'Error opening the gridfile %s' % datadir + filename
            raise
        self.lat = gc.variables['lat'][:]
	self.gmt = gmtgrid.Shift(gc.variables['lon'][:].copy())
        self.lon = self.gmt.lonvec 
        self.llon,self.llat = np.meshgrid(self.lon,self.lat)

    def load(self, fld="nwnd", **kwargs):
	"""Load field for a given julian date. Returns u,v, or nwnd(windnorm)"""
        self._timeparams(**kwargs)
	filename = os.path.join(self.datadir,
				"analysis_%04i%02i%02i_v11l30flk.nc" %
                                  	(self.yr,self.mn,self.dy))
        if os.path.isfile(filename):
            nc = netcdf_file(filename)
        else:
            raise IOError, 'Error opening the windfile %s' % filename
	uH = nc.variables['uwnd']
	vH = nc.variables['vwnd']
	uvel = self.gmt.field(uH.data.copy()) * uH.scale_factor
	vvel = self.gmt.field(vH.data.copy()) * vH.scale_factor
	
	uvel[uvel<(uH.missing_value * uH.scale_factor)] = np.nan
	vvel[vvel<(vH.missing_value * vH.scale_factor)] = np.nan
	if (fld=="u") | (fld=="uvel"):
	    self.uvel = gmtgrid.convert(np.squeeze(u), self.gr)
	elif (fld=="v") | (fld=="vvel"):
	    self.vvel = gmtgrid.convert(np.squeeze(v), self.gr)
	else:
   	    self.nwnd = gmtgrid.convert(np.squeeze(np.sqrt(u**2 + v**2)),self.gr)




class ncep:

    def __init__(self,datadir = "/projData/ncep/"):
        filename = "vwnd.sig995.2008.nc"        
        try:
            n = pycdf.CDF(datadir + filename)
        except:
            print 'Error opening the gridfile %s' % datadir + filename
            raise
        self.lat = n.var('lat')[:]
        self.lon,self.gr = gmtgrid.config(n.var('lon')[:],0)
        self.llon,self.llat = np.meshgrid(self.lon,self.lat)
        self.datadir = datadir

    def load(self,jd):
        yr = pl.num2date(jd).year
        yd = int((jd - pl.date2num(dtm(yr,1,1))) * 4)
        ufile = "uwnd.sig995.%04i.nc" % yr
        vfile = "vwnd.sig995.%04i.nc" % yr
        try:
            un = pycdf.CDF(self.datadir + ufile)
        except:
            print 'Error opening the windfile %s' % datadir + ufile
            raise
        try:
            vn = pycdf.CDF(self.datadir + vfile)
        except:
            print 'Error opening the windfile %s' % datadir + vfile
            raise    
        u = un.var('uwnd')[yd,:,:] * 0.01 + 225.45
        v = vn.var('vwnd')[yd,:,:] * 0.01 + 225.45
        nwnd = gmtgrid.convert(np.sqrt(u**2 + v**2),self.gr)
        nwnd[nwnd>200]=np.nan
        return nwnd

class Quikscat(base.Grid):
    
    def __init__(self, **kwargs):
        if not HAS_BLN:
            raise ImportError, "The bln module is missing."
        super(Quikscat, self).__init__(**kwargs)

    def setup_grid(self):
        self.lat,self.lon = bln.grid()
        self.llon,self.llat = np.meshgrid(self.lon,self.lat)
        
        
    def load(self,**kwargs):
        self._timeparams(**kwargs)
        u,v = bln.readuv_day(self.jd)
        nwnd =np.sqrt(u**2 + v**2)
        #nwnd[nwnd>200]=np.nan
        return nwnd[...,self.j1:self.j2, self.i1:self.i2]

class CORE2:

    def __init__(self,datadir = "/projData/CORE2/"):
        self.jdbase = pl.date2num(dtm(1948,1,1))+15
        self.datadir = datadir
        filename = "u_10.2005.05APR2010.nc"
        try:
            n = netcdf_file(datadir + filename)
        except:
            print 'Error opening the gridfile %s' % datadir + filename
            raise
        self.lat = n.variables['LAT'][:]
        self.gmt = gmtgrid.Shift(n.variables['LON'][:].copy())
        self.lon = self.gmt.lonvec 
        self.llon,self.llat = np.meshgrid(self.lon,self.lat)
        n.close()
	
    def load(self,jd1,jd2=None):
        yr = pl.num2date(jd1).year
        mn = pl.num2date(jd1).month
        dy = pl.num2date(jd1).day
        filesuff = ".%04i.05APR2010.nc" %(yr)
        try:
            nu = netcdf_file(self.datadir + "u_10" + filesuff)
            nv = netcdf_file(self.datadir + "v_10" + filesuff)
        except:
            print 'Error opening the windfile %s%s' % (self.datadir,filesuff)
            raise
        jdvec = nu.variables['TIME'][:] + self.jdbase
        t1 = int(np.nonzero(jdvec>jd1)[0].min())
        if not jd2:
            jd2 = jd1+1
            t2 = t1+4
        elif jd2<jdvec.max():
            t2 = int(t1+4*(jd2-jd1))
        else:
            jd11 = jd1
            jd22 = jdvec.max() -1
            while np.floor(jd2)>=np.ceil(jd22):
                print jd22-jd11,jd2-jd11,jd11,jd22
                wnd1 = self.load(jd11,jd22)
                jd11 = jd22 + 1
                jd22 += 365

            return
        djd = np.ceil(jd2 - jd1)
        wndjd = np.zeros( ( (djd,) + self.llon.shape) ) 
        self.uwnd = self.gmt.field(nu.variables['U_10_MOD'][t1:t2,...].copy())
        self.vwnd = self.gmt.field(nv.variables['V_10_MOD'][t1:t2,...].copy())
        nwnd = np.sqrt(self.uwnd**2 + self.vwnd**2)
        for t in np.arange(0,djd*4,4):
            wndjd[t/4,...] = np.mean(nwnd[t:t+4,...],axis=0)
        nu.close()
        nv.close()
        self.nwnd = np.squeeze(wndjd)
