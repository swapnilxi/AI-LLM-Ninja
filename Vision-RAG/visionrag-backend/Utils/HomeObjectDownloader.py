from ultralytics import YOLO
import torch, os

# download utility
torch.hub.download_url_to_file(
    "https://github.com/ultralytics/assets/releases/download/v0.0.0/homeobjects-3k.zip",
    "homeobjects-3k.zip"
)

# unzip
import zipfile
with zipfile.ZipFile("homeobjects-3k.zip", 'r') as zip_ref:
    zip_ref.extractall("datasets/")
