# ============================================================
# Gemini Vision API Integration for Image Labeling
# - Uses Google's Gemini Vision API to provide detailed descriptions
# - Integrates with Mask R-CNN segmentation results
# - Provides rich, contextual labels for segmented objects
# ============================================================

import google.generativeai as genai
import base64
import io
from PIL import Image
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiVisionLabeler:
    """
    Uses Gemini Vision API to provide detailed descriptions and labels
    for segmented images and individual object segments.
    """
    
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        """
        Initialize Gemini Vision API client.
        
        Args:
            api_key: Google AI API key
            model_name: Gemini model to use (default: gemini-1.5-flash)
        """
        self.api_key = api_key
        self.model_name = model_name
        self.model = None
        self._setup_client()
    
    def _setup_client(self):
        """Setup Gemini client with API key."""
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"Gemini Vision API client initialized with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise
    
    def encode_image_to_base64(self, image: Image.Image) -> str:
        """
        Convert PIL Image to base64 string for API transmission.
        
        Args:
            image: PIL Image object
            
        Returns:
            Base64 encoded string
        """
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return img_str
    
    def get_detailed_object_description(self, 
                                     full_image: Image.Image, 
                                     segment_mask: Image.Image,
                                     coco_label: str,
                                     confidence_score: float) -> Dict[str, Any]:
        """
        Get detailed description of a segmented object using Gemini Vision API.
        
        Args:
            full_image: Original full image
            segment_mask: Binary mask of the segmented object
            coco_label: COCO class label from Mask R-CNN
            confidence_score: Detection confidence score
            
        Returns:
            Dictionary containing detailed description and metadata
        """
        try:
            # Create a composite image showing the segment on the original
            composite = self._create_segment_composite(full_image, segment_mask)
            
            # Prepare prompt for detailed analysis
            prompt = self._create_analysis_prompt(coco_label, confidence_score)
            
            # Get Gemini's analysis
            response = self._analyze_with_gemini(composite, prompt)
            
            return {
                "coco_label": coco_label,
                "confidence_score": confidence_score,
                "gemini_description": response.get("description", ""),
                "object_type": response.get("object_type", coco_label),
                "attributes": response.get("attributes", []),
                "context": response.get("context", ""),
                "detailed_label": response.get("detailed_label", coco_label)
            }
            
        except Exception as e:
            logger.error(f"Error getting object description: {e}")
            return {
                "coco_label": coco_label,
                "confidence_score": confidence_score,
                "gemini_description": f"Error analyzing object: {str(e)}",
                "object_type": coco_label,
                "attributes": [],
                "context": "",
                "detailed_label": coco_label
            }
    
    def _create_segment_composite(self, 
                                 full_image: Image.Image, 
                                 segment_mask: Image.Image) -> Image.Image:
        """
        Create a composite image showing the segment highlighted on the original.
        
        Args:
            full_image: Original image
            segment_mask: Binary mask
            
        Returns:
            Composite image with segment highlighted
        """
        # Ensure mask is the same size as original
        if segment_mask.size != full_image.size:
            segment_mask = segment_mask.resize(full_image.size, Image.NEAREST)
        
        # Convert mask to RGBA with red highlight
        mask_rgba = Image.new("RGBA", full_image.size, (0, 0, 0, 0))
        mask_data = segment_mask.convert("L")
        
        # Create red highlight for the segment
        for x in range(mask_data.width):
            for y in range(mask_data.height):
                if mask_data.getpixel((x, y)) > 128:
                    mask_rgba.putpixel((x, y), (255, 0, 0, 128))
        
        # Composite the images
        composite = Image.alpha_composite(full_image.convert("RGBA"), mask_rgba)
        return composite.convert("RGB")
    
    def _create_analysis_prompt(self, coco_label: str, confidence_score: float) -> str:
        """
        Create a detailed prompt for Gemini Vision API analysis.
        
        Args:
            coco_label: COCO class label
            confidence_score: Detection confidence
            
        Returns:
            Formatted prompt string
        """
        return f"""
        Analyze this segmented object in detail. The object was detected as "{coco_label}" 
        with a confidence score of {confidence_score:.3f}.
        
        Please provide:
        1. A detailed description of what you see
        2. The specific type/category of object
        3. Key visual attributes (color, material, style, condition, etc.)
        4. Context about where this object might be used
        5. A more specific, descriptive label
        
        Focus on providing rich, contextual information that goes beyond the basic COCO label.
        Be specific about visual details, materials, and contextual usage.
        
        Respond in JSON format with these fields:
        {{
            "description": "detailed visual description",
            "object_type": "specific type/category",
            "attributes": ["attribute1", "attribute2", "..."],
            "context": "usage context and placement",
            "detailed_label": "specific descriptive label"
        }}
        """
    
    def _analyze_with_gemini(self, image: Image.Image, prompt: str) -> Dict[str, Any]:
        """
        Send image and prompt to Gemini Vision API.
        
        Args:
            image: Image to analyze
            prompt: Analysis prompt
            
        Returns:
            Parsed response from Gemini
        """
        try:
            # Convert image to base64
            img_base64 = self.encode_image_to_base64(image)
            
            # Create image part for Gemini
            image_part = {
                "mime_type": "image/png",
                "data": img_base64
            }
            
            # Generate content
            response = self.model.generate_content([prompt, image_part])
            
            # Parse response
            if response.text:
                try:
                    # Try to parse as JSON
                    return json.loads(response.text)
                except json.JSONDecodeError:
                    # If not JSON, create a structured response
                    return {
                        "description": response.text,
                        "object_type": "unknown",
                        "attributes": [],
                        "context": "",
                        "detailed_label": "unknown"
                    }
            else:
                return {
                    "description": "No response from Gemini",
                    "object_type": "unknown",
                    "attributes": [],
                    "context": "",
                    "detailed_label": "unknown"
                }
                
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return {
                "description": f"API Error: {str(e)}",
                "object_type": "unknown",
                "attributes": [],
                "context": "",
                "detailed_label": "unknown"
            }
    
    def analyze_full_image(self, image: Image.Image) -> Dict[str, Any]:
        """
        Get overall scene description for the full image.
        
        Args:
            image: Full image to analyze
            
        Returns:
            Dictionary with scene description
        """
        prompt = """
        Analyze this indoor scene image and provide:
        1. Overall room/space description
        2. Main objects and furniture visible
        3. Room type and purpose
        4. General atmosphere and style
        
        Respond in JSON format:
        {
            "scene_description": "overall description",
            "room_type": "type of room",
            "main_objects": ["object1", "object2", "..."],
            "style": "decorative style",
            "atmosphere": "overall atmosphere"
        }
        """
        
        try:
            response = self._analyze_with_gemini(image, prompt)
            return response
        except Exception as e:
            logger.error(f"Error analyzing full image: {e}")
            return {
                "scene_description": f"Error: {str(e)}",
                "room_type": "unknown",
                "main_objects": [],
                "style": "unknown",
                "atmosphere": "unknown"
            }
    
    def batch_analyze_segments(self, 
                              full_image: Image.Image, 
                              segment_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze multiple segments from the same image.
        
        Args:
            full_image: Original image
            segment_data: List of segment information from Mask R-CNN
            
        Returns:
            List of detailed segment descriptions
        """
        results = []
        
        for i, segment in enumerate(segment_data):
            logger.info(f"Analyzing segment {i+1}/{len(segment_data)}: {segment.get('label', 'unknown')}")
            
            # Create mask from segment data
            if 'mask' in segment:
                mask = Image.fromarray(segment['mask'], mode='L')
                description = self.get_detailed_object_description(
                    full_image, 
                    mask, 
                    segment.get('label', 'unknown'),
                    segment.get('score', 0.0)
                )
                results.append(description)
            else:
                logger.warning(f"Segment {i} missing mask data")
                results.append({
                    "coco_label": segment.get('label', 'unknown'),
                    "confidence_score": segment.get('score', 0.0),
                    "gemini_description": "No mask data available",
                    "object_type": segment.get('label', 'unknown'),
                    "attributes": [],
                    "context": "",
                    "detailed_label": segment.get('label', 'unknown')
                })
        
        return results
    
    def save_analysis_results(self, 
                            results: List[Dict[str, Any]], 
                            output_path: str) -> None:
        """
        Save analysis results to JSON file.
        
        Args:
            results: List of analysis results
            output_path: Path to save JSON file
        """
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            logger.info(f"Analysis results saved to: {output_file}")
        except Exception as e:
            logger.error(f"Error saving results: {e}")


# Utility function for easy integration
def create_gemini_labeler(api_key: str) -> GeminiVisionLabeler:
    """
    Create and return a configured GeminiVisionLabeler instance.
    
    Args:
        api_key: Google AI API key
        
    Returns:
        Configured GeminiVisionLabeler instance
    """
    return GeminiVisionLabeler(api_key)


if __name__ == "__main__":
    # Example usage
    print("Gemini Vision Labeler Module")
    print("This module provides integration with Google's Gemini Vision API")
    print("for detailed labeling of segmented images.")
    print("\nTo use:")
    print("1. Set your GOOGLE_AI_API_KEY environment variable")
    print("2. Import and use GeminiVisionLabeler class")
    print("3. Integrate with your Mask R-CNN segmentation pipeline")

