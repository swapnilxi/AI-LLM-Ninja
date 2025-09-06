# RUN: uv run python scripts/train_homeobjects.py
import torch
from ultralytics import YOLO
from pathlib import Path

DATA = Path("HomeObjects-Dataset/HomeObjects-3K.yaml")  # <-- adjust if needed
MODEL = "yolo11n.pt"
EPOCHS = 5
IMGSZ = 640

def main():
    model = YOLO(MODEL)
    model.train(
        data=str(DATA),
        epochs=EPOCHS,
        imgsz=IMGSZ,
        batch=8,
        device=0 if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu",
        project="runs/detect",
        name="homeobjects3k",
        exist_ok=True,
    )
    print("Best weights:", Path("runs/detect/homeobjects3k/weights/best.pt").resolve())

if __name__ == "__main__":
    main()
