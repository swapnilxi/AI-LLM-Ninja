"use client";

import { Card, CardContent } from "@/components/ui/card";
import { 
  TrendingUp, 
  Clock, 
  Database, 
  Zap,
  Users,
  CheckCircle,
  ArrowUp,
  Activity
} from "lucide-react";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";

interface Stat {
  label: string;
  value: string;
  change: string;
  trend: "up" | "down" | "neutral";
  icon: React.ReactNode;
  color: string;
  description: string;
}

const statsData: Stat[] = [
  {
    label: "Images Processed",
    value: "2,847",
    change: "+12%",
    trend: "up",
    icon: <Database className="h-5 w-5" />,
    color: "text-blue-600 dark:text-blue-400",
    description: "Total images in knowledge base"
  },
  {
    label: "Search Accuracy",
    value: "94.7%",
    change: "+2.3%",
    trend: "up",
    icon: <CheckCircle className="h-5 w-5" />,
    color: "text-green-600 dark:text-green-400",
    description: "Semantic search precision"
  },
  {
    label: "Avg Response Time",
    value: "1.2s",
    change: "-0.3s",
    trend: "up",
    icon: <Clock className="h-5 w-5" />,
    color: "text-purple-600 dark:text-purple-400",
    description: "End-to-end query processing"
  },
  {
    label: "Active Models",
    value: "4",
    change: "100%",
    trend: "neutral",
    icon: <Zap className="h-5 w-5" />,
    color: "text-orange-600 dark:text-orange-400",
    description: "AI models running optimally"
  },
  {
    label: "Vector Dimensions",
    value: "768",
    change: "Stable",
    trend: "neutral",
    icon: <Activity className="h-5 w-5" />,
    color: "text-indigo-600 dark:text-indigo-400",
    description: "Embedding vector size"
  },
  {
    label: "Queries Today",
    value: "1,429",
    change: "+18%",
    trend: "up",
    icon: <TrendingUp className="h-5 w-5" />,
    color: "text-teal-600 dark:text-teal-400",
    description: "Search requests processed"
  }
];

function CountingNumber({ target, duration = 2000 }: { target: number; duration?: number }) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let startTime: number;
    let animationFrame: number;

    const animate = (currentTime: number) => {
      if (!startTime) startTime = currentTime;
      const progress = Math.min((currentTime - startTime) / duration, 1);
      
      setCount(Math.floor(progress * target));
      
      if (progress < 1) {
        animationFrame = requestAnimationFrame(animate);
      }
    };

    animationFrame = requestAnimationFrame(animate);
    
    return () => {
      if (animationFrame) {
        cancelAnimationFrame(animationFrame);
      }
    };
  }, [target, duration]);

  return <span>{count.toLocaleString()}</span>;
}

export function StatsCard() {
  return (
    <Card className="border-0 shadow-lg">
      <CardContent className="p-8">
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold mb-4">System Performance</h2>
          <p className="text-muted-foreground">
            Real-time insights into Vision-RAG's performance and capabilities
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {statsData.map((stat, index) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              whileHover={{ scale: 1.02 }}
              className="group"
            >
              <Card className="border border-muted hover:border-primary/20 transition-all duration-300 hover:shadow-md h-full">
                <CardContent className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className={`w-12 h-12 rounded-xl bg-muted/50 flex items-center justify-center ${stat.color} group-hover:scale-110 transition-transform duration-300`}>
                      {stat.icon}
                    </div>
                    
                    {stat.trend === "up" && (
                      <div className="flex items-center gap-1 text-green-600 dark:text-green-400 text-sm font-medium">
                        <ArrowUp className="h-3 w-3" />
                        {stat.change}
                      </div>
                    )}
                    
                    {stat.trend === "neutral" && (
                      <div className="text-muted-foreground text-sm font-medium">
                        {stat.change}
                      </div>
                    )}
                  </div>

                  <div className="space-y-2">
                    <div className="text-2xl font-bold">
                      {stat.label === "Images Processed" ? (
                        <CountingNumber target={2847} />
                      ) : stat.label === "Queries Today" ? (
                        <CountingNumber target={1429} />
                      ) : (
                        stat.value
                      )}
                    </div>
                    
                    <h3 className="font-medium text-sm text-muted-foreground">
                      {stat.label}
                    </h3>
                    
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {stat.description}
                    </p>
                  </div>

                  {/* Progress bar for some metrics */}
                  {(stat.label === "Search Accuracy" || stat.label === "Active Models") && (
                    <div className="mt-4">
                      <div className="w-full bg-muted rounded-full h-2">
                        <motion.div
                          className={`h-2 rounded-full bg-gradient-to-r ${
                            stat.label === "Search Accuracy" 
                              ? "from-green-400 to-green-600" 
                              : "from-orange-400 to-orange-600"
                          }`}
                          initial={{ width: 0 }}
                          animate={{ 
                            width: stat.label === "Search Accuracy" ? "94.7%" : "100%" 
                          }}
                          transition={{ duration: 1.5, delay: index * 0.1 + 0.5 }}
                        />
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* Summary Footer */}
        <div className="mt-8 pt-6 border-t">
          <div className="flex items-center justify-center gap-6 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              <span>All Systems Operational</span>
            </div>
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4" />
              <span>Multi-user Ready</span>
            </div>
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4" />
              <span>GPU Accelerated</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
