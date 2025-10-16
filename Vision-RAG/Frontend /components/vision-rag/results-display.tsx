"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { VisionRAGResult } from "@/types/api";
import { Eye, FileText, Image as ImageIcon, Target, Zap } from "lucide-react";
import { YoloBoundingBox } from "./yolo-bounding-box";

interface ResultsDisplayProps {
  results: VisionRAGResult[];
  query?: string;
  method?: string;
}

export function ResultsDisplay({ results, query, method }: ResultsDisplayProps) {
  if (results.length === 0) {
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

      {/* Results Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Results ({results.length})</h3>
      </div>

      {/* Results Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {results.map((result, index) => (
          <Card key={result.id} className="overflow-hidden">
            <CardHeader className="p-4 pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium">
                  Result #{index + 1}
                </CardTitle>
                <div className="flex items-center gap-2">
                  {/* Similarity Score */}
                  <div className="flex items-center gap-1">
                    <div 
                      className={`w-2 h-2 rounded-full ${getScoreColor(result.score)}`}
                    />
                    <span className="text-xs text-muted-foreground">
                      {(result.score * 100).toFixed(1)}%
                    </span>
                  </div>
                  
                  {/* Engine Badge */}
                  {result.display_info?.engine && (
                    <Badge variant="secondary" className="text-xs gap-1">
                      {getEngineIcon(result.display_info.engine)}
                      {result.display_info.engine}
                    </Badge>
                  )}
                </div>
              </div>
            </CardHeader>
            
            <CardContent className="p-4 pt-0 space-y-3">
              {/* Image */}
              {result.display_info?.image_url && (
                <>
                  {/* YOLO results with bounding box */}
                  {result.display_info?.engine === 'yolo' && result.display_info?.bbox ? (
                    <YoloBoundingBox 
                      image_url={result.display_info.image_url}
                      bbox={result.display_info.bbox}
                      cls={result.display_info.cls}
                      conf={result.display_info.conf}
                      caption={result.display_info.caption}
                    />
                  ) : (
                    /* Regular image display for non-YOLO results */
                    <div className="aspect-video bg-muted rounded-lg overflow-hidden">
                      <img
                        src={result.display_info.image_url}
                        alt={result.display_info?.caption || "Result image"}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          const target = e.target as HTMLImageElement;
                          target.style.display = 'none';
                        }}
                      />
                    </div>
                  )}
                </>
              )}

              {/* Caption/Content */}
              {result.display_info?.caption && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">Caption:</p>
                  <p className="text-sm">{result.display_info.caption}</p>
                </div>
              )}
              
              {/* YOLO-specific class and confidence display */}
              {result.display_info?.engine === 'yolo' && (
                <div className="flex flex-wrap gap-3 mt-2">
                  {result.display_info?.cls && (
                    <Badge variant="outline" className="flex items-center gap-1 px-2 py-1">
                      <Target className="h-3 w-3" />
                      Class: {result.display_info.cls}
                    </Badge>
                  )}
                  {result.display_info?.conf !== undefined && (
                    <Badge variant="outline" className="flex items-center gap-1 px-2 py-1">
                      <div className={`w-2 h-2 rounded-full ${
                        result.display_info.conf >= 0.7 ? 'bg-green-500' : 
                        result.display_info.conf >= 0.5 ? 'bg-yellow-500' : 'bg-red-500'
                      }`} />
                      Confidence: {(result.display_info.conf * 100).toFixed(1)}%
                    </Badge>
                  )}
                </div>
              )}

              {/* Fallback Content */}
              {!result.display_info?.caption && result.content && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">Content:</p>
                  <p className="text-sm">{result.content}</p>
                </div>
              )}

              {/* Source */}
              {result.display_info?.source && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">Source:</p>
                  <p className="text-xs text-muted-foreground">{result.display_info.source}</p>
                </div>
              )}

              {/* URI */}
              {result.uri && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">URI:</p>
                  <p className="text-xs text-muted-foreground font-mono break-all">
                    {result.uri}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
