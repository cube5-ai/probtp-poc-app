"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useBreadcrumbs } from "@/contexts/BreadcrumbContext";
import { useRouter, useParams } from "next/navigation";
import { GitCompare, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import Loading from "@/components/common/loading";
import DocumentSidebar from "@/components/documents/DocumentSidebar";
import { documentService } from "@/lib/api/documents";

interface UploadedFile {
  id: string;
  file: File;
  preview: string;
  category?: string;
  status?: string;
  fileSize?: number; // Store actual file size from backend
}

const DocumentManagementPage = () => {
  const { user, loading } = useAuth();
  const { setBreadcrumbs } = useBreadcrumbs();
  const router = useRouter();
  const params = useParams();
  const projectId = params.project_id as string;

  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/signin");
      return;
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (projectId) {
      // Set the project context for document operations
      documentService.setDefaultProject(projectId);

      // Set breadcrumbs
      setBreadcrumbs([
        { label: "Projects", href: "/projects" },
        { label: "Project", href: `/projects/${projectId}` },
        { label: "Documents" },
      ]);

      // Load existing files from the backend
      const loadFiles = async () => {
        try {
          const fileListResponse = await documentService.getFiles(projectId);
          const existingFiles: UploadedFile[] = fileListResponse.files.map(
            (file) => ({
              id: file.id,
              file: new File([], file.original_name, {
                type: file.mime_type || "application/pdf",
              }),
              preview: "", // No preview for existing files
              category: "All",
              status: "completed",
              fileSize: file.file_size, // Store actual file size from backend
            })
          );
          setUploadedFiles(existingFiles);
        } catch (error) {
          console.error("Failed to load existing files:", error);
          // Continue without showing error to user
        }
      };

      loadFiles();
    }
  }, [projectId, setBreadcrumbs]);

  const handleFilesChange = (files: UploadedFile[]) => {
    setUploadedFiles(files);
  };

  const handleSelectionChange = (selectedIds: string[]) => {
    setSelectedFiles(selectedIds);
  };

  const handleCompareDocuments = () => {
    if (selectedFiles.length < 2) {
      alert("Please select at least 2 documents to compare");
      return;
    }

    // Navigate to comparison page with selected files
    const params = new URLSearchParams();
    selectedFiles.forEach((id) => params.append("selected", id));
    params.set("autoStart", "1");

    router.push(
      `/projects/${projectId}/documents/compare?${params.toString()}`
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loading />
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <div className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold">Documents</h1>

            <div className="flex items-center gap-2">
              <Button
                onClick={handleCompareDocuments}
                disabled={selectedFiles.length < 2}
                className="gap-2"
              >
                <GitCompare className="w-4 h-4" />
                Compare Selected ({selectedFiles.length})
              </Button>

              <Button
                variant="ghost"
                onClick={() => router.push(`/projects/${projectId}`)}
                className="gap-2"
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Document Sidebar */}
        <DocumentSidebar
          uploadedFiles={uploadedFiles}
          selectedFiles={selectedFiles}
          onFilesChange={handleFilesChange}
          onSelectionChange={handleSelectionChange}
          className="flex-shrink-0"
          projectId={projectId}
        />

        {/* Main Content Area */}
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center space-y-4 max-w-md">
            <div className="w-16 h-16 mx-auto bg-muted rounded-full flex items-center justify-center">
              <GitCompare className="w-8 h-8 text-muted-foreground" />
            </div>
            <div>
              <h3 className="text-lg font-semibold">Document Management</h3>
              <p className="text-muted-foreground">
                Upload and organize your documents using the sidebar. Select
                documents to compare them.
              </p>
            </div>

            {selectedFiles.length >= 2 && (
              <Button onClick={handleCompareDocuments} size="lg">
                <GitCompare className="w-4 h-4 mr-2" />
                Compare {selectedFiles.length} Documents
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DocumentManagementPage;
