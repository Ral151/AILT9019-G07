"""Regenerate the "tricky" (derived) eval photos from the clear photos.

The clear item photos come from Wikimedia Commons (see IMAGE_CREDITS.md).
This script derives the intentionally-hard cases from them:

    di-005  blurry bottle        <- di-001 (Gaussian blur)
    di-006  can + bottle         <- di-002 + di-001 (side-by-side)
    ti-011  blurry bottle        <- ti-001 (Gaussian blur)
    ti-012  very dark can        <- ti-002 (brightness reduced)
    ti-014  bottle + can + paper <- ti-001 + ti-002 + ti-003 (2x2 grid)
    ti-015  battery + bottle     <- di-003 + ti-001 (side-by-side)

Usage:
    python eval/make_derived_photos.py
"""

from PIL import Image, ImageFilter, ImageEnhance
import os

DEV = os.path.join('eval', 'cases', 'dev', 'images')
TEST = os.path.join('eval', 'cases', 'test', 'images')

WHITE = (255, 255, 255)


def load(path):
    return Image.open(path).convert('RGB')


def save(img, path):
    img.save(path, 'JPEG', quality=88)
    print(f'  {path}  {img.size[0]}x{img.size[1]}')


def blur(img, radius):
    return img.filter(ImageFilter.GaussianBlur(radius))


def darken(img, factor):
    return ImageEnhance.Brightness(img).enhance(factor)


def side_by_side(imgs, height=1024):
    """Scale each image to the same height and paste them horizontally."""
    resized = [im.resize((int(im.size[0] * height / im.size[1]), height)) for im in imgs]
    canvas = Image.new('RGB', (sum(im.size[0] for im in resized), height), WHITE)
    x = 0
    for im in resized:
        canvas.paste(im, (x, 0))
        x += im.size[0]
    return canvas


def grid2x2(imgs, cell=512):
    """Place up to 4 images in a 2x2 grid (missing cells stay white)."""
    canvas = Image.new('RGB', (cell * 2, cell * 2), WHITE)
    positions = [(0, 0), (cell, 0), (0, cell), (cell, cell)]
    for im, pos in zip(imgs, positions):
        im = im.copy()
        im.thumbnail((cell, cell))
        w, h = im.size
        canvas.paste(im, (pos[0] + (cell - w) // 2, pos[1] + (cell - h) // 2))
    return canvas


if __name__ == '__main__':
    bottle_dev = load(os.path.join(DEV, 'di-001.jpg'))
    can_dev = load(os.path.join(DEV, 'di-002.jpg'))
    battery = load(os.path.join(DEV, 'di-003.jpg'))
    bottle_test = load(os.path.join(TEST, 'ti-001.jpg'))
    can_test = load(os.path.join(TEST, 'ti-002.jpg'))
    paper = load(os.path.join(TEST, 'ti-003.jpg'))

    save(blur(bottle_dev, 18), os.path.join(DEV, 'di-005.jpg'))
    save(side_by_side([can_dev, bottle_dev]), os.path.join(DEV, 'di-006.jpg'))

    save(blur(bottle_test, 14), os.path.join(TEST, 'ti-011.jpg'))
    save(darken(can_test, 0.15), os.path.join(TEST, 'ti-012.jpg'))
    save(grid2x2([bottle_test, can_test, paper]), os.path.join(TEST, 'ti-014.jpg'))
    save(side_by_side([battery, bottle_test]), os.path.join(TEST, 'ti-015.jpg'))

    print('DONE')
