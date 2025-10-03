"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useBreadcrumbs } from "@/contexts/BreadcrumbContext";
import { useRouter, useParams } from "next/navigation";
import { GitCompare, ArrowLeft, Clock, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Loading from "@/components/common/loading";
import DocumentSidebar from "@/components/documents/DocumentSidebar";
import { documentService, type Project } from "@/lib/api/documents";
import { toast } from "sonner";

interface UploadedFile {
  id: string;
  file: File;
  preview: string;
  category?: string;
  status?: string;
}

interface ComparisonHistory {
  id: string;
  name: string;
  documents: string[];
  similarity: number;
  createdAt: string;
  status: 'completed' | 'processing' | 'failed';
}

const ProjectDashboard = () => {
  const { user, loading } = useAuth();
  const { setBreadcrumbs } = useBreadcrumbs();
  const router = useRouter();
  const params = useParams();
  const projectId = params.project_id as string;
  
  const [project, setProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [comparisonHistory, setComparisonHistory] = useState<ComparisonHistory[]>([]);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/signin");
      return;
    }
  }, [user, loading, router]);

  useEffect(() => {
    const loadProject = async () => {
      if (!user || !projectId) return;
      
      try {
        setIsLoading(true);
        
        // Set this project as the default for document operations
        documentService.setDefaultProject(projectId);
        
        // For now, create a mock project object since we don't have a get project endpoint
        const mockProject: Project = {
          id: projectId,
          name: "Document Comparison Project",
          description: "Default project for document comparison",
          created_by: user.uid,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        };
        
        setProject(mockProject);
        
        // Set breadcrumbs
        setBreadcrumbs([
          { label: "Projects", href: "/projects" },
          { label: mockProject.name }
        ]);
        
        // Load existing files from the backend
        try {
          const fileListResponse = await documentService.getFiles(projectId);
          const existingFiles: UploadedFile[] = fileListResponse.files.map(file => ({
            id: file.id,
            file: new File([], file.original_name, { type: file.mime_type || 'application/pdf' }),
            preview: '', // No preview for existing files
            category: "All",
            status: "completed"
          }));
          setUploadedFiles(existingFiles);
        } catch (error) {
          console.error('Failed to load existing files:', error);
          // Continue without showing error to user
        }
        
        // Mock comparison history
        setComparisonHistory([
          {
            id: '1',
            name: 'Contract Analysis #1',
            documents: ['contract_v1.pdf', 'contract_v2.pdf'],
            similarity: 85,
            createdAt: '2024-01-15T10:30:00Z',
            status: 'completed'
          },
          {
            id: '2', 
            name: 'Proposal Comparison',
            documents: ['proposal_a.pdf', 'proposal_b.pdf', 'proposal_c.pdf'],
            similarity: 72,
            createdAt: '2024-01-14T14:20:00Z',
            status: 'completed'
          }
        ]);
        
      } catch (error) {
        console.error('Failed to load project:', error);
        toast.error('Failed to load project');
        router.push('/projects');
      } finally {
        setIsLoading(false);
      }
    };

    loadProject();
  }, [user, projectId, router]);

  const handleFilesChange = (files: UploadedFile[]) => {
    setUploadedFiles(files);
  };

  const handleSelectionChange = (selectedIds: string[]) => {
    setSelectedFiles(selectedIds);
  };

  const handleStartComparison = () => {
    if (selectedFiles.length < 2) {
      toast.error("Please select at least 2 documents to compare");
      return;
    }
    
    // Navigate to comparison page
    router.push(`/projects/${projectId}/documents/compare`);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };


  if (loading || isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loading />
      </div>
    );
  }

  if (!user || !project) {
    return null;
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <div className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold">{project?.name || "Project"}</h1>
            
            <Button
              variant="ghost"
              onClick={() => router.push('/projects')}
              className="gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Projects
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Side - Document Upload */}
        <DocumentSidebar
          uploadedFiles={uploadedFiles}
          selectedFiles={selectedFiles}
          onFilesChange={handleFilesChange}
          onSelectionChange={handleSelectionChange}
          className="flex-shrink-0"
        />

        {/* Right Side - Selected Documents & Comparison History */}
        <div className="flex-1 p-6 space-y-6 overflow-y-auto">
          {/* Selected Documents for New Compare */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GitCompare className="w-5 h-5" />
                Selected Documents for New Compare
              </CardTitle>
            </CardHeader>
            <CardContent>
              {selectedFiles.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>Select documents from the sidebar to start a new comparison</p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="flex flex-wrap gap-2">
                    {selectedFiles.map((fileId) => {
                      const file = uploadedFiles.find(f => f.id === fileId);
                      return file ? (
                        <Badge key={fileId} variant="secondary" className="px-3 py-1">
                          {file.file.name}
                        </Badge>
                      ) : null;
                    })}
                  </div>
                  
                  <Button 
                    onClick={handleStartComparison}
                    disabled={selectedFiles.length < 2}
                    className="w-full"
                    size="lg"
                  >
                    <GitCompare className="w-4 h-4 mr-2" />
                    Compare {selectedFiles.length} Documents
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Comparison History */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="w-5 h-5" />
                Comparison History
              </CardTitle>
            </CardHeader>
            <CardContent>
              {comparisonHistory.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Clock className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>No comparisons yet. Start by comparing some documents!</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {comparisonHistory.map((comparison) => (
                    <Card key={comparison.id} className="cursor-pointer hover:shadow-md transition-shadow">
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between">
                          <div className="space-y-2">
                            <h4 className="font-semibold">{comparison.name}</h4>
                            <div className="flex flex-wrap gap-1">
                              {comparison.documents.map((doc, index) => (
                                <Badge key={index} variant="outline" className="text-xs">
                                  {doc}
                                </Badge>
                              ))}
                            </div>
                            <p className="text-sm text-muted-foreground">
                              {formatDate(comparison.createdAt)}
                            </p>
                          </div>
                          
                          <div className="text-right space-y-2">
                            <Badge 
                              variant={comparison.status === 'completed' ? 'default' : 'secondary'}
                            >
                              {comparison.status}
                            </Badge>
                            {comparison.status === 'completed' && (
                              <div className="text-lg font-bold text-primary">
                                {comparison.similarity}%
                              </div>
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default ProjectDashboard;
