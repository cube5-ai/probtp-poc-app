"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import Breadcrumbs from "@/components/navigation/Breadcrumbs";
import DocumentSidebar from "@/components/documents/DocumentSidebar";
import ComparisonArea from "@/components/documents/ComparisonArea";
import Loading from "@/components/common/loading";

interface UploadedFile {
  id: string;
  file: File;
  preview: string;
  category?: string;
}

const DocumentComparePage = () => {
  const { user, loading } = useAuth();
  const router = useRouter();
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
    
    // Simulate comparison process (replace with actual API call later)
    setTimeout(() => {
      setIsComparing(false);
    }, 3000);
  };

  const handleToggleSidebar = () => {
    setIsSidebarCollapsed(!isSidebarCollapsed);
  };

  const getSelectedFileObjects = (): UploadedFile[] => {
    return uploadedFiles.filter(file => selectedFiles.includes(file.id));
  };

  const breadcrumbItems = [
    { label: "Documents", href: "/documents" },
    { label: "Compare", current: true }
  ];

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
      {/* Header with Breadcrumbs */}
      <div className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <Breadcrumbs items={breadcrumbItems} />
            
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

export default DocumentComparePage;
