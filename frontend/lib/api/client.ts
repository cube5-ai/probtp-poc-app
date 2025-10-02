/**
 * API Client for Procurement Backend
 * Handles authentication, request/response interceptors, and base configuration
 */
import axios from "axios";
import type { AxiosInstance, AxiosRequestConfig } from "axios";

// API Configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

class ApiClient {
  private client: AxiosInstance;
  private authToken: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 120000, // 2 minutes for RFP processing
      headers: {
        "Content-Type": "application/json",
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor for auth
    this.client.interceptors.request.use(
      (config) => {
        if (this.authToken) {
          config.headers.Authorization = `Bearer ${this.authToken}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor for error handling and token refresh
    this.client.interceptors.response.use(
      (response) => {
        return response;
      },
      async (error) => {
        const originalRequest = error.config;

        // Check for specific "token used too early" error
        const isTokenTimingError =
          error.response?.status === 401 &&
          error.response?.data?.detail?.includes?.("Token used too early");

        if (isTokenTimingError && !originalRequest._retryForTiming) {
          originalRequest._retryForTiming = true;
          console.log(
            "⏰ Token timing issue detected, retrying after delay..."
          );

          // Wait a bit longer for token to become valid
          await new Promise((resolve) => setTimeout(resolve, 2000));

          // Retry with the same token
          return this.client(originalRequest);
        }

        if (
          (error.response?.status === 401 || error.response?.status === 403) &&
          !originalRequest._retry
        ) {
          originalRequest._retry = true;

          try {
            // Try to refresh the token
            console.log(
              "🔄 API Interceptor: Token expired, attempting refresh..."
            );
            const { authService } = await import("../auth/firebase");
            const newToken = await authService.getIdToken(true); // Force refresh

            if (newToken) {
              console.log(
                "✅ API Interceptor: Token refreshed, retrying request"
              );
              this.setAuthToken(newToken);
              originalRequest.headers.Authorization = `Bearer ${newToken}`;

              // Add small delay to prevent "token used too early" errors
              await new Promise((resolve) => setTimeout(resolve, 1000));

              // Retry the original request with new token
              return this.client(originalRequest);
            } else {
              console.error("❌ API Interceptor: No token received");
            }
          } catch (refreshError) {
            console.error(
              "❌ API Interceptor: Token refresh failed:",
              refreshError
            );
            this.clearAuth();
            // Redirect to login if we're in the browser
            if (typeof window !== "undefined") {
              console.log("🔄 Redirecting to login...");
              window.location.href = "/login";
            }
          }
        }

        return Promise.reject(error);
      }
    );
  }

  /**
   * Set authentication token
   */
  setAuthToken(token: string) {
    this.authToken = token;
    console.log("API Client: Auth token set");
  }

  /**
   * Clear authentication
   */
  clearAuth() {
    this.authToken = null;
    console.log("API Client: Auth token cleared");
  }

  /**
   * Get current auth token (for debugging)
   */
  getAuthToken() {
    return this.authToken;
  }

  /**
   * GET request
   */
  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.get(url, config);
    return response.data;
  }

  /**
   * POST request
   */
  async post<T>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await this.client.post(url, data, config);
    return response.data;
  }

  /**
   * PUT request
   */
  async put<T>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await this.client.put(url, data, config);
    return response.data;
  }

  /**
   * DELETE request
   */
  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.delete(url, config);
    return response.data;
  }

  /**
   * Upload file with progress
   */
  async uploadFile<T>(
    url: string,
    formData: FormData,
    onUploadProgress?: (progress: number) => void
  ): Promise<T> {
    const config: AxiosRequestConfig = {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      onUploadProgress: (progressEvent) => {
        if (onUploadProgress && progressEvent.total) {
          const progress = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onUploadProgress(progress);
        }
      },
    };

    const response = await this.client.post(url, formData, config);
    return response.data;
  }
}

// Create and export singleton instance
export const apiClient = new ApiClient();

// Export types for convenience
export type { AxiosRequestConfig };
