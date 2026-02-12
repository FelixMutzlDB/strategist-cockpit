import { useState, useEffect } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  listProjects,
  createProject,
  deleteProject,
  type Project,
} from "@/lib/api";
import {
  ExternalLink,
  Plus,
  Presentation,
  AppWindow,
  FileText,
  Trash2,
  Globe,
} from "lucide-react";

function getCategoryIcon(category: string | null) {
  switch (category) {
    case "Presentation":
      return Presentation;
    case "Application":
      return AppWindow;
    case "Document":
      return FileText;
    default:
      return Globe;
  }
}

function getCategoryColor(category: string | null) {
  switch (category) {
    case "Presentation":
      return "from-blue-500/20 to-indigo-500/20";
    case "Application":
      return "from-emerald-500/20 to-teal-500/20";
    case "Document":
      return "from-amber-500/20 to-orange-500/20";
    default:
      return "from-gray-500/20 to-slate-500/20";
  }
}

export default function Gallery() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [loading, setLoading] = useState(true);

  // Form state
  const [newName, setNewName] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newCategory, setNewCategory] = useState("Presentation");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      const data = await listProjects();
      setProjects(data);
    } catch (e) {
      console.error("Failed to load projects:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async () => {
    if (!newName.trim() || !newUrl.trim()) return;
    setSubmitting(true);
    try {
      await createProject({
        name: newName,
        url: newUrl,
        description: newDescription || undefined,
        category: newCategory || undefined,
      });
      setShowAddDialog(false);
      setNewName("");
      setNewUrl("");
      setNewDescription("");
      setNewCategory("Presentation");
      await loadProjects();
    } catch (e) {
      console.error("Failed to create project:", e);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteProject(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
    } catch (e) {
      console.error("Failed to delete project:", e);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Projects Gallery</h1>
        <p className="text-muted-foreground mt-1">
          Reusable assets, key artefacts, and important resources.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {loading ? (
          <p className="text-muted-foreground col-span-3">Loading...</p>
        ) : (
          <>
            {projects.map((project) => {
              const Icon = getCategoryIcon(project.category);
              const colorClass = getCategoryColor(project.category);
              return (
                <Card key={project.id} className="group relative flex flex-col">
                  <CardHeader>
                    <div
                      className={`h-32 -mx-6 -mt-6 rounded-t-lg bg-gradient-to-br ${colorClass} flex items-center justify-center mb-2`}
                    >
                      <Icon className="h-12 w-12 text-foreground/30" />
                    </div>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-base">{project.name}</CardTitle>
                        {project.category && (
                          <span className="text-xs text-muted-foreground">{project.category}</span>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => handleDelete(project.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5 text-destructive" />
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="flex-1">
                    <CardDescription className="text-sm">
                      {project.description || "No description"}
                    </CardDescription>
                  </CardContent>
                  <CardFooter>
                    <a
                      href={project.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="w-full"
                    >
                      <Button variant="outline" className="w-full" size="sm">
                        Open <ExternalLink className="h-3.5 w-3.5 ml-2" />
                      </Button>
                    </a>
                  </CardFooter>
                </Card>
              );
            })}

            {/* Add New Tile */}
            <Card
              className="flex flex-col items-center justify-center min-h-[280px] border-dashed cursor-pointer hover:bg-accent/50 transition-colors"
              onClick={() => setShowAddDialog(true)}
            >
              <div className="text-center space-y-2">
                <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                  <Plus className="h-6 w-6 text-primary" />
                </div>
                <p className="font-medium text-sm">Add New Project</p>
                <p className="text-xs text-muted-foreground">
                  Add a link to a presentation, app, or document
                </p>
              </div>
            </Card>
          </>
        )}
      </div>

      {/* Add Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New Project</DialogTitle>
            <DialogDescription>
              Add a link to an important artefact, presentation, or application.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                placeholder="e.g. Systems of Intelligence"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="url">Link</Label>
              <Input
                id="url"
                placeholder="https://..."
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="Brief description of the artefact..."
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="category">Category</Label>
              <select
                id="category"
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              >
                <option value="Presentation">Presentation</option>
                <option value="Application">Application</option>
                <option value="Document">Document</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleAdd} disabled={!newName.trim() || !newUrl.trim() || submitting}>
              {submitting ? "Adding..." : "Add Project"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
