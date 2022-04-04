# tinyssb/dbg.py

import sys
import time

def get_ms():
    if sys.platform == 'LoPy4':
        return str(time.ticks_ms() + 1000)[-3:]
    return str(time.time()).split('.')[1][:3]

TERM_GREEN    = "\x1b[92m"
TERM_GRAY     = "\x1b[37m"
TERM_MAGENTA  = "\x1b[95m"
TERM_RED      = "\x1b[91m"
TERM_BLUE     = "\x1b[94m"
TERM_YELLOW   = "\x1b[93m"
TERM_NORM     = "\x1b[0m"

GRE,GRA,MAG,RED,BLU,YEL = (TERM_GREEN, TERM_GRAY, TERM_MAGENTA,
                           TERM_RED, TERM_BLUE, TERM_YELLOW)

def dbg(col, *args):
    # t = time.time()
    # print(time.strftime('%H:%M:%S.') + str(t).split('.')[1][:3] + ' ', end='')
    t = time.localtime()
    print(('%02d:%02d:%02d.' % t[3:6]) + get_ms() + ' ', end='')
    print(col, end='')
    print(' '.join([str(a) for a in args]), end='')
    print(TERM_NORM)
