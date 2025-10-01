/**
 * Schema API client
 * Handles all schema-related API calls
 */
import { apiClient } from "./client";
import type {
  Schema,
  SchemaListResponse,
  SchemaCreateRequest,
  SchemaUpdateRequest,
  SchemaCloneRequest,
} from "@/types/schema.types";

// List all schemas with optional search
export async function listSchemas(params?: {
  search?: string;
}): Promise<SchemaListResponse> {
  const queryParams = new URLSearchParams();

  if (params?.search) {
    queryParams.append("search", params.search);
  }

  const url = `/schemas?${queryParams.toString()}`;
  const response = await apiClient.get<SchemaListResponse>(url);
  return response;
}

// Get template schemas only
export async function listTemplates(params?: {
  page?: number;
  pageSize?: number;
}): Promise<SchemaListResponse> {
  const queryParams = new URLSearchParams();

  if (params?.page) {
    queryParams.append("page", String(params.page));
  }
  if (params?.pageSize) {
    queryParams.append("page_size", String(params.pageSize));
  }

  const url = `/schemas/templates?${queryParams.toString()}`;
  const response = await apiClient.get<SchemaListResponse>(url);
  return response;
}

// Get a specific schema by ID
export async function getSchema(schemaId: string): Promise<Schema> {
  const response = await apiClient.get<Schema>(`/schemas/${schemaId}`);
  return response;
}

// Create a new schema
export async function createSchema(data: SchemaCreateRequest): Promise<Schema> {
  const response = await apiClient.post<Schema>("/schemas", data);
  return response;
}

// Update an existing schema
export async function updateSchema(
  schemaId: string,
  data: SchemaUpdateRequest
): Promise<Schema> {
  const response = await apiClient.put<Schema>(`/schemas/${schemaId}`, data);
  return response;
}

// Delete a schema
export async function deleteSchema(schemaId: string): Promise<void> {
  await apiClient.delete(`/schemas/${schemaId}`);
}

// Clone a schema
export async function cloneSchema(
  schemaId: string,
  data: SchemaCloneRequest
): Promise<Schema> {
  const response = await apiClient.post<Schema>(
    `/schemas/${schemaId}/clone`,
    data
  );
  return response;
}
