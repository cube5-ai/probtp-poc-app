"use client";

import { Download, ExternalLink } from "lucide-react";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";

interface FileViewerDialogProps {
  // File to display
  file: {
    id: string;
    name: string;
    url: string;
    type: string;
  } | null;
  // Whether the dialog is open
  isOpen: boolean;
  // Callback when dialog closes
  onClose: () => void;
  // Whether the file is loading
  isLoading?: boolean;
  // Optional callback for download action
  onDownload?: (fileId: string) => void;
}

// Renders a file viewer dialog for displaying documents
export const FileViewerDialog = ({
  file,
  isOpen,
  onClose,
  isLoading = false,
  onDownload,
}: FileViewerDialogProps) => {
  // Handle download action by navigating to download URL
  const handleDownload = () => {
    if (!file) return;

    if (onDownload) {
      // Use the provided callback
      onDownload(file.id);
    } else {
      // Fallback: navigate to URL directly (backend should handle download)
      const link = document.createElement("a");
      link.href = file.url;
      link.download = file.name;
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  // Handle opening in new tab
  const handleOpenInNewTab = () => {
    if (file?.url) {
      window.open(file.url, "_blank");
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-[95vw] w-[95vw] h-[90vh] flex flex-col sm:max-w-6xl">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between">
            <span className="truncate pr-4">{file?.name}</span>
            <div className="flex gap-2">
              {onDownload && (
                <Button variant="outline" size="sm" onClick={handleDownload}>
                  <Download className="h-4 w-4 mr-2" />
                  Download
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={handleOpenInNewTab}>
                <ExternalLink className="h-4 w-4 mr-2" />
                Open in New Tab
              </Button>
            </div>
          </DialogTitle>
          <DialogDescription>Preview of {file?.name}</DialogDescription>
        </DialogHeader>
        <div className="flex-1 overflow-hidden rounded-md border bg-muted/10">
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <Spinner className="h-8 w-8" />
            </div>
          ) : file?.type === "application/pdf" ? (
            <object
              data={file.url}
              type="application/pdf"
              className="w-full h-full"
              title={file.name}
            >
              <embed
                src={file.url}
                type="application/pdf"
                className="w-full h-full"
              />
              <div className="flex flex-col items-center justify-center h-full p-8 text-center">
                <p className="text-muted-foreground mb-4">
                  Your browser doesn&apos;t support PDF preview.
                </p>
                <div className="flex gap-2">
                  {onDownload && (
                    <Button variant="default" onClick={handleDownload}>
                      <Download className="h-4 w-4 mr-2" />
                      Download File
                    </Button>
                  )}
                  <Button variant="outline" onClick={handleOpenInNewTab}>
                    <ExternalLink className="h-4 w-4 mr-2" />
                    Open in New Tab
                  </Button>
                </div>
              </div>
            </object>
          ) : file?.type === "text/plain" ? (
            <div className="w-full h-full overflow-auto p-4">
              <iframe
                src={file.url}
                className="w-full h-full"
                title={file.name}
              />
            </div>
          ) : file?.type?.startsWith("image/") ? (
            <div className="w-full h-full overflow-auto p-4 flex items-center justify-center">
              <Image
                src={file.url}
                alt={file.name}
                width={800}
                height={600}
                className="max-w-full max-h-full object-contain"
                unoptimized
              />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
              <p className="text-muted-foreground mb-4">
                Preview not available for this file type.
              </p>
              <p className="text-sm text-muted-foreground mb-4">
                File type: {file?.type || "Unknown"}
              </p>
              <div className="flex gap-2">
                {onDownload && (
                  <Button variant="default" onClick={handleDownload}>
                    <Download className="h-4 w-4 mr-2" />
                    Download File
                  </Button>
                )}
                <Button variant="outline" onClick={handleOpenInNewTab}>
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Open in New Tab
                </Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
