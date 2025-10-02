"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { Plus, FolderOpen, Calendar, User, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Loading from "@/components/common/loading";
import { documentService, type Project } from "@/lib/api/documents";
import { toast } from "sonner";

const ProjectsPage = () => {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);

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
        
        // If user has exactly one project, redirect to it
        if (userProjects.length === 1) {
          router.push(`/projects/${userProjects[0].id}`);
          return;
        }
        
      } catch (error) {
        console.error('Failed to load projects:', error);
        toast.error('Failed to load projects');
      } finally {
        setIsLoading(false);
      }
    };

    loadProjects();
  }, [user, router]);


  const handleCreateProject = async () => {
    try {
      setIsCreating(true);
      const newProject = await documentService.createProject(
        `Project ${projects.length + 1}`,
        "New project for document comparison"
      );
      
      setProjects([...projects, newProject]);
      toast.success("Project created successfully!");
      
      // Redirect to the new project
      router.push(`/projects/${newProject.id}`);
      
    } catch (error) {
      console.error('Failed to create project:', error);
      toast.error('Failed to create project');
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteProject = async (projectId: string, projectName: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent card click navigation
    
    if (!confirm(`Are you sure you want to delete "${projectName}"? This action cannot be undone and will delete all files in this project.`)) {
      return;
    }
    
    try {
      await documentService.deleteProject(projectId);
      setProjects(prev => prev.filter(p => p.id !== projectId));
      toast.success(`Project "${projectName}" deleted successfully`);
    } catch (error) {
      console.error('Failed to delete project:', error);
      toast.error(`Failed to delete project: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
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
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-6xl mx-auto space-y-8">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold">Projects</h1>
              <p className="text-muted-foreground mt-2">
                Manage your document comparison projects
              </p>
            </div>
            
            <Button 
              onClick={handleCreateProject}
              disabled={isCreating}
              size="lg"
            >
              <Plus className="w-4 h-4 mr-2" />
              {isCreating ? "Creating..." : "New Project"}
            </Button>
          </div>

          {/* Projects Grid */}
          {projects.length === 0 && !isCreating ? (
            <div className="text-center py-12">
              <FolderOpen className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No projects yet</h3>
              <p className="text-muted-foreground mb-6">
                Create your first project to start comparing documents
              </p>
              <Button onClick={handleCreateProject} size="lg">
                <Plus className="w-4 h-4 mr-2" />
                Create First Project
              </Button>
            </div>
          ) : (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {projects.map((project) => (
                <Card 
                  key={project.id}
                  className="cursor-pointer hover:shadow-md transition-shadow"
                  onClick={() => router.push(`/projects/${project.id}`)}
                >
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <FolderOpen className="w-5 h-5" />
                        {project.name}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive hover:bg-destructive/10"
                        onClick={(e) => handleDeleteProject(project.id, project.name, e)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {project.description && (
                      <p className="text-sm text-muted-foreground">
                        {project.description}
                      </p>
                    )}
                    
                    <div className="space-y-2 text-xs text-muted-foreground">
                      <div className="flex items-center gap-2">
                        <Calendar className="w-3 h-3" />
                        Created {formatDate(project.created_at)}
                      </div>
                      <div className="flex items-center gap-2">
                        <User className="w-3 h-3" />
                        {project.created_by}
                      </div>
                    </div>
                    
                    <Badge variant="secondary" className="text-xs">
                      Active
                    </Badge>
                  </CardContent>
                </Card>
              ))}
              
              {/* Create New Project Card */}
              <Card 
                className="cursor-pointer hover:shadow-md transition-shadow border-dashed"
                onClick={handleCreateProject}
              >
                <CardContent className="flex flex-col items-center justify-center py-12">
                  <Plus className="w-8 h-8 text-muted-foreground mb-4" />
                  <h3 className="font-semibold mb-2">Create New Project</h3>
                  <p className="text-sm text-muted-foreground text-center">
                    Start a new document comparison project
                  </p>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProjectsPage;
