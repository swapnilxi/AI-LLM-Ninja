"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { visionRagApi } from "@/lib/api/client";
import { HealthResponse } from "@/types/api";
import { Activity, AlertCircle, Database, Wifi, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";

export function StatusIndicator() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const checkHealth = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await visionRagApi.health();
      setHealth(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setHealth(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
    // Check health every 30 seconds
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'ok':
        return 'bg-green-500';
      case 'error':
        return 'bg-red-500';
      default:
        return 'bg-yellow-500';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'ok':
        return <Wifi className="h-3 w-3" />;
      case 'error':
        return <WifiOff className="h-3 w-3" />;
      default:
        return <AlertCircle className="h-3 w-3" />;
    }
  };

  if (error) {
    return (
      <Card className="border-red-200 bg-red-50">
        <CardContent className="p-4">
          <div className="flex items-center gap-2">
            <WifiOff className="h-4 w-4 text-red-600" />
            <span className="text-sm font-medium text-red-600">Backend Offline</span>
            <Badge variant="destructive" className="text-xs">
              Error
            </Badge>
          </div>
          <p className="text-xs text-red-600 mt-1">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-muted rounded-full animate-pulse" />
            <span className="text-sm font-medium text-muted-foreground">Checking status...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!health) {
    return null;
  }

  return (
    <Card>
      <CardContent className="px-4 py-3">
        {/* System Status and Indicators in Row */}
        <div className="flex items-center gap-4">
          {/* System Status Label */}
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            <span className="text-sm font-medium">System Status</span>
          </div>
          
          {/* Backend Status */}
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${getStatusColor(health.status)}`} />
            <span className="text-sm">Backend</span>
            <Badge 
              variant={health.status === 'ok' ? 'default' : 'destructive'} 
              className="text-xs gap-1"
            >
              {getStatusIcon(health.status)}
              {health.status}
            </Badge>
          </div>

          {/* Database Status */}
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${getStatusColor(health.db_connection)}`} />
            <span className="text-sm">Database</span>
            <Badge 
              variant={health.db_connection === 'ok' ? 'default' : 'destructive'} 
              className="text-xs gap-1"
            >
              <Database className="h-3 w-3" />
              {health.db_connection}
            </Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
