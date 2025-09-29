"use client";

import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn, getStatusColor, getStatusBgColor } from "@/lib/utils";
import { RefreshCw, Wifi, WifiOff, AlertTriangle } from "lucide-react";

interface HealthResponse {
  status: string;
  timestamp: string;
  service: string;
  version: string;
}

export default function HealthStatus() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(
        process.env.NEXT_PUBLIC_API_URL + "/api/v1/health"
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data: HealthResponse = await response.json();
      setHealth(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch health status"
      );
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    // Refresh health status every 30 seconds
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const getStatusText = () => {
    if (loading) return "Checking...";
    if (error) return "Offline";
    if (health?.status === "healthy") return "Online";
    return health?.status || "Unknown";
  };

  const getStatusIcon = () => {
    if (loading) return <RefreshCw className="size-4 animate-spin" />;
    if (error) return <WifiOff className="size-4" />;
    if (health?.status === "healthy") return <Wifi className="size-4" />;
    return <AlertTriangle className="size-4" />;
  };

  const statusText = getStatusText();
  const statusColor = getStatusColor(statusText.toLowerCase());
  const statusBgColor = getStatusBgColor(statusText.toLowerCase());

  return (
    <Card className="h-fit">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">API Status</CardTitle>
          <div className="flex items-center gap-2">
            <div className={cn("w-2 h-2 rounded-full", statusBgColor)} />
            <div
              className={cn("flex items-center gap-1 font-medium", statusColor)}
            >
              {getStatusIcon()}
              <span className="text-sm">{statusText}</span>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {error && (
          <div className="status-error border rounded-md p-3">
            <p className="text-sm font-medium">Connection Error</p>
            <p className="text-xs text-muted-foreground mt-1">
              Make sure the backend is running on{" "}
              {process.env.NEXT_PUBLIC_API_URL}
            </p>
          </div>
        )}

        {health && (
          <div className="space-y-3">
            <div className="grid gap-2 text-sm">
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Service</span>
                <span className="font-mono text-xs">{health.service}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Version</span>
                <span className="font-mono text-xs">{health.version}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Last Check</span>
                <span className="font-mono text-xs">
                  {new Date(health.timestamp).toLocaleTimeString()}
                </span>
              </div>
            </div>
          </div>
        )}

        <Button
          onClick={fetchHealth}
          disabled={loading}
          variant="outline"
          size="sm"
          className="w-full"
        >
          <RefreshCw className={cn("size-3", loading && "animate-spin")} />
          {loading ? "Checking..." : "Refresh Status"}
        </Button>
      </CardContent>
    </Card>
  );
}
