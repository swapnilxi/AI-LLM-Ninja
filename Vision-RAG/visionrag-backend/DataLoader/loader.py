from torch.utils.data import DataLoader
from .dataset import YOLODataset
from .transforms import basic_transform
from .utils import collate_fn
import os

DATASET_BASE = os.path.join("room_dataset")
# Define some sensible defaults (relative to project root)
DEFAULT_IMG_DIR = os.path.join(DATASET_BASE, "train")
DEFAULT_LABEL_DIR = os.path.join(DATASET_BASE, "annotation")  


def get_dataloader(img_dir: str = None,
                   label_dir: str = None,
                   batch_size: int = 4,
                   shuffle: bool = True,
                   num_workers: int = 2):
    """
    Returns a DataLoader. If no img_dir/label_dir are passed,
    defaults to ./data/images/train and ./data/labels/train
    """
    img_dir = img_dir or DEFAULT_IMG_DIR
    label_dir = label_dir or DEFAULT_LABEL_DIR

    # check if paths exist, else raise a clear error
    if not os.path.exists(img_dir):
        raise FileNotFoundError(f"Image directory not found: {img_dir}")
    if not os.path.exists(label_dir):
        raise FileNotFoundError(f"Label directory not found: {label_dir}")

    dataset = YOLODataset(img_dir, label_dir, transform=basic_transform)
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        collate_fn=collate_fn
    )
    return loader
