import os
import sys
sys.path.append('..')

from dotenv import load_dotenv
load_dotenv()

from RAG_Module.embed import caption_image  # uses your existing function

def main():
    # change this path if your saved crop is different
    crop_path = "runs/crops/0_couch.jpg"
    if not os.path.exists(crop_path):
        raise FileNotFoundError(f"Crop not found: {crop_path}")

    # Load image bytes
    with open(crop_path, "rb") as f:
        img_bytes = f.read()
    
    # Generate caption using Gemini
    caption = caption_image(img_bytes)

    print("📝 Caption:", caption)

if __name__ == "__main__":
    main()
