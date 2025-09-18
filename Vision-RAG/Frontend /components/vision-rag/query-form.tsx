"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Search } from "lucide-react";
import { useState } from "react";
import { ImageUpload } from "./image-upload";

interface QueryFormProps {
  onSubmit: (query: string, image: string | undefined, k: number) => void;
  isLoading: boolean;
}

export function QueryForm({ onSubmit, isLoading }: QueryFormProps) {
  const [query, setQuery] = useState("");
  const [image, setImage] = useState<string | undefined>();
  const [k, setK] = useState(5);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() || image) {
      onSubmit(query.trim(), image, k);
    }
  };

  const handleImageUpload = (imageUrl: string) => {
    setImage(imageUrl);
  };

  const handleImageRemove = () => {
    setImage(undefined);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Search className="h-5 w-5" />
          Vision-RAG Query
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Text Query */}
          <div className="space-y-2">
            <Label htmlFor="query">Search Query</Label>
            <Textarea
              id="query"
              placeholder="Ask a question about images or describe what you're looking for..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={3}
              className="resize-none"
            />
          </div>

          {/* Image Upload */}
          <ImageUpload
            onImageUpload={handleImageUpload}
            onImageRemove={handleImageRemove}
            uploadedImage={image}
          />

          {/* Number of Results */}
          <div className="space-y-2">
            <Label htmlFor="k">Number of Results</Label>
            <Input
              id="k"
              type="number"
              min="1"
              max="20"
              value={k}
              onChange={(e) => setK(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-24"
            />
          </div>

          {/* Submit Button */}
          <Button 
            type="submit" 
            className="w-full" 
            disabled={isLoading || (!query.trim() && !image)}
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Searching...
              </>
            ) : (
              <>
                <Search className="h-4 w-4 mr-2" />
                Search
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
