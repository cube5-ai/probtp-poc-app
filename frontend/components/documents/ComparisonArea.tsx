"use client";

import { useState } from "react";
import { GitCompare, FileText, BarChart3, Download, Share } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { documentService, type ComparisonResult } from "@/lib/api/documents";
import { toast } from "sonner";

interface UploadedFile {
  id: string;
  file: File;
  preview: string;
  category?: string;
  status?: string;
  fileSize?: number; // Store actual file size from backend
}

interface ComparisonAreaProps {
  selectedFiles: UploadedFile[];
  onStartComparison: () => void;
  isComparing: boolean;
  className?: string;
}

const ComparisonArea = ({
  selectedFiles,
  onStartComparison,
  isComparing,
  className,
}: ComparisonAreaProps) => {
  const [comparisonResults, setComparisonResults] =
    useState<ComparisonResult | null>(null);
  const [comparisonProgress, setComparisonProgress] = useState(0);
  const [comparisonStep, setComparisonStep] = useState("");

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const handleStartComparison = async () => {
    if (selectedFiles.length < 2) return;

    // Only proceed with files that have completed upload
    const completedFiles = selectedFiles.filter(
      (file) =>
        file.status === "completed" ||
        !file.status ||
        !file.id.startsWith("temp_")
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
    setComparisonStep("Initializing comparison...");

    try {
      // Get file IDs (filter out temporary IDs)
      const fileIds = completedFiles
        .filter((file) => !file.id.startsWith("temp_")) // Only real backend IDs
        .map((file) => file.id);

      if (fileIds.length < 2) {
        throw new Error(
          "Not enough uploaded files to compare. Please ensure files are fully uploaded."
        );
      }

      const result = await documentService.compareDocuments(
        fileIds,
        (progress) => {
          setComparisonProgress(progress);

          // Update step based on progress
          if (progress <= 25) {
            setComparisonStep("Loading document details...");
          } else if (progress <= 70) {
            setComparisonStep("Parsing documents and extracting content...");
          } else if (progress <= 90) {
            setComparisonStep("Analyzing similarities and differences...");
          } else {
            setComparisonStep("Finalizing comparison results...");
          }
        }
      );

      setComparisonResults(result);
      setComparisonStep("Comparison completed successfully!");
      toast.success("Document comparison completed successfully!");
    } catch (error) {
      console.error("Comparison failed:", error);
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error occurred";
      toast.error(`Comparison failed: ${errorMessage}`);

      // Reset states on error
      setComparisonProgress(0);
      setComparisonStep("");
    }
  };

  if (selectedFiles.length === 0) {
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
              {selectedFiles.length} document
              {selectedFiles.length !== 1 ? "s" : ""} selected for analysis
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
      </div>

      {/* Comparison Process */}
      {isComparing && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary" />
              Analyzing Documents...
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>{comparisonStep || "Processing documents"}</span>
                <span>{comparisonProgress}%</span>
              </div>
              <Progress value={comparisonProgress} className="w-full" />
            </div>
            <div className="text-sm text-muted-foreground space-y-1">
              <p>• Loading document metadata and storage paths</p>
              <p>• Parsing documents using AI-powered extraction</p>
              <p>• Analyzing content blocks and document structure</p>
              <p>• Computing similarity metrics and generating insights</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Comparison Results */}
      {comparisonResults && !isComparing && (
        <div className="space-y-6">
          {/* Overall Results */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="w-5 h-5" />
                  Comparison Results
                </CardTitle>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm">
                    <Download className="w-4 h-4 mr-2" />
                    Export
                  </Button>
                  <Button variant="outline" size="sm">
                    <Share className="w-4 h-4 mr-2" />
                    Share
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Overall Similarity Score */}
              <div className="text-center space-y-2">
                <div className="text-3xl font-bold text-primary">
                  {comparisonResults.overallSimilarity}%
                </div>
                <p className="text-muted-foreground">
                  Overall Similarity Score
                </p>
                <Badge
                  variant={
                    comparisonResults.overallSimilarity > 70
                      ? "default"
                      : "secondary"
                  }
                  className="mt-2"
                >
                  {comparisonResults.overallSimilarity > 70
                    ? "High Similarity"
                    : "Moderate Similarity"}
                </Badge>
              </div>

              {/* Document Pair Comparisons */}
              <div className="space-y-4">
                <h4 className="font-semibold">Pairwise Comparisons</h4>
                {comparisonResults.documentPairs.map((pair, index) => (
                  <div key={index} className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="truncate">
                        {pair.doc1} ↔ {pair.doc2}
                      </span>
                      <span className="font-medium">{pair.similarity}%</span>
                    </div>
                    <Progress value={pair.similarity} className="w-full" />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Key Insights */}
          <div className="grid gap-6 md:grid-cols-2">
            {/* Key Differences */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Key Differences</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {comparisonResults.keyDifferences.map((diff, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm">
                      <div className="w-1.5 h-1.5 bg-red-500 rounded-full mt-2 flex-shrink-0" />
                      <span>{diff}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            {/* Common Elements */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Common Elements</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {comparisonResults.commonElements.map((element, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm">
                      <div className="w-1.5 h-1.5 bg-green-500 rounded-full mt-2 flex-shrink-0" />
                      <span>{element}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>

          {/* Detailed Analysis */}
          <Card>
            <CardHeader>
              <CardTitle>Detailed Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="text-center">
                    <div className="text-2xl font-bold">
                      {comparisonResults.textSimilarity}%
                    </div>
                    <div className="text-sm text-muted-foreground">
                      Text Similarity
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold">
                      {comparisonResults.structureMatch}%
                    </div>
                    <div className="text-sm text-muted-foreground">
                      Structure Match
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold">
                      {comparisonResults.semanticSimilarity}%
                    </div>
                    <div className="text-sm text-muted-foreground">
                      Semantic Similarity
                    </div>
                  </div>
                </div>

                <div className="bg-muted/50 p-4 rounded-lg">
                  <p className="text-sm text-muted-foreground">
                    {comparisonResults.summary}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default ComparisonArea;
