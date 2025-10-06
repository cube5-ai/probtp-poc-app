/**
 * Schema list component
 * Displays a grid of schema cards with filtering and search
 */
"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Plus,
  Search,
  ListFilter,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
} from "lucide-react";
import { toast } from "sonner";
import type { Schema } from "@/types/schema.types";
import { listSchemas, deleteSchema } from "@/lib/api/schemas";
import { SchemaCard } from "./schema-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/contexts/AuthContext";

export function SchemaList() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth(); // Get current user and auth loading state
  const [allSchemas, setAllSchemas] = useState<Schema[]>([]); // All schemas from backend
  const [loading, setLoading] = useState(false); // Changed to false, will be set by effect
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState("");
  const [filterType, setFilterType] = useState<"all" | "my" | "templates">(
    "all"
  );
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(6); // Fixed page size for client-side pagination
  const hasLoadedOnce = useRef(false); // Track if we've loaded data at least once

  // Debounce search term
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setCurrentPage(1); // Reset to first page when searching
    }, 300); // 300ms delay

    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Reset to page 1 when filter changes
  useEffect(() => {
    setCurrentPage(1);
  }, [filterType]);

  // Single unified data fetching effect - fetch ALL user's schemas once
  useEffect(() => {
    // Don't fetch until auth is ready
    if (authLoading) {
      setLoading(true);
      return;
    }

    const fetchSchemas = async () => {
      try {
        // Show skeleton loading only on first ever load
        const isFirstLoad = !hasLoadedOnce.current;
        setLoading(isFirstLoad);

        // Fetch all user's schemas (backend returns all, no filtering)
        const response = await listSchemas({
          search: debouncedSearchTerm || undefined,
        });

        setAllSchemas(response.schemas);

        // Mark that we've loaded at least once
        hasLoadedOnce.current = true;
      } catch (error) {
        toast.error("Failed to load schemas");
        console.error("Error fetching schemas:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchSchemas();
  }, [authLoading, debouncedSearchTerm]);

  const handleEdit = (schema: Schema) => {
    router.push(`/settings/schema/${schema.id}`);
  };

  const handleDelete = async (schemaId: string) => {
    try {
      console.log("Deleting schema:", schemaId);
      await deleteSchema(schemaId);
      console.log("Schema deleted successfully");
      toast.success("Schema deleted successfully");

      // Remove schema from local state (optimistic update)
      setAllSchemas((prevSchemas) =>
        prevSchemas.filter((s) => s.id !== schemaId)
      );
    } catch (err) {
      const error = err as {
        response?: {
          status?: number;
          statusText?: string;
          data?: { detail?: string };
        };
      };
      console.error("Error deleting schema:", error);
      console.error("Delete error details:", {
        status: error?.response?.status,
        statusText: error?.response?.statusText,
        data: error?.response?.data,
      });

      if (error?.response?.status === 401) {
        toast.error("Authentication required to delete schema.");
      } else if (error?.response?.status === 403) {
        toast.error("You don't have permission to delete this schema.");
      } else if (error?.response?.status === 404) {
        toast.error("Schema not found. It may have already been deleted.");
      } else if (error?.response?.data?.detail) {
        toast.error(`Error: ${error.response.data.detail}`);
      } else {
        toast.error("Failed to delete schema. Please try again.");
      }
    }
  };

  const handleClone = (schema: Schema) => {
    router.push(`/settings/schema/new?cloneFromId=${schema.id}`);
  };

  const handleCreateNew = () => {
    router.push("/settings/schema/new");
  };

  // Client-side filtering based on filter type
  const filteredSchemas = allSchemas.filter((schema) => {
    if (filterType === "templates") {
      return schema.isTemplate === true;
    } else if (filterType === "my") {
      return schema.isTemplate !== true;
    }
    // "all" - return everything
    return true;
  });

  // Client-side pagination (on filtered schemas)
  const total = filteredSchemas.length;
  const totalPages = Math.ceil(total / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  const paginatedSchemas = filteredSchemas.slice(startIndex, endIndex);
  const startItem = total > 0 ? startIndex + 1 : 0;
  const endItem = Math.min(endIndex, total);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const getFilterLabel = (type: "all" | "my" | "templates") => {
    switch (type) {
      case "all":
        return "All Schemas";
      case "my":
        return "My Schemas";
      case "templates":
        return "Templates";
      default:
        return "All Schemas";
    }
  };

  const handleFilterChange = (type: "all" | "my" | "templates") => {
    setFilterType(type);
    setCurrentPage(1); // Reset to first page when changing filter
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-10 bg-muted animate-pulse rounded" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-40 bg-muted animate-pulse rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Data Schemas</h2>
          <p className="text-muted-foreground mt-1">
            Manage your data extraction schemas
          </p>
        </div>
        <Button onClick={handleCreateNew}>
          <Plus className="mr-2 h-4 w-4" />
          New Schema
        </Button>
      </div>

      {/* Search and Filters */}
      <div className="flex gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search schemas..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline">
              <ListFilter className="mr-2 h-4 w-4" />
              {getFilterLabel(filterType)}
              <ChevronDown className="ml-2 h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => handleFilterChange("all")}>
              All Schemas
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleFilterChange("my")}>
              My Schemas
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleFilterChange("templates")}>
              Templates
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Results count and pagination info */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>
            Showing {startItem}-{endItem} of {total} schemas
          </span>
          {debouncedSearchTerm && (
            <Badge variant="secondary">Searching: {debouncedSearchTerm}</Badge>
          )}
        </div>

        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>

            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNum;
                if (totalPages <= 5) {
                  pageNum = i + 1;
                } else if (currentPage <= 3) {
                  pageNum = i + 1;
                } else if (currentPage >= totalPages - 2) {
                  pageNum = totalPages - 4 + i;
                } else {
                  pageNum = currentPage - 2 + i;
                }

                return (
                  <Button
                    key={pageNum}
                    variant={currentPage === pageNum ? "default" : "outline"}
                    size="sm"
                    onClick={() => handlePageChange(pageNum)}
                    className="w-8 h-8 p-0"
                  >
                    {pageNum}
                  </Button>
                );
              })}
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>

      {/* Schema Grid */}
      {paginatedSchemas.length === 0 ? (
        <Card className="p-12 text-center">
          <div className="flex flex-col items-center gap-4">
            <div className="rounded-full bg-muted p-6">
              <Search className="h-12 w-12 text-muted-foreground" />
            </div>
            <div>
              <h3 className="text-lg font-semibold mb-2">No schemas found</h3>
              <p className="text-muted-foreground mb-4">
                {debouncedSearchTerm
                  ? "Try adjusting your search term"
                  : "Get started by creating your first schema"}
              </p>
              {!debouncedSearchTerm && (
                <Button onClick={handleCreateNew}>
                  <Plus className="mr-2 h-4 w-4" />
                  Create Schema
                </Button>
              )}
            </div>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {paginatedSchemas.map((schema) => (
            <SchemaCard
              key={schema.id}
              schema={schema}
              currentUserId={user?.uid}
              onClick={handleEdit}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onClone={handleClone}
            />
          ))}
        </div>
      )}
    </div>
  );
}
