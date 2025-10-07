"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, GitCompare, FileText, Loader2, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import demoComparison from "@/fixtures/comparison-demo.json";
import DemoComparisonResults from "./DemoComparisonResults";

interface UploadedFile {
  id: string;
  file: File;
  preview: string;
  category?: string;
  status?: string;
  fileSize?: number; // Store actual file size from backend
}

type DemoComparisonResult = typeof demoComparison;

interface ComparisonAreaProps {
  selectedFiles: UploadedFile[];
  onStartComparison: () => void;
  isComparing: boolean;
  className?: string;
  onComparisonComplete?: () => void;
  autoStartToken?: number;
}

const COMPARISON_STORAGE_KEY = "comparisonArea:demoResults";

const ComparisonArea = ({
  selectedFiles,
  onStartComparison,
  isComparing,
  className,
  onComparisonComplete,
  autoStartToken = 0,
}: ComparisonAreaProps) => {
  const [comparisonResults, setComparisonResults] =
    useState<DemoComparisonResult | null>(null);
  const [comparisonProgress, setComparisonProgress] = useState(0);
  const [comparisonStep, setComparisonStep] = useState<string>("");
  const lastAutoStartTokenRef = useRef(0);

  useEffect(() => {
    if (typeof window === "undefined") return;

    try {
      const stored = window.localStorage.getItem(COMPARISON_STORAGE_KEY);
      if (!stored) return;

      const parsed = JSON.parse(stored) as DemoComparisonResult;
      setComparisonResults(parsed);
      setComparisonProgress(100);
      setComparisonStep("Comparison loaded from last session.");
    } catch (error) {
      console.error("Failed to load stored comparison results", error);
      window.localStorage.removeItem(COMPARISON_STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;

    if (comparisonResults) {
      window.localStorage.setItem(
        COMPARISON_STORAGE_KEY,
        JSON.stringify(comparisonResults)
      );
    } else {
      window.localStorage.removeItem(COMPARISON_STORAGE_KEY);
    }
  }, [comparisonResults]);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const demoSteps = useMemo(
    () => [
      { label: "Preparing documents", progress: 10 },
      { label: "Extracting key data", progress: 35 },
      { label: "Analyzing differences", progress: 65 },
      { label: "Summarizing findings", progress: 85 },
      { label: "Generating comparison report", progress: 100 },
    ],
    []
  );

  const handleStartComparison = useCallback(() => {
    if (selectedFiles.length < 2) return;

    const completedFiles = selectedFiles.filter(
      (file) => file.status !== "uploading" && file.status !== "failed"
    );

    if (completedFiles.length < 2) {
      toast.error(
        "Please wait for all files to finish uploading before comparing"
      );
      return;
    }

    onStartComparison();
    setComparisonResults(null);
    setComparisonProgress(0);
    setComparisonStep("Preparing comparison workspace...");

    demoSteps.forEach((step, index) => {
      const delay = 900 * (index + 1);
      setTimeout(() => {
        setComparisonProgress(step.progress);
        setComparisonStep(step.label);

        if (index === demoSteps.length - 1) {
          setTimeout(() => {
            setComparisonResults(demoComparison);
            setComparisonStep("Comparison completed. Enjoy the findings!");
            toast.success("Document comparison completed successfully!");
            onComparisonComplete?.();
          }, 600);
        }
      }, delay);
    });
  }, [demoSteps, onComparisonComplete, onStartComparison, selectedFiles]);

  useEffect(() => {
    if (!autoStartToken) return;
    if (autoStartToken === lastAutoStartTokenRef.current) return;
    if (selectedFiles.length < 2) return;

    lastAutoStartTokenRef.current = autoStartToken;
    handleStartComparison();
  }, [autoStartToken, handleStartComparison, selectedFiles]);

  const hasSelectedFiles = selectedFiles.length > 0;

  if (selectedFiles.length === 0 && !comparisonResults) {
    return (
      <div className={cn("flex-1 flex items-center justify-center", className)}>
        <div className="text-center space-y-4 max-w-md">
          <div className="w-16 h-16 mx-auto bg-muted rounded-full flex items-center justify-center">
            <GitCompare className="w-8 h-8 text-muted-foreground" />
          </div>
          <div>
            <h3 className="text-lg font-semibold">
              Ready to Compare Documents
            </h3>
            <p className="text-muted-foreground">
              Select at least 2 documents from the sidebar to start comparing
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex-1 p-6 space-y-6", className)}>
      {/* Selected Documents Header */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold">Document Comparison</h2>
            <p className="text-muted-foreground">
              {hasSelectedFiles
                ? `${selectedFiles.length} document${selectedFiles.length !== 1 ? "s" : ""} selected for analysis`
                : "Showing the most recent comparison results"}
            </p>
          </div>

          {!isComparing && !comparisonResults && (
            <Button
              onClick={handleStartComparison}
              disabled={
                selectedFiles.length < 2 ||
                selectedFiles.some(
                  (file) =>
                    file.status === "uploading" || file.status === "failed"
                )
              }
              size="lg"
            >
              <GitCompare className="w-4 h-4 mr-2" />
              {selectedFiles.some((file) => file.status === "uploading")
                ? "Waiting for uploads..."
                : "Start Comparison"}
            </Button>
          )}
        </div>

        {/* Selected Files Overview */}
        {hasSelectedFiles && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {selectedFiles.map((file, index) => (
              <Card key={file.id}>
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                      <FileText className="w-4 h-4 text-blue-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4
                        className="font-medium text-sm truncate"
                        title={file.file.name}
                      >
                        Document {index + 1}
                      </h4>
                      <p className="text-xs text-muted-foreground truncate">
                        {file.file.name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatFileSize(file.file.size)}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Comparison Process */}
      {isComparing && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              Running Comparison...
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm font-medium">
                <span>{comparisonStep || "Processing documents"}</span>
                <span>{comparisonProgress}%</span>
              </div>
              <Progress value={comparisonProgress} className="w-full" />
            </div>
            <div className="text-sm text-muted-foreground space-y-2">
              <p className="flex items-center gap-2">
                <Play className="h-4 w-4" />
                Hang tight while we analyze the selected documents.
              </p>
              <div className="grid gap-2 md:grid-cols-2">
                {demoSteps.map((step) => (
                  <div
                    key={step.label}
                    className={cn(
                      "flex items-center gap-2 rounded-md border p-2 text-xs",
                      comparisonStep === step.label
                        ? "border-primary bg-primary/10 text-primary"
                        : "text-muted-foreground"
                    )}
                  >
                    {comparisonProgress >= step.progress ? (
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    ) : (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    )}
                    {step.label}
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Comparison Results */}
      {comparisonResults && !isComparing && (
        <DemoComparisonResults
          data={comparisonResults}
          onShare={() => toast.info("Sharing is disabled in demo mode")}
        />
      )}
    </div>
  );
};

export default ComparisonArea;
