
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

def get_blurness(im, threshold=35. / 255, min_zero=.05):
    '''
    "Blur detection for digital images using wavelet transform"
    Hanghang Tong, 2004
    '''
    THRESHOLD = threshold
    MIN_ZERO = min_zero

    if len(im.shape) == 3 and im.shape[2] == 3:
        im = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    if im.dtype == np.uint8:
        im = im.astype(np.float) / 255.
    im_haar = im.copy()

    emax_list = []
    for i in range(4):
        w = im.shape[1] / (2 ** (i+1))
        h = im.shape[0] / (2 ** (i+1))

        haar = [_ for _ in haar_wavelet_transform(im_haar[:h*2, :w*2])]
        im_haar[:h*2, :w*2] = np.vstack([np.hstack([haar[0], haar[1]]), np.hstack([haar[2], haar[3]])])

        im_hl = im_haar[h:2*h, :w]
        im_lh = im_haar[:h, w:2*w]
        im_hh = im_haar[h:2*h, w:2*w]
        im_map = np.sqrt(im_lh ** 2 + im_hl ** 2 + im_hh ** 2)

        #im_c = cv2.applyColorMap(cv2.cvtColor(im_map, cv2.COLOR_GRAY2BGR), cv2.COLORMAP_OCEAN)
        #cv2.imshow(None, im_c)
        #ret = cv2.waitKey()

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

    per      = 0 if n_edge == 0 else float(n_dirac_astep) / n_edge
    blurness = 0 if n_roof_gstep == 0 else float(n_blurred_roof_gstep) / n_roof_gstep
    return (per, blurness)

def run_corner(im):
    im = im.copy()
    im_gray = cv2.cvtColor(im, cv2.cv.CV_BGR2GRAY)
    corner = cv2.cornerHarris(im_gray, 2, 5, 0.04)
    #cv2.imshow(None, im)
    #cv2.waitKey()

    ys, xs = np.where(corner > 0.05)
    for x, y in zip(xs, ys):
        cv2.circle(im, (x, y), radius=10, color=(0, 0, 1))
    cv2.imshow(None, im)
    cv2.waitKey()

def main(args):
    while len(args) > 0:
        image_path = args.pop(0)
        im = cv2.imread(image_path)
        assert im is not None

        scale = 1024. / im.shape[1]
        im = cv2.resize(im, None, fx=scale, fy=scale)
        im = im.astype(np.float32) / 255.

        run_corner(im)
        blur = get_blurness(im, threshold = 10 / 255.)
        print(blur[1])

        #cv2.imshow(None, im)
        #ret = cv2.waitKey()
        #if ret == 113:
        #    return

if __name__ == '__main__':
    import pdb
    import traceback
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        pass
    except:
        traceback.print_exc()
        pdb.post_mortem()
