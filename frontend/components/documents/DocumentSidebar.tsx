"use client";

import { useState, useCallback } from "react";
import { Upload, Search, MoreVertical, Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";
import { documentService } from "@/lib/api/documents";
import { toast } from "sonner";
import { Spinner } from "@/components/ui/spinner";
import { FileViewerDialog } from "./FileViewerDialog";

interface UploadedFile {
  id: string;
  file: File;
  preview: string;
  category?: string;
  status?: string;
  uploadProgress?: number;
  fileSize?: number; // Store actual file size from backend
}

interface DocumentSidebarProps {
  uploadedFiles: UploadedFile[];
  selectedFiles: string[];
  onFilesChange: (files: UploadedFile[]) => void;
  onSelectionChange: (selectedIds: string[]) => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  className?: string;
  disableUpload?: boolean;
}

const ALLOWED_FILE_TYPES = [
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
  "application/rtf",
];

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

const DocumentSidebar = ({
  uploadedFiles,
  selectedFiles,
  onFilesChange,
  onSelectionChange,
  isCollapsed = false,
  onToggleCollapse,
  className,
  disableUpload = false,
}: DocumentSidebarProps) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [activeFilter, setActiveFilter] = useState("All");
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [fileToDelete, setFileToDelete] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [fileToRename, setFileToRename] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [fileToView, setFileToView] = useState<{
    id: string;
    name: string;
    url: string;
    type: string;
  } | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);

  const filters = ["All", "Competitors", "PRO BTP"];

  // Note: Project initialization is now handled by parent components
  // DocumentSidebar assumes a project context is already set

  const validateFile = useCallback((file: File): string | null => {
    if (!ALLOWED_FILE_TYPES.includes(file.type)) {
      return `File type not supported. Allowed: PDF, DOC, DOCX, TXT, RTF`;
    }

    if (file.size > MAX_FILE_SIZE) {
      return `File too large. Maximum size: 50MB`;
    }

    return null;
  }, []);

  const handleFiles = useCallback(
    async (files: FileList) => {
      if (disableUpload) return;
      if (isUploading) return;

      const validFiles: File[] = [];
      const errors: string[] = [];

      // Validate files first
      Array.from(files).forEach((file) => {
        const error = validateFile(file);
        if (error) {
          errors.push(`${file.name}: ${error}`);
          return;
        }

        const isDuplicate = uploadedFiles.some(
          (existing) =>
            existing.file.name === file.name && existing.file.size === file.size
        );

        if (isDuplicate) {
          errors.push(`${file.name}: File already uploaded`);
          return;
        }

        validFiles.push(file);
      });

      if (errors.length > 0) {
        alert(errors.join("\n"));
      }

      if (validFiles.length === 0) return;

      setIsUploading(true);

      // Process files one by one
      for (const file of validFiles) {
        const tempId = `temp_${Date.now()}_${Math.random()
          .toString(36)
          .substr(2, 9)}`;

        // Add file to UI immediately with uploading status
        const tempFile: UploadedFile = {
          id: tempId,
          file,
          preview: URL.createObjectURL(file),
          category: "All",
          status: "uploading",
          uploadProgress: 0,
        };

        const updatedFiles = [...uploadedFiles, tempFile];
        onFilesChange(updatedFiles);

        try {
          // Upload file using real API
          const uploadedDocument = await documentService.uploadFile(
            file,
            undefined, // Use default project
            (progress) => {
              // Update progress in UI
              const progressFiles = updatedFiles.map((f) =>
                f.id === tempId ? { ...f, uploadProgress: progress } : f
              );
              onFilesChange(progressFiles);
            }
          );

          // Update file with success status and actual file size from backend
          const successFiles = updatedFiles.map((f) =>
            f.id === tempId
              ? {
                  ...f,
                  id: uploadedDocument.id, // Use real ID from backend
                  status: "completed",
                  uploadProgress: 100,
                  fileSize: uploadedDocument.file_size, // Store actual file size from backend
                }
              : f
          );
          onFilesChange(successFiles);
        } catch (error) {
          console.error("Upload failed:", error);

          // Update file with error status
          const errorFiles = updatedFiles.map((f) =>
            f.id === tempId
              ? {
                  ...f,
                  status: "failed",
                  uploadProgress: 0,
                }
              : f
          );
          onFilesChange(errorFiles);

          toast.error(
            `Upload failed for ${file.name}: ${
              error instanceof Error ? error.message : "Unknown error"
            }`
          );
        }
      }

      setIsUploading(false);
    },
    [uploadedFiles, onFilesChange, isUploading, validateFile, disableUpload]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);

      if (e.dataTransfer.files) {
        handleFiles(e.dataTransfer.files);
      }
    },
    [handleFiles]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (disableUpload) {
        e.target.value = "";
        return;
      }

      if (e.target.files) {
        handleFiles(e.target.files);
      }
    },
    [handleFiles, disableUpload]
  );

  const handleRemoveFile = useCallback(
    (fileId: string) => {
      const file = uploadedFiles.find((f) => f.id === fileId);
      const fileName = file?.file.name || "Unknown file";

      // Open confirmation dialog
      setFileToDelete({ id: fileId, name: fileName });
    },
    [uploadedFiles]
  );

  const confirmDelete = useCallback(async () => {
    if (!fileToDelete) return;

    const { id: fileId, name: fileName } = fileToDelete;

    try {
      setIsDeleting(true);
      // Delete from backend if it has a real ID (not a temporary upload ID)
      if (!fileId.startsWith("temp_")) {
        await documentService.deleteFile(fileId);
      }

      // Remove from UI
      const updatedFiles = uploadedFiles.filter((file) => {
        if (file.id === fileId) {
          URL.revokeObjectURL(file.preview);
          return false;
        }
        return true;
      });

      onFilesChange(updatedFiles);

      // Remove from selection if selected
      const updatedSelection = selectedFiles.filter((id) => id !== fileId);
      onSelectionChange(updatedSelection);

      // Show success message
      toast.success(`File "${fileName}" deleted successfully`);
    } catch (error) {
      console.error("Failed to delete file from backend:", error);
      toast.error(
        `Failed to delete "${fileName}": ${
          error instanceof Error ? error.message : "Unknown error"
        }`
      );
    } finally {
      setIsDeleting(false);
      setFileToDelete(null);
    }
  }, [
    fileToDelete,
    uploadedFiles,
    selectedFiles,
    onFilesChange,
    onSelectionChange,
  ]);

  const handleFileSelection = useCallback(
    (fileId: string) => {
      const isSelected = selectedFiles.includes(fileId);
      const updatedSelection = isSelected
        ? selectedFiles.filter((id) => id !== fileId)
        : [...selectedFiles, fileId];

      onSelectionChange(updatedSelection);
    },
    [selectedFiles, onSelectionChange]
  );

  const handleRenameFile = useCallback(
    (fileId: string) => {
      const file = uploadedFiles.find((f) => f.id === fileId);
      if (file) {
        setFileToRename({ id: fileId, name: file.file.name });
        setRenameValue(file.file.name);
      }
    },
    [uploadedFiles]
  );

  const confirmRename = useCallback(async () => {
    if (!fileToRename || !renameValue.trim()) return;

    const { id: fileId } = fileToRename;
    const newName = renameValue.trim();

    try {
      setIsRenaming(true);
      // Update file name in UI
      const updatedFiles = uploadedFiles.map((file) =>
        file.id === fileId
          ? {
              ...file,
              file: new File([file.file], newName, { type: file.file.type }),
            }
          : file
      );
      onFilesChange(updatedFiles);

      toast.success(`File renamed to "${newName}"`);
    } catch (error) {
      console.error("Failed to rename file:", error);
      toast.error(
        `Failed to rename file: ${
          error instanceof Error ? error.message : "Unknown error"
        }`
      );
    } finally {
      setIsRenaming(false);
      setFileToRename(null);
      setRenameValue("");
    }
  }, [fileToRename, renameValue, uploadedFiles, onFilesChange]);

  const handleOpenFile = useCallback(
    async (fileId: string) => {
      const file = uploadedFiles.find((f) => f.id === fileId);
      if (!file) return;

      try {
        setIsLoadingPreview(true);
        let viewUrl: string;
        let fileName = file.file.name;
        const fileType = file.file.type;

        // For real files, get view URL from backend
        if (!fileId.startsWith("temp_")) {
          const fileData = await documentService.getFile(fileId);
          if (fileData.view_url) {
            viewUrl = fileData.view_url;
            fileName = fileData.original_name;
          } else {
            viewUrl = file.preview;
          }
        } else {
          // For temporary files, use object URL
          viewUrl = file.preview;
        }

        setFileToView({
          id: fileId,
          name: fileName,
          url: viewUrl,
          type: fileType,
        });
      } catch (error) {
        console.error("Failed to open file:", error);
        toast.error(
          `Failed to open file: ${
            error instanceof Error ? error.message : "Unknown error"
          }`
        );
      } finally {
        setIsLoadingPreview(false);
      }
    },
    [uploadedFiles]
  );

  const handleDownloadFile = useCallback(
    async (fileId: string) => {
      const file = uploadedFiles.find((f) => f.id === fileId);
      if (!file) return;

      try {
        let downloadUrl: string;
        let fileName = file.file.name;

        // For real files, get download URL from backend
        if (!fileId.startsWith("temp_")) {
          const fileData = await documentService.getFile(fileId);
          if (fileData.download_url) {
            downloadUrl = fileData.download_url;
            fileName = fileData.original_name;
          } else {
            throw new Error("No download URL available");
          }
        } else {
          // For temporary files, use object URL
          downloadUrl = file.preview;
        }

        // Create a temporary anchor element to trigger download
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.download = fileName;
        // Don't open in new tab for downloads
        link.style.display = "none";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        toast.success(`Downloading "${fileName}"`);
      } catch (error) {
        console.error("Failed to download file:", error);
        toast.error(
          `Failed to download file: ${
            error instanceof Error ? error.message : "Unknown error"
          }`
        );
      }
    },
    [uploadedFiles]
  );

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const filteredFiles = uploadedFiles.filter((file) => {
    const matchesSearch = file.file.name
      .toLowerCase()
      .includes(searchTerm.toLowerCase());
    const matchesFilter =
      activeFilter === "All" || file.category === activeFilter;
    return matchesSearch && matchesFilter;
  });

  if (isCollapsed) {
    return (
      <div
        className={cn(
          "w-12 bg-muted/30 border-r flex flex-col items-center py-4",
          className
        )}
      >
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleCollapse}
          aria-label="Expand sidebar"
        >
          <Menu className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "w-80 bg-background border-r flex flex-col h-screen",
        className
      )}
    >
      {/* Header */}
      <div className="p-4 border-b space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Documents</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleCollapse}
            className="lg:hidden"
            aria-label="Collapse sidebar"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {!disableUpload && (
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={cn(
              "border-2 border-dashed rounded-lg p-4 text-center transition-colors cursor-pointer",
              isDragOver
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25",
              isUploading && "opacity-50 cursor-not-allowed"
            )}
          >
            <input
              type="file"
              multiple
              accept=".pdf,.doc,.docx,.txt,.rtf"
              onChange={handleFileInput}
              className="hidden"
              id="sidebar-file-upload"
              disabled={isUploading}
            />

            <label
              htmlFor="sidebar-file-upload"
              className="cursor-pointer block"
              tabIndex={0}
              role="button"
              aria-label="Upload files"
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  document.getElementById("sidebar-file-upload")?.click();
                }
              }}
            >
              <Upload className="mx-auto h-6 w-6 text-muted-foreground mb-2" />
              <p className="text-sm font-medium">
                {isUploading ? "Uploading..." : "Upload new files"}
              </p>
              <p className="text-xs text-muted-foreground">
                {isUploading ? "Please wait..." : "Click or drag files to upload"}
              </p>
            </label>
          </div>
        )}
      </div>

      {/* Search */}
      <div className="p-4 border-b">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search files"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="px-4 py-2 border-b">
        <div className="flex gap-1">
          {filters.map((filter) => (
            <Button
              key={filter}
              variant={activeFilter === filter ? "default" : "ghost"}
              size="sm"
              onClick={() => setActiveFilter(filter)}
              className="text-xs h-7"
            >
              {filter}
            </Button>
          ))}
        </div>
      </div>

      {/* File List */}
      <div className="flex-1 overflow-y-auto">
        {filteredFiles.length === 0 ? (
          <div className="p-4 text-center text-muted-foreground">
            <p className="text-sm">
              {uploadedFiles.length === 0
                ? "No files uploaded"
                : "No files match your search"}
            </p>
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {filteredFiles.map((file) => (
              <Card
                key={file.id}
                className={cn(
                  "cursor-pointer transition-colors hover:bg-muted/50",
                  selectedFiles.includes(file.id) &&
                    "bg-primary/10 border-primary"
                )}
                onClick={() => handleFileSelection(file.id)}
              >
                <CardContent className="p-3">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selectedFiles.includes(file.id)}
                      onChange={() => handleFileSelection(file.id)}
                      className="rounded"
                      onClick={(e) => e.stopPropagation()}
                    />

                    <div className="flex-1 min-w-0">
                      <p
                        className="text-sm font-medium truncate"
                        title={file.file.name}
                      >
                        {file.file.name}
                      </p>
                      <div className="text-xs text-muted-foreground">
                        <p>{formatFileSize(file.fileSize ?? file.file.size)}</p>
                        {file.status === "uploading" &&
                          file.uploadProgress !== undefined && (
                            <div className="mt-1">
                              <div className="w-full bg-muted rounded-full h-1">
                                <div
                                  className="bg-primary h-1 rounded-full transition-all duration-300"
                                  style={{ width: `${file.uploadProgress}%` }}
                                />
                              </div>
                              <p className="text-xs mt-1">
                                {file.uploadProgress}%
                              </p>
                            </div>
                          )}
                        {file.status === "failed" && (
                          <p className="text-red-500 text-xs">Upload failed</p>
                        )}
                      </div>
                    </div>

                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0"
                          onClick={(e) => e.stopPropagation()}
                          disabled={file.status === "uploading"}
                        >
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenFile(file.id);
                          }}
                        >
                          Open file
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDownloadFile(file.id);
                          }}
                        >
                          Download
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRenameFile(file.id);
                          }}
                        >
                          Rename
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRemoveFile(file.id);
                          }}
                          className="text-destructive focus:text-destructive"
                        >
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Footer Stats */}
      <div className="p-4 border-t bg-muted/30">
        <div className="space-y-2 text-xs text-muted-foreground">
          <div className="flex justify-between">
            <span>Total files:</span>
            <span>{uploadedFiles.length}</span>
          </div>
          <div className="flex justify-between">
            <span>Selected:</span>
            <span>{selectedFiles.length}</span>
          </div>
          {selectedFiles.length >= 2 && (
            <Badge variant="default" className="w-full justify-center text-xs">
              Ready to compare
            </Badge>
          )}
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog
        open={!!fileToDelete}
        onOpenChange={(open) => !open && !isDeleting && setFileToDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete File</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete{" "}
              <strong>{fileToDelete?.name}</strong>? This action cannot be
              undone and will permanently remove the file from storage.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting && <Spinner className="mr-2 h-4 w-4" />}
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Rename File Dialog */}
      <AlertDialog
        open={!!fileToRename}
        onOpenChange={(open) => !open && !isRenaming && setFileToRename(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Rename File</AlertDialogTitle>
            <AlertDialogDescription>
              Enter a new name for <strong>{fileToRename?.name}</strong>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-4">
            <Input
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              placeholder="Enter new file name"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !isRenaming) {
                  confirmRename();
                }
              }}
              disabled={isRenaming}
              autoFocus
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isRenaming}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmRename}
              disabled={!renameValue.trim() || isRenaming}
            >
              {isRenaming && <Spinner className="mr-2 h-4 w-4" />}
              {isRenaming ? "Renaming..." : "Rename"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* File Viewer Dialog */}
      <FileViewerDialog
        file={fileToView}
        isOpen={!!fileToView}
        onClose={() => setFileToView(null)}
        isLoading={isLoadingPreview}
        onDownload={handleDownloadFile}
      />
    </div>
  );
};

export default DocumentSidebar;
