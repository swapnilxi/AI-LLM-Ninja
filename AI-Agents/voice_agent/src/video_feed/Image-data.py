from transformers import BlipProcessor, BlipForConditionalGeneration
import torch
from PIL import Image
import cv2

processor = BlipProcessor.from_pretrained("Salesforce/blip2-flan-t5-xl")
model = BlipForConditionalGeneration.from_pretrained(
    "Salesforce/blip2-flan-t5-xl",
    device_map="auto",
    torch_dtype=torch.float16
)

image = Image.open('frame.jpg')
inputs = processor(image, return_tensors="pt").to('cuda')

generated_ids = model.generate(**inputs, max_new_tokens=50)
caption = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

print(f"Caption: {caption}")

"""
frame_pil = Image.fromarray(cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB))
inputs = processor(frame_pil, "", return_tensors="pt").to(blip_model.device)  # empty prompt for caption
out = blip_model.generate(**inputs)
caption = processor.decode(out[0], skip_special_tokens=True).strip()
print("Vision Caption:", caption)
"""