# Create a wordle in plotly
# 

from wordle import normalizeWordSize, placeWords, TOKENS_TO_USE

def drawOnPlotly(normalTokens, canvas_size):
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

    print(normalTokens[0].word)
    print(normalTokens[0].fontSize)
    print(normalTokens[0].color)

    x = [i.place[0] for i in normalTokens]
    y = [i.place[1] for i in normalTokens]
    colors = [f'rgb{i.color}' for i in normalTokens]
    sizes = [i.fontSize for i in normalTokens]
    text = [i.word for i in normalTokens]
    cloud = go.Scatter(x=x,
                 y=y,
                 mode='text',
                 text=text,
                 marker={'opacity': 0.3},
                 textfont={'size': sizes,
                           'color': colors})
    return cloud

def createPlotlyWordle(list, plotSize, interActive = False, horizontalProbability=1.0):
    # the master function, creates the wordle from a given text file

    tokens = FR.tokenize_list_IntoWords(list)
    tokens, freq = FR.tokenGroup(tokens)

    print('\n ===== Top', min(10, len(tokens) ),  'most frequent tokens =====\n')

    for i in range(  min(10, len(tokens) ) ):
        s = freq[i]
        print( str(s) +  (7 - len(str(s)))*' ' + ':  ' + tokens[i]  )


    normalTokens =  normalizeWordSize(tokens, freq, TOKENS_TO_USE, horizontalProbability)
    c_W, c_H = placeWords(normalTokens, plotSize)
    CH.colorTokens(normalTokens)
    wordle = drawOnPlotly(normalTokens, (c_W, c_H))
    return wordle
    