"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { CheckCircle2, Eye, Image as ImageIcon, Layers, Loader2, Upload, XCircle } from "lucide-react";
import { useRef, useState } from "react";

interface IngestResult {
  status: string;
  image_id?: string;
  caption?: string;
  segments?: number;
  engine?: string;
  segments_detected?: number;
}

export function IngestForm() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [engine, setEngine] = useState<"gemini" | "siglip">("gemini");
  const [useSegmentation, setUseSegmentation] = useState(true);
  const [useYolo, setUseYolo] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [error, setError] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      setResult(null);
      setError("");
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith('image/')) {
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      setResult(null);
      setError("");
    }
  };

  const handleIngest = async () => {
    if (!selectedFile) {
      setError("Please select an image file");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      // Choose endpoint based on whether YOLO is enabled
      const endpoint = useYolo 
        ? `/ingest/images:yolo?embedding_engine=${engine}&store_full_image=${useSegmentation}`
        : `/ingest/image:llm?engine=${engine}&segment=${useSegmentation}&yolo=false`;

      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      const response = await fetch(`${backendUrl}${endpoint}`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();
      setResult(data);
      
      // Clear file after successful upload
      setTimeout(() => {
        setSelectedFile(null);
        setPreviewUrl("");
      }, 3000);
    } catch (err: any) {
      setError(err.message || "Failed to ingest image");
      console.error("Ingestion error:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Upload className="h-5 w-5" />
          Ingest Image
        </CardTitle>
        <CardDescription>
          Upload an image to process and add to the database
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Image Upload Area */}
        <div className="space-y-2">
          <Label>Image File</Label>
          {previewUrl ? (
            <div className="relative">
              <img 
                src={previewUrl} 
                alt="Preview" 
                className="w-full h-48 object-contain rounded-lg border bg-muted"
              />
              <Button
                size="sm"
                variant="destructive"
                className="absolute top-2 right-2"
                onClick={() => {
                  setSelectedFile(null);
                  setPreviewUrl("");
                  setResult(null);
                }}
              >
                Clear
              </Button>
            </div>
          ) : (
            <div
              className="border-2 border-dashed rounded-lg p-8 text-center hover:border-primary/50 transition-colors cursor-pointer"
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <ImageIcon className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
              <p className="text-sm font-medium mb-1">
                Drop an image here, or click to select
              </p>
              <p className="text-xs text-muted-foreground">
                PNG, JPG, GIF, WebP supported
              </p>
            </div>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleFileSelect}
            className="hidden"
          />
        </div>

        {/* Engine Selection (simple buttons) */}
        <div className="space-y-2">
          <Label>Embedding Engine</Label>
          <div className="flex gap-2">
            <Button
              type="button"
              variant={engine === "gemini" ? "default" : "outline"}
              onClick={() => setEngine("gemini")}
              className="flex-1"
            >
              Gemini
            </Button>
            <Button
              type="button"
              variant={engine === "siglip" ? "default" : "outline"}
              onClick={() => setEngine("siglip")}
              className="flex-1"
            >
              SigLIP
            </Button>
          </div>
        </div>

        {/* Processing Options (simple checkboxes) */}
        <div className="space-y-3 border rounded-lg p-4">
          <Label className="text-sm font-medium">Processing Options</Label>
          
          <label className="flex items-center justify-between cursor-pointer">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">Gemini Segmentation</span>
            </div>
            <input
              type="checkbox"
              checked={useSegmentation}
              onChange={(e) => setUseSegmentation(e.target.checked)}
              className="h-4 w-4"
            />
          </label>

          <label className="flex items-center justify-between cursor-pointer">
            <div className="flex items-center gap-2">
              <Eye className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">YOLO Object Detection</span>
            </div>
            <input
              type="checkbox"
              checked={useYolo}
              onChange={(e) => setUseYolo(e.target.checked)}
              className="h-4 w-4"
            />
          </label>
        </div>

        {/* Ingest Button */}
        <Button 
          onClick={handleIngest} 
          disabled={!selectedFile || loading}
          className="w-full"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <Upload className="h-4 w-4 mr-2" />
              Ingest Image
            </>
          )}
        </Button>

        {/* Result Display */}
        {result && (
          <div className="bg-green-50 border-2 border-green-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
              <div className="space-y-2 flex-1">
                <p className="font-medium text-green-900">✓ Image ingested successfully!</p>
                <div className="text-sm text-green-800 space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="bg-white">
                      {result.image_id}
                    </Badge>
                  </div>
                  {result.caption && (
                    <p className="italic">"{result.caption}"</p>
                  )}
                  {(result.segments !== undefined || result.segments_detected !== undefined) && (
                    <p>
                      {result.segments || result.segments_detected} segment(s) detected
                    </p>
                  )}
                  {result.engine && (
                    <p>
                      Engine: <span className="font-medium">{result.engine}</span>
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border-2 border-red-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <XCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-medium text-red-900">Failed to ingest image</p>
                <p className="text-sm text-red-800 mt-1">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Info */}
        <div className="text-xs text-muted-foreground space-y-1 pt-2 border-t">
          <p>• Images are stored in the database with embeddings</p>
          <p>• Gemini generates captions and optional region descriptions</p>
          <p>• YOLO detects objects and creates searchable segments</p>
          <p>• You can query uploaded images immediately after ingestion</p>
        </div>
      </CardContent>
    </Card>
  );
}
