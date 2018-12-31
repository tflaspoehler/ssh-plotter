import os

def getFileType(l, ext):
    r = []
    for i in l:
        for j in ext:
            if os.path.splitext(i)[1] == "."+j:
                r.append(i)
    return r

def trimBreak(l):
    for i in range(0,len(l)):
        l[i] = l[i][:-1]
    return l

def hex_to_rgb(value):
    value = value.lstrip('#')
    lv = len(value)
    return tuple(int(value[i:i+lv/3], 16) for i in range(0, lv, lv/3))

def rgb_to_hex(rgb):
    return '#%02x%02x%02x' % rgb


def intMat(mat):
    if isinstance(mat, list):
        mx = []
    else:
        mx = ()
    for i in range(0, len(mat)):
        if isinstance(mat[i], list) or isinstance(mat[i],tuple):
            if isinstance(mat, list):
                mx.append( intMat(mat[i]) )
            else:
                mx = mx + (intMat(mat[i]),)
        else:
            if isinstance(mat, list):
                mx.append(int(mat[i]))
            else:
                mx = mx + (int(mat[i]),)
    return mx

def getMax(mat):
    import numpy as np
    mx = []
    if isinstance(mat,np.ndarray):
        return mat[mat>0].max()
    for i in range(0, len(mat)):
        if isinstance(mat[i], list):
            a = getMax(mat[i])
            if a != None:
                mx.append( a )
        else:
            print mat[i].__class__.__name__
            if (mat[i] > 0.):
               mx.append( mat[i] )
    if len(mx) < 1:
        return None
    else:
        return max(mx)

def getMin(mat):
    import numpy as np
    mx = []
    if isinstance(mat,np.ndarray):
        return mat[mat>0].min()
    for i in range(0, len(mat)):
        if isinstance(mat[i], list):
            a = getMin(mat[i])
            if a != None:
                mx.append( a )
        else:
            print mat[i].__class__.__name__
            if (mat[i] > 0.):
               mx.append( mat[i] )
    if len(mx) < 1:
        return None
    else:
        return min(mx)

def negate(mat):
    mx = []
    for i in range(0, len(mat)):
        if isinstance(mat[i], list):
            mx.append( negate(mat[i]) )
        else:
            if (mat[i] > 0.):
               mx.append( mat[i] )
            else:
                mx.append( 0. )
    return mx



def combine_funcs(*funcs):
    def combined_func(*args, **kwargs):
        for f in funcs:
            f(*args, **kwargs)
    return combined_func
