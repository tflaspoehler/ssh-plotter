from PIL import Image, ImageDraw
def hex_to_rgb(value):
    value = value.lstrip('#')
    lv = len(value)
    return tuple(int(value[i:i+lv/3], 16) for i in range(0, lv, lv/3))

def rgb_to_hex(rgb):
    return '#%02x%02x%02x' % rgb

def getColor(bounds, scale, value):
    width = bounds[1] - bounds[0]
    color = [0,0,0]
    for i in range(0, len(scale)-1):
        if (value - bounds[0])<=width*scale[i+1][1]:
            for j in range(0,3):
                color[j] = (value-(bounds[0]+ (scale[i][1])*width)) / (width*(scale[i+1][1] - scale[i][1]))
                if (scale[i][0][j] < scale[i+1][0][j]):
                    color[j] = scale[i][0][j] + (abs(scale[i][0][j] - scale[i+1][0][j]) * color[j])
                elif (scale[i][0][j] > scale[i+1][0][j]):
                    color[j] = scale[i][0][j] - (abs(scale[i][0][j] - scale[i+1][0][j]) * color[j])
                else:
                    color[j] = scale[i][0][j]
            return rgb_to_hex((color[0],color[1],color[2]))

def getInd(bounds, scale, value, rnd):
    width = bounds[1] - bounds[0]
    color = [0,0,0]
    rounders = []
    n = 12
    for j in range(0,n+1):
        rounders.append([getColor([0.,float(n)],scale,float(j),0),float(j)/float(n)])
    for i in range(0, len(rounders)-1):
        #print (value - bounds[0])/width,rounders[i+1][1]
        if (value - bounds[0])/width<=rounders[i+1][1]:
            return i+1
    return len(rounders)


def getRound(bounds, value, n):
    width = bounds[1] - bounds[0]
    for i in range(0, n):
        if (value - bounds[0])/width<=(i+1.)*(1./(n-1.)):
            return i+1
    return len(rounders)

def oldGetColor(bounds, scale, value, rnd):
    width = bounds[1] - bounds[0]
    color = [0,0,0]
    if (rnd==1):
        rounders = []
        n = 12
        for j in range(0,n+1):
            rounders.append([getColor([0.,float(n)],scale,float(j),0),float(j)/float(n)])
        for i in range(0, len(rounders)-1):
            if (value - bounds[0])/width<=rounders[i+1][1]:
                return rounders[i+1][0]
        return (scale[-1][0][0],scale[-1][0][1],scale[-1][0][0])
    else:
        for i in range(0, len(scale)-1):
            if (value - bounds[0])<=width*scale[i+1][1]:
                for j in range(0,3):
                    color[j] = (value-(bounds[0]+ (scale[i][1])*width)) / (width*(scale[i+1][1] - scale[i][1]))
                    if (scale[i][0][j] < scale[i+1][0][j]):
                        color[j] = scale[i][0][j] + (abs(scale[i][0][j] - scale[i+1][0][j]) * color[j])
                    elif (scale[i][0][j] > scale[i+1][0][j]):
                        color[j] = scale[i][0][j] - (abs(scale[i][0][j] - scale[i+1][0][j]) * color[j])
                    else:
                        color[j] = scale[i][0][j]
                return (color[0],color[1],color[2])

def getScale(bounds,scale,height,width,rnd,rot=0):
    plane = Image.new("RGB",(width,height), (0,0,0))
    draw = ImageDraw.Draw(plane)
    if (rot==0):
        for j in range(0,height):
            color = oldGetColor(bounds,scale,bounds[0]+((height-j)*(bounds[1]-bounds[0])/height),rnd)
            color = tuple(int(x) for x in color)
            draw.line([0,j,int(width),j],fill=color)
    else:
        for j in range(0,width):
            color = oldGetColor(bounds,scale,bounds[0]+((width-j)*(bounds[1]-bounds[0])/width),rnd)
            color = tuple(int(x) for x in color)
            draw.line([j,0,j,int(height)],fill=color)
    return plane
