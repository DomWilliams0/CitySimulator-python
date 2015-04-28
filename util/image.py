import os
import sys

from PIL import Image


class Transparenciser:
    def __init__(self, filename, pixel_func):
        filename = os.path.join(os.getcwd(), filename)

        self.im = Image.open(filename)
        self.size = self.im.size
        count = 0

        if len(self.im.getpixel((0, 0))) != 4:
            new = Image.new("RGBA", self.im.size, (255, 255, 255, 255))
            new.paste(self.im)
            self.im = new

        for x in xrange(self.size[0]):
            for y in xrange(self.size[1]):
                pos = (x, y)
                p = self.im.getpixel(pos)
                modified = pixel_func(self, p, pos)

                if modified != p:
                    count += 1
                    self.im.putpixel(pos, modified)

        # move old file
        filepath, ext = os.path.splitext(filename)
        original = "%s_orig%s" % (filepath, ext)

        if os.path.exists(original):
            os.remove(original)
        os.rename(filename, original)
        self.im.save(filename)

        print "Processed %d pixels" % count


def modify_car_windows(image, pixel, pixel_pos):
    if 150 < pixel[2] < 255:
        # differentiate between front and back windows
        if 32 <= pixel_pos[1] <= image.size[1] - 32:
            alpha = 170
        else:
            alpha = 220
    else:
        alpha = pixel[3]

    return combine(pixel, alpha)


def remove_solid_white(image, pixel, pixel_pos):
    alpha = pixel[3]
    if pixel[:3] == (255, 255, 255):
        alpha = 0

    return combine(pixel, alpha)


def combine(rgb, alpha):
    return rgb[:3] + (alpha,)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise StandardError("Usage: image.py [png file]")

    filearg = sys.argv[1]
    Transparenciser(filearg, remove_solid_white)

