
import os
import sys
import math

import cv2
import numpy as np

def haar_wavelet_transform(im):
    haar_v1 = lambda im: (im[:, ::2] + im[:, 1::2]) / math.sqrt(2.)
    haar_v2 = lambda im: (im[:, ::2] - im[:, 1::2]) / math.sqrt(2.)
    haar_h1 = lambda im: haar_v1(im.transpose()).transpose()
    haar_h2 = lambda im: haar_v2(im.transpose()).transpose()

    return [
        haar_h1(haar_v1(im)),
        haar_h1(haar_v2(im)),
        haar_h2(haar_v1(im)),
        haar_h2(haar_v2(im)),
    ]

def get_blurness(im, threshold=35., min_zero=.05):
    '''
    "Blur detection for digital images using wavelet transform"
    Hanghang Tong, 2004
    '''
    THRESHOLD = threshold
    MIN_ZERO = min_zero

    im = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    im_haar = im.copy()

    emax_list = []
    for i in range(3):
        w = im.shape[1] / (2 ** (i+1))
        h = im.shape[0] / (2 ** (i+1))

        haar = [_ for _ in haar_wavelet_transform(im_haar[:h*2, :w*2])]
        im_haar[:h*2, :w*2] = np.vstack([np.hstack([haar[0], haar[1]]), np.hstack([haar[2], haar[3]])])

        im_hl = im_haar[h:2*h, :w]
        im_lh = im_haar[:h, w:2*w]
        im_hh = im_haar[h:2*h, w:2*w]
        im_map = np.sqrt(im_lh ** 2 + im_hl ** 2 + im_hh ** 2)

        wsize = 2 ** (3 - i)
        emax = np.zeros((h / wsize, w / wsize)).astype(np.float32)
        for x in range(0, w / wsize):
            for y in range(0, h/ wsize):
                yy = y * wsize
                xx = x * wsize
                emax[y, x] = im_map[yy:yy+wsize, xx:xx+wsize].max()
        emax_list.append(emax)

    thr = THRESHOLD
    n_edge = 0
    n_dirac_astep = 0
    n_roof_gstep = 0
    n_blurred_roof_gstep = 0
    h, w = emax_list[0].shape
    for x in range(w):
        for y in range(h):
            e1 = emax_list[0][y,x]
            e2 = emax_list[1][y,x]
            e3 = emax_list[2][y,x]
            if e1 > thr or e2 > thr or e3 > thr:
                n_edge += 1
                if e3 < e2 and e2 < e1:
                    # dirac or astep
                    n_dirac_astep += 1
                    pass
                elif (e1 < e2 and e2 < e3) or (e1 < e2 and e3 < e2):
                    # in the above condition,
                    # term 1 = True => roof or gstep
                    # term 2 = True => roof
                    n_roof_gstep += 1
                    if e1 < thr:
                        # blurred
                        n_blurred_roof_gstep += 1
                    pass

    per = float(n_dirac_astep) / n_edge
    blurness = float(n_blurred_roof_gstep) / n_roof_gstep
    return (per, blurness)
