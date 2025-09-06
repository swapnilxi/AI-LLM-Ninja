# Gemini Vision API Integration for Image Segmentation

This project integrates Google's Gemini Vision API with PyTorch Mask R-CNN to provide rich, contextual labels for segmented images. Instead of just basic COCO class labels, you'll get detailed descriptions, attributes, and context for each detected object.

## 🚀 Features

- **Enhanced Object Labeling**: Get detailed descriptions beyond basic COCO labels
- **Contextual Analysis**: Understand object placement and room context
- **Rich Attributes**: Color, material, style, condition, and usage context
- **Batch Processing**: Analyze multiple segments efficiently
- **Flexible Output**: JSON, CSV, or text output formats
- **Error Handling**: Robust error handling with retry mechanisms

## 📋 Prerequisites

- Python 3.10+
- PyTorch 2.0+
- Google AI API key (Gemini Vision API)
- Required Python packages (see `pyproject.toml`)

## 🔑 Setup

### 1. Get Google AI API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy the key to your clipboard

### 2. Set Environment Variable

```bash
# Set your API key
export GOOGLE_AI_API_KEY="your_actual_api_key_here"

# For permanent setup, add to your shell profile
echo 'export GOOGLE_AI_API_KEY="your_key"' >> ~/.bashrc
# or for zsh
echo 'export GOOGLE_AI_API_KEY="your_key"' >> ~/.zshrc

# Reload your shell
source ~/.bashrc  # or source ~/.zshrc
```

### 3. Verify Setup

```bash
# Check if the key is set
echo $GOOGLE_AI_API_KEY

# Should show your API key (starts with AI...)
```

## 📁 Project Structure

```
visionrag-backend/
├── gemini_vision_labeler.py      # Core Gemini Vision API integration
├── MaskCnn_Enhanced.py           # Enhanced Mask R-CNN with Gemini labeling
├── example_gemini_usage.py       # Usage examples and demos
├── config/
│   └── gemini_config.yaml        # Configuration file
├── room_dataset/
│   ├── input_images/             # Place your images here
│   ├── outputs_infer/            # Enhanced segmented images
│   └── analysis_results/         # Detailed analysis results
└── README_Gemini_Integration.md  # This file
```

## 🎯 Quick Start

### 1. Basic Usage

```python
from gemini_vision_labeler import create_gemini_labeler
from PIL import Image

# Create labeler instance
labeler = create_gemini_labeler("your_api_key")

# Analyze a full image
image = Image.open("your_image.jpg")
scene_analysis = labeler.analyze_full_image(image)
print(f"Room type: {scene_analysis['room_type']}")
```

### 2. Segment Analysis

```python
# Analyze individual segments
description = labeler.get_detailed_object_description(
    full_image=image,
    segment_mask=mask_image,
    coco_label="chair",
    confidence_score=0.95
)

print(f"Detailed label: {description['detailed_label']}")
print(f"Attributes: {description['attributes']}")
```

### 3. Batch Processing

```python
# Process multiple segments
segments = [
    {'label': 'chair', 'score': 0.95, 'mask': mask1},
    {'label': 'table', 'score': 0.88, 'mask': mask2}
]

results = labeler.batch_analyze_segments(image, segments)
```

## 🔧 Advanced Usage

### 1. Enhanced Segmentation Pipeline

Run the complete enhanced segmentation with Gemini labeling:

```bash
python MaskCnn_Enhanced.py
```

This will:

- Load your images from `room_dataset/input_images/`
- Run Mask R-CNN segmentation
- Analyze each segment with Gemini Vision API
- Save enhanced images to `room_dataset/outputs_infer/`
- Save detailed analysis to `room_dataset/analysis_results/`

### 2. Custom Configuration

Edit `config/gemini_config.yaml` to customize:

- API settings (model, timeout, retries)
- Analysis parameters (confidence thresholds, max segments)
- Output formats and directories
- Performance settings (parallel processing, caching)

### 3. Example Scripts

Run the example script to see all features in action:

```bash
python example_gemini_usage.py
```

## 📊 Output Examples

### Enhanced Image Output

The enhanced segmentation images include:

- Original COCO labels with confidence scores
- Detailed Gemini-generated labels
- Color-coded segments
- Professional-looking annotations

### Analysis Results

Each analysis produces a JSON file with:

```json
{
  "segment_info": {
    "box": [100, 100, 300, 200],
    "label": "chair",
    "score": 0.95,
    "label_id": 62
  },
  "gemini_analysis": {
    "coco_label": "chair",
    "confidence_score": 0.95,
    "gemini_description": "A modern ergonomic office chair with adjustable height...",
    "object_type": "ergonomic office chair",
    "attributes": ["modern", "ergonomic", "adjustable", "mesh back", "black"],
    "context": "Office workspace, suitable for long hours of computer work",
    "detailed_label": "Modern Ergonomic Office Chair"
  }
}
```

## ⚙️ Configuration Options

### API Settings

```yaml
api:
  model: "gemini-1.5-flash" # Model to use
  timeout: 30 # Request timeout
  max_retries: 3 # Retry attempts
```

### Analysis Settings

```yaml
analysis:
  min_confidence: 0.3 # Minimum confidence for analysis
  max_segments_per_image: 20 # Max segments to analyze
  analyze_full_image: true # Include scene analysis
```

### Performance Settings

```yaml
performance:
  parallel_processing: false # Enable parallel processing
  num_workers: 2 # Number of worker processes
  api_call_delay: 0.1 # Delay between API calls
```

## 🐛 Troubleshooting

### Common Issues

1. **API Key Not Set**

   ```bash
   echo $GOOGLE_AI_API_KEY
   # Should show your key, not empty
   ```

2. **Rate Limiting**

   - Increase `api_call_delay` in config
   - Reduce `batch_size` for processing

3. **Memory Issues**

   - Reduce `max_segments_per_image`
   - Process images one at a time

4. **API Errors**
   - Check your API key validity
   - Verify internet connection
   - Check API quotas and limits

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📈 Performance Tips

1. **Batch Processing**: Process multiple images together
2. **Caching**: Enable response caching for repeated analyses
3. **Parallel Processing**: Use multiple workers for large datasets
4. **Optimized Thresholds**: Adjust confidence thresholds based on your needs

## 🔒 Security Considerations

- Never commit API keys to version control
- Use environment variables for sensitive data
- Monitor API usage and costs
- Implement rate limiting for production use

## 📚 API Reference

### GeminiVisionLabeler Class

#### Methods

- `__init__(api_key, model_name)`: Initialize the labeler
- `analyze_full_image(image)`: Analyze complete scene
- `get_detailed_object_description(image, mask, label, score)`: Analyze single segment
- `batch_analyze_segments(image, segments)`: Process multiple segments
- `save_analysis_results(results, path)`: Save results to file

#### Parameters

- `api_key`: Your Google AI API key
- `model_name`: Gemini model to use (default: "gemini-1.5-flash")
- `image`: PIL Image object
- `mask`: Binary mask for segment
- `label`: COCO class label
- `score`: Detection confidence score

## 🎨 Customization

### Custom Prompts

Modify prompts in `config/gemini_config.yaml`:

```yaml
prompts:
  segment_analysis: |
    Your custom prompt here...
    Use {coco_label} and {confidence_score} placeholders
```

### Custom Output Formats

Extend the labeler to support custom output formats:

```python
class CustomGeminiLabeler(GeminiVisionLabeler):
    def custom_output_format(self, results):
        # Your custom formatting logic
        pass
```

## 📞 Support

For issues and questions:

1. Check the troubleshooting section above
2. Review the example scripts
3. Check Google AI API documentation
4. Review error logs in `gemini_errors.log`

## 🔄 Updates and Maintenance

- Keep your `google-generativeai` package updated
- Monitor Google AI API changes and announcements
- Regularly review and update your API keys
- Monitor usage and costs

## 📄 License

This integration is provided as-is. Please ensure compliance with:

- Google AI API terms of service
- Your organization's data usage policies
- Applicable privacy and security regulations

---

**Happy labeling! 🎯✨**

