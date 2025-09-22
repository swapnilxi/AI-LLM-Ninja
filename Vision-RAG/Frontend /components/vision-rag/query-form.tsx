"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Eye, Hash, Loader2, MessageSquare, Search, Sparkles, Upload } from "lucide-react";
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
    <Card className="bg-gradient-to-br from-white via-blue-50 to-purple-50 dark:from-slate-900 dark:via-blue-950 dark:to-purple-950 border-0 shadow-xl">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-3">
          <div className="w-8 h-8 bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 rounded-lg flex items-center justify-center shadow-lg">
            <Eye className="h-4 w-4 text-white" />
          </div>
          <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent font-bold">
            Vision-RAG Query
          </span>
          <div className="ml-auto">
            <div className="w-6 h-6 bg-gradient-to-br from-yellow-400 to-orange-500 rounded-full flex items-center justify-center">
              <Sparkles className="h-3 w-3 text-white" />
            </div>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Text Query */}
          <div className="space-y-3">
            <Label htmlFor="query" className="flex items-center gap-2 text-sm font-medium">
              <div className="w-5 h-5 bg-gradient-to-br from-green-500 to-emerald-600 rounded-md flex items-center justify-center">
                <MessageSquare className="h-3 w-3 text-white" />
              </div>
              Search Query
            </Label>
            <div className="relative">
              <Textarea
                id="query"
                placeholder="Ask a question about images or describe what you're looking for..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                rows={3}
                className="resize-none border-2 border-gray-200 dark:border-gray-700 focus:border-blue-500 dark:focus:border-blue-400 bg-white/80 dark:bg-slate-800/80 backdrop-blur-sm transition-all duration-200 shadow-sm"
              />
              <div className="absolute top-2 right-2">
                <div className="w-6 h-6 bg-gradient-to-br from-blue-400 to-purple-500 rounded-full flex items-center justify-center opacity-20">
                  <Search className="h-3 w-3 text-white" />
                </div>
              </div>
            </div>
          </div>

          {/* Image Upload Section */}
          <div className="space-y-3">
            <Label className="flex items-center gap-2 text-sm font-medium">
              <div className="w-5 h-5 bg-gradient-to-br from-orange-500 to-red-600 rounded-md flex items-center justify-center">
                <Upload className="h-3 w-3 text-white" />
              </div>
              Image Upload
            </Label>
            <div className="p-4 bg-gradient-to-br from-orange-50 to-red-50 dark:from-orange-950/30 dark:to-red-950/30 rounded-lg border-2 border-dashed border-orange-200 dark:border-orange-800">
              <ImageUpload
                onImageUpload={handleImageUpload}
                onImageRemove={handleImageRemove}
                uploadedImage={image}
              />
            </div>
          </div>

          {/* Number of Results */}
          <div className="space-y-3">
            <Label htmlFor="k" className="flex items-center gap-2 text-sm font-medium">
              <div className="w-5 h-5 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-md flex items-center justify-center">
                <Hash className="h-3 w-3 text-white" />
              </div>
              Number of Results
            </Label>
            <div className="relative w-32">
              <Input
                id="k"
                type="number"
                min="1"
                max="20"
                value={k}
                onChange={(e) => setK(Math.max(1, parseInt(e.target.value) || 1))}
                className="border-2 border-gray-200 dark:border-gray-700 focus:border-purple-500 dark:focus:border-purple-400 bg-white/80 dark:bg-slate-800/80 backdrop-blur-sm transition-all duration-200 shadow-sm"
              />
            </div>
          </div>

          {/* Submit Button */}
          <Button 
            type="submit" 
            className="w-full bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 hover:from-blue-700 hover:via-purple-700 hover:to-pink-700 text-white font-semibold py-3 px-6 text-base shadow-xl hover:shadow-2xl transition-all duration-300 transform hover:scale-[1.02] border-0" 
            disabled={isLoading || (!query.trim() && !image)}
          >
            {isLoading ? (
              <>
                <Loader2 className="h-5 w-5 mr-3 animate-spin" />
                <span className="flex items-center gap-2">
                  Searching with AI
                  <div className="flex gap-1">
                    <div className="w-1 h-1 bg-white rounded-full animate-bounce" style={{animationDelay: '0ms'}} />
                    <div className="w-1 h-1 bg-white rounded-full animate-bounce" style={{animationDelay: '150ms'}} />
                    <div className="w-1 h-1 bg-white rounded-full animate-bounce" style={{animationDelay: '300ms'}} />
                  </div>
                </span>
              </>
            ) : (
              <>
                <Search className="h-5 w-5 mr-3" />
                <span>Start AI Search</span>
                <Sparkles className="h-4 w-4 ml-2" />
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
