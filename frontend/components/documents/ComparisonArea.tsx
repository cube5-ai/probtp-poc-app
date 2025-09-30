"use client";

import { useState } from "react";
import { GitCompare, FileText, BarChart3, Download, Share } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface UploadedFile {
  id: string;
  file: File;
  preview: string;
  category?: string;
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
  className 
}: ComparisonAreaProps) => {
  const [comparisonResults, setComparisonResults] = useState<any>(null);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const handleStartComparison = () => {
    if (selectedFiles.length < 2) return;
    onStartComparison();
    
    // Mock comparison results after delay
    setTimeout(() => {
      setComparisonResults({
        overallSimilarity: 78,
        documentPairs: [
          { doc1: selectedFiles[0].file.name, doc2: selectedFiles[1].file.name, similarity: 78 },
          ...(selectedFiles.length > 2 ? [
            { doc1: selectedFiles[0].file.name, doc2: selectedFiles[2].file.name, similarity: 65 },
            { doc1: selectedFiles[1].file.name, doc2: selectedFiles[2].file.name, similarity: 82 }
          ] : [])
        ],
        keyDifferences: [
          "Pricing structure varies significantly",
          "Different payment terms mentioned",
          "Scope of work has minor variations"
        ],
        commonElements: [
          "Similar contract duration",
          "Consistent quality standards",
          "Matching confidentiality clauses"
        ]
      });
    }, 3000);
  };

  if (selectedFiles.length === 0) {
    return (
      <div className={cn("flex-1 flex items-center justify-center", className)}>
        <div className="text-center space-y-4 max-w-md">
          <div className="w-16 h-16 mx-auto bg-muted rounded-full flex items-center justify-center">
            <GitCompare className="w-8 h-8 text-muted-foreground" />
          </div>
          <div>
            <h3 className="text-lg font-semibold">Ready to Compare Documents</h3>
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
              {selectedFiles.length} document{selectedFiles.length !== 1 ? 's' : ''} selected for analysis
            </p>
          </div>
          
          {!isComparing && !comparisonResults && (
            <Button 
              onClick={handleStartComparison}
              disabled={selectedFiles.length < 2}
              size="lg"
            >
              <GitCompare className="w-4 h-4 mr-2" />
              Start Comparison
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
                    <h4 className="font-medium text-sm truncate" title={file.file.name}>
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
                <span>Processing documents</span>
                <span>Step 1 of 4</span>
              </div>
              <Progress value={25} className="w-full" />
            </div>
            <div className="text-sm text-muted-foreground space-y-1">
              <p>• Extracting text content from documents</p>
              <p>• Analyzing document structure</p>
              <p>• Identifying key sections and clauses</p>
              <p>• Computing similarity metrics</p>
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
                <p className="text-muted-foreground">Overall Similarity Score</p>
                <Badge 
                  variant={comparisonResults.overallSimilarity > 70 ? "default" : "secondary"}
                  className="mt-2"
                >
                  {comparisonResults.overallSimilarity > 70 ? "High Similarity" : "Moderate Similarity"}
                </Badge>
              </div>

              {/* Document Pair Comparisons */}
              <div className="space-y-4">
                <h4 className="font-semibold">Pairwise Comparisons</h4>
                {comparisonResults.documentPairs.map((pair: any, index: number) => (
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
                  {comparisonResults.keyDifferences.map((diff: string, index: number) => (
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
                  {comparisonResults.commonElements.map((element: string, index: number) => (
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
                    <div className="text-2xl font-bold">95%</div>
                    <div className="text-sm text-muted-foreground">Text Similarity</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold">87%</div>
                    <div className="text-sm text-muted-foreground">Structure Match</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold">72%</div>
                    <div className="text-sm text-muted-foreground">Semantic Similarity</div>
                  </div>
                </div>
                
                <div className="bg-muted/50 p-4 rounded-lg">
                  <p className="text-sm text-muted-foreground">
                    The documents show high structural similarity with consistent formatting and section organization. 
                    Key variations are found in pricing terms and specific deliverables, while maintaining similar 
                    legal language and contract structure.
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
