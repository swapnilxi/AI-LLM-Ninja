"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { motion } from "framer-motion";
import {
    Brain,
    Code,
    Cpu,
    Database,
    Globe,
    Image as ImageIcon,
    Server,
    Zap
} from "lucide-react";

interface TechItem {
  name: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  category: string;
}

const techStack: TechItem[] = [
  {
    name: "Gemini Vision",
    description: "Advanced multimodal AI for image understanding",
    icon: <Brain className="h-5 w-5" />,
    color: "bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-400",
    category: "AI/ML"
  },
  {
    name: "PostgreSQL + pgvector",
    description: "Vector database for similarity search",
    icon: <Database className="h-5 w-5" />,
    color: "bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-400",
    category: "Database"
  },
  {
    name: "SigLIP",
    description: "State-of-the-art vision-language model",
    icon: <Zap className="h-5 w-5" />,
    color: "bg-yellow-100 text-yellow-600 dark:bg-yellow-900 dark:text-yellow-400",
    category: "AI/ML"
  },
  {
    name: "YOLO Segmentation",
    description: "Real-time object detection and segmentation",
    icon: <ImageIcon className="h-5 w-5" />,
    color: "bg-purple-100 text-purple-600 dark:bg-purple-900 dark:text-purple-400",
    category: "Computer Vision"
  },
  {
    name: "FastAPI",
    description: "High-performance Python web framework",
    icon: <Server className="h-5 w-5" />,
    color: "bg-red-100 text-red-600 dark:bg-red-900 dark:text-red-400",
    category: "Backend"
  },
  {
    name: "Next.js 14",
    description: "React framework with server components",
    icon: <Code className="h-5 w-5" />,
    color: "bg-indigo-100 text-indigo-600 dark:bg-indigo-900 dark:text-indigo-400",
    category: "Frontend"
  },
  {
    name: "CUDA",
    description: "GPU acceleration for ML inference",
    icon: <Cpu className="h-5 w-5" />,
    color: "bg-orange-100 text-orange-600 dark:bg-orange-900 dark:text-orange-400",
    category: "Infrastructure"
  },
  {
    name: "REST API",
    description: "RESTful web services for seamless integration",
    icon: <Globe className="h-5 w-5" />,
    color: "bg-teal-100 text-teal-600 dark:bg-teal-900 dark:text-teal-400",
    category: "API"
  }
];

const categories = Array.from(new Set(techStack.map(tech => tech.category)));

export function TechStack() {
  return (
    <Card className="border-0 shadow-lg">
      <CardContent className="p-8">
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold mb-4">Technology Stack</h2>
          <p className="text-muted-foreground">
            Built with cutting-edge technologies for optimal performance and scalability
          </p>
        </div>

        <div className="space-y-8">
          {categories.map((category, categoryIndex) => (
            <div key={category}>
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <div className="w-2 h-2 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full" />
                {category}
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {techStack
                  .filter(tech => tech.category === category)
                  .map((tech, index) => (
                    <motion.div
                      key={tech.name}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ 
                        duration: 0.5, 
                        delay: categoryIndex * 0.1 + index * 0.1 
                      }}
                      whileHover={{ scale: 1.02 }}
                      className="group"
                    >
                      <Card className="border border-muted hover:border-primary/20 transition-all duration-300 hover:shadow-md">
                        <CardContent className="p-4">
                          <div className="flex items-start gap-3">
                            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${tech.color} group-hover:scale-110 transition-transform duration-300`}>
                              {tech.icon}
                            </div>
                            
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <h4 className="font-semibold text-sm">{tech.name}</h4>
                                <Badge variant="outline" className="text-xs">
                                  {tech.category}
                                </Badge>
                              </div>
                              <p className="text-xs text-muted-foreground leading-relaxed">
                                {tech.description}
                              </p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </motion.div>
                  ))}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-8 pt-6 border-t">
          <div className="flex flex-wrap justify-center gap-2">
            {techStack.map((tech) => (
              <Badge 
                key={tech.name} 
                variant="secondary" 
                className="gap-1 hover:scale-105 transition-transform duration-200 cursor-default"
              >
                {tech.icon}
                {tech.name}
              </Badge>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
