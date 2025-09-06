#!/usr/bin/env python3
# ============================================================
# Example: Using Gemini Vision API for Image Segmentation Labeling
# ============================================================

import os
from pathlib import Path
from PIL import Image
import json

# Import our Gemini Vision integration
from gemini_vision_labeler import GeminiVisionLabeler, create_gemini_labeler

def example_single_image_analysis():
    """
    Example: Analyze a single image with Gemini Vision API.
    """
    print("=== Example: Single Image Analysis ===")
    
    # Check if API key is available
    api_key = os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        print("❌ GOOGLE_AI_API_KEY environment variable not set")
        print("   Get your API key from: https://makersuite.google.com/app/apikey")
        print("   Then run: export GOOGLE_AI_API_KEY='your_key_here'")
        return
    
    try:
        # Create Gemini Vision labeler
        labeler = create_gemini_labeler(api_key)
        print("✅ Gemini Vision API client initialized")
        
        # Example: Analyze a full image
        # Replace with path to your actual image
        image_path = "room_dataset/input_images/your_image.jpg"
        
        if Path(image_path).exists():
            print(f"📸 Analyzing image: {image_path}")
            image = Image.open(image_path).convert("RGB")
            
            # Get full image analysis
            scene_analysis = labeler.analyze_full_image(image)
            print("\n🏠 Scene Analysis:")
            print(f"   Room Type: {scene_analysis.get('room_type', 'Unknown')}")
            print(f"   Style: {scene_analysis.get('style', 'Unknown')}")
            print(f"   Atmosphere: {scene_analysis.get('atmosphere', 'Unknown')}")
            print(f"   Main Objects: {', '.join(scene_analysis.get('main_objects', []))}")
            
            # Save analysis results
            output_path = "example_analysis.json"
            labeler.save_analysis_results([scene_analysis], output_path)
            print(f"💾 Analysis saved to: {output_path}")
            
        else:
            print(f"⚠️  Image not found: {image_path}")
            print("   Please place an image in the input_images directory")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def example_segment_analysis():
    """
    Example: Analyze individual segments (masks) from segmentation.
    """
    print("\n=== Example: Segment Analysis ===")
    
    api_key = os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        print("❌ API key not available")
        return
    
    try:
        labeler = create_gemini_labeler(api_key)
        
        # Example: Create a simple mask (in practice, this would come from Mask R-CNN)
        # This creates a simple rectangular mask for demonstration
        from PIL import Image, ImageDraw
        
        # Create a sample image
        sample_image = Image.new('RGB', (400, 300), color='white')
        draw = ImageDraw.Draw(sample_image)
        draw.rectangle([100, 100, 300, 200], fill='lightblue', outline='blue')
        draw.text((150, 150), "Sample Object", fill='black')
        
        # Create a mask for the object
        mask = Image.new('L', (400, 300), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rectangle([100, 100, 300, 200], fill=255)
        
        print("🔍 Analyzing sample segment...")
        
        # Get detailed description
        description = labeler.get_detailed_object_description(
            full_image=sample_image,
            segment_mask=mask,
            coco_label="chair",  # Example COCO label
            confidence_score=0.95
        )
        
        print("\n📝 Segment Analysis:")
        print(f"   COCO Label: {description['coco_label']}")
        print(f"   Detailed Label: {description['detailed_label']}")
        print(f"   Object Type: {description['object_type']}")
        print(f"   Attributes: {', '.join(description['attributes'])}")
        print(f"   Context: {description['context']}")
        print(f"   Description: {description['gemini_description']}")
        
        # Save results
        labeler.save_analysis_results([description], "example_segment_analysis.json")
        print("💾 Segment analysis saved")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def example_batch_processing():
    """
    Example: Process multiple segments from the same image.
    """
    print("\n=== Example: Batch Segment Processing ===")
    
    api_key = os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        print("❌ API key not available")
        return
    
    try:
        labeler = create_gemini_labeler(api_key)
        
        # Create a sample image with multiple objects
        sample_image = Image.new('RGB', (600, 400), color='white')
        from PIL import ImageDraw
        draw = ImageDraw.Draw(sample_image)
        
        # Draw multiple objects
        draw.rectangle([50, 50, 200, 150], fill='lightblue', outline='blue')
        draw.rectangle([250, 50, 400, 150], fill='lightgreen', outline='green')
        draw.rectangle([450, 50, 550, 150], fill='lightcoral', outline='red')
        
        # Create sample segment data (in practice, this comes from Mask R-CNN)
        segments = [
            {
                'label': 'chair',
                'score': 0.95,
                'mask': Image.new('L', (600, 400), 0)  # Simplified mask
            },
            {
                'label': 'table',
                'score': 0.88,
                'mask': Image.new('L', (600, 400), 0)  # Simplified mask
            },
            {
                'label': 'lamp',
                'score': 0.92,
                'mask': Image.new('L', (600, 400), 0)  # Simplified mask
            }
        ]
        
        print("🔄 Processing multiple segments...")
        
        # Batch analyze segments
        results = labeler.batch_analyze_segments(sample_image, segments)
        
        print(f"\n📊 Batch Analysis Results ({len(results)} segments):")
        for i, result in enumerate(results):
            print(f"\n   Segment {i+1}:")
            print(f"     Label: {result['detailed_label']}")
            print(f"     Type: {result['object_type']}")
            print(f"     Attributes: {', '.join(result['attributes'][:3])}...")
        
        # Save batch results
        labeler.save_analysis_results(results, "example_batch_analysis.json")
        print("💾 Batch analysis saved")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def setup_environment():
    """
    Help user set up the environment for Gemini Vision API.
    """
    print("=== Environment Setup ===")
    
    api_key = os.getenv("GOOGLE_AI_API_KEY")
    if api_key:
        print("✅ GOOGLE_AI_API_KEY is set")
        print(f"   Key starts with: {api_key[:8]}...")
    else:
        print("❌ GOOGLE_AI_API_KEY is not set")
        print("\n📋 To set up Gemini Vision API:")
        print("   1. Visit: https://makersuite.google.com/app/apikey")
        print("   2. Create a new API key")
        print("   3. Set environment variable:")
        print("      export GOOGLE_AI_API_KEY='your_actual_api_key'")
        print("   4. Restart your terminal or run:")
        print("      source ~/.bashrc  # or ~/.zshrc")
    
    print(f"\n📁 Current working directory: {Path.cwd()}")
    print(f"📁 Input images directory: {Path('room_dataset/input_images')}")
    
    # Check if input directory exists
    input_dir = Path("room_dataset/input_images")
    if input_dir.exists():
        images = list(input_dir.glob("*.jpg")) + list(input_dir.glob("*.png"))
        print(f"📸 Found {len(images)} images in input directory")
        for img in images[:3]:  # Show first 3
            print(f"   - {img.name}")
        if len(images) > 3:
            print(f"   ... and {len(images) - 3} more")
    else:
        print("⚠️  Input directory does not exist")
        print("   Create it and add some images to test with")

def main():
    """
    Main function to run examples.
    """
    print("🚀 Gemini Vision API Integration Examples")
    print("=" * 50)
    
    # Setup check
    setup_environment()
    
    # Run examples if API key is available
    if os.getenv("GOOGLE_AI_API_KEY"):
        example_single_image_analysis()
        example_segment_analysis()
        example_batch_processing()
    else:
        print("\n💡 Set your API key to run the examples!")
    
    print("\n" + "=" * 50)
    print("🎯 Next Steps:")
    print("   1. Set your GOOGLE_AI_API_KEY")
    print("   2. Place images in room_dataset/input_images/")
    print("   3. Run MaskCnn_Enhanced.py for full segmentation + labeling")
    print("   4. Check the analysis_results/ directory for detailed outputs")

if __name__ == "__main__":
    main()

