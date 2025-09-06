def collate_fn(batch):
    """
    Custom collate function to handle batches where each image
    can have a variable number of bounding boxes.
    """
    imgs, targets = zip(*batch)
    return list(imgs), list(targets)