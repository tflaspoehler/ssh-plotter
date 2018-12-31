from Tkinter import *
import ttk
from PIL import Image, ImageTk, ImageDraw
import paramiko
import threading
import os
import tkFont
from math import *
import time
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap, LogNorm, ListedColormap, Normalize
from matplotlib.ticker import MaxNLocator, LogLocator
from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib.collections import LineCollection
from functools import partial

import xlwt
from xlrd import open_workbook
from xlutils.copy import copy
import clipboard, io

from basics import *
from color import *

def interval(planes, point):
    for i in range(1, len(planes)):
        if planes[i] > point:
            return i-1
    return 0
## ====================================
## Initialize tkinter 
## ====================================
global fig, ax
root = Tk()
fig = plt.figure(figsize=(800/72, 800/72))
fig.patch.set_facecolor('white')
font = {'fontname':'Times New Roman',
        'family' : 'normal',
        'weight' : 'bold',
        'size'   : 9}
plt.rc('font', family='serif')
plt.xlabel('theta (radians)')
plt.ylabel('r (cm)')
ax = fig.add_subplot(111)

## ====================================
## Threaded Classes for network jabber
## ====================================
## ------------------------------------
# -- Directory Parsing Thread
# -- send and recv ls data @ remote host
class search_thread_class(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global directory_info_lock
        directory_info_main = False
        while 1:
            global directory_info
            if directory_info.connect:
                if directory_info_lock.acquire():
                    self.connect()
                    directory_info.connect = False
                    directory_info_lock.release()
            if directory_info.read:
                if directory_info_lock.acquire():
                    self.ls()
                    directory_info.read = False
                    directory_info_lock.release()
            if directory_info_lock.locked() and not directory_info_main:
                directory_info_main = True
            elif not directory_info_lock.locked() and directory_info_main:
                directory_info_main = False
            time.sleep(0.1)

    def connect(self):
        global directory_info
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print directory_info.login+" is connecting to "+directory_info.host
        try:
            self.ssh.connect(directory_info.host,username=directory_info.login,password=directory_info.passwd)
        except Exception, e:
            print "FAILED",e
            return e
        ##stdin, stdout, stderr = self.ssh.exec_command("pwd")
        ##directory_info.pwd = trimBreak(stdout.readlines())[0]
        self.ls()

    def ls(self):
        global directory_info
        directory_info.path = filter(None, directory_info.pwd.split("/"))
        stdin, stdout, stderr = self.ssh.exec_command("cd "+directory_info.pwd+";ls -d */")
        directory_info.d = trimBreak(stdout.readlines())
        stdin, stdout, stderr = self.ssh.exec_command("cd "+directory_info.pwd+";ls -p | grep -v '/'")
        directory_info.f = trimBreak(stdout.readlines())
## ------------------------------------
        
## ------------------------------------
# -- File Input/Output Thread
# -- read meshfiles from cluster
class fileIO_thread_class(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global directory_info_lock
        directory_info_main = False
        while 1:
            global directory_info
            if directory_info.connect:
                if directory_info_lock.acquire():
                    self.connect()
                    directory_info_lock.release()
            if directory_info.open:
                if directory_info_lock.acquire() and plane_data_lock.acquire():
                    global display_settings
                    display_settings.zoomed = False
                    display_settings.setAspect = True
                    if directory_info.file_type == 'varscl' or directory_info.file_type == 'msm' or  directory_info.file_type == 'dff':
                        self.open_varscl_file()
                        self.read_varscl_plane()
                    elif directory_info.file_type == 'aardvarc' or  directory_info.file_type == 'aard' or  directory_info.file_type == '3dmap' or  directory_info.file_type == 'amap' or  directory_info.file_type == 'tmap' or  directory_info.file_type == 'pmap' or  directory_info.file_type == 'mim':
                        self.open_aard_file()
                        self.read_aard_plane()
                    directory_info.open = False
                    directory_info_lock.release()
                    plane_data_lock.release()
            if directory_info.line:
                if directory_info_lock.acquire() and plane_data_lock.acquire():
                    if directory_info.file_type == 'varscl' or directory_info.file_type == 'msm' or  directory_info.file_type == 'dff':
                        self.read_varscl_plane()
                    elif directory_info.file_type == 'aardvarc' or  directory_info.file_type == 'aard' or  directory_info.file_type == '3dmap' or  directory_info.file_type == 'amap' or  directory_info.file_type == 'tmap' or  directory_info.file_type == 'pmap' or  directory_info.file_type == 'mim':
                        print "about to read plane"
                        self.read_aard_plane()
                    directory_info.line = False
                    directory_info_lock.release()
                    plane_data_lock.release()
            if directory_info.plot:
                if directory_info_lock.acquire() and plane_data_lock.acquire():
                    print "getting varscl plot"
                    self.read_varscl_plot()
                    directory_info.plot = False
                    display_settings.plot = False
                    directory_info_lock.release()
                    plane_data_lock.release()
                
            if directory_info_lock.locked() and not directory_info_main:
                directory_info_main = True
            elif not directory_info_lock.locked() and directory_info_main:
                directory_info_main = False
            time.sleep(0.1)

    def connect(self):
        global directory_info
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print directory_info.login+" is connecting to "+directory_info.host
        try:
            self.ssh.connect(directory_info.host,username=directory_info.login,password=directory_info.passwd)
        except Exception, e:
            print "FAILED",e
            return e

    def open_varscl_file(self):
        global directory_info, plane_data, display_settings
        filename = "/".join([directory_info.pwd,directory_info.file])
        script = "source .bash_profile;echo$$;varscl"
        if  directory_info.file_type == 'msm':
            script = "source .bash_profile;echo$$;msm"
        if  directory_info.file_type == 'dff':
            script = "source .bash_profile;echo$$;dff"
        print "opening file ", filename," with ",  script
        self.stdin, self.stdout, self.stderr = self.ssh.exec_command(script)
        #self.pid = self.stdout.readline()
        self.stdin.write(filename+"\n")
        if "adjoint" in filename:
            self.stdin.write("1\n")
        else:
            self.stdin.write("0\n")
        while 1:
            nextline = self.stdout.readline()
            print nextline
            if "msm" in filename:
                break
            try:
                int(nextline)
                break
            except:
                pass
        display_settings.ng = int(nextline)
        display_settings.nx = int(self.stdout.readline())
        display_settings.ny = int(self.stdout.readline())
        display_settings.nz = int(self.stdout.readline())
        display_settings.ox = display_settings.nx
        display_settings.oy = display_settings.ny
        display_settings.oz = display_settings.nz
        
        print "Mesh Size:",display_settings.nx,display_settings.ny,display_settings.nz,display_settings.ng
        display_settings.hasMaterial = int(self.stdout.readline())
        print "HAS MATERIAL", display_settings.hasMaterial
        display_settings.isCoupled, display_settings.bottom = tuple(int(i) for i in self.stdout.readline().split())
        if display_settings.isCoupled == 0:
            display_settings.ng = display_settings.bottom
        if display_settings.isCoupled == 1:
            display_settings.ng = display_settings.bottom
        ##if display_settings.isCoupled == 2:
        ##    display_settings.ng = display_settings.bottom
        display_settings.e = [float(i) for i in self.stdout.readline().split()]
        display_settings.ng = len(display_settings.e)-1
        display_settings.x = [float(i) for i in self.stdout.readline().split()]
        display_settings.y = [float(i) for i in self.stdout.readline().split()]
        display_settings.z = [float(i) for i in self.stdout.readline().split()]
        display_settings.oxp = display_settings.x
        display_settings.oyp = display_settings.y
        display_settings.ozp = display_settings.z
        
        display_settings.g = 1
        
        print display_settings.e
        print display_settings.x
        print display_settings.y
        print display_settings.z
        print display_settings.g

        ##display_settings.z = [display_settings.z[-1] - i + display_settings.z[0] for i in display_settings.z]
        display_settings.plane = 1 + (len(display_settings.z)-1) / 2
        plane_data.nsub = 0
        plane_data.sub = {}

    def read_varscl_plane(self):
        global directory_info, plane_data, display_settings
        #self.pid = self.stdout.readline()
        ## Begin Reading Plane / Don't Close File
        self.stdin.write("0\n")
        ## Send the View (0-xy, 1-xz, 2-yz)
        self.stdin.write(repr(display_settings.view)+"\n")
        ## Plane Number (z, y, x)
        self.stdin.write(repr(display_settings.plane)+"\n")
        ## Energy Group
        self.stdin.write(repr(display_settings.g)+"\n")
        readout = [float(i) for i in self.stdout.readline().split()]
        plane_data.min, plane_data.max = tuple(readout)
        print "writes",0, display_settings.view, display_settings.plane, display_settings.g

        if display_settings.view == 0:
            length = display_settings.ny
            plane_data.nx = display_settings.nx
            plane_data.ny = display_settings.ny
            plane_data.xp = display_settings.x
            plane_data.yp = display_settings.y          
        elif display_settings.view == 1:
            length = display_settings.nz
            plane_data.nx = display_settings.nx
            plane_data.ny = display_settings.nz
            plane_data.xp = display_settings.x
            plane_data.yp = display_settings.z        
        elif display_settings.view == 2:
            length = display_settings.nz
            plane_data.nx = display_settings.ny
            plane_data.ny = display_settings.nz
            plane_data.xp = display_settings.y
            plane_data.yp = display_settings.z
        plane_data.data = []
        for j in range(0, length):
            plane_data.data.append([abs(float(i)) for i in self.stdout.readline().split()])
        if (display_settings.hasMaterial):
            plane_data.geo = []
            for j in range(0, length):
                next_line = self.stdout.readline().split()
                ##print next_line
                ##print "PLANE", display_settings.plane
                try:
                    plane_data.geo.append([float(i) for i in next_line])
                except:
                    print "last line failed"
                    plane_data.geo.append([float(0) for i in next_line[-1]])
            ## for j in range(0, length):
            ##     for i in range(0, len(plane_data.geo[0])):
            ##         ##if plane_data.geo[j][i] != 23:
            ##         if plane_data.geo[j][i] == 1 or plane_data.geo[j][i] == 2 or plane_data.geo[j][i] == 3 or plane_data.geo[j][i] == 5:
            ##             plane_data.geo[j][i] = 0
        
        plane_data.dimensions = [plane_data.xp[0],
                                 plane_data.xp[-1],
                                 plane_data.yp[0],
                                 plane_data.yp[-1]]
        plane_data.aspect = abs(plane_data.yp[-1] - plane_data.yp[0]) / abs(plane_data.xp[-1] - plane_data.xp[0])


        plane_data.data = np.array(plane_data.data)
        try:
            plane_data.max = plane_data.data[plane_data.data>0].max()
            plane_data.min = plane_data.data[plane_data.data>0].min()
        except:
            plane_data.max = 1.
            plane_data.min = 0.1
        plane_data.xp = np.array(plane_data.xp)
        plane_data.yp = np.array(plane_data.yp)
        display_settings.xlim = [plane_data.xp[0], plane_data.xp[1]]
        display_settings.ylim = [plane_data.yp[0], plane_data.yp[1]]
        root.event_generate("<<redraw>>", when='tail')
        root.event_generate("<<newfile>>", when='tail')
        if display_settings.hasMaterial: ## or display_settings.drawMesh:
            plane_data.get_geo()

    def open_aard_file(self):
        global directory_info, plane_data, display_settings
        filename = "/".join([directory_info.pwd,directory_info.file])
        script = "source .bash_profile;echo$$;aard"
        if  directory_info.file_type == '3dmap':
            script = "source .bash_profile;echo$$;3dmap"
        if  directory_info.file_type == 'amap':
            script = "source .bash_profile;echo$$;amap"
        if  directory_info.file_type == 'tmap':
            script = "source .bash_profile;echo$$;tmap"
        if  directory_info.file_type == 'pmap':
            script = "source .bash_profile;echo$$;p_map"
        if  directory_info.file_type == 'mim':
            script = "source .bash_profile;echo$$;mim"
        print "opening file ", filename," with ",  script
        self.stdin, self.stdout, self.stderr = self.ssh.exec_command(script)
        #self.pid = self.stdout.readline()
        self.stdin.write(filename+"\n")
        while True:
            nl = self.stdout.readline()
            try:
                int( nl.split()[0] )
                break
            except:
                ## pass
                print "broke at ",nl
                print " splitted",nl.split()
        display_settings.sub_exists = int( nl.split()[0] )
        display_settings.hasUncertainty = int( self.stdout.readline() )
        self.stdout.readline()
        
        display_settings.nx = int(self.stdout.readline())
        print "NX=",display_settings.nx
        display_settings.ny = int(self.stdout.readline())
        print "NY=",display_settings.ny
        display_settings.nz = int(self.stdout.readline())
        print "NZ=",display_settings.nz
        
        display_settings.ox = display_settings.nx
        display_settings.oy = display_settings.ny
        display_settings.oz = display_settings.nz
        
        if ".tmap" in filename:
            display_settings.ox = int(self.stdout.readline())
            display_settings.oy = int(self.stdout.readline())
            display_settings.oz = int(self.stdout.readline())
            
        
        display_settings.x = [float(i) for i in self.stdout.readline().split()]
        display_settings.y = [float(i) for i in self.stdout.readline().split()]
        display_settings.z =[float(i) for i in self.stdout.readline().split()]
        
        display_settings.oxp = display_settings.x
        display_settings.oyp = display_settings.y
        display_settings.ozp = display_settings.z
        
        if ".tmap" in filename:
            display_settings.oxp = [float(i) for i in self.stdout.readline().split()]
            display_settings.oyp = [float(i) for i in self.stdout.readline().split()]
            display_settings.ozp  =[float(i) for i in self.stdout.readline().split()]
        if display_settings.z[-1] <= display_settings.z[-2]:
            display_settings.z[-1] = display_settings.z[-2] + 0.1
        if display_settings.ozp[-1] <= display_settings.ozp[-2]:
            display_settings.ozp[-1] = display_settings.ozp[-2] + 0.1
        
        print "xplanes", display_settings.x
        print "yplanes", display_settings.y
        print "zplanes", display_settings.z
        
        ##redo = False
        ##for i in range(0, display_settings.nx):
        ##    if ( display_settings.x[i] <= display_settings.x[i+1] ):
        ##        redo = True
        ##if redo:
        ##    dx = display_settings.x[1] - display_settings.x[0]
        ##    display_settings.x = [display_settings.x[0] for i in range(0, display_settings.nx+1)]
        ##    for i in range(0, display_settings.nx):
        ##        display_settings.x[i+1] = display_settings.x[i] + dx
        ##    print "xplanes", display_settings.x
        ##        
        ##print "yplanes", display_settings.y
        ##redo = False
        ##for j in range(0, display_settings.ny):
        ##    if ( display_settings.y[j] <= display_settings.y[j+1] ):
        ##        redo = True
        ##if redo:
        ##    dy = display_settings.y[1] - display_settings.y[0]
        ##    display_settings.y = [display_settings.y[0] for i in range(0, display_settings.nx+1)]
        ##    for j in range(0, display_settings.ny):
        ##        display_settings.y[j+1] = display_settings.y[j] + dy
        ##    print "yplanes", display_settings.y
        ##        
        ##print "zplanes", display_settings.z
        ##redo = False
        ##for k in range(0, display_settings.nz):
        ##    if ( display_settings.z[k] <= display_settings.z[k+1] ):
        ##        redo = True
        ##if redo:
        ##    dz = display_settings.z[1] - display_settings.z[0]
        ##    display_settings.z = [display_settings.z[0] for i in range(0, display_settings.nz+1)]
        ##    for k in range(0, display_settings.nz):
        ##        display_settings.z[k+1] = display_settings.z[k] + dz
        ##    print "zplanes", display_settings.z
        
        
        
        display_settings.hasMaterial = int(self.stdout.readline())
        display_settings.ng = int(self.stdout.readline())
        rmperfam = [int(i) for i in self.stdout.readline().split()]
        if len(rmperfam) == 1:
            display_settings.isCoupled == 0
        else:
            display_settings.isCoupled == 1
        tmp = self.stdout.readline().split()
        print "TMP=",tmp
        display_settings.e = []
        for i in range(0, len(tmp)):
            try:
                float(tmp[i])
                display_settings.e.append(float(tmp[i]))
            except:
                display_settings.e.append(0.)
        lower = [float(i) for i in self.stdout.readline().split()]
        for i in range(len(rmperfam)-1, -1, -1):
            display_settings.e.insert(rmperfam[i], lower[i])
        print lower
            
        ##display_settings.z = [display_settings.z[-1] - i + display_settings.z[0] for i in display_settings.z]
        display_settings.plane = 1 + (len(display_settings.z)-1) / 2
        display_settings.view = 0
        display_settings.g = 1
        print "Reading Plane",display_settings.plane, display_settings.x, display_settings.y, display_settings.z, display_settings.g

    def read_aard_plane(self):
        global directory_info, plane_data, display_settings
        #self.pid = self.stdout.readline()
        ## Begin Reading Plane / Don't Close File
        self.stdin.write("0\n")
        ## Send the View (0-xy, 1-xz, 2-yz)
        self.stdin.write(repr(display_settings.view)+"\n")
        ## Values / Unc (0-Value, 1-Unc)
        self.stdin.write(repr(display_settings.hasUncertainty)+"\n")
        ## Plane Number (z, y, x)
        self.stdin.write(repr(display_settings.plane)+"\n")
        ## Energy Group
        self.stdin.write(repr(display_settings.g)+"\n")
        readout = self.stdout.readline()
        new_line = []
        for i in readout.split():
            if ('E' in i):
                new_line.append( float(i) )
            else:
                new_line.append( 0.0 )
        print new_line
        plane_data.min, plane_data.max = tuple(new_line)
        print 0, repr(display_settings.view), repr(display_settings.hasUncertainty), repr(display_settings.plane), repr(display_settings.g)
        # delete all the rows and multiply the columns

        if display_settings.view == 0:
            length = display_settings.ny
            plane_data.nx = display_settings.nx
            plane_data.ny = display_settings.ny
            plane_data.xp = display_settings.x
            plane_data.yp = display_settings.y          
        elif display_settings.view == 1:
            length = display_settings.nz
            plane_data.nx = display_settings.nx
            plane_data.ny = display_settings.nz
            plane_data.xp = display_settings.x
            plane_data.yp = display_settings.z        
        elif display_settings.view == 2:
            length = display_settings.nz
            plane_data.nx = display_settings.ny
            plane_data.ny = display_settings.nz
            plane_data.xp = display_settings.y
            plane_data.yp = display_settings.z
        plane_data.data = []
        print "reading data"
        for j in range(0, length):
            readout = self.stdout.readline()
            new_line = []
            for i in readout.split():
                if ('E' in i):
                    new_line.append( abs(float(i)) )
                else:
                    new_line.append( 0.0 )            
            ##print new_line
            ##print new_line
            plane_data.data.append(new_line)
        plane_data.data = np.ma.masked_where(plane_data.data<=0,plane_data.data)
        for j in range(0, length):
            for i in range(0, len(plane_data.data[j])):
                if np.isnan(plane_data.data[j][i]):
                    plane_data.data[j][i] = 0.
        print "Finishing Reading plane_data.data"
        print plane_data.data

        plane_data.geo = []
        print "reading sub_mesh / hasMaterial", display_settings.hasMaterial
        if (display_settings.hasMaterial != 0):
            for j in range(0, length):
                new_line = self.stdout.readline().split()
                plane_data.geo.append([float(i) for i in new_line ])
            ## for j in range(0, length):
            ##     for i in range(0, len(plane_data.geo[0])):
            ##         if plane_data.geo[j][i] != 23:
            ## ## #        if plane_data.geo[j][i] == 1 or plane_data.geo[j][i] == 2 or plane_data.geo[j][i] == 3 or plane_data.geo[j][i] == 5:
            ##             plane_data.geo[j][i] = 0
            ##             plane_data.data[j][i] = 0.0
            ## ##     #print plane_data.geo[-1]
            ## ##     #if any(pl < 0 for pl in plane_data.geo[-1]):
            ## ##         #print plane_data.geo[-1]
            ## ##plane_data.geo = plane_data.geos
            plane_data.nsub = sum([[1 for i in a if i < 0].count(1) for a in plane_data.geo])
            #print "sub_cells on this plane",plane_data.nsub
            plane_data.sub = {}
            for j in range(0,len(plane_data.data)):
                for i in range(0,len(plane_data.data[0])):
                    if ( plane_data.geo[j][i] < 0 ):
                        nx, ny = ( int(m) for m in self.stdout.readline().split() )
                        xp = [float(m) for m in self.stdout.readline().split()]
                        yp = [float(m) for m in self.stdout.readline().split()]
                        
                        ##xp = display_settings.x
                        ##yp = display_settings.y
                        step = ny
                        start_data = []
                        for l in range(0,step):
                            new_data = [m for m in self.stdout.readline().split()]
                            ## print new_data
                            for dat in range(0, len(new_data)):
                                if "-" in new_data[dat] and len(new_data[dat].split("-")[-1]) > 2:
                                    new_data[dat] = 0.0
                                else:
                                    new_data[dat] = float(new_data[dat])
                            start_data.append(new_data)
                            ##if len( start_data[-1] ) < step:
                            ##    for i in range( 0, step - len( start_data[-1] ) ):
                            ##        start_data[-1].append( start_data[-1][-1] )
                        start_geo = []
                        for l in range(0,step):
                            try:
                                start_geo.append([int(m) for m in self.stdout.readline().split()])
                            except:
                                start_geo.append( [ 1 for k in range(0, step) ] )
                        start_data = np.array(start_data)
                        start_geo = np.array(start_geo)
                        start_dimensions = [xp[0], xp[-1], yp[0], yp[-1]]
                        ##print "data", start_data, j, i
                        ##print "xplanes", xp
                        ##print "yplanes", yp
                        plane_data.sub[ int(-1*plane_data.geo[j][i]) ] = plane_data_class(start_data, start_geo, xp, yp)
                        if (( plane_data.geo[j][i] < 0) and (np.any( plane_data.sub[-1*plane_data.geo[j][i]].data <= 0. ) ) ):
                            plane_data.data[j][i] = 0
        plane_data.dimensions = [plane_data.xp[0],
                                 plane_data.xp[-1],
                                 plane_data.yp[0],
                                 plane_data.yp[-1]]
        print plane_data.dimensions
        plane_data.aspect = abs(plane_data.yp[-1] - plane_data.yp[0]) / abs(plane_data.xp[-1] - plane_data.xp[0])


        plane_data.data = np.array(plane_data.data)
        if (plane_data.data.sum()) != 0:
            plane_data.max = plane_data.data[plane_data.data>0].max()
            plane_data.min = plane_data.data[plane_data.data>0].min()
        else:
            plane_data.max = 0.
            plane_data.min = 0.
        plane_data.xp = np.array(plane_data.xp)
        plane_data.yp = np.array(plane_data.yp)
        display_settings.xlim = [plane_data.xp[0], plane_data.xp[1]]
        display_settings.ylim = [plane_data.yp[0], plane_data.yp[1]]
        if display_settings.hasMaterial or display_settings.drawMesh:
            plane_data.get_geo()
        root.event_generate("<<redraw>>", when='tail')
        root.event_generate("<<newfile>>", when='tail')

    def read_varscl_plot(self):
        global directory_info, plane_data, display_settings
        #self.pid = self.stdout.readline()
        ## Begin Reading Plane / Don't Close File
        print "    talking to file"
        self.stdin.write("0\n")
        ## Send the View (3)
        self.stdin.write('3'+"\n")
        ## value or uncertainty
        self.stdin.write("0\n")
        ## Position (x, y, z)
        self.stdin.write(repr(display_settings.pos[0])+"\n")
        self.stdin.write(repr(display_settings.pos[1])+"\n")
        self.stdin.write(repr(display_settings.pos[2])+"\n")
        print "    reading the spectrum"
        plane_data.line = [float(i) for i in self.stdout.readline().split()]
        ##root.event_generate("<<redraw>>", when='tail')
        ##root.event_generate("<<newfile>>", when='tail')
        print "    opening file"
        o = open("spectrum.dat", "a")
        o.write(" ".join(["%.7e" % i for i in plane_data.line])+"\n")
        print len(plane_data.line)
        print "    saving file"
        o.close()
        
## ------------------------------------
## ====================================



## ====================================
## Global Classes
## ====================================
    
## ------------------------------------
# -- Plane Data Class
# -- contains current plane view data
class plane_data_class():
    def __init__(self, start_data, start_geo, start_xp, start_yp):
        self.dimensions = [ start_yp[0], start_yp[-1], start_xp[0], start_xp[-1]]
        print start_xp
        print start_yp
        self.aspect = ( abs(start_yp[-1] - start_yp[0]) / abs(start_xp[-1] - start_xp[0]) )
        print start_data[0]
        self.nx = len(start_data[0])
        self.ny = len(start_data)
        self.xp = np.array( start_xp )
        self.yp = np.array( start_yp )
        self.data = start_data
        self.geo = start_geo
        self.nsub = 0
        self.sub = {}
        ##self.get_geo()
        if (self.data[self.data>0].size > 0):
            self.max = self.data[self.data>0].max()
            self.min = self.data[self.data>0].min()
        else:
            self.max = 1.
            self.min = 0.1
        self.line = []

    def get_geo(self):
        print "getting geometry grid lines and subgrid lines"
        global display_settings
        self.grid_lines = []
        self.sub_grid_lines = []
        print self.ny, self.nx, len(self.geo), len(self.geo[-1])
        for j in range(0, self.ny):
            if len(self.geo[j]) < self.nx:
                self.geo[j].append(0)
            highest = 1
            self.grid_lines.append( ( [self.xp[0], self.yp[j]], [self.xp[-1], self.yp[j]] ) )
            for i in range(0, self.nx):
                if j == 0:
                    self.grid_lines.append( ( [self.xp[i], self.yp[0]], [self.xp[i], self.yp[-1]] ) )
                if display_settings.hasMaterial:
                    ## aprint "j,i",j,i
                    ## aprint len(self.geo), len(self.geo[j])
                    if self.geo[j][i] < 0:
                        print int(-1*self.geo[j][i]) 
                        s = int(-1*self.geo[j][i])
                        nx = self.sub[ s ].nx
                        ny = self.sub[ s ].ny
                        for l in range(1, ny):
                            self.sub_grid_lines.append( ( [self.xp[i], self.sub[ s ].yp[l]], [self.xp[i+1], self.sub[ s ].yp[l]] ) )
                        ##for l in range(0, ny+1):
                        ##    self.sub_grid_lines.append( ( [self.xp[i], self.sub[ s ].yp[l]], [self.xp[i+1], self.sub[ s ].yp[l]] ) )
                        for l in range(1, nx):
                            self.sub_grid_lines.append( ( [self.sub[ s ].xp[l], self.yp[j]], [self.sub[ s ].xp[l], self.yp[j+1]] ) )
                        ##for l in range(0, nx+1):
                        ##    self.sub_grid_lines.append( ( [self.sub[ s ].xp[l], self.yp[j]], [self.sub[ s ].xp[l], self.yp[j+1]] ) )
        self.grid_lines.append( ( [self.xp[0], self.yp[-1]], [self.xp[-1], self.yp[-1]] ) ) 
        self.grid_lines.append( ( [self.xp[-1], self.yp[0]], [self.xp[-1], self.yp[-1]] ) )
        self.lines = []            
        if display_settings.hasMaterial:
        
            ## ______________________________
            ##  this will only show results
            ##     for a given material
            # for j in range(0, len(self.geo)):
            #     for i in range(0, len(self.geo[j])):
            #         if (self.geo[j][i] != 2):
            #             self.data[j][i] = 0.0
            #             self.geo[j][i] = 0
                        
                        
            ##print "getting the geometry"
            ##print "nx,ny",len(self.geo[0]), len(self.geo)
            ##print "xp,yp",len(self.xp), len(self.yp)
            ##print "self.geo", self.geo
            ##print "xplanes", self.xp
            ##print "yplanes", self.yp
            l = 0
            for j in range(0, len(self.geo)):
                ## print "looping through j=", j
                for i in range(0, len(self.geo[j])):
                    ## print "looping through i=", j
                    # if this block does not have a sub_mesh
                    if self.geo[j][i] >= 0:
                        if j < len(self.geo)-1:
                            if self.geo[j+1][i] < 0:
                                n = int( -1*self.geo[j+1][i] )
                                for k in range(0, self.sub[n].nx):
                                    if self.geo[j][i] != self.sub[n].geo[0][k]:
                                        self.lines.append(([self.sub[n].xp[k], self.yp[j+1]], [self.sub[n].xp[k+1], self.yp[j+1]]))     
                            else:
                                if self.geo[j][i] != self.geo[j+1][i]:
                                    self.lines.append(([self.xp[i], self.yp[j+1]], [self.xp[i+1], self.yp[j+1]]))
                        if i < len(self.geo[0])-1:
                            if self.geo[j][i+1] < 0:
                                n = int( -1*self.geo[j][i+1] )
                                for k in range(0, self.sub[n].ny):
                                    if self.geo[j][i] != self.sub[n].geo[k][0]:
                                        self.lines.append(([self.xp[i+1], self.sub[n].yp[k]], [self.xp[i+1], self.sub[n].yp[k+1]]))
                                        
                            else:
                                if self.geo[j][i] != self.geo[j][i+1]:
                                    self.lines.append(([self.xp[i+1], self.yp[j]], [self.xp[i+1], self.yp[j+1]]))
                    # if this cell has a sub_mesh
                ### this is the most recent one!!!!if self.geo[j][i] < 0:
                ### this is the most recent one!!!!    n = int( -1*self.geo[j][i] )
                ### this is the most recent one!!!!    self.sub[n].get_geo()
                ### this is the most recent one!!!!    sub_grid_material = self.sub[n].lines
                ### this is the most recent one!!!!    for k in sub_grid_material:
                ### this is the most recent one!!!!        self.lines.append(k)
                ### this is the most recent one!!!!    
                ### this is the most recent one!!!!    # want to compare with the above cell boundary
                ### this is the most recent one!!!!    if j < len(self.geo):
                ### this is the most recent one!!!!        if self.geo[j+1][i] < 0:
                ### this is the most recent one!!!!            m = int( -1*self.geo[j+1][i] )
                ### this is the most recent one!!!!            # if the current cell has more x cells on the top boundary line
                ### this is the most recent one!!!!            if self.sub[n].nx == self.sub[m].nx:
                ### this is the most recent one!!!!                for k in range(0, self.sub[n].nx):
                ### this is the most recent one!!!!                    next = k
                ### this is the most recent one!!!!                    if (self.sub[n].geo[-1][k] != self.sub[m].geo[0][next]):
                ### this is the most recent one!!!!                        self.lines.append(([self.sub[n].xp[k], self.yp[j+1]], [self.sub[n].xp[k+1], self.yp[j+1]]))
                ### this is the most recent one!!!!            elif self.sub[n].nx > self.sub[m].nx:
                ### this is the most recent one!!!!                for k in range(0, self.sub[n].nx):
                ### this is the most recent one!!!!                    next = interval(self.sub[m].xp, self.sub[n].xp[k])
                ### this is the most recent one!!!!                    if (self.sub[n].geo[-1][k] != self.sub[m].geo[0][next]):
                ### this is the most recent one!!!!                        self.lines.append(([self.sub[n].xp[k], self.yp[j+1]], [self.sub[n].xp[k+1], self.yp[j+1]]))
                ### this is the most recent one!!!!            else:
                ### this is the most recent one!!!!                for k in range(0, self.sub[m].nx):
                ### this is the most recent one!!!!                    next = interval(self.sub[n].xp, self.sub[m].xp[k])
                ### this is the most recent one!!!!                    if (self.sub[m].geo[0][k] != self.sub[n].geo[-1][next]):
                ### this is the most recent one!!!!                        self.lines.append(([self.sub[m].xp[k], self.yp[j+1]], [self.sub[m].xp[k+1], self.yp[j+1]]))
                ### this is the most recent one!!!!        else:
                ### this is the most recent one!!!!            for k in range(0, self.sub[n].nx):
                ### this is the most recent one!!!!                start_x = self.sub[n].xp[k]
                ### this is the most recent one!!!!                point = self.sub[n].xp[k+1]
                ### this is the most recent one!!!!                if (self.sub[n].geo[-1][k] != self.geo[j+1][i]):
                ### this is the most recent one!!!!                    self.lines.append(([start_x, self.yp[j+1]], [point, self.yp[j+1]]))
                ### this is the most recent one!!!!    
                ### this is the most recent one!!!!    # want to compare with the above cell boundary
                ### this is the most recent one!!!!    if i < len(self.geo[0]):
                ### this is the most recent one!!!!        if len(self.geo[j]) > 1 and self.geo[j][i+1] < 0:
                ### this is the most recent one!!!!            m = int( -1*self.geo[j][i+1] )
                ### this is the most recent one!!!!            # if the current cell has more x cells on the top boundary line
                ### this is the most recent one!!!!            if self.sub[n].ny == self.sub[m].ny:
                ### this is the most recent one!!!!                for k in range(0, self.sub[n].ny):
                ### this is the most recent one!!!!                    next = k
                ### this is the most recent one!!!!                    if (self.sub[n].geo[k][-1] != self.sub[m].geo[next][0]):
                ### this is the most recent one!!!!                        self.lines.append(([self.xp[i+1], self.sub[n].yp[k]], [self.xp[i+1], self.sub[n].yp[k+1]]))
                ### this is the most recent one!!!!            elif self.sub[n].ny > self.sub[m].ny:
                ### this is the most recent one!!!!                for k in range(0, self.sub[n].ny):
                ### this is the most recent one!!!!                    next = interval(self.sub[m].yp, self.sub[n].yp[k])
                ### this is the most recent one!!!!                    if (self.sub[n].geo[k][-1] != self.sub[m].geo[next][0]):
                ### this is the most recent one!!!!                        self.lines.append(([self.xp[i+1], self.sub[n].yp[k]], [self.xp[i+1], self.sub[n].yp[k+1]]))
                ### this is the most recent one!!!!            else:
                ### this is the most recent one!!!!                for k in range(0, self.sub[m].ny):
                ### this is the most recent one!!!!                    next = interval(self.sub[n].yp, self.sub[m].yp[k])
                ### this is the most recent one!!!!                    if (self.sub[m].geo[k][0] != self.sub[n].geo[next][-1]):
                ### this is the most recent one!!!!                        self.lines.append(([self.xp[i+1], self.sub[m].yp[k]], [self.xp[i+1], self.sub[m].yp[k+1]]))
                ### this is the most recent one!!!!        else:
                ### this is the most recent one!!!!            for k in range(0, self.sub[n].ny):
                ### this is the most recent one!!!!                start_y = self.sub[n].yp[k]
                ### this is the most recent one!!!!                point = self.sub[n].yp[k+1]
                ### this is the most recent one!!!!                if (self.sub[n].geo[k][-1] != self.geo[j][i+1]):
                ### this is the most recent one!!!!                    self.lines.append(([self.xp[i+1], start_y], [self.xp[i+1], point]))
                        
                        # want to compare with the right cell boundary
                        ##if i < len(self.geo[0]):
                        ##    if self.geo[j][i+1] < 0:
                        ##        m = int( -1*self.geo[j][i+1] )
                        ##        # if the current cell has more x cells on the top boundary line
                        ##        for k in range(0, self.sub[n].ny):
                        ##            start_y = self.sub[n].yp[k]
                        ##            point = self.sub[n].yp[k+1]
                        ##            done = False
                        ##            while not done:
                        ##                next = interval(self.sub[m].yp, start_y)
                        ##                print "next", next
                        ##                print "start_y, point", start_y, point
                        ##                if next == 0:
                        ##                    done = True
                        ##                else:
                        ##                    point  = min(self.sub[n].yp[k+1], self.sub[m].yp[next+1])
                        ##                    if (self.sub[n].geo[-1][k] != self.sub[m].geo[0][next]):
                        ##                        self.lines.append(([ self.xp[i+1], start_y], [self.xp[i+1], point]))
                        ##                        start_y = point
                        ##                    start_y = point
                        ##                if (start_y == self.sub[n].yp[k+1]):
                        ##                    done = True
                        ##    else:
                        ##        for k in range(0, self.sub[n].ny):
                        ##            start_y = self.sub[n].yp[k]
                        ##            point = self.sub[n].yp[k+1]
                        ##            if (self.sub[n].geo[k][-1] != self.geo[j][i+1]):
                        ##                self.lines.append(([self.xp[i+1], start_x], [self.xp[i+1], point]))         

    def get_indices(self, x, y):
        i = 0
        j = 0
        xup = len(self.xp)
        yup = len(self.yp)
        while i+1 != xup:
            m = int(floor(float(i+xup)/2.))
            if x < self.xp[m]:
                xup = m
            else:
                i = m
        while j+1 != yup:
            m = int(floor(float(j+yup)/2.))
            if y < self.yp[m]:
                yup = m
            else:
                j = m
        return i, j
## ------------------------------------

## ------------------------------------ 
# -- TK Image Class
# -- prolly looking into multiple views
class data_view_class(ImageTk.PhotoImage):
    def __init__(self):
        ImageTk.PhotoImage.__init__(self, 'RGB', [800,600])

## ------------------------------------

## ------------------------------------
# -- Display Settings Class
# -- how the plane_data is displayed
class display_settings_class():
    def __init__(self):
        global plane_data
        self.ng = 1
        self.nx = len(plane_data.data[0])
        self.ny = len(plane_data.data)
        self.nz = 1
        self.ox = 0
        self.oy = 0
        self.oz = 0
        self.cart = True
        self.drawMesh = False
        self.hasMaterial = 1
        self.hasUncertainty = 0
        self.drawMaterial = True
        self.drawData = True
        self.isCoupled = 0
        self.bottom = 0
        self.setAspect = False
        self.e = [2., 1.]
        self.x = plane_data.xp
        self.y = plane_data.yp
        self.z  =[0., 2.]
        self.oxp = self.x
        self.oyp = self.y
        self.ozp = self.z
        self.xlim = [plane_data.xp[0], plane_data.xp[1]]
        self.ylim = [plane_data.yp[0], plane_data.yp[1]]
        self.max = plane_data.max
        self.min = plane_data.min
        self.maxed = False
        self.mined = False
        self.zoomed = False
        self.autosave = False
        self.file_name = 1

        self.view = 0
        self.g = 1
        self.plane = 1
        self.log = False
        self.binned = False
        self.bins = 10
        self.gradient = 0
        self.plot = 0
        self.pos = [1,1,1]
        
        self.radial = False
        self.nice = False
## ------------------------------------

## ------------------------------------
# -- Present Directory Info
# -- pwd & connection data
class directory_info_class():
    def __init__(self):
        self.host   = ""
        self.passwd = ""
        self.login  = ""
        self.pwd    = "~"
        self.path    = "~"

        self.f = []
        self.d = []
        self.connect = False
        self.read = False
        self.line = False
        self.file = ''
        self.open = False
        self.plot = False
## ------------------------------------
## ====================================



## ====================================
## Other Classes
## ====================================
    
## ------------------------------------
# -- SSH Bar Class
# -- gui tab w/ login & pwd info
class ssh_bar_class(Frame):
    def __init__(self, parent, *args, **kwargs):
        global directory_info
        Frame.__init__(self)
        parent.add(self, width=200, stretch="never")
        ##self.pack()
        junk = None
        
        try:
            f = open("salt","r")
            lines = f.readlines()
            self.connections = []
            for line in lines:
                self.connections.append( line.replace("\n","").replace("\r","").split(" ") )
            f.close()
            junk = self.connections[0]
        except:
            pass
            
        try:
            f = open("last","r")
            lines = f.readlines()
            for line in lines:
                if directory_info.host in line:
                    directory_info.pwd = line.replace("\n","").replace("\r","").split(":")[1:][0]
                    print 'pwd = ', directory_info.pwd, directory_info.host
                    directory_info.path = filter(None, directory_info.pwd.split("/"))
                    print 'path = ', directory_info.path, self.host
            f.close()
        except:
            self.pwd = ''
            self.path = ''
            
        if junk == None:
            junk = ["b2.neely.gatech.edu","tflaspoehler","passcode"]
        
        self.cns = []
        print self.connections
        for i in range(0, len( self.connections ) ):
            print "ADDING", self.connections[i][:], i
            ## self.cns.append( Button(self, text=self.connections[i][1]+"@"+self.connections[i][0], command=lambda:self.connect(int(i)) ) )
            self.cns.append( Button(self, text=self.connections[i][1]+"@"+self.connections[i][0], command=partial(self.connect, i) ) )
            self.cns[-1].pack(fill=X)
        
        self.hst = Entry(self)
        self.hst.pack(fill=X)
        self.hst.insert(0,junk[0])

        self.unme = Entry(self)
        self.unme.pack(fill=X)
        self.unme.insert(0,junk[1])

        self.pw = Entry(self, show="*")
        self.pw.pack(fill=X)
        self.pw.insert(0,"password")

        self.login = Button(self, text="Login", command=lambda:self.start_ssh(), justify=CENTER)
        self.login.pack(fill=X)
        self.start_ssh()
        directory_info.connect = True
        directory_info.host = self.hst.get()
        directory_info.login = self.unme.get()
        directory_info.passwd = self.pw.get()
        root.bind("<Key>", lambda x:self.keyPress(x))

    def start_ssh(self):
        global directory_info_lock
        if directory_info_lock.acquire():
            self.update()
            directory_info_lock.release()

    def update(self):
        global directory_info
        directory_info.host = self.hst.get()
        directory_info.login = self.unme.get()
        directory_info.passwd = self.pw.get()
        f = open("salt","w")
        add = True
        for i in range(0, len( self.connections )):
            if (directory_info.host == self.connections[i][0]):
                add = False
        f.write(directory_info.host + " " + directory_info.login+'\n')
        for i in range(0, len( self.connections )):
            if (directory_info.host != self.connections[i][0]):
                f.write(self.connections[i][0] + " " + self.connections[i][1]+'\n')
        f.close()
        directory_info.connect = True
        
    def keyPress(self,event):
        if event.keysym=='Return':
            err = self.start_ssh()
            if err!=0:
                print err
                

    def connect(self, c):
        self.hst.delete(0, 'end')
        self.unme.delete(0, 'end')
        self.hst.insert( 0, self.connections[c][0] )
        self.unme.insert( 0, self.connections[c][1] )
        print "changing to i,",c,self.connections[c][0] ,self.connections[c][1] 
## ------------------------------------
    
## ------------------------------------
# -- Navigation Bar Class
# -- gui tab for changing views 
class navigate_bar_class(Frame):
    def __init__(self, parent, *args, **kwargs):
        global display_settings
        self.parent = parent
        Frame.__init__(self)
        parent.add(self, width=200, stretch="never")
        ##self.pack(fill=Y, side=LEFT)
        self.update()

    def update(self, event=None):
        global display_settings, plane_data
        try:
            self.wrapper.destroy()
        except:
            pass
        self.wrapper = Frame(self, width=200)
        self.wrapper.pack(fill=BOTH, expand=1)
        ## Apply Button
        self.apply = Button(self.wrapper, text="Apply / Redraw", command=lambda:self.reset(), justify=LEFT)
        self.apply.pack(fill=X)
        ## Mesh
        self.mes = BooleanVar()
        if display_settings.drawMesh:
            self.mes.set(True)
        else:
            self.mes.set(False)
        self.mes.set(self.mes.get())
        self.mes_box = Checkbutton(self.wrapper, text="Show Mesh", variable=self.mes, justify=LEFT)
        self.mes_box.pack(fill=X)
        ## Material
        self.mat = BooleanVar()
        if display_settings.drawMaterial:
            self.mat.set(True)
        else:
            self.mat.set(False)
        self.mat.set(self.mat.get())
        self.mat_box = Checkbutton(self.wrapper, text="Show Material", variable=self.mat, justify=LEFT)
        self.mat_box.pack(fill=X)
        ## Data
        self.dat = BooleanVar()
        if display_settings.drawData:
            self.dat.set(True)
        else:
            self.dat.set(False)
        self.dat.set(self.dat.get())
        self.dat_box = Checkbutton(self.wrapper, text="Show Data", variable=self.dat, justify=LEFT)
        self.dat_box.pack(fill=X)
        ## Log Scale
        self.log = BooleanVar()
        if display_settings.log:
            self.log.set(True)
        else:
            self.log.set(False)
        self.log_box = Checkbutton(self.wrapper, text="Log Scale", variable=self.log, justify=LEFT)
        self.log_box.pack(fill=X)
        ## Radial Coordinates
        self.rad = BooleanVar()
        if display_settings.radial:
            self.rad.set(True)
        else:
            self.rad.set(False)
        self.rad_box = Checkbutton(self.wrapper, text="Radial Coordinates", variable=self.rad, justify=LEFT)
        self.rad_box.pack(fill=X)
        ## Show Relative Uncertainty
        self.unc = BooleanVar()
        if display_settings.hasUncertainty:
            self.unc.set(True)
        else:
            self.unc.set(False)
        self.unc_box = Checkbutton(self.wrapper, text="Relative Uncertainty", variable=self.unc, justify=LEFT)
        self.unc_box.pack(fill=X)
        ## Nice logarithmic contours
        self.nic = BooleanVar()
        if display_settings.nice:
            self.nic.set(True)
        else:
            self.nic.set(False)
        self.nic_box = Checkbutton(self.wrapper, text="Nice Intervals", variable=self.nic, justify=LEFT)
        self.nic_box.pack(fill=X)
        ## Binned Settings
        self.binned = BooleanVar()
        if display_settings.binned:
            self.binned.set(True)
        else:
            self.binned.set(False)
        self.bins = StringVar()
        self.bins.set(repr(display_settings.bins))
        self.bin_box = Frame(self.wrapper)
        
        self.binned_box = Checkbutton(self.bin_box, text="Discrete Intervals", variable=self.binned, justify=LEFT)
        self.binned_box.grid(row=0, column=0)
        self.bins_box = Entry(self.bin_box, textvariable=self.bins)
        self.bins_box.grid(row=0, column=1)
        self.bin_box.pack(fill=X)
        ## Maximum Settings
        self.maxed = BooleanVar()
        if display_settings.maxed:
            self.maxed.set(True)
            self.max = StringVar()
            self.max.set("%.7e" % display_settings.max)
        else:
            self.maxed.set(False)
            self.max = StringVar()
            self.max.set("%.7e" % plane_data.max)
        self.max_box = Frame(self.wrapper)
        
        self.maxed_box = Checkbutton(self.max_box, text="Max:", variable=self.maxed, justify=LEFT)
        self.maxed_box.grid(row=0, column=0)
        self.maxs_box = Entry(self.max_box, textvariable=self.max)
        self.maxs_box.grid(row=0, column=1)
        self.max_box.pack(fill=X)
        
        self.max_box = Frame(self.wrapper)
        ## Minimum Settings
        self.mined = BooleanVar()
        if display_settings.mined:
            self.mined.set(True)
            self.min = StringVar()
            self.min.set("%.7e" % display_settings.min)
        else:
            self.mined.set(False)
            self.min = StringVar()
            self.min.set("%.7e" % plane_data.min)
        self.min_box = Frame(self.wrapper)
        
        self.mined_box = Checkbutton(self.min_box, text="Min:", variable=self.mined, justify=LEFT)
        self.mined_box.grid(row=0, column=0)
        self.mins_box = Entry(self.min_box, textvariable=self.min)
        self.mins_box.grid(row=0, column=1)
        self.min_box.pack(fill=X)
        
        self.min_box = Frame(self.wrapper)
        
        ## Autosave images
        self.aut = BooleanVar()
        if display_settings.autosave:
            self.aut.set(True)
        else:
            self.aut.set(False)
        self.aut_box = Checkbutton(self.wrapper, text="Autosave Images", variable=self.aut, justify=LEFT)
        self.aut_box.pack(fill=X)
        
        ## Button for Averaging everything to 1.
        self.average = Button(self.wrapper, text="Average", command=lambda:self.ave(), justify=LEFT)
        self.average.pack(fill=X)
        
        ## Menu for View
        self.view = StringVar()
        if display_settings.view == 0:
            self.view.set("Top - XY")
        elif display_settings.view == 1:
            self.view.set("Front - XZ")
        elif display_settings.view == 2:
            self.view.set("Side - YZ")
        self.view_menu = OptionMenu(self.wrapper, self.view, "Top - XY", "Front - XZ", "Side - YZ")
        self.view_menu.pack(fill=X)
        self.view.trace("w",self.change)
        ## Menu for Energy Group
        self.group = Frame(self.wrapper)
        self.group_scroll = Scrollbar(self.group)
        self.group_list = Listbox(self.group, yscrollcommand=self.group_scroll.set, exportselection=False)
        self.group_scroll.config(command=self.group_list.yview)
        if (display_settings.isCoupled):
            for i in range(0, display_settings.bottom):
                self.group_list.insert("end",repr(i+1) + " Neutron (%1.2e - %1.2e)"%(display_settings.e[i], display_settings.e[i+1]))
            for i in range(display_settings.bottom+1, display_settings.ng):
                self.group_list.insert("end",repr(i) + " Photon (%1.2e - %1.2e)"%(display_settings.e[i], display_settings.e[i+1]))
        else:
            ##for i in range(0, display_settings.ng):
            print "ng", display_settings.ng, len(display_settings.e)
            print " e", display_settings.e
            for i in range(0, display_settings.ng):
                try:
                    ##print "Group",i, display_settings.e[i],"of",display_settings.ng
                    self.group_list.insert("end",repr(i+1) + " Neutron (%1.2e - %1.2e)"%(display_settings.e[i], display_settings.e[i+1]))
                except:
                    #self.group_list.insert("end", "neutrons")
                    self.group_list.insert("end",repr(i+1) + " Photon (%1.2e - %1.2e)"%(display_settings.e[i], display_settings.e[i+1]))
        self.group_value = display_settings.g
        self.group_list.select_set(self.group_value-1)
        self.group_list.yview(self.group_value-1)
        self.group_list.grid(row=0,column=0,sticky=NSEW)
        self.group_scroll.grid(row=0,column=1,sticky=NS)
        self.group.columnconfigure(0, weight=1)
        self.group.pack(fill=BOTH)
        self.group_list.bind('<<ListboxSelect>>', self.set_group)
        ## Menu for Plane
        if display_settings.view == 0:
            z = display_settings.ozp
            nz = display_settings.oz
        elif display_settings.view == 1:
            z = display_settings.oyp
            nz = display_settings.oy
        elif display_settings.view == 2:
            z = display_settings.oxp
            nz = display_settings.ox
        self.plane = Frame(self.wrapper)
        self.plane_scroll = Scrollbar(self.plane)
        self.plane_list = Listbox(self.plane, yscrollcommand=self.plane_scroll.set,  exportselection=False)
        self.plane_scroll.config(command=self.plane_list.yview)
        print z
        print nz
        for i in range(0, nz):
            self.plane_list.insert("end",repr(i+1)+" ( %1.2f - %1.2f)"%(z[i+1],z[i]))
        self.plane_value = display_settings.plane
        self.plane_list.select_set(self.plane_value-1)
        self.plane_list.yview(self.plane_value-1)
        self.plane_list.grid(row=0,column=0,sticky=NSEW)
        self.plane_scroll.grid(row=0,column=1,sticky=NS)
        self.plane.columnconfigure(0, weight=1)
        self.plane.pack(fill=BOTH)
        self.plane_list.bind('<<ListboxSelect>>', self.set_plane)

    def ave(self):
        global plane_data
        plane_data.data = plane_data.data / np.average( plane_data.data[plane_data.data>0] )
        
    def change(self,*args):
        global display_settings
        try:
            self.plane.pack_forget()
            ##self.apply.pack_forget()
        except:
            pass
        ## Menu for Plane
        if self.view.get() == "Top - XY":
            z = display_settings.ozp
            nz = display_settings.oz
        elif self.view.get() == "Front - XZ":
            z = display_settings.oyp
            nz = display_settings.oy
        elif self.view.get() == "Side - YZ":
            z = display_settings.oxp
            nz = display_settings.ox
        ## Apply Button
        ##self.apply = Button(self.wrapper, text="Apply / Redraw", command=lambda:self.reset(), justify=LEFT)
        ##self.apply.pack(fill=X)
        self.plane = Frame(self.wrapper)
        self.plane_scroll = Scrollbar(self.plane)
        self.plane_list = Listbox(self.plane, yscrollcommand=self.plane_scroll.set,  exportselection=False)
        self.plane_scroll.config(command=self.plane_list.yview)
        for i in range(0, nz):
            self.plane_list.insert("end",repr(i+1)+" ( %1.2f - %1.2f)"%(z[i+1],z[i]))
        self.plane_value = nz/2
        if self.plane_value == 0:
            self.plane_value = 1
        self.plane_list.select_set(self.plane_value-1)
        self.plane_list.yview(self.plane_value-1)
        self.plane_list.grid(row=0,column=0,sticky=NSEW)
        self.plane_scroll.grid(row=0,column=1,sticky=NS)
        self.plane.columnconfigure(0, weight=1)
        self.plane.pack(fill=BOTH, expand=1)
        self.plane_list.bind('<<ListboxSelect>>', self.set_plane)
        
    def reset(self):
        global display_settings, display_settings_lock, directory_info, plane_data
        print "Apply / Reset"
        if display_settings_lock.acquire():
            ## Change to show mesh data
            display_settings.drawMesh = self.mes.get()
            ## Change to show material data
            display_settings.drawMaterial = self.mat.get()
            ## Change to show data
            display_settings.drawData = self.dat.get()
            ## Change the Scale
            display_settings.log = self.log.get()
            ## Change Coordinates
            display_settings.radial = self.rad.get()
            ## Change to Uncertainty
            if self.unc.get() == True:
                if display_settings.hasUncertainty == 0:
                    directory_info.line = True
                display_settings.hasUncertainty = 1
            else:
                if display_settings.hasUncertainty == 1:
                    directory_info.line = True
                display_settings.hasUncertainty = 0
            if self.nic.get() == True:
                display_settings.nice = True
            else:
                display_settings.nice = False
            ## Change to Binned Intervals
            display_settings.binned = self.binned.get()
            ## Change to Number of Bins
            display_settings.bins = int(self.bins.get())
            ## Change the max value to a custom value
            if self.maxed.get() == True:
                display_settings.maxed = True
                display_settings.max = float(self.max.get())
            else:
                display_settings.maxed = False
                display_settings.max = plane_data.max
                self.max.set("%.7e" % plane_data.max)
            ## Change the min value to a custom value
            if self.mined.get() == True:
                display_settings.mined = True
                display_settings.min = float(self.min.get())
            else:
                display_settings.mined = False
                display_settings.min = plane_data.min
                self.min.set("%.7e" % plane_data.min)
            display_settings.autosave = self.aut.get()
            ## Change the View
            if self.view.get() == "Top - XY":
                if display_settings.view != 0:
                    directory_info.line = True
                display_settings.view = 0
            elif self.view.get() == "Front - XZ":
                if display_settings.view != 1:
                    directory_info.line = True
                display_settings.view = 1
            elif self.view.get() == "Side - YZ":
                if display_settings.view != 2:
                    directory_info.line = True
                display_settings.view = 2
            ## Change the Group
            if display_settings.g != self.group_value:
                print "old group / new group", display_settings.g, "/", self.group_value
                directory_info.line = True
            if display_settings.plane != self.plane_value:
                directory_info.line = True
            display_settings.g = self.group_value
            display_settings.plane = self.plane_value
            display_settings_lock.release()
            ## Change the Plane
            #try:
            #    display_settings_lock.release()
            #except:
            #    pass
            if directory_info.line == False:
                root.event_generate("<<redraw>>", when='tail')
                
    def set_plane(self, e):
        self.plane_value = int(filter(None, self.plane_list.get(self.plane_list.curselection()).split(" "))[0])
        print self.plane_value
                
    def set_group(self, e):
        self.group_value = int(filter(None, self.group_list.get(self.group_list.curselection()).split(" "))[0])
        print self.group_value
## ------------------------------------
                    
## ------------------------------------
# -- TreeView Class
# -- displays content of pwd
class tree_explorer(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent, width=200)
        self.pack(fill=BOTH, expand=1)
        self.update()

    def update(self):
        global directory_info
        # Clear previous Frames
        try:
            if self.header.winfo_exists():
                self.header.pack_forget()
        except:
            pass
        try:
            if self.directory_view.winfo_exists():
                self.directory_view.pack_forget()
        except:
            pass
        # Header with Path of Current Directory
        self.header = Frame(self)
        self.path = []
        for i in range(0, len(directory_info.path)):
            p = directory_info.path[i]
            self.path.append(Label(self.header, text="/"+p))
            self.path[-1].pack(side=LEFT)
            self.path[-1].bind("<Button-1>", lambda event, arg="/"+"/".join(directory_info.path[:i+1]): cd(event, arg))
        
        # Frame w/ Scroll Bars and Tree View for Current Directory
        folder_image = ImageTk.PhotoImage(Image.open(os.path.join("img","folder.gif")))
        file_image   = ImageTk.PhotoImage(Image.open(os.path.join("img","document.tif")))
        self.plant = ttk.Treeview(self,
                             columns=('size','date'))
        ybar = ttk.Scrollbar(self,
                             orient='vertical'
                             , command=self.plant.yview)
        xbar = ttk.Scrollbar(self,
                             orient='horizontal',
                             command=self.plant.xview)
        self.plant.configure(yscroll=ybar.set,xscroll=xbar.set)
        self.plant.heading("#0",text='Path',anchor='w')
        i = 1
        self.plant.insert('','end',text='..',open="True", iid='..', image=folder_image)
        i+=1
        for d in directory_info.d:
            self.plant.insert('','end',text=d,open=True,iid=d, image=folder_image)
            i+=1
        for f in directory_info.f:
            self.plant.insert('','end',text=f,open=True,iid=f, image=file_image)
            i+=1
        self.plant.bind("<Double-1>", self.onDoubleClick)
        self.plant.grid(row=1, column=0, sticky=NSEW)
        self.plant.rowconfigure(1, weight=1)
        ybar.grid(row=1, column=1, sticky=NS)
        xbar.grid(row=2, column=0, sticky=EW)
        self.header.grid(row=0, column=0, sticky=EW)


    def onDoubleClick(self, event):
        global directory_info
        item = self.plant.selection()[0]
        if item[-1]=="/" or item[-1]=="\\":
            cd(0, "/".join([directory_info.pwd, item]))
        elif item=="..":
            cd(0, "/"+"/".join(directory_info.path[:-1]))
        else:
            directory_info.file = item
            directory_info.file_type = item.split('.')[-1]
            directory_info.open = True
## ------------------------------------
                    
## ------------------------------------
# -- binned_cmap_class
# -- discretizes colormaps
class  binned_LinearSegmentedColormap(LinearSegmentedColormap):
    def __init__(self, name, oldMap, bins, *args, **kwargs):
        numbers = [0.]
        step = 1. / float(bins-1)
        for i in range(0,bins-1):
            numbers.append(numbers[-1]+step)
        colours = []
        for i in range(0, len(numbers)):
            colours.append([[j*255 for j in oldMap(numbers[i])[:3]],numbers[i]])
        numbers = [0.]
        step = 1. / float(bins)
        for i in range(0,bins):
            numbers.append(numbers[-1]+step)
        cmp = {}
        cmp['blue']  = [ ( 0., float(colours[0][0][2])/255., float(colours[0][0][2])/255.) ]
        cmp['green'] = [ ( 0., float(colours[0][0][1])/255., float(colours[0][0][1])/255.) ]
        cmp['red']   = [ ( 0., float(colours[0][0][0])/255., float(colours[0][0][0])/255.) ]
        for j in range(1, len(colours)):
            cmp['blue'].append(  ( numbers[j], float(colours[j-1][0][2])/255., float(colours[j][0][2])/255.) )
            cmp['green'].append( ( numbers[j], float(colours[j-1][0][1])/255., float(colours[j][0][1])/255.) )
            cmp['red'].append(   ( numbers[j], float(colours[j-1][0][0])/255., float(colours[j][0][0])/255.) )
        cmp['blue'].append(   ( 1., float(colours[-1][0][2])/255., float(colours[-1][0][2])/255.) )
        cmp['green'].append(  ( 1., float(colours[-1][0][1])/255., float(colours[-1][0][1])/255.) )
        cmp['red'].append(    ( 1., float(colours[-1][0][0])/255., float(colours[-1][0][0])/255.) )
        LinearSegmentedColormap.__init__(self, name, cmp)
## ------------------------------------
                    
## ------------------------------------
# -- Custom cMaps Class
# -- reads in colormaps from older code
class custom_cmaps_class(list):
    def __init__(self):
        list.__init__(self)
        scales = []
        scales.append([ [[127,0,255],0.], [[0,0,255],1./5.], [[0,255,0],2./5.], [[255,255,0],3./5.], [[255,0,0],1.]])
        scales.append([ [[127,0,255],0.], [[0,0,255],0.2], [[0,255,255],0.4], [[0,255,0],0.6], [[255,255,0],0.8], [[255,0,0],1.]])
        scales.append([ [[0,0,255],0.], [[0,255,255],0.25], [[0,255,0],0.5], [[255,255,0],0.75], [[255,0,0],1.] ])
        scales.append([ [[0,0,255],0.],  [[0,255,255],0.375], [[255,255,0],0.625], [[255,0,0],0.875], [[127,0,0],1.]  ])
        scales.append([ [[0,0,127],0.], [[0,0,255],0.125], [[0,255,255],0.375], [[255,255,0],0.625], [[255,0,0],0.875], [[127,0,0],1.]  ])
        scales.append([ [[245,245,245],0.], [[75,75,75],1.] ])
        scales.append([ [[255,255,255],0.], [[200,0,0],1.] ])
        binned = 0
        shift = 0
        if binned:
         shift = 1
        for i in range(0,len(scales)):
            self.append({})
            self[-1]['blue']  = [ ( scales[i][0][1], float(scales[i][0][0][2])/255., float(scales[i][0+shift][0][2])/255.) ]
            self[-1]['green'] = [ ( scales[i][0][1], float(scales[i][0][0][1])/255., float(scales[i][0+shift][0][1])/255.) ]
            self[-1]['red']   = [ ( scales[i][0][1], float(scales[i][0][0][0])/255., float(scales[i][0+shift][0][0])/255.) ]
            #self[-1]['alpha']  =[ ( scales[i][0][1], float(scales[i][0][1]), float(scales[i][0][1]) ) ]
            for j in range(1, len(scales[i])-1):
                self[-1]['blue'].append(  ( scales[i][j][1], float(scales[i][j+shift][0][2])/255., float(scales[i][j][0][2])/255.) )
                self[-1]['green'].append( ( scales[i][j][1], float(scales[i][j+shift][0][1])/255., float(scales[i][j][0][1])/255.) )
                self[-1]['red'].append(   ( scales[i][j][1], float(scales[i][j+shift][0][0])/255., float(scales[i][j][0][0])/255.) )
            self[-1]['blue'].append(   ( scales[i][-1][1], float(scales[i][-1-shift][0][2])/255., float(scales[i][-1][0][2])/255.) )
            self[-1]['green'].append(  ( scales[i][-1][1], float(scales[i][-1-shift][0][1])/255., float(scales[i][-1][0][1])/255.) )
            self[-1]['red'].append(    ( scales[i][-1][1], float(scales[i][-1-shift][0][0])/255., float(scales[i][-1][0][0])/255.) )
            #self[-1]['alpha'].append( ( scales[i][-1][1], float(scales[i][-1][1]), float(scales[i][-1][1]) ) )
## ====================================

                
## ====================================
## TKinter Loop
## ====================================
def tk_lock_check():
    global plane_data_lock, data_view_lock, display_settings_lock, directory_info_lock
    global plane_data_main, data_view_main, display_settings_main, directory_info_main
    
##    if plane_data_lock.locked() and not plane_data_main:
##        print "plane_data_main is LOCKED"
##        plane_data_main = True
##    elif not plane_data_lock.locked() and plane_data_main:
##        plane_data_main = False
##        update_canvas()
##        print "Updated Canvas"
        
    if data_view_lock.locked() and not data_view_main:
        data_view_main = True
    elif not data_view_lock.locked() and data_view_main:
        data_view_main = False
        root.ssh_view.explorer.update()
        
    if display_settings_lock.locked() and not display_settings_main:
        print "display_settings is LOCKED"
        display_settings_main = True
    elif not display_settings_lock.locked() and display_settings_main:
        display_settings_main = False
        
    if directory_info_lock.locked() and not directory_info_main:
        directory_info_main = True
    elif not directory_info_lock.locked() and directory_info_main:
        directory_info_main = False
        root.ssh_view.explorer.update()
    root.after(100, tk_lock_check)

                
## ====================================
## Random Tkinter helper functions
## ====================================
## ------------------------------------
def cd(event, arg):
    global directory_info
    print "cd -> "+arg
    f = open("last","r")
    lines = f.readlines()
    f.close()
    f = open("last","w")
    add = True
    for line in lines:
        if directory_info.host in line:
            add = False
    if add:
        f.write(directory_info.host + ':' + arg + '\n')
    for line in lines:
        if directory_info.host in line:
            f.write(directory_info.host + ':' + arg + '\n')
        else:
            f.write(line)
    f.close()
    directory_info.pwd = arg
    directory_info.read  = True
## ------------------------------------
def save_image(event=None, name=False):
    global directory_info
    buf = io.BytesIO()
    #### fig.savefig(buf, format="png", dpi=500, bbox_inches='tight', pad_inches=0)
    #### fig.savefig(buf, format="png", dpi=100) ###, bbox_inches='tight', pad_inches=0)
    fig.savefig(buf, format="png", dpi=200, bbox_inches='tight', pad_inches=0)
    buf.seek(0)
    im = Image.open(buf)
    clipboard.send_to_clipboard(im)
    if name:
        fig.savefig(name + ".png", dpi=200)
    print "saved figure"
## ------------------------------------
def save_plane(event=None):
    global plane_data, directory_info
    
    f = open(directory_info.file.split(".")[0]+".dat", "w")
    for j in range(0, len(plane_data.data)):
        next_line = " ".join(["%e" % i for i in plane_data.data[j][:]])
        f.write(next_line+'\n')
    f.close()
    return
    
def save_excel_plane(event=None):
    global plane_data, directory_info
                
    old_book = "output.xls"
    
    print "checking file", old_book, " and it's existence", os.path.exists(old_book)
    n_sheets = 0
    if os.path.exists(old_book):
        rb = open_workbook(old_book, formatting_info=True)
        n_sheets = rb.nsheets
        ## while True:
        ##     try:
        ##         r_sheet = rb.sheet_by_index(n_sheets+1)
        ##         n_sheets = n+1
        ##         print "loaded a sheet"
        ##     except:
        ##         print "failed to load a sheet"
        ##         break
        book = copy(open_workbook(old_book))
    else:
        book = xlwt.Workbook()
    sheet = book.add_sheet(repr(n_sheets+1))
    stile = xlwt.XFStyle()
    sheet.write(0,0,"X/Y",stile)
    f = open("power.dat","w")
    n = 1
    for i in range(0, len(plane_data.data[0])+1):
        sheet.write(0,i+1,plane_data.xp[i])
    for j in range(0, len(plane_data.data)):
        sheet.write(j+1,0,plane_data.yp[j])
        f.write("["+", ".join( [repr(i) for i in plane_data.data[j]] )[:-1]+"],\n")
        for i in range(0, len(plane_data.data[0])):
            sheet.write(j+1,i+1,plane_data.data[j][i],stile)
    f.close()
    sheet.write(j+2,0,plane_data.yp[j+1])
    book.save("output.xls")
    print "saved plane"
## ------------------------------------
def key_input(event=None):
    if event.char in ('e','s','r'):
        print "ello gov"
## ------------------------------------
def update_canvas(event=None):
    root.update()
    global plane_data, display_settings, display, scales
    custom_cmap = LinearSegmentedColormap('custom_cmap', scales[display_settings.gradient]) ### SCALE DEFAULT
    custom_cmap = plt.get_cmap('jet')
    ##custom_cmap.init() 
    if display_settings.binned:
        custom_cmap = binned_LinearSegmentedColormap('custom_cmap', custom_cmap, display_settings.bins)
    ##custom_cmap = ListedColormap(custom_cmap.colors[::-1])
    ##alphas = np.abs(np.linspace(-1.0, 1.0, custom_cmap.N))
    ##custom_cmap._lut[:-3,-1] = alphas
    cmap = custom_cmap
    a = [int(255*i) for i in cmap(0.5)[0:3]]
    print a
    print (255*i for i in cmap(0.5)[0:3])
    plt.rcParams['figure.figsize'] = display.winfo_width() / 72, display.winfo_height() / 72
    plt.clf()
    s = plane_data.data.sum()
    if display_settings.radial and s != 0:
        ax = fig.add_axes([0.1,0.1,0.8,0.8], polar=True)
        if display_settings.log:
            bounds = [log(getMin(plane_data.data)),log(plane_data.data.max())]
            for r in range(0, plane_data.data.shape[1]):
                for t in range(0, plane_data.data.shape[0]):
                    if plane_data.data[t][r] <= 0:
                        color = (0.,0.,0.,0.)
                    else:
                        color = cmap((log(plane_data.data[t][r]) - bounds[0])/(bounds[1]-bounds[0]))
                    ax.bar(t * 2. * np.pi / float(plane_data.data.shape[0]), 1., width=2. * np.pi / float(plane_data.data.shape[0]), bottom=float(r), color=color, edgecolor = color)
        else:
            for r in range(0, plane_data.data.shape[1]):
                for t in range(0, plane_data.data.shape[0]):
                    color = cmap(plane_data.data[t][r] / plane_data.data.max())
                    ax.bar(t * 2. * np.pi / float(plane_data.data.shape[0]), 1., width=2. * np.pi / float(plane_data.data.shape[0]), bottom=float(r), color=color, edgecolor = color)

        
        ax.set_yticks([])
        ax.set_ylim(0,plane_data.data.shape[1])
    else:
        ax = fig.add_subplot(111)
        
        if display_settings.drawMesh:
            alph = 0.5
            wid = 1.0
            if (display_settings.drawData == False):
                alph = 0.5
            if (plane_data.nsub > 0):
                sub_grid_lines = LineCollection(plane_data.sub_grid_lines, color='black', alpha=alph, linewidths=wid)
                grid_lines = LineCollection(plane_data.grid_lines, color='black', alpha=alph, linewidths=wid)
                ax.add_collection(grid_lines)
                ax.add_collection(sub_grid_lines)
            else:
                grid_lines = LineCollection(plane_data.grid_lines, color='black', alpha=alph, linewidths=wid)
                ax.add_collection(grid_lines)
            ##grid_lines.set_linewidth(0.5)
                    
        if display_settings.drawMaterial and display_settings.hasMaterial:
            if display_settings.drawMesh:
                alpha = 0.75
            else:
                alpha = 0.75
            wid = 1.0
            lines = LineCollection(plane_data.lines, color='black', alpha = alpha)#, linewidths=wid)
            ##lines.set_linewidth(1)
            ax.add_collection(lines)
            if (plane_data.nsub > 0):
                sub_grid_lines = []
                for sub in plane_data.sub.itervalues():
                    ##print "SUB",sub
                    try:
                        pass
                        ##sub_grid_lines.append(LineCollection(sub.lines, color='black', alpha = alpha*0.1), linewidths=wid*0.1)
                        ##ax.add_collection(sub_grid_lines[-1])
                    except:
						pass
                        ##print "sub has no grid_lines"
        testing = False
        vmin = display_settings.min
        vmax = display_settings.max
        if display_settings.drawData and s != 0:
            if display_settings.log:
                if (vmin <= 0):
                    vmin = plane_data.data[plane_data.data>0].min()
                ##plt.pcolormesh(plane_data.xp, plane_data.yp, plane_data.data, cmap=cmap, norm=LogNorm(), vmin=10.**floor(log10(plane_data.min)), vmax=10.**ceil(log10(plane_data.max)))
                if not testing:
                    if display_settings.nice:
                        print "plane_data.min/max = ",vmin, vmax
                        print "X planes", plane_data.xp
                        print "Y planes", plane_data.yp
                        plt.pcolormesh( plane_data.xp, 
                                        plane_data.yp,
                                        plane_data.data, 
                                        cmap=cmap, 
                                        norm=LogNorm(), 
                                        vmin=10.**floor(log10(vmin)), 
                                        vmax=10.**ceil( log10(vmax)) )
                    else:
                        print "plane_data.min/max = ",plane_data.data[plane_data.data>0].min(),plane_data.data[plane_data.data>0].max()
                        print "X planes", plane_data.xp
                        print "Y planes", plane_data.yp
                        plt.pcolormesh( plane_data.xp,
                                        plane_data.yp,
                                        plane_data.data, 
                                        cmap=cmap, 
                                        norm=LogNorm(), 
                                        vmin=vmin,
                                        vmax=vmax )
                        
                else:
                    xp = []
                    for i in range(0, plane_data.xp.size-1):
                        xp.append( 0.5*(plane_data.xp[i] + plane_data.xp[i+1]) )
                    yp = []
                    for i in range(0, plane_data.yp.size-1):
                        yp.append( 0.5*(plane_data.yp[i] + plane_data.yp[i+1]) )
                    plt.contourf(xp, yp, plane_data.data, cmap=cmap, norm=LogNorm())
            else:
                if not testing:
                    z = np.ma.masked_array(plane_data.data, plane_data.data <= 0.)
                    ##z = 1.0 * plane_data.data
                    ##z[z <= 0.0] = 1.0
                    coarse = plt.pcolormesh(plane_data.xp, plane_data.yp, z, cmap=cmap)
                    ##coarse.set_clim(vmin=getMin(plane_data.data),vmax=getMax(plane_data.data))
                    coarse.set_clim( vmin=vmin, vmax=vmax )
                else:
                    xp = []
                    for i in range(0, plane_data.xp.size-1):
                        xp.append( 0.5*(plane_data.xp[i] + plane_data.xp[i+1]) )
                    yp = []
                    for i in range(0, plane_data.yp.size-1):
                        yp.append( 0.5*(plane_data.yp[i] + plane_data.yp[i+1]) )
                    count = plt.contourf(xp, yp, plane_data.data, cmap=cmap, levels=np.linspace(plane_data.data.min(),plane_data.data.max(),100))
                    ##plt.clabel(count, fmt = '%2.1f', colors = 'w', fontsize=14)
            if (plane_data.nsub > 0):
                if display_settings.log:
                    subs = []
                    for sub in plane_data.sub.itervalues():
                        if display_settings.nice:
                            subs.append(plt.pcolormesh(sub.xp, sub.yp, sub.data, cmap=cmap, norm=LogNorm(), 
                                        vmin=10.**floor(log10(vmin)), 
                                        vmax=10.**ceil( log10(vmax)) ))
                            subs[-1].set_clim(vmin=10.**floor(log10(display_settings.min)),vmax=10.**ceil(log10(display_settings.max)))
                        else:
                            subs.append(plt.pcolormesh(sub.xp, sub.yp, sub.data, cmap=cmap, norm=LogNorm()))
                            subs[-1].set_clim(vmin=display_settings.min,vmax=display_settings.max)
                else:
                    subs = []
                    for sub in plane_data.sub.itervalues():
                        subs.append(plt.pcolormesh(sub.xp, sub.yp, sub.data, cmap=cmap))
                        ##print "MAX", getMin(plane_data.data), getMax(plane_data.data)
                        subs[-1].set_clim(vmin=display_settings.min,vmax=display_settings.max)
        
        if display_settings.zoomed:
            ax.set_xlim(display_settings.xlim)
            ax.set_ylim(display_settings.ylim)
        else:
            plt.axis(plane_data.dimensions)
        if display_settings.view == 0:
            plt.xlabel('x (cm)')
            plt.ylabel('y (cm)')
        elif display_settings.view == 1:
            plt.xlabel('x (cm)')
            plt.ylabel('z (cm)')
        elif display_settings.view == 2:
            plt.xlabel('y (cm)')
            plt.ylabel('z (cm)')
        if display_settings.setAspect:
            ax.set(aspect=1.)
            ax.set(aspect=1.)
            display_settings.xlim = ax.get_xlim()
            display_settings.ylim = ax.get_ylim()
            ## plt.axis('equal')
        else:    
            ## ax.set(aspect=1.)
            plt.axis('equal')
        if display_settings.drawData and s != 0:
            divider = make_axes_locatable(ax)
            cax = divider.append_axes("right", size="5%", pad=0.125)
            if display_settings.log and display_settings.nice:
                cb = plt.colorbar(format=r"%1.2e", cax=cax, norm=Normalize(vmin=vmin, vmax=vmax))
                cb.set_ticklabels(log_intervals(vmin,vmax, True))
                cb.set_ticks(log_intervals(vmin,vmax, True))
            elif display_settings.log:
                cb = plt.colorbar(format=r"%1.2e", cax=cax, norm=Normalize(vmin=vmin, vmax=vmax))
                cb.set_ticklabels(log_intervals(vmin,vmax))
                cb.set_ticks(log_intervals(vmin,vmax))
            else:
                cb = plt.colorbar(cax=cax, norm=Normalize(vmin=0.0, vmax=1.0))
                ##cb.set_ticks([0,0.05,0.1,0.15,0.2])
                ##cb.set_ticklabels(["0%","5%","10%","15%","20%"])
            ##print cb.ax.yaxis.label()
            ##for label in cb.ax.yaxis.get_ticklabels():
            ##    label.set_font_properties(font)
            ##cb.set_label("Neutron Flux\n (n/cm2s)",x=-10.,  y=1.05, rotation=0)
            
        
        ##if display_settings.plot == 1:
        ##    ax2 = fig.add_subplot(221)
        ##    print display_settings.e[:len(plane_data.line)]
        ##    print plane_data.line
        ##    print len(display_settings.e[:len(plane_data.line)]), len(plane_data.line)
        ##    ax2.plot(display_settings.e[:len(plane_data.line)], plane_data.line)
        ax.format_coord = format_coord
        fig.canvas.mpl_connect('button_press_event', onclick)
        fig.canvas.mpl_connect('scroll_event', zoom_fig)
    plt.gcf().canvas.draw()
    if display_settings.autosave:
        save_image(name=repr(display_settings.file_name))
        display_settings.file_name += 1
## ------------------------------------
def log_intervals(bot, top, round=False):
    if round:
        a = []
        for j in range(int(floor(log10(bot))), int(ceil(log10(top))) + 1):
            a.append( float(10**j) )
        return a
    else:
        a = [bot]
        for j in range(int(ceil(log10(bot))), int(ceil(log10(top)))):
            a.append( float(10**j) )
        a.append(top)
        return a
## ------------------------------------
def zoom_fig(event):
    global ax, display_settings
    base_scale = 1.5
    if display_settings.zoomed:
        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()
    else:
        cur_xlim = display_settings.xlim
        cur_ylim = display_settings.ylim
    print "Before", cur_xlim, cur_ylim
    cur_xrange = (cur_xlim[1] - cur_xlim[0])*.5
    cur_yrange = (cur_ylim[1] - cur_ylim[0])*.5
    xdata = event.xdata # get event x location
    ydata = event.ydata # get event y location
    if event.button == 'up':
        # deal with zoom in
        scale_factor = 1./base_scale
    elif event.button == 'down':
        # deal with zoom out
        scale_factor = base_scale
    else:
        # deal with something that should never ha
        scale_factor = 1.
        print event.button
    # set new limits
    display_settings.xlim = [xdata - cur_xrange*scale_factor,
                 xdata + cur_xrange*scale_factor]
    display_settings.ylim = [ydata - cur_yrange*scale_factor,
                 ydata + cur_yrange*scale_factor]
    display_settings.zoomed = True
    ax.set_xlim(display_settings.xlim)
    ax.set_ylim(display_settings.ylim)
    cur_xlim = ax.get_xlim()
    cur_ylim = ax.get_ylim()
    print "After", cur_xlim, cur_ylim
    update_canvas()
    
def onclick(event):
    try:
        if (event.button == 3):
            global display_settings, plane_data
            if display_settings.view == 0:
                display_settings.pos[2] = display_settings.plane
                display_settings.pos[0], display_settings.pos[1] = plane_data.get_indices(event.xdata, event.ydata)
                display_settings.pos[0] += 1
                display_settings.pos[1] += 1
            elif display_settings.view == 1:
                display_settings.pos[1] = display_settings.plane
                display_settings.pos[0], display_settings.pos[2] = plane_data.get_indices(event.xdata, event.ydata)
                display_settings.pos[0] += 1
                display_settings.pos[2] += 1
            elif display_settings.view == 2:
                display_settings.pos[0] = display_settings.plane
                display_settings.pos[1], display_settings.pos[2] = plane_data.get_indices(event.xdata, event.ydata)
                display_settings.pos[1] += 1
                display_settings.pos[2] += 1
            directory_info.plot = True
            print "reading data"
    except:
        print 'outside of plot'
## ------------------------------------
def resize_canvas(event=None):
    global display
    plt.rcParams['figure.figsize'] = display.winfo_width() / 72, display.winfo_height() / 72
    plt.gcf().canvas.draw()
    root.update()
## ------------------------------------
def format_coord(x, y):
    global plane_data
    try:
        i, j = plane_data.get_indices(x, y)
        ni = i
        nj = j
        z = plane_data.data[j][i]
        m = plane_data.geo[j][i]
        if plane_data.geo[j][i] < 0:
            l = int(-1*plane_data.geo[j][i])
            for g in plane_data.sub[l].geo:
                print g
            ni, nj = plane_data.sub[l].get_indices(x, y)
            z = plane_data.sub[l].data[nj][ni]
            m = plane_data.sub[l].geo[nj][ni]
            ni = int( float(ni) / float(plane_data.sub[l].nx) ) + float(i)
            nj = int( float(nj) / float(plane_data.sub[l].ny) ) + float(j)
    except:
        pass
        z = 0.
        i = 0.
        j = 0.
        m = 0
    return 'Material = %2i; (x,y) = %+1.4f, %+1.4f; (i,j) = %+1.2f, %+1.2f; z=%+1.4e'%(m, x, y, ni+1, nj+1, z)
##    else:
##        return 'x=%1.4f, y=%1.4f'%(x, y)



## ====================================
## Initializing Function
## ====================================
def main():

    ## ====================================
    ## Create Locks
    global plane_data_lock, data_view_lock, display_settings_lock, directory_info_lock
    global plane_data_main, data_view_main, display_settings_main, directory_info_main
    plane_data_lock = threading.Lock()
    data_view_lock  = threading.Lock()
    display_settings_lock = threading.Lock()
    directory_info_lock   = threading.Lock()
    plane_data_main = False
    data_view_main = False
    display_settings_main = False
    directory_info_main = False
    ## ====================================


    ## ====================================
    ## Create Global Classes
    ## ------------------------------------
    global plane_data, data_view, display_settings, directory_info
    ## Creat Fake Data
    ##start_data = np.loadtxt('prb.xs')
    ##start_data = np.loadtxt("core1.dat")
    start_data = np.loadtxt("fission.dat")
    ##start_data = np.loadtxt("obama.dat")
    start_data = start_data[::-1]
    start_dimensions = [ -1.,1., -1.*float(len(start_data))/float(len(start_data[0])),float(len(start_data))/float(len(start_data[0])) ]
    start_geo = []
    start_xplanes = []
    start_yplanes = []
    for j in range(0, len(start_data)):
        start_yplanes.append( start_dimensions[0] + (j*(start_dimensions[1]-start_dimensions[0]) ) )
    for i in range(0, len(start_data[0])):
        start_xplanes.append( start_dimensions[2] + (i*(start_dimensions[3]-start_dimensions[2]) ) )
    for j in range(0, len(start_data)):
        start_geo.append([])
        for i in range(0, len(start_data[0])):
            start_geo[-1].append(0)
    start_geo = np.array(start_geo)
    ## ------------------------------------
    plane_data = plane_data_class(start_data, start_geo, start_xplanes, start_yplanes)
    data_view  = data_view_class()
    display_settings = display_settings_class()
    plane_data.get_geo()
    directory_info   = directory_info_class()
    ## ====================================


    ## ====================================
    ## Create Threads
    # -- fileIO
    fileIO_thread = fileIO_thread_class()
    fileIO_thread.start()
    # -- search
    search_thread = search_thread_class()
    search_thread.start()
    ## ====================================


    ## ====================================
    ## ------------------------------------
    time.sleep(1)
    ## Organize tkinter Areas on Screen
    root.title("myPlotter")
    root.minsize(300,300)
    root.geometry("800x600")
    ## ------------------------------------
    ## Menu Bar
    menu_bar = Menu(root)
    # -- File Menu
    file_menu = Menu(menu_bar, tearoff=1)
    file_menu.add_command(label="Save",command=lambda:root.event_generate("<<save_image>>"))
    file_menu.add_command(label="Export Plane to dat",command=lambda:root.event_generate("<<save_plane>>"))
    file_menu.add_command(label="Export Plane to xls",command=lambda:root.event_generate("<<save_excel_plane>>"))
    file_menu.add_command(label="Exit", command=root.quit)
    menu_bar.add_cascade(label="File",menu=file_menu)
    # -- View Menu
    edit_menu = Menu(menu_bar, tearoff=0)
    edit_menu.add_command(label="Lock",command=lambda:plane_data_lock.acquire())
    edit_menu.add_command(label="Unlock", command=lambda:root.event_generate("<<redraw>>") )
    menu_bar.add_cascade(label="View",menu=edit_menu)
    ## ------------------------------------
    root.config(menu=menu_bar)
    ## ------------------------------------
    global scales
    scales = custom_cmaps_class()
    ## ------------------------------------
    ## Main View (SWITCHED TO TABS...)
    global display
    display = ttk.Notebook(root)
    display.pack(fill=BOTH)
    # -- Display Image
    
    # -- new tab
    display_wrapper = Frame(display)
    display.add(display_wrapper, text="file_1")
    # -- new file pane
    new_file = PanedWindow(display_wrapper, orient=HORIZONTAL, sashwidth=4, bg="#888888", opaqueresize=FALSE)
    new_file.pack(fill=BOTH, expand=1)
    
    # -- SSH pane
    root.ssh_view = ssh_bar_class(new_file)
    
    ##new_file.add(root.ssh_view)
    root.ssh_view.explorer = tree_explorer(root.ssh_view)
    # -- matplotlib canvas
    middle = Frame(new_file)
    new_file.add( middle, stretch="middle" )
    canvas = FigureCanvasTkAgg(fig, master=middle)
    toolbar = NavigationToolbar2TkAgg(canvas,middle)
    canvas.get_tk_widget().pack(anchor=CENTER)
    toolbar.pack()
    
    # -- Navigate pane
    navigation_bar = navigate_bar_class(new_file)
    
    # -- new file button
    display_add = Frame(display)
    display.add(display_add, text="+")
    ## ------------------------------------
    ## ====================================


    ## ====================================
    ## Start TKINTER Lock Checker Loop
    update_canvas()
    root.after(1000, tk_lock_check)
    ## ====================================


    ## ====================================
    ## Define Resize Event
    ##root.bind( "<Configure>", resize_canvas )
    root.bind("<<redraw>>", update_canvas)
    root.bind("<<save_image>>", save_image)
    root.bind("<<save_plane>>", save_plane)
    root.bind_all('<Alt-s>',save_image)
    root.bind("<<newfile>>", navigation_bar.update)
    root.bind("<Control-c>", save_image)
    ## ====================================


    
    ## ====================================
    ## Start TKINTER
    root.mainloop()
## ====================================
    

main()