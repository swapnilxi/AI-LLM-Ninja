"use client";

import { Badge } from '@/components/ui/badge';
import { useState } from 'react';

interface BoundingBoxProps {
  image_url: string;
  bbox: [number, number, number, number]; // [x1, y1, x2, y2] 
  cls?: string; // class label
  conf?: number; // confidence score
  caption?: string;
}

export function YoloBoundingBox({ 
  image_url, 
  bbox, 
  cls, 
  conf, 
  caption 
}: BoundingBoxProps) {
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageWidth, setImageWidth] = useState(0);
  const [imageHeight, setImageHeight] = useState(0);
  
  // Handle image load to get dimensions
  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    setImageWidth(img.naturalWidth);
    setImageHeight(img.naturalHeight);
    setImageLoaded(true);
  };

  // Calculate position and size of bounding box
  const getBoundingBoxStyle = () => {
    if (!imageLoaded || !bbox) return {};
    
    const [x1, y1, x2, y2] = bbox;
    const left = (x1 / imageWidth) * 100;
    const top = (y1 / imageHeight) * 100;
    const width = ((x2 - x1) / imageWidth) * 100;
    const height = ((y2 - y1) / imageHeight) * 100;
    
    return {
      left: `${left}%`,
      top: `${top}%`,
      width: `${width}%`,
      height: `${height}%`,
    };
  };

  const getConfidenceColor = (conf?: number) => {
    if (!conf) return 'bg-gray-400';
    if (conf >= 0.7) return 'bg-green-500';
    if (conf >= 0.5) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="relative aspect-video bg-muted rounded-lg overflow-hidden">
      <img
        src={image_url}
        alt={caption || "YOLO detection"}
        className="w-full h-full object-contain"
        onLoad={handleImageLoad}
        onError={(e) => {
          const target = e.target as HTMLImageElement;
          target.style.display = 'none';
        }}
      />
      
      {imageLoaded && bbox && (
        <div 
          className="absolute border-2 border-yellow-400 box-border pointer-events-none"
          style={getBoundingBoxStyle()}
        >
          {cls && (
            <div className="absolute -top-6 -left-1 flex items-center gap-1.5">
              <Badge variant="outline" className="bg-black/70 text-white border-none text-xs py-0">
                {cls}
              </Badge>
              {conf !== undefined && (
                <span className="flex items-center gap-1">
                  <div className={`w-2 h-2 rounded-full ${getConfidenceColor(conf)}`} />
                  <span className="text-xs bg-black/70 text-white px-1 rounded">
                    {(conf * 100).toFixed(0)}%
                  </span>
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}