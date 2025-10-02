/**
 * TypeScript types for Schema entities
 */

export interface Schema {
  id: string;
  userId: string;
  name: string;
  description?: string;
  schemaDefinition: SchemaDefinition;
  baseSchemaId?: string;
  isTemplate: boolean;
  version: number;
  createdAt: string;
  updatedAt: string;
}

export interface SchemaDefinition {
  type: string;
  properties: Record<string, SchemaProperty>;
  required?: string[];
}

export interface SchemaProperty {
  type: string;
  description?: string;
  format?: string;
  items?: SchemaProperty;
  properties?: Record<string, SchemaProperty>;
}

export interface SchemaListResponse {
  schemas: Schema[];
  total: number;
  page: number;
  page_size: number;
}

export interface SchemaCreateRequest {
  name: string;
  description?: string;
  schemaDefinition: SchemaDefinition;
  baseSchemaId?: string;
  isTemplate?: boolean;
}

export interface SchemaUpdateRequest {
  name?: string;
  description?: string;
  schemaDefinition?: SchemaDefinition;
}

export interface SchemaCloneRequest {
  name: string;
  description?: string;
}

export enum FieldType {
  TEXT = "text",
  NUMBER = "number",
  DATE = "date",
  BOOLEAN = "boolean",
  EMAIL = "email",
  URL = "url",
  ARRAY = "array",
  OBJECT = "object",
}
