from torchvision import transforms

# Basic preprocessing transform: resize to 640x640 and convert to tensor
basic_transform = transforms.Compose([
    transforms.Resize((640, 640)),
    transforms.ToTensor()
])

# Add more augmentation pipelines here if needed
