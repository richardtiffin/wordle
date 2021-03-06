# Designed and implemented by: Hayk Aleksanyan
# based on the approach by Jonathan Feinberg, see http://static.mrfeinberg.com/bv_ch03.pdf

from PIL import Image, ImageColor, ImageFont, ImageDraw

import math
import random

import timeit   # for calculating running time (TESTING purposes only)
import sys
import os

import fileReader as FR
import spirals as SP
import BBox
import Trees
from Trees import Node, Tree
import colorHandler as CH


# constants:
TOKENS_TO_USE = 400       # number of different tokens to use in the wordle
STAY_AWAY = 2             # force any two words to stay at least this number of pixels away from each other
FONT_SIZE_MIN = 10        # the smallest font of a word
FONT_SIZE_MAX = 300       # the largest font of a word, might go slightly above this value
DESIRED_HW_RATIO = 0.618  # height/widht ratio of the canvas
QUADTREE_MINSIZE = 5      # minimal height-width of the box in quadTree partition
FONT_NAME = "/home/rich/code/visualization/wordle/fonts/arial.ttf"   # the font (true type) used to draw the word shapes


class Token:
    """
        encapsulates the main information on a token into a single class
        Token here represents a word to be placed on canvas for the final wordle Image

        most of the attributes are filled with functions during processing of the tokens
    """

    def __init__(self, word, fontSize = 10, drawAngle = 0):
        self.word = word
        self.fontSize = fontSize      # an integer
        self.drawAngle = drawAngle    # an integer representing the rotation angle of the image; 0 - for NO rotation
        self.imgSize = None           # integers (width, height) size of the image of this word with the given fontSize
        self.quadTree = None          # the quadTree of the image of this word with the above characteristics
        self.place = None             # tuple, the coordinate of the upper-left corner of the token on the final canvas
        self.color = None             # the fill color on canvas (R, G, B) triple


def proposeCanvasSize(normalTokens):
    """
      Given a list of normalized tokens we propose a canvase size (width, height)
      based on the areas covered by words. The areas are determined via leaves of the
      corresponding quadTrees.

      It is assumed that tokens come sorted (DESC), i.e. bigger sized words come first.
      We use this assumption when enforcing the canvas size to be larger
      than total area of the bounding boxes of the first few tokens.
    """

    area = 0         # the area covered by the quadTrees, i.e. the actual shape of the token
    boxArea = []     # the areas covered by the bounding box of the tokens

    for token in normalTokens:
        area += token.quadTree.areaCovered()
        boxArea.append( Trees.rectArea(token.quadTree.root.value) )

    ensure_space = 5    # force the sum of the total area to cover at least the first @ensure_space tokens

    total = area + sum ( boxArea[:ensure_space] )
    w = int( math.sqrt(total/DESIRED_HW_RATIO) ) + 1
    h = int(DESIRED_HW_RATIO*w) + 1

    print('Ratio of the area covered by trees over the total area of bounding boxes of words',  area/sum(boxArea))
    return w, h

def randomFlips(n, p):
    """
     Return an array of length n of random bits {0, 1} where Probability(0) = p and Probability(1) = 1 - p
     this is used for randomly selecting some of the tokens for vertical placement.
    """
    ans = n*[0]
    for i in range(n):
        x = random.random()
        if x > p:
            ans[i] = 1

    return ans


def normalizeWordSize(tokens, freq, N_of_tokens_to_use, horizontalProbability = 1.0):
    """
     (linearly) scale the font sizes of tokens to a new range depending on the ratio of the current min-max
     and take maximum @N_of_tokens_to_use of these tokens
     allow some words to have vertical orientation defined by @horizontalProbability
    """

    words = tokens[:N_of_tokens_to_use]
    sizes = freq[:N_of_tokens_to_use]
    normalTokens = [ ] # the list of Tokens to be returned

    # scale the range of sizes; the scaling rules applied below are fixed from some heuristic considerations
    # the user of this code is welcome to apply their own reasoning

    a, b = min(sizes), max(sizes)
    print( '\nThe ratio of MAX font-size over MIN equals ',  b/a  )
    if a == b:
        sizes = len(sizes)*[30]
    else:
        if b <= 8*a:
            m, M = 15, 1 + int(20*b/a)
        elif b <= 16*a:
            m, M = 14, 1 + int(18*b/a)
        elif b <= 32*a:
            m, M = 13, 1 + int(9*b/a)
        elif b <= 64*a:
            m, M = 11, 1 + int(4.7*b/a)
        else:
            m, M = FONT_SIZE_MIN, FONT_SIZE_MAX

        sizes = [  int(((M - m )/(b - a))*( x - a ) + m )  for x in sizes ]

    print( 'after scaling of fonts min = {}, max = {} '.format( min(sizes), max(sizes) ), '\n'  )

    # allow some vertical placement; the probability is defined by the user
    flips = randomFlips(len( words ), horizontalProbability )
    for i in range(len(sizes)):
        normalTokens.append( Token( words[i], sizes[i], 0 if flips[i] == 0 else 90 ) )

    return normalTokens



def drawWord(token, useColor = False):
    """
      gets an instance of Token class and draws the word it represents
      returns an image of the given word in the given font size
      the image is NOT cropped
    """

    font = ImageFont.truetype(FONT_NAME, token.fontSize)
    w, h = font.getsize(token.word)

    im = Image.new('RGBA', (w,h), color = None)
    draw = ImageDraw.Draw(im)
    if useColor == False:
        draw.text((0, 0), token.word, font = font)
    else:
        draw.text((0, 0), token.word, font = font, fill = token.color)

    if token.drawAngle != 0:
        im = im.rotate( token.drawAngle,  expand = 1)

    return im


def drawOnCanvas(normalTokens, canvas_size):
    """
       given a list of tokens and a canvas size, we put the token images onto the canvas
       the places of each token on this canvas has already been determined during placeWords() call.

       Notice, that it is not required that the @place of each @token is inside the canvas;
       if necessary we may enlarge the canvas size to embrace these missing images
    """

    c_W,c_H = canvas_size        # the suggested canvas size, might change here

    # there can be some positions of words which fell out of the canvas
    # we first need to go through these exceptions (if any) and expand the canvas and (or) shift the coordinate's origin.

    X_min, Y_min = 0, 0

    for i, token in enumerate(normalTokens):
        if token.place == None:
            continue

        if X_min > token.place[0]:  X_min = token.place[0]
        if Y_min > token.place[1]:  Y_min = token.place[1]

    x_shift, y_shift = 0, 0
    if X_min < 0:   x_shift = -X_min
    if Y_min < 0:   y_shift = -Y_min

    X_max , Y_max = 0, 0
    for i, token in enumerate(normalTokens):
        if token.place == None:
            continue

        token.place = ( token.place[0] + x_shift, token.place[1] + y_shift )
        if X_max < token.place[0] + token.imgSize[0]:
            X_max = token.place[0] + token.imgSize[0]
        if Y_max < token.place[1] + token.imgSize[1]:
            Y_max = token.place[1] + token.imgSize[1]

    c_W = max(c_W, X_max)
    c_H = max(c_H, Y_max)

    im_canvas = Image.new('RGBA', (c_W + 10 ,c_H + 10 ), color = None )
    im_canvas_white = Image.new('RGBA', (c_W + 10 ,c_H + 10 ), color = (255,255,255,255) )

    # decide the background color with a coin flip; 0 -for white; 1 - for black (will need brigher colors)
    background = random.randint(0,1)

    dd = ImageDraw.Draw(im_canvas)
    if background == 0: # white
        dd_white = ImageDraw.Draw(im_canvas_white)


    # add color to each word to be placed on canvas, pass on the background info as well
    CH.colorTokens(normalTokens, background)

    for i, token in enumerate(normalTokens):
        if token.place == None:
            print('the word <' + token.word + '> was skipped' )
            continue

        font1 = ImageFont.truetype(FONT_NAME, token.fontSize)
        c = token.color

        if token.drawAngle != 0:
            # place vertically, since PIL does support drawing text in vertical orientation,
            # we first draw the token in a temporary image, the @im, then past that at the location of
            # the token on the canvas; this might introduce some rasterization for smaller fonts
            im = drawWord(token, useColor = True)
            im_canvas.paste(im,  token.place, im )
            if background == 0:
                im_canvas_white.paste(im,  token.place, im )
        else:
            dd.text( token.place, token.word, fill = c,  font = font1 )
            if background == 0:
                dd_white.text( token.place, token.word, fill = c,  font = font1 )


    margin_size = 10 # the border margin size
    box = im_canvas.getbbox()

    if background == 0:
        # white background
        im_canvas_1 = Image.new('RGBA', ( box[2] - box[0] + 2*margin_size, box[3] - box[1] + 2*margin_size ), color = (100,100,100,100)  )
        im_canvas_1.paste( im_canvas_white.crop(box), ( margin_size, margin_size, margin_size + box[2] - box[0], margin_size + box[3] - box[1] ) )
    else:
        # black background
        im_canvas_1 = Image.new('RGB', ( box[2] - box[0] + 2*margin_size, box[3] - box[1] + 2*margin_size ), color = (0,0,0)  )
        im_canvas_1.paste( im_canvas.crop(box), ( margin_size, margin_size, margin_size + box[2] - box[0], margin_size + box[3] - box[1] ) )

    return im_canvas_1



def createQuadTrees(normalTokens):
    """
        given a list of tokens we fill their quadTree attributes and cropped image size
    """

    for i, token in enumerate(normalTokens):
        im_tmp = drawWord(token)
        T = BBox.getQuadTree( im_tmp , QUADTREE_MINSIZE, QUADTREE_MINSIZE )
        T.compress()
        im_tmp = im_tmp.crop(im_tmp.getbbox())

        token.quadTree = T
        token.imgSize = im_tmp.size

def placeWords(normalTokens, plotSize=None):
    """
      gets a list of tokens and their frequencies
      executes the placing strategy and
      returns canvas size, locations of upper-left corner of words and words' sizes
    """

    # 1. we first create the QuadTrees for all words and determine a size for the canvas

    word_img_path = [] # shows the path passed through the spiral before hitting a free space

    print('Number of tokens equals', len(normalTokens), '\n')

    T_start = timeit.default_timer()

    # create the quadTrees and collect sizes (width, height) of the cropped images of the words
    createQuadTrees(normalTokens)

    T_stop = timeit.default_timer()
    print('(i)  QuadTrees have been made for all words in', T_stop - T_start, 'seconds.','\n')

    #2. We now find places for the words on our canvas

    if plotSize == None:
        #c_W, c_H = 4000, 4000
        #c_W, c_H = 2000, 1000
        c_W, c_H = 3000, 1500
        #c_W, c_H = 1000, 500
    else:
        c_W, c_H = plotSize


    print('(ii) Now trying to place the words.\n')
    sys.stdout.flush()

    T_start = timeit.default_timer()

    #3a. we start with the 1st word

    ups_and_downs = [ random.randint(0,20)%2  for i in range( len(normalTokens) )]

    for i, token in enumerate(normalTokens):
        print( token.word , end = ' ' )
        sys.stdout.flush()     # force the output to display what is in the buffer

        a = 0.2                # the parameter of the spiral
        if ups_and_downs[i] == 1:
            # add some randomness to the placing strategy
            a = -a

        # determine a starting position on the canvas of this token, near half of the width of canvas
        w, h =   random.randint( int(0.3*c_W), int(0.7*c_W) ) ,  (c_H >> 1) - (token.imgSize[1] >> 1)
        if w < 0 or w >= c_W:
            w = c_W >> 1
        if h < 0 or h >= c_H:
            h = c_H >> 1


        if ups_and_downs[i] == 0:
            A = SP.Archimedian(a).generator
        else:
            A = SP.Rectangular(2, ups_and_downs[i]).generator

        dx0, dy0 = 0, 0
        place1 = (w, h)

        word_img_path.append( (w,h) )

        last_hit_index = 0 # we cache the index of last hit

        iter_ = 0

        start_countdown = False
        max_iter = 0
        for dx, dy in A:
            w, h = place1[0] + dx, place1[1] + dy

            if start_countdown == True:
                max_iter -= 1
                if max_iter == 0:
                    break
            else:
                iter_ += 1

            if ( w < 0 or w >= c_W or h < 0 or h > c_H ):
                #  the shape has fallen outside the canvas
                if start_countdown == False:
                    start_countdown = True
                    max_iter  = 1 + 10*iter_


            place1 = ( w, h )
            collision = False

            if last_hit_index < i:
                j = last_hit_index
                if normalTokens[j].place != None:
                    collision = BBox.collisionTest( token.quadTree, normalTokens[j].quadTree, place1, normalTokens[j].place, STAY_AWAY)

            if collision == False:
                # NO collision with the cached index
                for j in range( i ): # check for collisions with the rest of the tokens
                    if ((j != last_hit_index) and (normalTokens[j].place != None)):
                        if BBox.collisionTest(token.quadTree, normalTokens[j].quadTree, place1, normalTokens[j].place, STAY_AWAY) == True:
                            collision = True
                            last_hit_index = j

                            break # no need to check with the rest of the tokens, try a new position now

            if collision == False:
                if BBox.insideCanvas( token.quadTree , place1, (c_W, c_H) ) == True:
                    # at this point we have found a place inside the canvas where the current token has NO collision
                    # with the already placed tokens; The search has been completed.
                    token.place = place1
                    break   # breaks the spiral movement
                else:
                    if token.place == None:
                        # even though this place is outside the canvas, it is collision free and we
                        # store it in any case to ensure that the token will be placed
                        token.place = place1



    T_stop = timeit.default_timer()

    print('\n Words have been placed in ' + str( T_stop - T_start ) + ' seconds.\n')

    return c_W, c_H

def createWordle_fromFile(fName, interActive = False, horizontalProbability=1.0):
    # the master function, creates the wordle from a given text file

    tokens = FR.tokenize_file_IntoWords(fName)
    tokens, freq = FR.tokenGroup(tokens)

    print('\n ===== Top', min(10, len(tokens) ),  'most frequent tokens =====\n')

    for i in range(  min(10, len(tokens) ) ):
        s = freq[i]
        print( str(s) +  (7 - len(str(s)))*' ' + ':  ' + tokens[i]  )


    normalTokens =  normalizeWordSize(tokens, freq, TOKENS_TO_USE, horizontalProbability)
    canvas_W, canvas_H = placeWords(normalTokens)

    wordle = drawOnCanvas(normalTokens, (canvas_W, canvas_H ) )
    wordle.save( fName[0:-4] + '_wordle.png')
    print( 'the wordle image was sucessfully saved on the disc as <' + fName[0:-4]  + '_wordle.png >' )

    if interActive == True:
        # we allow the user to repaint the existing tokens with other color schemes as many times as they wish
        print('\n=========== You may repaint the existing wordle with other color schemes =========== \n')
        print('To stop, please type the text inside the quotes: "q" folowed by Enter')
        print('To try a new scheme type any other char\n')

        version = 1
        while True:
            userInput = input(str(version) + '.   waiting for new user input ... ')
            if userInput == 'q':
                print('exiting...')
                break
            wordle = drawOnCanvas(normalTokens, (canvas_W, canvas_H) )
            newFileName = fName[0:-4] + '_wordle_v' + str(version) + '.png'
            wordle.save( newFileName)
            print( '=== saved on the disc as <', newFileName, '>\n')
            version += 1

def paramHelper():
    """prints the parameters necessary for the routine to operate"""

    print('the following are all parameters of this module.\n')

    strMessage = """The text file on which the word-cloud will be generated.
If the file is in the same path as the wordle.py then only file name will suffice, otherwise the full path of the txt file is necessary.\n"""
    print('--fileName= ', strMessage)

    strMessage = """The probability of words to be placed vertically. To force all horizontal placement choose 1.0 or leave this parameter.\n"""
    print('--vertProb=', strMessage)

    strMessage = """The interactive flag, if 1 then the program keeps changing the color scheme until not instructed by the user to exit. The parameter can be skipped, in which case the default value of 0 will be used.\n"""
    print('--interactive=', strMessage)

if __name__ == "__main__":
    # waits for .txt fileName and interactive flag {0, 1} for processing

    argv = sys.argv
    if '--help' in argv:
        paramHelper()
        sys.exit(0)

    interactive = False   # if True, keep repainting the wordle on user's demand
    vertProb = 0          # the probability of placing some words vertically
    fName = ""            # the .txt file on which the wordle will be build

    params = dict()
    for s in argv[1:]:
        s = s.split('=')
        if len(s) != 2 or len(s[0]) <= 2 or s[0][:2] != '--':
            print('paramter {} is in incorrect format, terminating.'.format(s))
            sys.exit(0)
        params[ s[0][2:] ] = s[1] # drop the -- (double hyphen from the beginning of the key)

    print("The paramters are\n", params)

    if not 'fileName' in params:
        print('--fileName parameter is missing, terminating.')
        sys.exit(0)

    fName = params['fileName']
    if os.path.isfile(fName) == False:
        print('the file', fName, 'does not exist, terminating.')
        sys.exit(0)

    if 'interactive' in params:
        if params['interactive'] == '1':
            interactive = True
    if 'vertProb' in params:
        try:
            vertProb = float(params['vertProb'])
            if vertProb > 1: vertProb = 1.0
            if vertProb < 0: vertProb = 0.0
        except:
            vertProb = 0.0


    createWordle_fromFile( fName, interactive, 1 - vertProb )
