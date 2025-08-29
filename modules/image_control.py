import math
from PIL import Image, ImageEnhance
import PIL

def resizeImage(path, width=640, height=480, rotation=90):
    print('resize')
    importedImage = Image.open(path)
    w, h = importedImage.size
    gcd = math.gcd(w, h)
    wratio = w/gcd
    hratio = h/gcd
    wMax = width/wratio
    hMax = height/hratio
    mult = min(wMax, hMax)
    newWidth = math.ceil(wratio*mult)
    newHeight = math.ceil(hratio*mult)
    im = importedImage.resize((newWidth, newHeight))
    im = im.rotate(rotation, PIL.Image.NEAREST, expand=1)
    return im


def convertJpgToBmp(path, width=532, height=399, rotation=90):
    print('convert to bmp')
    resizedImage = resizeImage(path, width, height, rotation)
    enhancer = ImageEnhance.Brightness(resizedImage)
    im = enhancer.enhance(1.5)
    #im = im.convert('1')
    output_path = path.rsplit('.', 1)[0] + '.bmp'
    im.save(output_path)
    return im

def combineImages(imagePaths):
    pbWidth = 400
    pbHeight = 300
    bufferSpace = 10
    processed_images = []
    
    for path in imagePaths:
        # convert to bmp and resize
        img = convertJpgToBmp(path, width=pbWidth, height=pbHeight, rotation=0)
        processed_images.append(img)

    # calculate total height for all images
    pics_count = len(processed_images)
    total_width = pbWidth
    total_height = (pbHeight * pics_count) + ( (pics_count+1) * bufferSpace)

    # create new image with white background
    combined_image = Image.new('RGB', (total_width, total_height), 'white')

    # paste each image vertically
    for index, image in enumerate(processed_images):
        y_position = index * (pbHeight + bufferSpace)
        combined_image.paste(image, (0, y_position+bufferSpace))

    # save the combined image as bmp
    output_path = '/home/pi/Desktop/picamera/pics/combined_photos.bmp'
    combined_image.save(output_path)

    return combined_image


def convertImg():
    updated = resizeImage("/home/pi/Desktop/picamera/pics/combined_photos2.bmp", 400, 1400,0)
    updated.save('/home/pi/Desktop/picamera/pics/test.bmp')
    
