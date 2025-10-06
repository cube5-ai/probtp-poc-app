"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useBreadcrumbs } from "@/contexts/BreadcrumbContext";
import { useRouter, useParams } from "next/navigation";
import { Menu, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import DocumentSidebar from "@/components/documents/DocumentSidebar";
import ComparisonArea from "@/components/documents/ComparisonArea";
import Loading from "@/components/common/loading";
import { documentService } from "@/lib/api/documents";

interface UploadedFile {
  id: string;
  file: File;
  preview: string;
  category?: string;
  status?: string;
  fileSize?: number; // Store actual file size from backend
}

const ProjectDocumentComparePage = () => {
  const { user, loading } = useAuth();
  const { setBreadcrumbs } = useBreadcrumbs();
  const router = useRouter();
  const params = useParams();
  const projectId = params.project_id as string;

  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [isComparing, setIsComparing] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

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
        { label: "Documents", href: `/projects/${projectId}/documents` },
        { label: "Compare" },
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

  const handleStartComparison = () => {
    if (selectedFiles.length < 2) {
      alert("Please select at least 2 documents to compare");
      return;
    }

    setIsComparing(true);

    // The comparison will be handled by ComparisonArea component
    // which now uses real backend APIs
  };

  const handleToggleSidebar = () => {
    setIsSidebarCollapsed(!isSidebarCollapsed);
  };

  const getSelectedFileObjects = (): UploadedFile[] => {
    return uploadedFiles.filter((file) => selectedFiles.includes(file.id));
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
        <div className="container  px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold">Compare Documents</h1>

            <div className="flex items-center gap-2">
              {/* Mobile sidebar toggle */}
              <Button
                variant="ghost"
                size="sm"
                onClick={handleToggleSidebar}
                className="lg:hidden"
                aria-label="Toggle sidebar"
              >
                <Menu className="h-4 w-4" />
              </Button>

              {/* Back to Documents */}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => router.push(`/projects/${projectId}/documents`)}
                className="gap-2"
              >
                <ArrowLeft className="w-4 h-4" />
                Back to Documents
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <DocumentSidebar
          uploadedFiles={uploadedFiles}
          selectedFiles={selectedFiles}
          onFilesChange={handleFilesChange}
          onSelectionChange={handleSelectionChange}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={handleToggleSidebar}
          className="flex-shrink-0"
        />

        {/* Main Comparison Area */}
        <ComparisonArea
          selectedFiles={getSelectedFileObjects()}
          onStartComparison={handleStartComparison}
          isComparing={isComparing}
          className="flex-1 overflow-y-auto"
        />
      </div>
    </div>
  );
};

export default ProjectDocumentComparePage;
