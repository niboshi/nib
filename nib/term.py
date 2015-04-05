termColorMap = {
    "black":   "0;30",
    "red":     "0;31",
    "green":   "0;32",
    "brown":   "0;33",
    "blue":    "0;34",
    "purple":  "0;35",
    "cyan":    "0;36",
    "lgray":   "0;37",
    "gray":    "1;30",
    "lred":    "1;31",
    "lgreen":  "1;32",
    "yellow":  "1;33",
    "lblue":   "1;34",
    "lpurple": "1;35",
    "lcyan":   "1;36",
    "white":   "1;37",
}




def color(color = None):
    if color == None:
        color = "0"
    elif color in termColorMap:
        color = termColorMap[color]
    return "\033[" + color + "m"

def colorBytes(size, colors = ('lgray', 'green', 'brown', 'red')):
    import sys
    if sys.version_info.major <= 2:
        ints = (int, long)
    else:
        ints = (int,)
    if not isinstance(size, ints):
        raise TypeError('Invalid type: ' + str(type(size)))

    sizestr = ''
    s = size
    ic = 0
    l = 0
    while s > 0:
        c = colors[ic]
        ic = min(ic+1, len(colors)-1)
        if s >= 1000:
            ss = ("%03d" % (s % 1000))
            sizestr = color(c) + ss + sizestr
            l += len(ss)
            s //= 1000
        else:
            ss = str(s % 1000)
            sizestr = color(c) + ss + sizestr
            l += len(ss)
            break
        pass
    sizestr = sizestr + color()
    return (sizestr, l)
