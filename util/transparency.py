from PIL import Image
import sys
import os

def main():
    if len(sys.argv) != 2:
        raise StandardError("Usage: transparency.py [png file]")
        
    filename = os.path.join(os.getcwd(), sys.argv[1])
    
    im = Image.open(filename)
    size = im.size
    count = 0
    
    
    if len(im.getpixel((0, 0))) != 4:
        new = Image.new("RGBA", im.size, (255, 255, 255, 255))
        new.paste(im)
        im = new
    
    
    for x in xrange(size[0]):
        for y in xrange(size[1]):
            p = im.getpixel((x,y))
            if p[:3] == (255, 255, 255):
                alpha = 0
                count += 1
            else:
                alpha = 255
            im.putpixel((x, y), p[:3] + (alpha, ))
    
    im.save(filename)
    print "Transparencied %d pixels" % count
    
    
    
if __name__ == "__main__":
    main()