"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useBreadcrumbs } from "@/contexts/BreadcrumbContext";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
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
  const searchParams = useSearchParams();
  const projectId = params.project_id as string;

  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [isComparing, setIsComparing] = useState(false);
  const [hasAppliedUrlSelection, setHasAppliedUrlSelection] = useState(false);
  const [autoStartRequested, setAutoStartRequested] = useState(false);
  const [autoStartToken, setAutoStartToken] = useState(0);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/signin");
      return;
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (projectId && user) {
      documentService.setDefaultProject(projectId);
      setBreadcrumbs([
        { label: "Projects", href: "/projects" },
        { label: "Project", href: `/projects/${projectId}` },
        { label: "Documents", href: `/projects/${projectId}/documents` },
        { label: "Compare" },
      ]);

      const loadFiles = async () => {
        try {
          const fileListResponse = await documentService.getFiles(projectId);
          const existingFiles: UploadedFile[] = fileListResponse.files.map(
            (file) => ({
              id: file.id,
              file: new File([], file.original_name, {
                type: file.mime_type || "application/pdf",
              }),
              preview: "",
              category: "All",
              status: "completed",
            })
          );
          setUploadedFiles(existingFiles);
        } catch (error) {
          console.error("Failed to load existing files:", error);
        }
      };

      loadFiles();
    }
  }, [projectId, user, setBreadcrumbs]);

  const handleStartComparison = () => {
    if (selectedFiles.length < 2) {
      alert("Please select at least 2 documents to compare");
      return;
    }

    setIsComparing(true);

    // The comparison will be handled by ComparisonArea component
    // which now uses real backend APIs
  };

  const getSelectedFileObjects = (): UploadedFile[] => {
    return uploadedFiles.filter((file) => selectedFiles.includes(file.id));
  };

  useEffect(() => {
    if (!searchParams) return;
    if (hasAppliedUrlSelection) return;

    const urlSelected = searchParams.getAll("selected");
    const autoStartParam = searchParams.get("autoStart");

    if (urlSelected.length === 0) {
      if (autoStartParam === "1") {
        setAutoStartRequested(true);
      }
      setHasAppliedUrlSelection(true);
      return;
    }

    if (uploadedFiles.length === 0) {
      return;
    }

    const uploadedIds = new Set(uploadedFiles.map((file) => file.id));
    const validSelection = urlSelected.filter((id) => uploadedIds.has(id));

    if (validSelection.length === 0) {
      setHasAppliedUrlSelection(true);
      return;
    }

    setSelectedFiles(validSelection);

    if (autoStartParam === "1" && validSelection.length >= 2) {
      setAutoStartRequested(true);
    }

    setHasAppliedUrlSelection(true);
  }, [searchParams, uploadedFiles, hasAppliedUrlSelection]);

  useEffect(() => {
    if (!autoStartRequested) return;
    if (selectedFiles.length < 2) return;

    setAutoStartToken((token) => token + 1);
    setAutoStartRequested(false);
  }, [autoStartRequested, selectedFiles]);

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

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden">
        <ComparisonArea
          selectedFiles={getSelectedFileObjects()}
          onStartComparison={handleStartComparison}
          isComparing={isComparing}
          className="h-full overflow-y-auto"
          autoStartToken={autoStartToken}
          onComparisonComplete={() => setIsComparing(false)}
          projectId={projectId}
        />
      </div>
    </div>
  );
};

export default ProjectDocumentComparePage;
