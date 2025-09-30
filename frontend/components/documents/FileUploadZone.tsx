"use client";

import { useState, useCallback } from "react";
import { Upload, FileText, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface UploadedFile {
  id: string;
  file: File;
  preview: string;
}

interface FileUploadZoneProps {
  onFilesChange: (files: UploadedFile[]) => void;
  maxFiles?: number;
  className?: string;
}

const FileUploadZone = ({ onFilesChange, maxFiles = 10, className }: FileUploadZoneProps) => {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);

  const ALLOWED_FILE_TYPES = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
    'application/rtf'
  ];

  const ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.txt', '.rtf'];
  const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

  const validateFile = (file: File): string | null => {
    if (!ALLOWED_FILE_TYPES.includes(file.type)) {
      return `File type not supported. Allowed types: ${ALLOWED_EXTENSIONS.join(', ')}`;
    }
    
    if (file.size > MAX_FILE_SIZE) {
      return `File too large. Maximum size: 50MB`;
    }
    
    return null;
  };

  const handleFiles = useCallback((files: FileList) => {
    const newFiles: UploadedFile[] = [];
    const errors: string[] = [];

    Array.from(files).forEach((file) => {
      const error = validateFile(file);
      if (error) {
        errors.push(`${file.name}: ${error}`);
        return;
      }

      if (uploadedFiles.length + newFiles.length >= maxFiles) {
        errors.push(`Maximum ${maxFiles} files allowed`);
        return;
      }

      const isDuplicate = uploadedFiles.some(existing => 
        existing.file.name === file.name && existing.file.size === file.size
      );

      if (isDuplicate) {
        errors.push(`${file.name}: File already uploaded`);
        return;
      }

      const uploadedFile: UploadedFile = {
        id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        file,
        preview: URL.createObjectURL(file)
      };

      newFiles.push(uploadedFile);
    });

    if (errors.length > 0) {
      alert(errors.join('\n'));
    }

    if (newFiles.length > 0) {
      const updatedFiles = [...uploadedFiles, ...newFiles];
      setUploadedFiles(updatedFiles);
      onFilesChange(updatedFiles);
    }
  }, [uploadedFiles, maxFiles, onFilesChange]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    
    if (e.dataTransfer.files) {
      handleFiles(e.dataTransfer.files);
    }
  }, [handleFiles]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      handleFiles(e.target.files);
    }
  }, [handleFiles]);

  const handleRemoveFile = useCallback((fileId: string) => {
    const updatedFiles = uploadedFiles.filter(file => {
      if (file.id === fileId) {
        URL.revokeObjectURL(file.preview);
        return false;
      }
      return true;
    });
    
    setUploadedFiles(updatedFiles);
    onFilesChange(updatedFiles);
  }, [uploadedFiles, onFilesChange]);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className={cn("space-y-6", className)}>
      {/* Upload Zone */}
      <Card>
        <CardContent className="p-6">
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={cn(
              "border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer",
              isDragOver ? "border-primary bg-primary/5" : "border-muted-foreground/25",
              uploadedFiles.length >= maxFiles && "opacity-50 cursor-not-allowed"
            )}
          >
            <input
              type="file"
              multiple
              accept=".pdf,.doc,.docx,.txt,.rtf"
              onChange={handleFileInput}
              className="hidden"
              id="file-upload"
              disabled={uploadedFiles.length >= maxFiles}
            />
            
            <label 
              htmlFor="file-upload" 
              className="cursor-pointer"
              tabIndex={0}
              role="button"
              aria-label="Upload files"
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  document.getElementById('file-upload')?.click();
                }
              }}
            >
              <Upload className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <div className="space-y-2">
                <p className="text-lg font-medium">
                  {isDragOver ? "Drop files here" : "Drag & drop files here"}
                </p>
                <p className="text-sm text-muted-foreground">
                  or click to select files
                </p>
                <div className="text-xs text-muted-foreground space-y-1">
                  <p>Supported formats: PDF, DOC, DOCX, TXT, RTF</p>
                  <p>Maximum file size: 50MB</p>
                  <p>Maximum files: {maxFiles} ({uploadedFiles.length}/{maxFiles} uploaded)</p>
                </div>
              </div>
            </label>
          </div>
        </CardContent>
      </Card>

      {/* Uploaded Files */}
      {uploadedFiles.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">
            Uploaded Documents ({uploadedFiles.length})
          </h3>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {uploadedFiles.map((uploadedFile) => (
              <Card key={uploadedFile.id} className="relative">
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <FileText className="h-8 w-8 text-blue-500 flex-shrink-0 mt-1" />
                    <div className="flex-1 min-w-0">
                      <h4 className="font-medium text-sm truncate" title={uploadedFile.file.name}>
                        {uploadedFile.file.name}
                      </h4>
                      <div className="text-xs text-muted-foreground space-y-1">
                        <p>{formatFileSize(uploadedFile.file.size)}</p>
                        <p>{uploadedFile.file.type}</p>
                        <p>Ready for comparison</p>
                      </div>
                    </div>
                  </div>
                  
                  <Button
                    variant="ghost"
                    size="sm"
                    className="absolute top-2 right-2 h-6 w-6 p-0"
                    onClick={() => handleRemoveFile(uploadedFile.id)}
                    aria-label={`Remove ${uploadedFile.file.name}`}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default FileUploadZone;
