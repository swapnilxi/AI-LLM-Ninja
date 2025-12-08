# RAG Client Integration Guide

## Overview

The RAG (Retrieval-Augmented Generation) client provides seamless integration between the Vision-RAG database system and hand gesture recognition. You can now:

1. **Search the database** for images by text query
2. **Retrieve image metadata** (name, path, ID)
3. **Load and display** images as interactive thumbnails
4. **Control with hand gestures** - pinch to grab, drag to move, release to drop

---

## Architecture

### Files

1. **`rag_client.py`** – Core RAG client module
   - `RAGImageRetriever`: Database search and image loading
   - `InteractiveImageGallery`: Hand-controlled gallery interface

2. **`handTracking_rag_integrated.py`** – Example integration
   - `RAGIntegratedHandTracking`: Complete example application
   - Shows database fetch → display → hand control

### Data Flow

```
User Query
    ↓
Database Search (Gemini embeddings)
    ↓
Image Metadata (name, path, ID)
    ↓
Load Images from Disk
    ↓
Display as Thumbnail Gallery
    ↓
Hand Gesture Detection
    ↓
Pinch → Select
Move → Drag
Release → Drop
```

---

## Usage

### Method 1: Using Interactive Gallery (Easiest)

```python
from GestureDetection.rag_client import InteractiveImageGallery

# Create and run gallery
gallery = InteractiveImageGallery(width=1280, height=720)
gallery.run_interactive_gallery(query="living room furniture", limit=6)
```

**What happens:**
1. Searches database for "living room furniture"
2. Fetches up to 6 images
3. Displays them in a 3-column grid
4. Enables hand gesture control (pinch/drag/drop)

### Method 2: Using RAG Image Retriever (Manual Control)

```python
from GestureDetection.rag_client import RAGImageRetriever

# Initialize retriever
retriever = RAGImageRetriever(use_gemini=True, use_yolo=False)

# Search for images
results = retriever.search_images_by_query("office desk", limit=5)

# Process results
for result in results:
    name = result.get('name')
    path = result.get('path')
    image_id = result.get('id')
    
    # Load image
    image = retriever.load_image_file(path)
    # ... do something with image
```

### Method 3: Full Integration (Recommended)

```bash
cd /Users/swapnil/Documents/Coding/Python/AI-LLM-Ninja/Vision-RAG/visionrag-backend/test_Files

# Run with default query
python handTracking_rag_integrated.py

# Run with custom query
python handTracking_rag_integrated.py --query "bedroom furniture" --limit 6

# Run with custom resolution
python handTracking_rag_integrated.py --query "kitchen items" --width 1920 --height 1080
```

---

## Database Schema

The RAG client expects the database to return results with these fields:

```python
{
    'id': int,           # Unique image ID
    'name': str,         # Image filename
    'path': str,         # Full file path on disk
    'embedding': list,   # Vector embedding (for search)
    'metadata': dict,    # Additional metadata (optional)
    'created_at': str,   # Timestamp (optional)
    # ... other fields
}
```

---

## Hand Gesture Controls

### Pinch Detection

```
Thumb Tip ← → Index Finger Tip
    |           |
    └─ Distance < 50px = PINCH DETECTED
```

### Interaction Sequence

```
1. Move hand over image
   │
   ├─ No action (just hovering)
   │
2. Bring thumb and index together (PINCH)
   │
   ├─ Image is selected (highlighted in yellow)
   ├─ Status changes to "SELECTED"
   │
3. Move hand while pinching
   │
   ├─ Image follows hand in real-time
   ├─ Position updates every frame
   │
4. Release pinch (open hand)
   │
   ├─ Image is deselected
   ├─ Position is locked in place
   ├─ Status changes back to ready
```

---

## API Reference

### RAGImageRetriever

```python
class RAGImageRetriever:
    """Handles database queries and image loading"""
    
    def search_images_by_query(query: str, limit: int) -> List[Dict]:
        """Search by text query using Gemini embeddings"""
        
    def search_images_by_object(query: str, limit: int) -> List[Dict]:
        """Search by object detection using YOLO"""
        
    def get_image_by_id(image_id: int) -> Dict:
        """Get single image by ID"""
        
    def load_image_file(image_path: str) -> np.ndarray:
        """Load image from disk"""
```

### InteractiveImageGallery

```python
class InteractiveImageGallery:
    """Display gallery with hand gesture control"""
    
    def search_and_load_gallery(query: str, limit: int) -> bool:
        """Search database and load images"""
        
    def detect_hand_and_gesture(frame) -> Tuple:
        """Detect hand and classify gesture"""
        
    def render_gallery(frame, index_pos, gesture, pinching) -> ndarray:
        """Draw gallery on frame"""
        
    def run_interactive_gallery(query: str):
        """Main loop with hand gesture control"""
```

### RAGIntegratedHandTracking

```python
class RAGIntegratedHandTracking:
    """Complete integration of RAG + hand tracking"""
    
    def fetch_images_from_database() -> bool:
        """Fetch from database"""
        
    def detect_hand_and_gesture(frame):
        """Detect hand"""
        
    def render_gallery_on_frame(frame, ...) -> ndarray:
        """Render gallery"""
        
    def run():
        """Main execution loop"""
```

---

## Important Code Snippets

### 1. Fetch Images and Get Names

```python
from GestureDetection.rag_client import RAGImageRetriever

retriever = RAGImageRetriever()
results = retriever.search_images_by_query("home objects", limit=5)

# Get image names
for result in results:
    image_name = result['name']  # ← Image name from database
    image_id = result['id']
    print(f"{image_name} (ID: {image_id})")
```

### 2. Display Images with Hand Control

```python
from GestureDetection.rag_client import InteractiveImageGallery

gallery = InteractiveImageGallery(width=1280, height=720)
gallery.run_interactive_gallery(query="kitchen furniture")
```

### 3. Load and Process Images

```python
retriever = RAGImageRetriever()

# Get results from database
results = retriever.search_images_by_query("office desk", limit=3)

# Load each image
images = []
for result in results:
    img = retriever.load_image_file(result['path'])
    if img is not None:
        images.append({
            'name': result['name'],
            'image': img,
            'id': result['id']
        })
```

### 4. Pinch Gesture Detection

```python
from GestureDetection.HandGestures import detect_pinch_gesture
import mediapipe as mp

mp_hands = mp.solutions.hands
hands = mp_hands.Hands()

# In main loop
rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
results = hands.process(rgb)

if results.multi_hand_landmarks:
    hand = results.multi_hand_landmarks[0]
    
    # Detect pinch
    is_pinching, index_pos, thumb_pos = detect_pinch_gesture(
        hand, frame_width, frame_height, threshold=50
    )
    
    if is_pinching:
        print(f"Pinch detected! Index at: {index_pos}")
```

---

## Example Output

```
=== RAG Image Retrieval Demo ===

Searching for: living room furniture
──────────────────────────────────────────────

✓ Found 5 results:
1. living_room_1.jpg (ID: 101)
2. sofa_brown.png (ID: 102)
3. furniture_set.jpg (ID: 103)
4. interior_modern.jpg (ID: 104)
5. room_decor.png (ID: 105)

==================================================
Gallery initialized with 5 images
==================================================

Interactive Gallery with Hand Gestures ===
Commands:
  • Pinch (thumb + index close): Select and grab image
  • Move hand while pinching: Drag image
  • Release pinch: Drop image
  • ESC: Exit

[Camera opens with gallery displayed]

Query: living room furniture
Gesture: Five
Status: Ready

[Pinch detected]
Selected: living_room_1.jpg

[Moving while pinching]
[Release pinch]
Released: living_room_1.jpg

Exiting gallery...
✓ Resources cleaned up
```

---

## Troubleshooting

### Problem: "No images found in database"

**Solution:**
- Check database connection
- Verify images exist in database
- Try different search query
- Check database permissions

```python
retriever = RAGImageRetriever(use_gemini=True)
# Verify database initialized
if retriever.db is None:
    print("Database not initialized")
```

### Problem: Images not loading

**Solution:**
- Verify image paths are correct in database
- Check file permissions
- Ensure image format is supported (JPG, PNG)

```python
# Test image loading
img = retriever.load_image_file("/path/to/image.jpg")
if img is None:
    print("Failed to load image")
else:
    print(f"Image loaded: {img.shape}")
```

### Problem: Pinch detection not working

**Solution:**
- Ensure good lighting
- Increase confidence threshold
- Test with different hand distances

```python
# Adjust threshold (default 50px)
is_pinching, idx_pos, thumb_pos = detect_pinch_gesture(
    hand_lms, 
    frame_width, 
    frame_height, 
    threshold=60  # ← Increase threshold
)
```

### Problem: Camera not opening

**Solution:**
- Check camera permissions
- Verify camera device ID (usually 0)
- Try different camera index

```python
# Test camera
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    # Try camera 1
    cap = cv2.VideoCapture(1)
```

---

## Performance Tips

1. **Reduce image count:** Use `limit=3` for faster loading
2. **Lower resolution:** Use 480p instead of 1080p
3. **Skip frames:** Process every 2nd frame for faster FPS
4. **GPU acceleration:** MediaPipe uses GPU if available
5. **Smaller thumbnails:** Reduce image size from 150x150 to 100x100

```python
# Fast configuration
gallery = InteractiveImageGallery(width=640, height=480)
gallery.run_interactive_gallery(query="furniture", limit=3)
```

---

## Integration with Your Backend

### Connecting to Existing RAG Module

```python
from RAG_Module.retrieval_gemini import GeminiRetrieval
from RAG_Module.db import DatabaseConnection

# Use existing RAG setup
db = DatabaseConnection()
retriever = GeminiRetrieval()

# This is what rag_client.py does internally
```

### Adding to API Endpoint

```python
from fastapi import FastAPI
from GestureDetection.rag_client import RAGImageRetriever

app = FastAPI()
rag_client = RAGImageRetriever()

@app.get("/search/{query}")
def search_images(query: str, limit: int = 5):
    results = rag_client.search_images_by_query(query, limit)
    return {"results": results, "count": len(results)}

# curl http://localhost:8000/search/furniture?limit=10
```

---

## Next Steps

1. ✅ Run basic example: `python handTracking_rag_integrated.py`
2. ✅ Test with different queries: `python handTracking_rag_integrated.py --query "bedroom"`
3. ✅ Integrate with your API endpoints
4. ✅ Add custom database filters
5. ✅ Extend with additional gestures (ok sign, thumbs up, etc.)

---

## Support

For issues or questions, check:
- Database connectivity (RAG_Module/db.py)
- Image paths in database
- Hand detection confidence thresholds
- Camera permissions on your OS
