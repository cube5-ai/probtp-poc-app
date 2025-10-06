"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import {
  Plus,
  FolderOpen,
  Calendar,
  FileText,
  MoreVertical,
  Trash2,
} from "lucide-react";
import { format } from "date-fns";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
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
import Loading from "@/components/common/loading";
import { Spinner } from "@/components/ui/spinner";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import { documentService, type Project } from "@/lib/api/documents";
import { toast } from "sonner";

const ProjectsPage = () => {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/signin");
      return;
    }
  }, [user, loading, router]);

  useEffect(() => {
    const loadProjects = async () => {
      if (!user) return;

      try {
        setIsLoading(true);

        // Get user's projects from backend
        const userProjects = await documentService.getProjects();
        setProjects(userProjects);
      } catch (error) {
        console.error("Failed to load projects:", error);
        toast.error("Failed to load projects");
      } finally {
        setIsLoading(false);
      }
    };

    loadProjects();
  }, [user, router]);

  const handleCreateProject = async (name: string, description?: string) => {
    try {
      const newProject = await documentService.createProject(name, description);

      setProjects([...projects, newProject]);
      toast.success("Project created successfully!");

      // Redirect to the new project
      router.push(`/projects/${newProject.id}`);
    } catch (error) {
      console.error("Failed to create project:", error);
      toast.error("Failed to create project");
      throw error; // Re-throw so dialog can handle it
    }
  };

  const handleDeleteProject = async () => {
    if (!projectToDelete) return;

    try {
      setIsDeleting(true);
      await documentService.deleteProject(projectToDelete.id);
      setProjects((prev) => prev.filter((p) => p.id !== projectToDelete.id));
      toast.success("Project deleted successfully");
    } catch (error) {
      console.error("Failed to delete project:", error);
      toast.error(
        `Failed to delete project: ${
          error instanceof Error ? error.message : "Unknown error"
        }`
      );
    } finally {
      setIsDeleting(false);
      setProjectToDelete(null);
    }
  };

  const handleProjectClick = (project: Project) => {
    router.push(`/projects/${project.id}`);
  };

  if (loading || isLoading) {
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
    <>
      {/* Create Project Dialog */}
      <CreateProjectDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        onSubmit={handleCreateProject}
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog
        open={!!projectToDelete}
        onOpenChange={(open) =>
          !open && !isDeleting && setProjectToDelete(null)
        }
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Project</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;
              {projectToDelete?.name}&quot;? This action cannot be undone and
              will delete all files in this project.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteProject}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting && <Spinner className="mr-2 h-4 w-4" />}
              {isDeleting ? "Deleting..." : "Delete Project"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <div className="min-h-screen bg-background">
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-5xl mx-auto space-y-8">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold">Projects</h1>
                <p className="text-muted-foreground mt-2">
                  Manage your document comparison projects
                </p>
              </div>

              <Button onClick={() => setShowCreateDialog(true)} size="lg">
                <Plus className="w-4 h-4 mr-2" />
                New Project
              </Button>
            </div>

            {/* Projects List */}
            {projects.length === 0 ? (
              <Empty>
                <EmptyHeader>
                  <EmptyMedia variant="icon">
                    <FolderOpen className="w-16 h-16" />
                  </EmptyMedia>
                  <EmptyTitle>No projects yet</EmptyTitle>
                  <EmptyDescription>
                    Create your first project to start comparing documents
                  </EmptyDescription>
                </EmptyHeader>
                <EmptyContent>
                  <Button onClick={() => setShowCreateDialog(true)} size="lg">
                    <Plus className="w-4 h-4 mr-2" />
                    Create First Project
                  </Button>
                </EmptyContent>
              </Empty>
            ) : (
              <div className="bg-card rounded-lg border">
                <ul role="list" className="divide-y divide-border">
                  {projects.map((project) => (
                    <li
                      key={project.id}
                      className="flex items-center justify-between gap-x-6 p-5 hover:bg-accent/50 transition-colors cursor-pointer"
                      onClick={() => handleProjectClick(project)}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start gap-x-3">
                          <FolderOpen className="h-5 w-5 text-muted-foreground mt-0.5 flex-shrink-0" />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-x-2 flex-wrap">
                              <p className="text-sm font-semibold leading-6 text-foreground">
                                {project.name}
                              </p>
                              <Badge variant="secondary" className="text-xs">
                                Active
                              </Badge>
                            </div>
                            {project.description ? (
                              <p className="mt-1 text-sm text-muted-foreground line-clamp-1">
                                {project.description}
                              </p>
                            ) : (
                              <p className="mt-1 text-sm italic text-muted-foreground line-clamp-1">
                                No description
                              </p>
                            )}
                            <div className="mt-1 flex items-center gap-x-2 text-xs text-muted-foreground">
                              <div className="flex items-center gap-x-1">
                                <Calendar className="h-3 w-3" />
                                <time dateTime={project.created_at}>
                                  {format(
                                    new Date(project.created_at),
                                    "MMM d, yyyy"
                                  )}
                                </time>
                              </div>
                              <svg
                                viewBox="0 0 2 2"
                                className="h-0.5 w-0.5 fill-current"
                              >
                                <circle r={1} cx={1} cy={1} />
                              </svg>
                              <div className="flex items-center gap-x-1">
                                <FileText className="h-3 w-3" />
                                <span>
                                  {project.file_count}{" "}
                                  {project.file_count === 1 ? "file" : "files"}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                      <div className="flex flex-none items-center gap-x-4">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleProjectClick(project);
                          }}
                          className="hidden sm:flex"
                        >
                          View project
                          <span className="sr-only">, {project.name}</span>
                        </Button>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <span className="sr-only">Open options</span>
                              <MoreVertical className="h-5 w-5" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                setProjectToDelete({
                                  id: project.id,
                                  name: project.name,
                                });
                              }}
                              className="text-destructive"
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                              <span className="sr-only">, {project.name}</span>
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
};

export default ProjectsPage;
