import torch
from torch.utils.data import Dataset
from PIL import Image
import os

class YOLODataset(Dataset):
    """
    Custom dataset for YOLO-style labeled data.
    Expects:
    - Images in img_dir
    - Label files (YOLO .txt) in label_dir
    """
    def __init__(self, img_dir, label_dir, transform=None):
        self.img_dir = img_dir
        self.label_dir = label_dir
        self.transform = transform
        self.img_files = [f for f in os.listdir(img_dir) if f.endswith((".jpg", ".png"))]

    def __len__(self):
        return len(self.img_files)

    def __getitem__(self, idx):
        img_path = os.path.join(self.img_dir, self.img_files[idx])
        img = Image.open(img_path).convert("RGB")

        # read labels
        label_path = os.path.join(
            self.label_dir,
            os.path.splitext(self.img_files[idx])[0] + ".txt"
        )
        boxes = []
        if os.path.exists(label_path):
            with open(label_path) as f:
                for line in f.readlines():
                    cls, x, y, w, h = map(float, line.strip().split())
                    boxes.append([cls, x, y, w, h])
        boxes = torch.tensor(boxes)

        if self.transform:
            img = self.transform(img)

        return img, boxes
