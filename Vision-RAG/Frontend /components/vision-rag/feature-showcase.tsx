"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Search, 
  Image as ImageIcon, 
  Brain, 
  Zap,
  Upload,
  MessageSquare,
  Eye,
  Layers,
  ArrowRight,
  PlayCircle,
  Sparkles,
  Target
} from "lucide-react";
import { motion } from "framer-motion";
import { useState } from "react";

interface Feature {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  benefits: string[];
  demo: string;
  tags: string[];
}

const features: Feature[] = [
  {
    id: "multimodal-search",
    title: "Multimodal Search",
    description: "Search through images using natural language descriptions or upload similar images to find related content.",
    icon: <Search className="h-6 w-6" />,
    color: "from-blue-500 to-cyan-500",
    benefits: [
      "Text-to-image search capabilities",
      "Image-to-image similarity search",
      "Cross-modal understanding",
      "Natural language queries"
    ],
    demo: "Try: 'Find images with red cars' or upload a photo",
    tags: ["AI", "Search", "NLP"]
  },
  {
    id: "smart-segmentation",
    title: "Smart Object Detection",
    description: "YOLO-powered segmentation automatically identifies and catalogs objects within images for granular search.",
    icon: <Target className="h-6 w-6" />,
    color: "from-purple-500 to-pink-500",
    benefits: [
      "Real-time object detection",
      "Precise boundary segmentation",
      "Multi-object recognition",
      "Automated tagging"
    ],
    demo: "Upload an image to see automatic object detection",
    tags: ["Computer Vision", "YOLO", "Segmentation"]
  },
  {
    id: "vision-understanding",
    title: "AI Vision Understanding",
    description: "Gemini Vision generates intelligent captions and deep semantic understanding of visual content.",
    icon: <Eye className="h-6 w-6" />,
    color: "from-green-500 to-emerald-500",
    benefits: [
      "Intelligent image captioning",
      "Scene understanding",
      "Context-aware descriptions",
      "Multi-language support"
    ],
    demo: "See how AI describes and understands your images",
    tags: ["Gemini", "Vision AI", "Captions"]
  },
  {
    id: "vector-embeddings",
    title: "Vector Embeddings",
    description: "SigLIP creates powerful multimodal embeddings for semantic similarity and lightning-fast retrieval.",
    icon: <Layers className="h-6 w-6" />,
    color: "from-orange-500 to-red-500",
    benefits: [
      "High-dimensional representations",
      "Semantic similarity matching",
      "Cross-modal embeddings",
      "Scalable vector search"
    ],
    demo: "Experience semantic search across modalities",
    tags: ["SigLIP", "Embeddings", "Vector DB"]
  }
];

export function FeatureShowcase() {
  const [activeFeature, setActiveFeature] = useState<string | null>(null);
  const [hoveredFeature, setHoveredFeature] = useState<string | null>(null);

  return (
    <Card className="border-0 shadow-lg overflow-hidden">
      <CardContent className="p-8">
        <div className="text-center mb-12">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <h2 className="text-3xl font-bold mb-4">Core Features</h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              Discover the powerful capabilities that make Vision-RAG a cutting-edge 
              multimodal AI system for visual content understanding and retrieval.
            </p>
          </motion.div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Feature Cards */}
          <div className="space-y-4">
            {features.map((feature, index) => (
              <motion.div
                key={feature.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                onMouseEnter={() => setHoveredFeature(feature.id)}
                onMouseLeave={() => setHoveredFeature(null)}
                onClick={() => setActiveFeature(
                  activeFeature === feature.id ? null : feature.id
                )}
                className="cursor-pointer group"
              >
                <Card className={`transition-all duration-300 hover:shadow-lg border ${
                  activeFeature === feature.id 
                    ? 'border-primary shadow-lg' 
                    : 'border-muted hover:border-primary/20'
                }`}>
                  <CardContent className="p-6">
                    <div className="flex items-start gap-4">
                      <motion.div
                        className={`w-12 h-12 rounded-xl bg-gradient-to-br ${feature.color} flex items-center justify-center text-white shadow-lg`}
                        whileHover={{ scale: 1.1, rotate: 5 }}
                        transition={{ duration: 0.2 }}
                      >
                        {feature.icon}
                      </motion.div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <h3 className="font-semibold text-lg">{feature.title}</h3>
                          {hoveredFeature === feature.id && (
                            <motion.div
                              initial={{ scale: 0 }}
                              animate={{ scale: 1 }}
                              exit={{ scale: 0 }}
                            >
                              <ArrowRight className="h-4 w-4 text-primary" />
                            </motion.div>
                          )}
                        </div>

                        <p className="text-muted-foreground mb-3 leading-relaxed">
                          {feature.description}
                        </p>

                        <div className="flex flex-wrap gap-1 mb-3">
                          {feature.tags.map((tag) => (
                            <Badge key={tag} variant="secondary" className="text-xs">
                              {tag}
                            </Badge>
                          ))}
                        </div>

                        {activeFeature === feature.id && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.3 }}
                            className="border-t pt-4 mt-4"
                          >
                            <h4 className="font-medium mb-2 flex items-center gap-2">
                              <Sparkles className="h-4 w-4 text-primary" />
                              Key Benefits
                            </h4>
                            <ul className="space-y-1 mb-4">
                              {feature.benefits.map((benefit, idx) => (
                                <motion.li
                                  key={idx}
                                  initial={{ opacity: 0, x: -10 }}
                                  animate={{ opacity: 1, x: 0 }}
                                  transition={{ delay: idx * 0.1 }}
                                  className="text-sm text-muted-foreground flex items-center gap-2"
                                >
                                  <div className="w-1.5 h-1.5 bg-primary rounded-full" />
                                  {benefit}
                                </motion.li>
                              ))}
                            </ul>

                            <div className="bg-muted/50 rounded-lg p-3">
                              <p className="text-sm font-medium mb-1 flex items-center gap-2">
                                <PlayCircle className="h-4 w-4 text-primary" />
                                Try it out:
                              </p>
                              <p className="text-sm text-muted-foreground italic">
                                {feature.demo}
                              </p>
                            </div>
                          </motion.div>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>

          {/* Interactive Demo Area */}
          <div className="lg:sticky lg:top-8">
            <Card className="border-2 border-dashed border-muted-foreground/20 min-h-[400px]">
              <CardContent className="p-8 h-full flex flex-col justify-center">
                {activeFeature ? (
                  <motion.div
                    key={activeFeature}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.4 }}
                    className="text-center"
                  >
                    <div className={`w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br ${
                      features.find(f => f.id === activeFeature)?.color
                    } flex items-center justify-center text-white shadow-xl`}>
                      {features.find(f => f.id === activeFeature)?.icon}
                    </div>
                    
                    <h3 className="text-2xl font-bold mb-4">
                      {features.find(f => f.id === activeFeature)?.title}
                    </h3>
                    
                    <p className="text-muted-foreground mb-6 leading-relaxed">
                      {features.find(f => f.id === activeFeature)?.description}
                    </p>

                    <div className="space-y-4">
                      <Button 
                        size="lg" 
                        className="w-full gap-2"
                        variant="default"
                      >
                        <Upload className="h-4 w-4" />
                        Try This Feature
                      </Button>
                      
                      <Button 
                        size="sm" 
                        variant="outline"
                        className="w-full gap-2"
                      >
                        <MessageSquare className="h-4 w-4" />
                        Learn More
                      </Button>
                    </div>
                  </motion.div>
                ) : (
                  <div className="text-center space-y-6">
                    <motion.div
                      animate={{ 
                        rotate: [0, 10, -10, 0],
                        scale: [1, 1.1, 1]
                      }}
                      transition={{ 
                        duration: 4,
                        repeat: Infinity,
                        repeatType: "reverse"
                      }}
                      className="w-16 h-16 mx-auto bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center text-white shadow-lg"
                    >
                      <Brain className="h-8 w-8" />
                    </motion.div>
                    
                    <div>
                      <h3 className="text-xl font-semibold mb-2">Interactive Demo</h3>
                      <p className="text-muted-foreground mb-4">
                        Click on any feature to explore its capabilities and see how 
                        Vision-RAG can transform your visual content workflow.
                      </p>
                      
                      <Button variant="outline" className="gap-2">
                        <Zap className="h-4 w-4" />
                        Explore Features
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
