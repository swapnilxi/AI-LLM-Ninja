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

  const handleQuery = async (query: string, image: string | undefined, k: number, engine: 'gemini' | 'siglip') => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await visionRagApi.queryImage({
        question: query,
        image: image,
        k: k,
        engine
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
                <Card className="h-96 bg-gradient-to-br from-slate-50 via-blue-50 to-purple-50 dark:from-slate-800 dark:via-blue-900 dark:to-purple-900 border-0 shadow-lg">
                  <CardContent className="h-full flex items-center justify-center">
                    <div className="text-center space-y-6">
                      <div className="relative">
                        <div className="w-20 h-20 mx-auto bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 rounded-full flex items-center justify-center shadow-xl animate-pulse">
                          <Search className="h-10 w-10 text-white" />
                        </div>
                        <div className="absolute -top-1 -right-1 w-6 h-6 bg-gradient-to-br from-yellow-400 to-orange-500 rounded-full flex items-center justify-center shadow-lg">
                          <Sparkles className="h-3 w-3 text-white" />
                        </div>
                      </div>
                      <div className="space-y-3">
                        <h3 className="text-xl font-semibold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">Ready to Search</h3>
                        <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
                          Enter a text query or upload an image to start searching through the knowledge base with AI-powered precision.
                        </p>
                        <div className="flex items-center justify-center gap-2 pt-2">
                          <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{animationDelay: '0ms'}} />
                          <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{animationDelay: '150ms'}} />
                          <div className="w-2 h-2 bg-pink-400 rounded-full animate-bounce" style={{animationDelay: '300ms'}} />
                        </div>
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
      <div className="container mx-auto px-4 py-20 max-w-5xl">
        {/* Main Header */}
        <div className="text-center mb-20">
          <div className="flex items-center justify-center mb-8">
            <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-3xl flex items-center justify-center shadow-xl">
              <Eye className="h-10 w-10 text-white" />
            </div>
          </div>
          
          <h1 className="text-6xl font-bold mb-8 bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-300 bg-clip-text text-transparent">
            Vision-RAG
          </h1>
          
          <p className="text-2xl text-muted-foreground mb-12 max-w-4xl mx-auto leading-relaxed">
            Revolutionary <strong>AI-powered multimodal search engine</strong> that understands both images and text. 
            Ask questions in natural language, upload images, and discover relevant content with unprecedented accuracy.
          </p>

          {/* Key Features Badges */}
          <div className="flex flex-wrap justify-center gap-3 mb-12">
            <Badge variant="secondary" className="gap-2 px-4 py-2 text-sm">
              <Zap className="h-4 w-4" />
              Gemini Vision AI
            </Badge>
            <Badge variant="secondary" className="gap-2 px-4 py-2 text-sm">
              <Database className="h-4 w-4" />
              Vector Database
            </Badge>
            <Badge variant="secondary" className="gap-2 px-4 py-2 text-sm">
              <Brain className="h-4 w-4" />
              Smart Embeddings
            </Badge>
            <Badge variant="secondary" className="gap-2 px-4 py-2 text-sm">
              <ImageIcon className="h-4 w-4" />
              Object Detection
            </Badge>
          </div>

          {/* CTA Button */}
          <div className="mb-16">
            <Button 
              size="lg" 
              onClick={() => setShowChat(true)}
              className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white px-12 py-6 text-xl font-semibold gap-4 shadow-2xl hover:shadow-3xl transition-all duration-300 transform hover:scale-105 rounded-2xl"
            >
              <MessageSquare className="h-6 w-6" />
              Start Chat
              <ArrowRight className="h-6 w-6" />
            </Button>
            <p className="text-sm text-muted-foreground mt-4">
              No signup required • Start searching instantly
            </p>
          </div>
        </div>

        {/* What is Vision-RAG Section */}
        <Card className="mb-20 border-0 shadow-xl bg-white/80 dark:bg-slate-800/80 backdrop-blur-sm">
          <CardContent className="p-12">
            <div className="text-center mb-12">
              <h2 className="text-4xl font-bold mb-6">What is Vision-RAG?</h2>
              <p className="text-lg text-muted-foreground max-w-3xl mx-auto leading-relaxed">
                Vision-RAG combines the power of computer vision, natural language processing, and vector databases 
                to create an intelligent search system that truly understands visual content.
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
              {/* Left Side - Explanation */}
              <div className="space-y-8">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900 rounded-xl flex items-center justify-center flex-shrink-0">
                    <Upload className="h-6 w-6 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold mb-2">Upload & Analyze</h3>
                    <p className="text-muted-foreground">
                      Upload images and let our AI automatically detect objects, generate captions, 
                      and create semantic embeddings for intelligent indexing.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900 rounded-xl flex items-center justify-center flex-shrink-0">
                    <Search className="h-6 w-6 text-purple-600 dark:text-purple-400" />
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold mb-2">Smart Search</h3>
                    <p className="text-muted-foreground">
                      Search using natural language descriptions or upload similar images. 
                      Our AI understands context and finds semantically similar content.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-green-100 dark:bg-green-900 rounded-xl flex items-center justify-center flex-shrink-0">
                    <Brain className="h-6 w-6 text-green-600 dark:text-green-400" />
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold mb-2">AI Understanding</h3>
                    <p className="text-muted-foreground">
                      Powered by Gemini Vision and SigLIP, providing deep understanding 
                      of visual content and cross-modal relationships.
                    </p>
                  </div>
                </div>
              </div>

              {/* Right Side - Visual Representation */}
              <div className="relative">
                <Card className="border-2 border-dashed border-muted-foreground/30 p-8 text-center">
                  <div className="space-y-6">
                    <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto">
                      <Eye className="h-8 w-8 text-white" />
                    </div>
                    <div>
                      <h3 className="text-xl font-semibold mb-2">Try It Now</h3>
                      <p className="text-muted-foreground mb-6">
                        Experience the power of multimodal AI search
                      </p>
                      <div className="space-y-3">
                        <div className="flex items-center gap-3 text-sm text-muted-foreground">
                          <div className="w-2 h-2 bg-green-500 rounded-full" />
                          Ask: "Show me images with red cars"
                        </div>
                        <div className="flex items-center gap-3 text-sm text-muted-foreground">
                          <div className="w-2 h-2 bg-blue-500 rounded-full" />
                          Upload an image to find similar ones
                        </div>
                        <div className="flex items-center gap-3 text-sm text-muted-foreground">
                          <div className="w-2 h-2 bg-purple-500 rounded-full" />
                          Describe what you're looking for
                        </div>
                      </div>
                    </div>
                  </div>
                </Card>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* How It Works */}
        <Card className="mb-20 border-0 shadow-xl">
          <CardContent className="p-12">
            <h2 className="text-4xl font-bold text-center mb-12">How Vision-RAG Works</h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
              <div className="text-center group">
                <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform duration-300 shadow-lg">
                  <Upload className="h-10 w-10 text-white" />
                </div>
                <h3 className="text-xl font-semibold mb-3">1. Upload</h3>
                <p className="text-muted-foreground leading-relaxed">
                  Upload images or documents. AI automatically detects objects and generates intelligent captions.
                </p>
              </div>
              
              <div className="text-center group">
                <div className="w-20 h-20 bg-gradient-to-br from-purple-500 to-purple-600 rounded-full flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform duration-300 shadow-lg">
                  <Sparkles className="h-10 w-10 text-white" />
                </div>
                <h3 className="text-xl font-semibold mb-3">2. Process</h3>
                <p className="text-muted-foreground leading-relaxed">
                  Convert visual and textual content into high-dimensional semantic embeddings.
                </p>
              </div>
              
              <div className="text-center group">
                <div className="w-20 h-20 bg-gradient-to-br from-green-500 to-green-600 rounded-full flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform duration-300 shadow-lg">
                  <Database className="h-10 w-10 text-white" />
                </div>
                <h3 className="text-xl font-semibold mb-3">3. Index</h3>
                <p className="text-muted-foreground leading-relaxed">
                  Store embeddings in PostgreSQL with pgvector for lightning-fast similarity search.
                </p>
              </div>
              
              <div className="text-center group">
                <div className="w-20 h-20 bg-gradient-to-br from-orange-500 to-orange-600 rounded-full flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform duration-300 shadow-lg">
                  <Search className="h-10 w-10 text-white" />
                </div>
                <h3 className="text-xl font-semibold mb-3">4. Search</h3>
                <p className="text-muted-foreground leading-relaxed">
                  Query with natural language or images to find semantically similar content instantly.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Final CTA Section */}
        <div className="text-center bg-gradient-to-r from-blue-50 to-purple-50 dark:from-slate-800 dark:to-slate-700 rounded-3xl p-12">
          <h2 className="text-4xl font-bold mb-6">Ready to Experience the Future?</h2>
          <p className="text-xl text-muted-foreground mb-10 max-w-3xl mx-auto leading-relaxed">
            Join the revolution in visual content search. Upload an image, ask a question, 
            or describe what you're looking for – and watch Vision-RAG understand and deliver results 
            with unprecedented accuracy.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Button 
              size="lg" 
              onClick={() => setShowChat(true)}
              className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white px-10 py-6 text-lg font-semibold gap-3 shadow-xl hover:shadow-2xl transition-all duration-300 transform hover:scale-105 rounded-xl"
            >
              <MessageSquare className="h-5 w-5" />
              Start Exploring Now
              <ArrowRight className="h-5 w-5" />
            </Button>
            
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              <span>Live demo • No account required</span>
            </div>
          </div>
        </div>

        {/* Status Indicator */}
        <div className="mt-16 max-w-md mx-auto">
          <StatusIndicator />
        </div>
      </div>
    </div>
  );
}
