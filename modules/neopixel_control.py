import time

# 0 = R
# 1 = G
# 2 = B
# 3 = X
def setLED(pixels, color):
    pixels[0] = color
    pixels.show()
    return True

def flashLED(pixels, c, flashes = 5):
    for i in range(flashes):
        setLED(pixels,OFF)
        time.sleep(0.2)
        setLED(pixels,c)
        time.sleep(0.2)

def setRing(pixels, color):
    for i in range(16):
        pixels[i+1] = color
    pixels.show()

def flashRing(pixels, c, flashes = 5):
    global OFF
    for i in range(flashes):
        setRing(pixels, OFF)
        time.sleep(0.2)
        setRing(pixels, c)
        time.sleep(0.2)

def fineControlRing(pixels, colors):
    for i in range(len(colors)):
        pixels[i+1] = colors[i]
    pixels.show()
