"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { QueryForm } from "@/components/vision-rag/query-form";
import { ResultsDisplay } from "@/components/vision-rag/results-display";
import { StatusIndicator } from "@/components/vision-rag/status-indicator";
import { visionRagApi } from "@/lib/api/client";
import { QueryResponse } from "@/types/api";
import {
  ArrowRight,
  Brain,
  Database,
  Eye,
  Image as ImageIcon,
  MessageSquare,
  Search,
  Sparkles,
  Upload,
  Zap
} from "lucide-react";
import { useState } from "react";

export default function Home() {
  const [showChat, setShowChat] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleQuery = async (query: string, image: string | undefined, k: number) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await visionRagApi.queryImage({
        question: query,
        image: image,
        k: k
      });
      
      if (response.error) {
        setError(response.error);
        setResults(null);
      } else {
        setResults(response);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      setResults(null);
    } finally {
      setIsLoading(false);
    }
  };

  if (showChat) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
        <div className="container mx-auto px-4 py-8 max-w-7xl">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center">
                <Eye className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold">Vision-RAG</h1>
                <p className="text-sm text-muted-foreground">Multimodal AI Search</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <StatusIndicator />
              <Button 
                variant="outline" 
                onClick={() => setShowChat(false)}
                className="gap-2"
              >
                <ArrowRight className="h-4 w-4 rotate-180" />
                Back to Home
              </Button>
            </div>
          </div>

          {/* Main Content */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Query Form */}
            <div className="lg:col-span-1">
              <QueryForm onSubmit={handleQuery} isLoading={isLoading} />
            </div>

            {/* Results */}
            <div className="lg:col-span-2">
              {error && (
                <Card className="border-red-200 bg-red-50 mb-6">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 bg-red-500 rounded-full" />
                      <span className="font-medium text-red-800">Error</span>
                    </div>
                    <p className="text-red-700 mt-1">{error}</p>
                  </CardContent>
                </Card>
              )}

              {results ? (
                <ResultsDisplay 
                  results={results.results} 
                  query={results.query_text}
                  method={results.method}
                />
              ) : (
                <Card className="h-96">
                  <CardContent className="h-full flex items-center justify-center">
                    <div className="text-center space-y-4">
                      <div className="w-16 h-16 mx-auto bg-muted rounded-full flex items-center justify-center">
                        <Search className="h-8 w-8 text-muted-foreground" />
                      </div>
                      <div>
                        <h3 className="font-medium mb-2">Ready to Search</h3>
                        <p className="text-sm text-muted-foreground max-w-md">
                          Enter a text query or upload an image to start searching through the knowledge base.
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 dark:from-slate-900 dark:via-slate-800 dark:to-indigo-900">
      {/* Hero Section */}
      <div className="container mx-auto px-4 py-16 max-w-6xl">
        {/* Header */}
        <div className="text-center mb-16">
          <div className="flex items-center justify-center mb-6">
            <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg">
              <Eye className="h-8 w-8 text-white" />
            </div>
          </div>
          
          <h1 className="text-5xl font-bold mb-6 bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-300 bg-clip-text text-transparent">
            Vision-RAG
          </h1>
          
          <p className="text-xl text-muted-foreground mb-8 max-w-3xl mx-auto leading-relaxed">
            Advanced <strong>Vision + Retrieval-Augmented Generation</strong> system that understands both images and text. 
            Search through visual content using natural language or image queries with AI-powered precision.
          </p>

          <div className="flex flex-wrap justify-center gap-2 mb-8">
            <Badge variant="secondary" className="gap-1">
              <Zap className="h-3 w-3" />
              Gemini Vision
            </Badge>
            <Badge variant="secondary" className="gap-1">
              <Database className="h-3 w-3" />
              pgvector
            </Badge>
            <Badge variant="secondary" className="gap-1">
              <Brain className="h-3 w-3" />
              SigLIP
            </Badge>
            <Badge variant="secondary" className="gap-1">
              <ImageIcon className="h-3 w-3" />
              YOLO Segmentation
            </Badge>
          </div>
        </div>

        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-16">
          {/* Multimodal Search */}
          <Card className="border-0 shadow-lg hover:shadow-xl transition-shadow duration-300">
            <CardContent className="p-6">
              <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900 rounded-lg flex items-center justify-center mb-4">
                <Search className="h-6 w-6 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="text-xl font-semibold mb-3">Multimodal Search</h3>
              <p className="text-muted-foreground leading-relaxed">
                Search using text descriptions, upload images, or combine both for more precise results. 
                Our AI understands context across modalities.
              </p>
            </CardContent>
          </Card>

          {/* Smart Segmentation */}
          <Card className="border-0 shadow-lg hover:shadow-xl transition-shadow duration-300">
            <CardContent className="p-6">
              <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900 rounded-lg flex items-center justify-center mb-4">
                <ImageIcon className="h-6 w-6 text-purple-600 dark:text-purple-400" />
              </div>
              <h3 className="text-xl font-semibold mb-3">Smart Segmentation</h3>
              <p className="text-muted-foreground leading-relaxed">
                YOLO-powered object detection and segmentation automatically identifies and catalogs 
                objects within images for granular search capabilities.
              </p>
            </CardContent>
          </Card>

          {/* AI-Powered Understanding */}
          <Card className="border-0 shadow-lg hover:shadow-xl transition-shadow duration-300">
            <CardContent className="p-6">
              <div className="w-12 h-12 bg-green-100 dark:bg-green-900 rounded-lg flex items-center justify-center mb-4">
                <Brain className="h-6 w-6 text-green-600 dark:text-green-400" />
              </div>
              <h3 className="text-xl font-semibold mb-3">AI Understanding</h3>
              <p className="text-muted-foreground leading-relaxed">
                Gemini Vision generates intelligent captions and embeddings, while SigLIP provides 
                robust multimodal representations for semantic search.
              </p>
            </CardContent>
          </Card>
        </div>

        {/* How It Works */}
        <Card className="mb-16 border-0 shadow-lg">
          <CardContent className="p-8">
            <h2 className="text-3xl font-bold text-center mb-8">How Vision-RAG Works</h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
              <div className="text-center">
                <div className="w-16 h-16 bg-blue-500 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Upload className="h-8 w-8 text-white" />
                </div>
                <h3 className="font-semibold mb-2">1. Ingest</h3>
                <p className="text-sm text-muted-foreground">
                  Upload images or documents. YOLO segments objects and Gemini generates captions.
                </p>
              </div>
              
              <div className="text-center">
                <div className="w-16 h-16 bg-purple-500 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Sparkles className="h-8 w-8 text-white" />
                </div>
                <h3 className="font-semibold mb-2">2. Embed</h3>
                <p className="text-sm text-muted-foreground">
                  Convert visual and textual content into high-dimensional vector embeddings.
                </p>
              </div>
              
              <div className="text-center">
                <div className="w-16 h-16 bg-green-500 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Database className="h-8 w-8 text-white" />
                </div>
                <h3 className="font-semibold mb-2">3. Store</h3>
                <p className="text-sm text-muted-foreground">
                  Index embeddings in PostgreSQL with pgvector for lightning-fast similarity search.
                </p>
              </div>
              
              <div className="text-center">
                <div className="w-16 h-16 bg-orange-500 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Search className="h-8 w-8 text-white" />
                </div>
                <h3 className="font-semibold mb-2">4. Retrieve</h3>
                <p className="text-sm text-muted-foreground">
                  Query with text or images to find semantically similar content across modalities.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* CTA Section */}
        <div className="text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to Explore?</h2>
          <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
            Experience the power of multimodal AI search. Upload an image, ask a question, 
            or search through visual content with natural language.
          </p>
          
          <Button 
            size="lg" 
            onClick={() => setShowChat(true)}
            className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white px-8 py-4 text-lg gap-3 shadow-lg hover:shadow-xl transition-all duration-300"
          >
            <MessageSquare className="h-5 w-5" />
            Start Chat
            <ArrowRight className="h-5 w-5" />
          </Button>
        </div>

        {/* Status Indicator */}
        <div className="mt-16 max-w-md mx-auto">
          <StatusIndicator />
        </div>
      </div>
    </div>
  );
}
