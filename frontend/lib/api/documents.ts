/**
 * Document API Service - Real Backend Integration
 * Handles document upload, management, and parsing with the ProBTP backend
 */
import { apiClient } from './client';

// Type definitions based on backend schemas
export interface Project {
  id: string;
  name: string;
  description?: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface FileUploadRequest {
  filename: string;
  file_size: number;
}

export interface FileUploadResponse {
  upload_id: string;
  upload_url: string;
  upload_method: string;
  expires_at: string;
  max_file_size: number;
}

export interface FileConfirmResponse {
  file_id: string;
  status: string;
  message: string;
}

export interface UserInfo {
  id: string;
  email: string;
  name?: string;
}

export interface DocumentFile {
  id: string;
  original_name: string;
  file_size: number;
  status: string;
  uploaded_by: UserInfo;
  created_at: string;
  updated_at: string;
}

export interface FileListResponse {
  files: DocumentFile[];
  pagination: {
    page: number;
    size: number;
    total: number;
    pages: number;
  };
}

export class DocumentService {
  private defaultProjectId: string | null = null;

  setDefaultProject = (projectId: string): void => {
    this.defaultProjectId = projectId;
  };

  createProject = async (name: string, description?: string): Promise<Project> => {
    const response = await apiClient.post<Project>('/api/v1/projects', {
      name,
      description
    });
    
    if (!this.defaultProjectId) {
      this.defaultProjectId = response.id;
    }
    
    return response;
  };

  getProjects = async (): Promise<Project[]> => {
    return await apiClient.get<Project[]>('/api/v1/projects');
  };

  uploadFile = async (
    file: File,
    projectId?: string,
    onProgress?: (progress: number) => void
  ): Promise<DocumentFile> => {
    const targetProjectId = projectId || this.defaultProjectId;
    
    if (!targetProjectId) {
      throw new Error('No project ID specified. Create a project first.');
    }

    try {
      // Step 1: Initialize upload
      onProgress?.(10);
      const uploadResponse = await this.initializeUpload(file, targetProjectId);
      
      // Step 2: Upload to signed URL
      onProgress?.(20);
      await this.uploadToSignedUrl(
        file,
        uploadResponse.upload_url,
        uploadResponse.upload_method,
        (progress) => {
          const totalProgress = 20 + (progress * 0.6);
          onProgress?.(Math.round(totalProgress));
        }
      );

      // Step 3: Confirm upload
      onProgress?.(90);
      const confirmResponse = await this.confirmUpload(uploadResponse.upload_id, targetProjectId);
      
      // Step 4: Get file details
      onProgress?.(95);
      const fileDetails = await this.getFile(confirmResponse.file_id, targetProjectId);
      
      onProgress?.(100);
      return fileDetails;
      
    } catch (error) {
      console.error('File upload failed:', error);
      throw error;
    }
  };

  private initializeUpload = async (
    file: File, 
    projectId: string
  ): Promise<FileUploadResponse> => {
    const request: FileUploadRequest = {
      filename: file.name,
      file_size: file.size
    };

    return await apiClient.post<FileUploadResponse>(
      `/api/v1/projects/${projectId}/files/upload`,
      request
    );
  };

  private uploadToSignedUrl = async (
    file: File,
    uploadUrl: string,
    method: string = 'PUT',
    onProgress?: (progress: number) => void
  ): Promise<void> => {
    const xhr = new XMLHttpRequest();
    
    return new Promise((resolve, reject) => {
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable && onProgress) {
          const progress = Math.round((event.loaded / event.total) * 100);
          onProgress(progress);
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve();
        } else {
          reject(new Error(`Upload failed with status: ${xhr.status}`));
        }
      });

      xhr.addEventListener('error', () => {
        reject(new Error('Upload failed'));
      });

      xhr.open(method, uploadUrl);
      xhr.setRequestHeader('Content-Type', file.type);
      xhr.send(file);
    });
  };

  private confirmUpload = async (
    uploadId: string,
    projectId: string,
    md5Hash?: string
  ): Promise<FileConfirmResponse> => {
    const request = {
      md5_hash: md5Hash
    };

    return await apiClient.put<FileConfirmResponse>(
      `/api/v1/projects/${projectId}/files/${uploadId}/confirm`,
      request
    );
  };

  getFiles = async (
    projectId?: string,
    page: number = 1,
    size: number = 20
  ): Promise<FileListResponse> => {
    const targetProjectId = projectId || this.defaultProjectId;
    
    if (!targetProjectId) {
      throw new Error('No project ID specified');
    }

    return await apiClient.get<FileListResponse>(
      `/api/v1/projects/${targetProjectId}/files?page=${page}&size=${size}`
    );
  };

  getFile = async (fileId: string, projectId?: string): Promise<DocumentFile> => {
    const targetProjectId = projectId || this.defaultProjectId;
    
    if (!targetProjectId) {
      throw new Error('No project ID specified');
    }

    return await apiClient.get<DocumentFile>(
      `/api/v1/projects/${targetProjectId}/files/${fileId}`
    );
  };

  deleteFile = async (fileId: string, projectId?: string): Promise<void> => {
    const targetProjectId = projectId || this.defaultProjectId;
    
    if (!targetProjectId) {
      throw new Error('No project ID specified');
    }

    await apiClient.delete(`/api/v1/projects/${targetProjectId}/files/${fileId}`);
  };
}

// Export singleton instance
export const documentService = new DocumentService();
