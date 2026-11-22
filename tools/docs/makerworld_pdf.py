"""Build the English assembly guide PDF for MakerWorld from Docs/makerworld/assembly-guide.html.

  python tools/docs/makerworld_pdf.py            # -> build/makerworld/BekantX_Assembly_Guide.pdf

Prepares the images from Docs/bilder into build/makerworld/img (renders cropped to their content and flattened on
white, photos scaled, everything as JPEG to keep the PDF small), copies the HTML next to them and prints it with
headless Microsoft Edge (Chromium print engine: CSS paged media, page counters). Needs Pillow and Edge.
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "Docs" / "makerworld" / "assembly-guide.html"
IMG = ROOT / "Docs" / "bilder"
OUT = ROOT / "build" / "makerworld"
PDF = OUT / "BekantX_Assembly_Guide.pdf"
EDGE = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
MAX = 1800  # px, long side

RENDERS = ["enclosure_exploded", "enclosure_back_open", "enclosure_front", "pcb_iso_top", "pcb_iso_bottom",
           "assembly_open", "assembly_exploded", "assembly_closed"]
PHOTOS = ["Bild1", "Bild2", "Bild3", "Bild4"]
# landscape crops of the portrait photos (fractions of width/height: left, top, right, bottom)
WIDE = {"Bild1": (0.08, 0.22, 0.93, 0.70), "Bild3": (0.08, 0.22, 0.92, 0.69)}


def flatten(im):
    """RGBA -> RGB on white, cropped to the visible content with a small margin."""
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        im = bg
    im = im.convert("RGB")
    diff = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).convert("L")
    box = diff.point(lambda v: 255 if v > 8 else 0).getbbox()
    if box:
        m = int(0.03 * max(im.size))
        box = (max(box[0] - m, 0), max(box[1] - m, 0), min(box[2] + m, im.width), min(box[3] + m, im.height))
        im = im.crop(box)
    return im


def save(im, name):
    im.thumbnail((MAX, MAX), Image.LANCZOS)
    im.save(OUT / "img" / f"{name}.jpg", quality=86, optimize=True, progressive=True)


def prepare_images():
    (OUT / "img").mkdir(parents=True, exist_ok=True)
    for n in RENDERS:
        save(flatten(Image.open(IMG / f"{n}.png")), n)
    for n in PHOTOS:
        im = Image.open(IMG / f"{n}.jpg").convert("RGB")
        save(im.copy(), n)
        if n in WIDE:
            l, t, r, b = WIDE[n]
            save(im.crop((int(l * im.width), int(t * im.height), int(r * im.width), int(b * im.height))), f"{n}_wide")
    save(Image.open(IMG / "BekantX Controller-Gehäuse-1.png").convert("RGB"), "cover")


def print_pdf():
    shutil.copy(SRC, OUT / "assembly-guide.html")
    PDF.unlink(missing_ok=True)
    prof = OUT / ".edge-profile"   # own profile: does not touch a running Edge
    cmd = [str(EDGE), "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={prof}",
           "--no-pdf-header-footer", "--generate-pdf-document-outline", f"--print-to-pdf={PDF}",
           (OUT / "assembly-guide.html").as_uri()]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    # msedge.exe hands the job to a browser process and returns early: wait until the file is there and stable
    last, t0 = -1, time.time()
    while time.time() - t0 < 90:
        size = PDF.stat().st_size if PDF.exists() else -1
        if size > 0 and size == last:
            break
        last = size
        time.sleep(1.5)
    else:
        raise SystemExit("Edge did not write the PDF")
    print(f"{PDF} ({PDF.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    if not EDGE.exists():
        sys.exit(f"Edge not found at {EDGE}")
    prepare_images()
    print_pdf()
