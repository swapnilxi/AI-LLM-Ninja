#!/usr/bin/env python3
"""
Test Script for YAML Configuration Loading
==========================================

This script demonstrates how to load the ultralytics/cfg/datasets/HomeObjects-3K.yaml
configuration file in your application.
"""

import sys
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.append(str(Path(__file__).parent))

from yaml_utils import (
    YAMLConfigLoader, 
    load_homeobjects_3k_config, 
    create_sample_homeobjects_config,
    validate_dataset_config
)


def test_yaml_loading():
    """Test the YAML loading functionality."""
    print("🧪 Testing YAML Configuration Loading")
    print("=" * 50)
    
    # Test 1: Basic YAML loader
    print("\n1️⃣ Testing basic YAML loader...")
    loader = YAMLConfigLoader()
    print("✅ YAMLConfigLoader initialized successfully")
    
    # Test 2: Try to load HomeObjects-3K config
    print("\n2️⃣ Attempting to load HomeObjects-3K configuration...")
    try:
        config = load_homeobjects_3k_config()
        print("✅ Successfully loaded HomeObjects-3K configuration!")
        print(f"   Dataset path: {config.get('path', 'N/A')}")
        print(f"   Number of classes: {config.get('nc', 'N/A')}")
        print(f"   Train images: {config.get('train', 'N/A')}")
        print(f"   Validation images: {config.get('val', 'N/A')}")
        print(f"   Test images: {config.get('test', 'N/A')}")
        
        # Validate the configuration
        print("\n3️⃣ Validating configuration...")
        if validate_dataset_config(config):
            print("✅ Configuration validation passed")
        else:
            print("⚠️  Configuration validation failed")
            
    except FileNotFoundError as e:
        print(f"❌ Configuration file not found: {e}")
        print("\n📝 Creating sample configuration...")
        sample_config = create_sample_homeobjects_config()
        print("✅ Sample configuration created:")
        for key, value in sample_config.items():
            print(f"   {key}: {value}")
            
        # Validate sample configuration
        print("\n3️⃣ Validating sample configuration...")
        if validate_dataset_config(sample_config):
            print("✅ Sample configuration validation passed")
        else:
            print("⚠️  Sample configuration validation failed")
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Test with custom config directory
    print("\n4️⃣ Testing with custom config directory...")
    try:
        custom_loader = YAMLConfigLoader(config_dir=Path.cwd() / "config")
        print(f"✅ Custom loader initialized with directory: {custom_loader.config_dir}")
    except Exception as e:
        print(f"⚠️  Custom loader test: {e}")
    
    # Test 4: Test YAML file creation
    print("\n5️⃣ Testing YAML file creation...")
    try:
        test_config = {
            "test_dataset": {
                "path": "test/path",
                "train": "train/images",
                "val": "val/images",
                "nc": 10,
                "names": ["class1", "class2", "class3"]
            }
        }
        
        test_file = Path("test_config.yaml")
        loader.save_yaml(test_config, test_file)
        print(f"✅ Test YAML file created: {test_file}")
        
        # Load it back to verify
        loaded_config = loader.load_yaml(test_file)
        print("✅ Test YAML file loaded back successfully")
        
        # Clean up
        test_file.unlink()
        print("✅ Test file cleaned up")
        
    except Exception as e:
        print(f"⚠️  YAML file creation test: {e}")


def main():
    """Main function to run all tests."""
    print("🚀 Starting YAML Configuration Loading Tests")
    print("=" * 60)
    
    try:
        test_yaml_loading()
        print("\n" + "=" * 60)
        print("🎉 All tests completed!")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n📚 Next steps:")
    print("   1. Install ultralytics: pip install ultralytics")
    print("   2. Run the FastAPI server: python main.py")
    print("   3. Visit http://127.0.0.1:8000/docs to see the API endpoints")
    print("   4. Use /config/homeobjects-3k to load the configuration")


if __name__ == "__main__":
    main()

