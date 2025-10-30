"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Eye, FileText, Grid3x3, Image as ImageIcon, Layers, Target, Zap } from "lucide-react";
import { YoloBoundingBox } from "./yolo-bounding-box";

interface ResultsDisplayProps {
  results: any[];
  segments?: any[];
  query?: string;
  method?: string;
}

export function ResultsDisplay({ results, segments = [], query, method }: ResultsDisplayProps) {
  // Debug logging
  console.log('=== [ResultsDisplay] Component Rendered ===');
  console.log('[ResultsDisplay] Received data:', { 
    results, 
    segments, 
    resultsLength: results.length, 
    segmentsLength: segments.length,
    firstResult: results[0],
    firstSegment: segments[0]
  });
  
  // Log environment variable
  console.log('[ResultsDisplay] Backend URL:', process.env.NEXT_PUBLIC_BACKEND_URL);
  
  // Detailed logging of first result structure
  if (results.length > 0) {
    console.log('[ResultsDisplay] First result detailed structure:', {
      id: results[0].id,
      uri: results[0].uri,
      display_info: results[0].display_info,
      caption: results[0].caption,
      score: results[0].score,
      similarity: results[0].similarity,
      source: results[0].source,
      meta: results[0].meta,
      meta_parsed: results[0].meta_parsed,
      allKeys: Object.keys(results[0])
    });
  }
  
  const hasImages = results.length > 0;
  const hasSegments = segments.length > 0;
  
  if (!hasImages && !hasSegments) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <div className="w-16 h-16 mx-auto mb-4 bg-muted rounded-full flex items-center justify-center">
            <Eye className="h-8 w-8 text-muted-foreground" />
          </div>
          <p className="text-muted-foreground">No results found. Try a different query.</p>
        </CardContent>
      </Card>
    );
  }

  // Helper function to construct proper image URL
  const getImageUrl = (path: string | undefined): string => {
    if (!path) return '';
    
    // If it's already a full URL, return as-is
    if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('data:')) {
      return path;
    }
    
    // If it's a relative path, construct the full URL
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    
    // Remove leading slash if present
    const cleanPath = path.startsWith('/') ? path.slice(1) : path;
    
    // Construct full URL
    return `${backendUrl}/${cleanPath}`;
  };

  // Helper to build image src from result (supports inline base64 or path/uri)
  const getImageSrc = (result: any, path?: string): string => {
    // Check for inline base64 payloads on display_info or meta_parsed or top-level
    const b64 = result?.display_info?.image_base64 || result?.meta_parsed?.image_base64 || result?.meta?.image_base64 || result?.image_base64;
    const mime = result?.display_info?.mime_type || result?.meta_parsed?.mime_type || result?.meta?.mime_type || result?.mime_type;
    if (b64) {
      const safeMime = mime || 'image/jpeg';
      return `data:${safeMime};base64,${b64}`;
    }

    // If backend only returned an image identifier (e.g., image_id: "krishna.png"),
    // construct the backend file-serving endpoint so frontend can fetch it.
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    const imageId = result?.image_id || result?.imageId || result?.id;
    if (imageId && (!path || path === "")) {
      return `${backendUrl}/image?path=${encodeURIComponent(imageId)}`;
    }

    // Fallback to building URL from path/uri
    return getImageUrl(path);
  };

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return "bg-green-500";
    if (score >= 0.6) return "bg-yellow-500";
    return "bg-red-500";
  };

  const getEngineIcon = (engine?: string) => {
    switch (engine?.toLowerCase()) {
      case 'gemini':
        return <Zap className="h-3 w-3" />;
      case 'siglip':
        return <ImageIcon className="h-3 w-3" />;
      case 'yolo':
        return <Eye className="h-3 w-3" />;
      default:
        return <FileText className="h-3 w-3" />;
    }
  };

  const renderResultCard = (result: any, index: number, type: "image" | "segment") => {
    // Handle both segment and image formats - backend sends different structures
    const rawImageUrl = type === "segment" 
      ? (result.crop_path || result.image_uri || result.display_info?.image_url || result.uri)
      : (result.uri || result.display_info?.image_url);
    
  const imageUrl = getImageSrc(result, rawImageUrl);
    
    const caption = result.caption || result.display_info?.caption || result.content;
    const cls = result.cls || result.display_info?.cls || result.meta_parsed?.cls || result.meta?.cls;
    const conf = result.conf ?? result.display_info?.conf ?? result.meta_parsed?.conf ?? result.meta?.conf;
    const bbox = result.bbox || result.display_info?.bbox || result.meta_parsed?.bbox;
    const engine = result.display_info?.engine || result.meta_parsed?.engine || result.meta?.engine;
    const score = result.score || result.similarity || 0;
    
    // Debug log for each result
    console.log(`[ResultsDisplay] Rendering ${type} #${index + 1}:`, { 
      rawImageUrl,
      imageUrl, 
      caption, 
      cls, 
      conf, 
      bbox,
      score,
      rawResult: result 
    });
    
    return (
      <Card key={`${type}-${result.id || index}`} className="overflow-hidden hover:shadow-lg transition-shadow">
        <CardHeader className="p-4 pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              {type === "segment" ? <Layers className="h-4 w-4" /> : <ImageIcon className="h-4 w-4" />}
              {type === "segment" ? "Segment" : "Image"} #{index + 1}
            </CardTitle>
            <div className="flex items-center gap-2">
              {/* Similarity Score */}
              <div className="flex items-center gap-1">
                <div 
                  className={`w-2 h-2 rounded-full ${getScoreColor(score)}`}
                />
                <span className="text-xs text-muted-foreground">
                  {(score * 100).toFixed(1)}%
                </span>
              </div>
              
              {/* Engine Badge */}
              {engine && (
                <Badge variant="secondary" className="text-xs gap-1">
                  {getEngineIcon(engine)}
                  {engine}
                </Badge>
              )}
            </div>
          </div>
        </CardHeader>
        
        <CardContent className="p-4 pt-0 space-y-3">
          {/* Image Display */}
          {imageUrl && (
            <>
              {/* YOLO results with bounding box */}
              {engine === 'yolo' && bbox ? (
                <YoloBoundingBox 
                  image_url={imageUrl}
                  bbox={bbox}
                  cls={cls}
                  conf={conf}
                  caption={caption}
                />
              ) : (
                /* Regular image display */
                <div className="relative aspect-video bg-muted rounded-lg overflow-hidden">
                  <img
                    src={imageUrl}
                    alt={caption || "Result image"}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      console.error(`[ResultsDisplay] ❌ Failed to load image:`, {
                        url: imageUrl,
                        rawUrl: rawImageUrl,
                        result: result
                      });
                      const target = e.target as HTMLImageElement;
                      target.style.display = 'none';
                      const parent = target.parentElement;
                      if (parent) {
                        parent.classList.add('bg-destructive/10');
                        parent.innerHTML = `
                          <div class="flex flex-col items-center justify-center h-full p-4 text-center">
                            <svg class="w-12 h-12 text-muted-foreground mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                            </svg>
                            <p class="text-xs text-muted-foreground">Image failed to load</p>
                            <p class="text-xs text-muted-foreground font-mono mt-1 break-all">${imageUrl}</p>
                          </div>
                        `;
                      }
                    }}
                    onLoad={() => {
                      console.log(`[ResultsDisplay] ✅ Image loaded successfully:`, imageUrl);
                    }}
                  />
                </div>
              )}
            </>
          )}

          {/* Show message if no imageUrl */}
          {!imageUrl && (
            <div className="aspect-video bg-muted rounded-lg overflow-hidden flex items-center justify-center p-4">
              <div className="text-center">
                <ImageIcon className="w-12 h-12 text-muted-foreground mx-auto mb-2" />
                <p className="text-xs text-muted-foreground">No image URL available</p>
                <p className="text-xs text-muted-foreground font-mono mt-1">
                  Check console for details
                </p>
              </div>
            </div>
          )}

          {/* Segment-specific: show crop image if different from main imageUrl */}
          {type === "segment" && result.crop_path && getImageSrc(result, result.crop_path) !== imageUrl && (
            <div className="aspect-video bg-muted rounded-lg overflow-hidden border-2 border-primary/20">
              <img
                src={getImageSrc(result, result.crop_path)}
                alt={caption || "Segment crop"}
                className="w-full h-full object-contain"
                onError={(e) => {
                  console.error(`[ResultsDisplay] Failed to load crop: ${result.crop_path}`);
                  const target = e.target as HTMLImageElement;
                  target.style.display = 'none';
                }}
              />
            </div>
          )}

          {/* Caption/Content */}
          {caption && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                <FileText className="h-3 w-3" />
                Caption:
              </p>
              <p className="text-sm leading-relaxed">{caption}</p>
            </div>
          )}

          {/* Fallback Content */}
          {!caption && result.content && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                <FileText className="h-3 w-3" />
                Content:
              </p>
              <p className="text-sm leading-relaxed">{result.content}</p>
            </div>
          )}
          
          {/* YOLO/Segment-specific metadata */}
          {(cls || conf !== undefined || bbox) && (
            <div className="flex flex-wrap gap-2 pt-2 border-t">
              {cls && (
                <Badge variant="outline" className="flex items-center gap-1 px-2 py-1">
                  <Target className="h-3 w-3" />
                  {cls}
                </Badge>
              )}
              {conf !== undefined && (
                <Badge variant="outline" className="flex items-center gap-1 px-2 py-1">
                  <div className={`w-2 h-2 rounded-full ${
                    conf >= 0.7 ? 'bg-green-500' : 
                    conf >= 0.5 ? 'bg-yellow-500' : 'bg-red-500'
                  }`} />
                  {(conf * 100).toFixed(1)}%
                </Badge>
              )}
              {bbox && (
                <Badge variant="outline" className="flex items-center gap-1 px-2 py-1 text-xs">
                  <Grid3x3 className="h-3 w-3" />
                  BBox
                </Badge>
              )}
            </div>
          )}

          {/* Source */}
          {(result.source || result.display_info?.source) && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Source:</p>
              <p className="text-xs text-muted-foreground">{result.source || result.display_info?.source}</p>
            </div>
          )}

          {/* Metadata */}
          {result.metadata && Object.keys(result.metadata).length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Metadata:</p>
              <div className="text-xs text-muted-foreground space-y-1">
                {Object.entries(result.metadata).map(([key, value]) => (
                  <div key={key}>
                    <span className="font-medium">{key}:</span> {String(value)}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* URI - only show if different from image_url */}
          {result.uri && result.uri !== rawImageUrl && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">URI:</p>
              <p className="text-xs text-muted-foreground font-mono break-all">
                {result.uri}
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="space-y-4">
      {/* Query Info */}
      {query && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Eye className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">Query:</span>
                <span className="text-sm text-muted-foreground">{query}</span>
              </div>
              {method && (
                <Badge variant="outline" className="text-xs">
                  {method}
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results Tabs */}
      {hasImages && hasSegments ? (
        <Tabs defaultValue="images" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="images" className="flex items-center gap-2">
              <ImageIcon className="h-4 w-4" />
              Images ({results.length})
            </TabsTrigger>
            <TabsTrigger value="segments" className="flex items-center gap-2">
              <Layers className="h-4 w-4" />
              Segments ({segments.length})
            </TabsTrigger>
          </TabsList>
          
          <TabsContent value="images" className="mt-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {results.map((result, index) => renderResultCard(result, index, "image"))}
            </div>
          </TabsContent>
          
          <TabsContent value="segments" className="mt-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {segments.map((segment, index) => renderResultCard(segment, index, "segment"))}
            </div>
          </TabsContent>
        </Tabs>
      ) : (
        <>
          {/* Show only images or only segments without tabs */}
          {hasImages && (
            <>
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                  <ImageIcon className="h-5 w-5" />
                  Images ({results.length})
                </h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {results.map((result, index) => renderResultCard(result, index, "image"))}
              </div>
            </>
          )}
          
          {hasSegments && (
            <>
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                  <Layers className="h-5 w-5" />
                  Segments ({segments.length})
                </h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {segments.map((segment, index) => renderResultCard(segment, index, "segment"))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
