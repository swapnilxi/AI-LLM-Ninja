#!/usr/bin/env python3
"""
YAML Utilities for Vision-RAG Backend
=====================================

This module provides utilities for loading and working with YAML configuration files,
particularly ultralytics dataset configurations.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
import os


class YAMLConfigLoader:
    """Utility class for loading and managing YAML configuration files."""
    
    def __init__(self, config_dir: Optional[Union[str, Path]] = None):
        """
        Initialize the YAML config loader.
        
        Args:
            config_dir: Directory to search for configuration files
        """
        self.config_dir = Path(config_dir) if config_dir else Path.cwd()
    
    def load_yaml(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load a YAML file and return its contents as a dictionary.
        
        Args:
            file_path: Path to the YAML file
            
        Returns:
            Dictionary containing the YAML file contents
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            yaml.YAMLError: If the YAML file is malformed
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"YAML file not found: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                return config if config else {}
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Error parsing YAML file {file_path}: {e}")
        except Exception as e:
            raise Exception(f"Error reading YAML file {file_path}: {e}")
    
    def load_ultralytics_dataset_config(self, dataset_name: str) -> Dict[str, Any]:
        """
        Load an ultralytics dataset configuration file.
        
        Args:
            dataset_name: Name of the dataset (e.g., 'HomeObjects-3K')
            
        Returns:
            Dictionary containing the dataset configuration
            
        Raises:
            FileNotFoundError: If the dataset config file doesn't exist
        """
        # Try to find the config file in common ultralytics locations
        possible_paths = [
            self.config_dir / "ultralytics" / "cfg" / "datasets" / f"{dataset_name}.yaml",
            self.config_dir / "cfg" / "datasets" / f"{dataset_name}.yaml",
            Path.home() / ".ultralytics" / "cfg" / "datasets" / f"{dataset_name}.yaml",
            Path("/usr/local/lib/python3.*/site-packages/ultralytics/cfg/datasets") / f"{dataset_name}.yaml",
        ]
        
        # Also check if ultralytics is installed and try to find its config directory
        try:
            import ultralytics
            ultralytics_path = Path(ultralytics.__file__).parent
            possible_paths.append(ultralytics_path / "cfg" / "datasets" / f"{dataset_name}.yaml")
        except ImportError:
            pass
        
        # Try each possible path
        for path in possible_paths:
            if path.exists():
                return self.load_yaml(path)
        
        # If not found, raise an error with helpful information
        raise FileNotFoundError(
            f"Dataset configuration file '{dataset_name}.yaml' not found in any of these locations:\n" +
            "\n".join(str(p) for p in possible_paths) +
            "\n\nPlease ensure the ultralytics package is installed or provide the correct path."
        )
    
    def save_yaml(self, data: Dict[str, Any], file_path: Union[str, Path]) -> None:
        """
        Save data to a YAML file.
        
        Args:
            data: Dictionary to save
            file_path: Path where to save the YAML file
        """
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as file:
            yaml.dump(data, file, default_flow_style=False, indent=2, allow_unicode=True)
    
    def validate_dataset_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate that a dataset configuration has the required fields.
        
        Args:
            config: Dataset configuration dictionary
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['path', 'train', 'val', 'test', 'nc', 'names']
        
        for field in required_fields:
            if field not in config:
                print(f"Warning: Missing required field '{field}' in dataset config")
                return False
        
        return True


def load_homeobjects_3k_config() -> Dict[str, Any]:
    """
    Convenience function to load the HomeObjects-3K dataset configuration.
    
    Returns:
        Dictionary containing the HomeObjects-3K dataset configuration
    """
    loader = YAMLConfigLoader()
    return loader.load_ultralytics_dataset_config("HomeObjects-3K")


def create_sample_homeobjects_config() -> Dict[str, Any]:
    """
    Create a sample HomeObjects-3K configuration if the original is not found.
    
    Returns:
        Sample dataset configuration dictionary
    """
    return {
        "path": "../datasets/HomeObjects-3K",  # Dataset root directory
        "train": "images/train",               # Train images (relative to 'path')
        "val": "images/val",                   # Val images (relative to 'path')
        "test": "images/test",                 # Test images (relative to 'path')
        "nc": 3000,                           # Number of classes
        "names": [f"object_{i}" for i in range(3000)]  # Class names (simplified)
    }


if __name__ == "__main__":
    # Example usage
    try:
        config = load_homeobjects_3k_config()
        print("✅ Successfully loaded HomeObjects-3K configuration:")
        print(f"   Dataset path: {config.get('path', 'N/A')}")
        print(f"   Number of classes: {config.get('nc', 'N/A')}")
        print(f"   Train images: {config.get('train', 'N/A')}")
        print(f"   Validation images: {config.get('val', 'N/A')}")
        print(f"   Test images: {config.get('test', 'N/A')}")
        
        # Validate the configuration
        if validate_dataset_config(config):
            print("✅ Configuration validation passed")
        else:
            print("⚠️  Configuration validation failed")
            
    except FileNotFoundError as e:
        print(f"❌ Configuration file not found: {e}")
        print("\nCreating sample configuration...")
        sample_config = create_sample_homeobjects_config()
        print("📝 Sample configuration created:")
        for key, value in sample_config.items():
            print(f"   {key}: {value}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

