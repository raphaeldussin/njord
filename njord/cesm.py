import os
import glob 

import numpy as np
import pylab as pl
from scipy.io import netcdf_file
import random
from matplotlib.mlab import griddata
import matplotlib.cm as cm

import grid
import bln
from pysea import sw, wind2pv
from reuerflux import pv2fl, pv2wpv
import gmtgrid

import base

def nodimb(a,b): return (a-b) / b

c2o2 =170./117

class Base(base.Grid):

    def __init__(self, **kwargs):
        super(Base, self).__init__(**kwargs)
        self.add_mp()
        
    def setup_grid(self):
        """Setup necessary variables for grid """
        g = netcdf_file(self.gridfile, 'r')
        self.llat = g.variables['TLAT'][:]
        self.gmt  = gmtgrid.Shift(g.variables['TLONG'][0,:].copy())
        self.lon  = self.gmt.lonvec
        self.llon = g.variables['TLONG'][:].copy()
        self.llon[self.llon>180] = self.llon[self.llon>180]-360
        self.llon = self.gmt.field(self.llon)       
        #self.zlev = g.variables['z_t'][:]
        #self.zlev = g.variables['HT'][:]
            
    def add_landmask(self):
        """ Generate a landmask for t-positions"""
        self.landmask = np.isnan(self.llat)

        
class csm:
    def __init__(self, fname='BEC.gx3.22.pi.cv2.Ar.daily.2004-02.nc',
                 datadir='/projData/CSMBGC/Ar_daily/',
                 t1=None, t2=None, k1=None, k2=None,
                 i1=None, i2=None, j1=None, j2=None,
                 ln='', dt=''):
        """Init the class and setup the grid. Paths are defined here."""  
        n = pycdf.CDF(datadir + os.path.split(fname)[1])
        g = pycdf.CDF(datadir + 'grid_cell_xy.nc')
        self.datadir = datadir
        self.t1 = t1; self.t2 = t2
        self.i1 = i1; self.i2 = i2
        self.j1 = j1; self.j2 = j2
        self.k1 = k1; self.k2 = k2
        if t1>60:
            self.tw = t1-60
        else:
            self.tw = t1

        self.fname = os.path.split(fname)[1]
        self.llat = self.readfield(n, 'TLAT')
        self.llon,self.gr  = gmtgrid.config(g.var('TLONG')[:],0)
        self.llat = self.llat[i1:i2,j1:j2]
        self.llon = self.llon[i1:i2,j1:j2]
        self.dz   = n.var('dz')[:] / 100 
        self.dzt  = self.dz.copy()
        self.dyu  = cnv(g.var('DYU')[:]/100,   self.gr)[i1:i2,j1:j2] 
        self.dxu  = cnv(g.var('DXU')[:]/100,   self.gr)[i1:i2,j1:j2] 
        self.area = cnv(n.var('TAREA')[:]/100/100, self.gr)[i1:i2,j1:j2]
        self.zlev = n.var('z_t')[:] /100
        self.create_tvec()

        def lim(val1,val2):
            if not val1: return val2
            return val1
            

        self.t1 = lim(t1,0); self.t2 = lim(t2,len(self.tvec))
        self.i1 = lim(i1,0); self.i2 = lim(i2,self.llat.shape[0])
        self.j1 = lim(j1,0); self.j2 = lim(j2,self.llat.shape[1])
        self.k1 = lim(k1,0); self.k2 = lim(k2,len(self.zlev))



        self.keypref = 'daily_'

        self.pa = {'tvec':('time',120),
                   'o2fl':('FG_O2',-864),
                   'nwndsqr':('U10_SQR', 0.0001),
                   'nwnd':('',1),
                   'arfl':('FG_Ar',  864),
                   'o2ss':('O2SAT',1),
                   'arss':('ArSAT',1),
                   'o2pv':('PV_O2',864),
                   'arpv':('PV_Ar',864),
                   'ncpo':('NCP_O2',24*3600),
                   'o2ct':('O2',1),
                   'arct':('Ar',1),
                   'mldp':('HMXL',1.0e-2),
                   'uvel':('UVEL',864),
                   'vvel':('VVEL',864),
                   'salt':('SALT',1000),
                   'temp':('TEMP',1),
                   'atpr':('ATM_PRESS_USED',1),
                   'taux':('TAUX',1),
                   'tauy':('TAUY',1),
                   'poco':('',1),
                   'spC':('spC',1),
                   'diatC':('diatC',1),
                   'diazC':('diazC',1),
                   'chlo':    ('',1),
                   'spChl':   ('spChl',1),
                   'diatChl': ('diatChl',1),
                   'diazChl': ('diazChl',1),
                   'o2st':('',1),
                   'arst':('',1),
                   'o2ar':('',1),
                   'dens':('',1),
                   'mldk':('',1),
                   'nn10':('',1),
                   'nrm10':('',1),
                   'wpv':('',1),
                   'ssht':('',1),
                   'icef':('IFRAC',1),
                   'wwfl':('',1),
                   'crwwfl':('',1)
                   }

        self.km = self.dzt.shape[0];  self.kr = np.arange(self.km)
        self.im = self.area.shape[0]; self.ir = range(self.im)
        self.jm = self.area.shape[1]; self.jr = range(self.jm)        
        self.vol = np.zeros([self.km, self.im, self.jm])
        for k in self.kr: 
            self.vol[k,:,:]=self.area[:,:] * self.dzt[k]
        self.create_pardict()
        self.tm = self.tvec.shape[0]; self.tr = np.arange(self.tm)

        self.params=[]
        self.gcm = 'csm'

    def readfield(self,nc, fieldName,slope=1):
        tmp = np.ma.masked_greater(nc.var(fieldName)[:],1e30)
        if tmp.ndim >1:
            fld = tmp.copy()
            fld[...,39:] = tmp[...,:61]
            fld[...,:39] = tmp[...,61:]
            del tmp
        else:
            fld = tmp
        return fld * slope * 1.0
    
    def load(self, par, surf=False,mldint=False,fullint=False,noneg=False):
        self.params.append(par)
        key = self.pa[par][0]
        self.par=par; vd=self.vd;
        t1 = self.t1; t2 = self.t2
        i1 = self.i1; i2 = self.i2
        j1 = self.j1; j2 = self.j2
        k1 = self.k1; k2 = self.k2

        pref = self.datadir + "BEC.gx3.22.pi.cv2.Ar.daily."
        def readfield(par):
            for y in [2003,2004,2005,2006]:
                for m in np.arange(1,13):
                    n = pycdf.CDF(pref + "%04i-%02i.nc" % (y,m) )
                    tmpfld = cnv(n.var(self.pa[par][0])[:],
                                 self.gr)[...,i1:i2,j1:j2]
                    try:
                        fld = np.concatenate((fld,tmpfld),axis=0)
                    except UnboundLocalError:
                        fld = tmpfld
            return fld * self.pa[par][1]

        def condload(parlist):
            for par in (parlist):
                if not hasattr(self,par): 
                    self.load(par)        
        if  mldint:
            na = np.newaxis
            exists = False
            if hasattr(self,par): exists = True
            condload( ('mldk',par) )
            if self.mldk.ndim == 1:
                self.mldk = self.mldk[:,na,na]
                self.__dict__[par] =  self.__dict__[par][:,:,na,na]
            elif self.mldk.ndim == 2:
                self.mldk = self.mldk[:,na]
                self.__dict__[par] =  self.__dict__[par][:,:,na]
            fld = self.mldk * 0
            for m in np.unique(self.mldk):
                t,i,j = np.nonzero(self.mldk == m)
                fld[t,i,j] = np.sum(self.__dict__[par][t,:m,i,j] *
                                       self.dzt[:m], axis=1)
            self.__dict__[par[:-1] + 'm'] = fld
            if not exists: del self.__dict__[par]
            return
        if par == 'o2ar':
            condload( ('o2ct','o2st','arst','arct') )
            self.o2ar = ( (self.o2ct/self.o2st)/
                          (self.arct/self.arst) ) * 100 - 100
            return
        elif par == 'o2st':
            condload( ('temp','salt','o2ss') )
            self.o2st = sw.satO2(self.salt,self.temp)
            self.o2st[:,0] = self.o2ss[:]
            return
        elif par == 'arst':
            condload( ('temp','salt','arss') )
            self.arst = sw.satAr(self.salt,self.temp)
            self.arst[:,0] = self.arss[:]
            return
        elif par == 'ssht':
            self.__dict__['ssht'] = self.dxu * 0
            return
        elif par == 'icef':
            pref = (self.datadir +
                    "/BEC.gx3.22.pi.cv2.Ar.daily.IFRAC.1999-2006.nc")
            n = pycdf.CDF(pref)
            self.icef = cnv(n.var('IFRAC')[t1:t2,...], self.gr)[:,i1:,j1:j2]
            self.icef[self.icef>1] = np.nan
            return
        
        elif par == 'dens':
            condload( ('temp','salt') )
            self.dens = sw.dens0(self.salt,self.temp)
            return
        elif par == 'nwnd':
            self.load('nwndsqr')
            self.nwnd = np.sqrt(self.nwndsqr)
            del self.nwndsqr
            return
        elif par == 'mldk':
            condload( ('mldp',) )
            self.mldk = np.ceil(np.interp(self.mldp, 
                                          self.zlev, np.arange(25)) )
            return
        elif par == 'nn10':
            if not hasattr(self,'ncpm'):
                self.load('ncpo',mldint=True)
            self.nn10 =self.ncpm.copy() * np.nan
            for t in np.arange(10,self.nn10.shape[0]):
                self.nn10[t,...]=np.mean(self.ncpm[t-10:t,...],axis=0)
            return                  
        elif par == 'wwfl':
            condload( ('o2ar','dens','mldp','nwnd','icef') )
            self.wwfl = pv2fl(self.o2ar,
                              self.temp,
                              self.mldp,
                              self.nwnd,
                              wtlen=60,
                              o2st=self.o2st,
                              dens=self.dens)
            ii2= min(i2,26)
            if i1<26:
                self.wwfl[:,i1:ii2,:] = ( (1- self.icef[:,i1:ii2,:]) *
                                          self.wwfl[:,i1:ii2,:] )
            """
            nulmat = np.zeros( (self.t1-self.tw,self.k2-self.k1,
                                self.i2-self.i1,self.j2-self.j1) )
            self.t1 = self.tw
            self.load('nwnd')

            #self.wwfl = self.o2ar.copy()*0
            self.wwfl = pv2fl(np.concatenate((nulmat,self.o2ar),axis=0), 
                              np.concatenate((nulmat,self.temp),axis=0),
                              np.concatenate((nulmat[:,0,:,:],
                                              self.mldp),axis=0),
                              self.nwnd,
                              wtlen=60,
                              o2st=np.concatenate((nulmat,
                                                   self.o2st),axis=0), 
                              dens=np.concatenate((nulmat,
                                                   self.dens),axis=0))
            #self.wwfl=self.wwfl[t1:t2,...]
            self.t1 = t1
            """
            return
        elif par == 'crwwfl':
            condload( ('wwfl',) )
            return
        elif par == 'nrm10':
            condload( ('wwfl','nn10') )
            self.nrm10 = nodimb(self.wwfl,self.nn10)
            return
        elif par == 'wpv':
            condload( ('wwfl',) )
            self.wpv = pv2wpv(self.temp,self.mldp,self.nwnd,dens=self.dens)
            return
        elif par == 'chlo':
            condload( ('spChl','diatChl','diazChl') )
            self.chlo = self.spChl + self.diatChl + self.diazChl
            del self.spChl, self.diatChl, self.diazChl
            return
        elif par == 'poco':
            condload( ('spC','diatC','diazC') )
            self.poco = self.spC + self.diatC + self.diazC
            del self.spC, self.diatC, self.diazC
            return
        elif 'z_t' in self.vd[key][1]:
            fld = readfield(par)[t1:t2,k1:k2,...]
        else:
            fld = readfield(par)[t1:t2,...]

        if 'z_t' in vd[key][1] and surf:
            exists = False
            if hasattr(self,par): exists = True
            condload( ('mldk',par) )
            self.__dict__[par[:-1] + 'm'] = self.__dict__[par][:,0,...]
            if not exists: del self.__dict__[par] 
            return
        elif  'z_t' in vd[key][1] and fullint:
            """ Integrate over each column """
            na = np.newaxis
            exists = False
            if not hasattr(self,par): exists = True
            condload( (par,'mldp','ssht') )
            fld = self.__dict__[par] * self.dz[na,:,na,na]
            if noneg: fld[fld<0] = 0
            fld[:,0,:,:] = fld[:,0,:,:] * (self.ssht+self.dz[0]) / self.dz[0]
            fld = np.nansum(fld,axis=1)
            if exists: del self.__dict__[par]
            par = par[:-1] + 'f'
        
        print par + ": ",fld.shape
        fld[fld <-1e9] = np.nan
        fld[fld > 1e9] = np.nan
        self.__dict__[par] = fld


    def create_pardict(self,lnmsk='',dtmsk=''):
        vardict = {}
        for f in glob.glob(self.datadir + "BEC*.nc")[:1]:
            n = pycdf.CDF(f)
            for k in n.variables().keys():
                vardict[k] = ( (k,) + n.variables()[k]
                               + (f,) )
        self.vd = vardict

    def create_tvec(self,lnmsk='',dtmsk=''):
        self.tvec = np.arange(pl.datestr2num('2003-01-01'),
                              pl.datestr2num('2006-12-31'))
        self.tvec = self.tvec[self.t1:self.t2]

    def create_months(self):
        self.create_tvec()
        self.months = np.array([ dt.month for dt in pl.num2date(self.tvec)])

    def add_seaslen(self,dfn='ncpm'):
        if dfn == 'o2ar':
            self.condload( ('o2ar',) )
            if self.o2ar.ndim == 3:
                msk = self.o2ar[:,:,:].copy()
            else:
                msk = self.o2ar[:,0,:,:].copy()
            msk[msk>0] = 1
            msk[msk<0] = 0
            msk[np.isnan(msk)] = 0
            seaslen = np.sum(msk,axis=0) * 365 / len(self.tvec)
            self.seaslen = msk
            self.seaslen[:] = seaslen
        else:
            if not hasattr(self,'ncpm'):
                self.load('ncpo',mldint=True)
            msk = self.ncpm[:,:,:].copy()
            msk[msk>0] = 1
            msk[msk<0] = 0
            msk[np.isnan(msk)] = 0
            seaslen = np.sum(msk,axis=0) * 365 / len(self.tvec)
            self.seaslen = msk
            self.seaslen[:] = seaslen

    def add_year(self):
        pass

    def __call__(self):
        for v in self.params:
            print v

            






    #Massbalances
    
    def volflux (self, cncfld):
        # === Create u and v fluxes over the cell bundaries ===
        cnc = self.__dict__[cncfld]
        uflx = cnc[:]*0; vflx = cnc.copy()*0  
        uflx[...,1:,:] = (self.uvel[...,1:,:] + self.uvel[...,:-1,:])/2
        vflx[...,:,1:] = (self.vvel[...,:,1:] + self.vvel[...,:,:-1])/2
        for t in self.tr:
            for k in self.kr:
                fp =  np.maximum(uflx[t,k,:,:-1],uflx[t,k,:,:-1]*0)*cnc[t,k,:,1:]
                fn =  np.minimum(uflx[t,k,:,:-1],uflx[t,k,:,:-1]*0)*cnc[t,k,:,:-1]
                uflx[t,k,:,1:] = (fn+fp) * self.dzt[k]*self.dyu[:,1:]
                fp =  np.maximum(vflx[t,k,:-1,:],vflx[t,k,:-1,:]*0)*cnc[t,k,1:,:]
                fn =  np.minimum(vflx[t,k,:-1,:],vflx[t,k,:-1,:]*0)*cnc[t,k,:-1,:]
                vflx[t,k,1:,:] = (fn+fp) * self.dzt[k]*self.dxu[1:,:]
                del fp,fn
        self.__dict__[cncfld + 'uflux'] = uflx
        self.__dict__[cncfld + 'vflux'] = vflx
 
    def fluxbalance(self):
        self.load()
        self.volflux('o2ct')
        ut = self.o2ctuflux 
        vt = self.o2ctvflux 
        ubal = ut.copy()
        vbal = ut.copy()

        ubal[...,1:,:] = ut[...,:-1,:] - ut[...,1:,:]
        vbal[...,:,1:] = vt[...,:,:-1] - vt[...,:,1:]

        bal = ubal + vbal
        for t in self.tr: 
            bal[t,...]=bal[t,...] / self.area
        self.o2ad = bal
        self.ubal = ubal
        self.vbal = vbal

    def set_region(self,area):
        self.projarea=area
    def get_region(self,area):
        if hasattr(self,'projarea'):
            return self.projarea
        else:
            raise('Region not set')

    def add_ij(self):
        self.jmat,self.imat = np.meshgrid(np.arange(self.j2-self.j1),
                                          np.arange(self.i2-self.i1))
        self.ijvec = np.vstack((np.ravel(self.imat),np.ravel(self.jmat))).T
    def add_kd(self,mask=None):
        from scipy.spatial import KDTree, cKDTree

        latvec = np.ravel(self.llat)
        lonvec = np.ravel(self.llon)
        if not mask is None: 
            latvec = latvec[~np.isnan(np.ravel(mask))]
            lonvec = lonvec[~np.isnan(np.ravel(mask))]
            self.add_ij()
            self.ijvec = self.ijvec[~np.isnan(np.ravel(mask))]
        self.kd = cKDTree(list(np.vstack((lonvec,latvec)).T))
    def ll2ij(self,lon,lat,nei=1):
        if not hasattr(self,'imat'):
            self.add_kd()
            self.add_ij()
        dist,ij = self.kd.query(list(np.vstack((lon,lat)).T),nei)
        return self.ijvec[ij-1][:,0],self.ijvec[ij-1][:,1]
