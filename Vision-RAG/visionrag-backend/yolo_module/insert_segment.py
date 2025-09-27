import os, uuid, asyncio
from datetime import datetime
import sys
sys.path.append('..')

from RAG_Module.db import init_pool, close_pool, init_db, insert_image, insert_image_segment
from RAG_Module.embed import embed_text

# ----- CONFIG you may tweak -----
CROP_PATH = "runs/crops/0_couch.jpg"   # your saved crop
ORIG_URI  = "unsplash:photo-1505691938895-1758d7feb511"  # identify the original image
CAPTION   = ("A cream-colored sofa is adorned with two solid dark teal pillows, "
             "two cream pillows with a teal geometric pattern, and one dark teal "
             "textured rectangular pillow, with two distinct teal decorative vases "
             "positioned in the foreground.")

# Minimal YOLO metadata (optional)
BBOX = []            # e.g., [x1, y1, x2, y2] if you have it; keep [] for now
CLS  = "couch"       # if you know it
CONF = 0.90          # if you know it

async def main():
    if not os.path.exists(CROP_PATH):
        raise FileNotFoundError(CROP_PATH)

    # 1) DB ready
    await init_pool()
    await init_db()   # safe to call repeatedly

    # 2) Create an image_id and insert parent image row
    image_id = str(uuid.uuid4())
    # For now we embed the *caption* as the image embedding too (works fine for first pass).
    caption_vec = embed_text(CAPTION)[0].tolist()  # returns list[float] len=768
    await insert_image(
        image_id=image_id,
        uri=ORIG_URI,
        embedding=caption_vec,  # using caption as proxy for image embedding
        meta={"source": "step3.5", "local_crop_path": CROP_PATH, "caption_embedding": caption_vec},
    )

    # 3) Insert the segment row
    meta = {
        "cls": CLS,
        "conf": CONF,
        "crop_path": CROP_PATH,
        "source": "step3.5"
    }
    await insert_image_segment(
        image_id=image_id,
        bbox=BBOX,
        caption=CAPTION,
        embedding=caption_vec,  # same vector for now
        meta={"caption_embedding": caption_vec, **meta}
    )

    print("✅ Inserted one image + one segment.")
    await close_pool()

if __name__ == "__main__":
    asyncio.run(main())
