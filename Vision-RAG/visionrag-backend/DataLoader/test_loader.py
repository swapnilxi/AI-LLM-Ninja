from loader import get_dataloader

if __name__ == "__main__":
    # 🔹 This is where you define the actual folders
    img_dir = "data/images/train"
    label_dir = "data/labels/train"

    loader = get_dataloader(img_dir, label_dir, batch_size=8)

    for imgs, targets in loader:
        print("Batch size:", len(imgs))
        print("First target:", targets[0])
        break
