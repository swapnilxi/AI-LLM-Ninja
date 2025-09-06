#!/usr/bin/env python3
# ============================================================
# Test Script for Gemini Vision API Integration
# ============================================================

import os
import sys
from pathlib import Path
import traceback

def test_imports():
    """Test if all required modules can be imported."""
    print("🔍 Testing imports...")
    
    try:
        import google.generativeai as genai
        print("✅ google.generativeai imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import google.generativeai: {e}")
        return False
    
    try:
        from gemini_vision_labeler import GeminiVisionLabeler, create_gemini_labeler
        print("✅ gemini_vision_labeler imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import gemini_vision_labeler: {e}")
        return False
    
    try:
        import torch
        import torchvision
        print("✅ PyTorch and TorchVision imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import PyTorch: {e}")
        return False
    
    try:
        from PIL import Image
        print("✅ PIL (Pillow) imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import PIL: {e}")
        return False
    
    return True

def test_api_key():
    """Test if API key is set."""
    print("\n🔑 Testing API key...")
    
    api_key = os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        print("❌ GOOGLE_AI_API_KEY environment variable not set")
        print("   Set it with: export GOOGLE_AI_API_KEY='your_key_here'")
        return False
    
    if len(api_key) < 10:
        print("❌ API key seems too short")
        return False
    
    print(f"✅ API key is set (starts with: {api_key[:8]}...)")
    return True

def test_gemini_client():
    """Test if Gemini client can be created."""
    print("\n🤖 Testing Gemini client creation...")
    
    try:
        from gemini_vision_labeler import create_gemini_labeler
        
        api_key = os.getenv("GOOGLE_AI_API_KEY")
        labeler = create_gemini_labeler(api_key)
        
        if labeler and hasattr(labeler, 'model'):
            print("✅ Gemini client created successfully")
            return True
        else:
            print("❌ Gemini client creation failed")
            return False
            
    except Exception as e:
        print(f"❌ Error creating Gemini client: {e}")
        traceback.print_exc()
        return False

def test_basic_functionality():
    """Test basic functionality without making API calls."""
    print("\n🧪 Testing basic functionality...")
    
    try:
        from gemini_vision_labeler import GeminiVisionLabeler
        
        # Test class instantiation (without API key for this test)
        labeler = GeminiVisionLabeler.__new__(GeminiVisionLabeler)
        
        # Test method existence
        required_methods = [
            'get_detailed_object_description',
            'analyze_full_image',
            'batch_analyze_segments',
            'save_analysis_results'
        ]
        
        for method in required_methods:
            if hasattr(labeler, method):
                print(f"✅ Method {method} exists")
            else:
                print(f"❌ Method {method} missing")
                return False
        
        print("✅ All required methods exist")
        return True
        
    except Exception as e:
        print(f"❌ Error testing basic functionality: {e}")
        return False

def test_image_creation():
    """Test if we can create test images."""
    print("\n🖼️  Testing image creation...")
    
    try:
        from PIL import Image, ImageDraw
        
        # Create a simple test image
        test_image = Image.new('RGB', (100, 100), color='white')
        draw = ImageDraw.Draw(test_image)
        draw.rectangle([20, 20, 80, 80], fill='blue')
        
        # Create a test mask
        test_mask = Image.new('L', (100, 100), 0)
        mask_draw = ImageDraw.Draw(test_mask)
        mask_draw.rectangle([20, 20, 80, 80], fill=255)
        
        print("✅ Test images created successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error creating test images: {e}")
        return False

def test_directory_structure():
    """Test if required directories exist or can be created."""
    print("\n📁 Testing directory structure...")
    
    required_dirs = [
        "room_dataset",
        "room_dataset/input_images",
        "room_dataset/outputs_infer",
        "room_dataset/analysis_results",
        "config"
    ]
    
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists():
            print(f"✅ Directory exists: {dir_path}")
        else:
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"✅ Directory created: {dir_path}")
            except Exception as e:
                print(f"❌ Failed to create directory {dir_path}: {e}")
                return False
    
    return True

def test_config_file():
    """Test if configuration file exists."""
    print("\n⚙️  Testing configuration file...")
    
    config_path = Path("config/gemini_config.yaml")
    if config_path.exists():
        print("✅ Configuration file exists")
        return True
    else:
        print("❌ Configuration file missing")
        return False

def run_integration_test():
    """Run a simple integration test if API key is available."""
    print("\n🚀 Running integration test...")
    
    api_key = os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        print("⚠️  Skipping integration test (no API key)")
        return True
    
    try:
        from gemini_vision_labeler import create_gemini_labeler
        from PIL import Image, ImageDraw
        
        # Create test image
        test_image = Image.new('RGB', (200, 150), color='white')
        draw = ImageDraw.Draw(test_image)
        draw.rectangle([50, 50, 150, 100], fill='lightblue', outline='blue')
        
        # Create labeler
        labeler = create_gemini_labeler(api_key)
        
        # Test full image analysis
        print("   Testing full image analysis...")
        scene_analysis = labeler.analyze_full_image(test_image)
        
        if scene_analysis and isinstance(scene_analysis, dict):
            print("✅ Full image analysis successful")
            print(f"   Room type: {scene_analysis.get('room_type', 'Unknown')}")
        else:
            print("❌ Full image analysis failed")
            return False
        
        print("✅ Integration test passed")
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🧪 Gemini Vision API Integration Test Suite")
    print("=" * 50)
    
    tests = [
        ("Import Tests", test_imports),
        ("API Key Test", test_api_key),
        ("Gemini Client Test", test_gemini_client),
        ("Basic Functionality Test", test_basic_functionality),
        ("Image Creation Test", test_image_creation),
        ("Directory Structure Test", test_directory_structure),
        ("Configuration Test", test_config_file),
        ("Integration Test", run_integration_test)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Integration is ready to use.")
        print("\n🚀 Next steps:")
        print("   1. Place images in room_dataset/input_images/")
        print("   2. Run: python MaskCnn_Enhanced.py")
        print("   3. Check results in room_dataset/analysis_results/")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        print("\n🔧 Common fixes:")
        print("   1. Set GOOGLE_AI_API_KEY environment variable")
        print("   2. Install missing dependencies")
        print("   3. Check file permissions")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

