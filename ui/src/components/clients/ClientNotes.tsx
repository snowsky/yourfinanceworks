import React, { useState, useEffect } from "react";
import { crmApi, ClientNote } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Edit, Save, X, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";

interface ClientNotesProps {
  clientId: number;
}

export function ClientNotes({ clientId }: ClientNotesProps) {
  const [notes, setNotes] = useState<ClientNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [newNote, setNewNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [editingText, setEditingText] = useState("");
  const [updating, setUpdating] = useState(false);
  const [noteToDelete, setNoteToDelete] = useState<ClientNote | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const fetchNotes = async () => {
      setLoading(true);
      try {
        const data = await crmApi.getNotesForClient(clientId);
        setNotes(data);
      } catch (error) {
        toast.error("Failed to load client notes.");
      } finally {
        setLoading(false);
      }
    };
    fetchNotes();
  }, [clientId]);

  const handleAddNote = async () => {
    if (!newNote.trim()) {
      toast.error("Note cannot be empty.");
      return;
    }
    setSubmitting(true);
    try {
      const addedNote = await crmApi.createNoteForClient(clientId, { note: newNote });
      setNotes([addedNote, ...notes]);
      setNewNote("");
      toast.success("Note added successfully.");
    } catch (error) {
      toast.error("Failed to add note.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleEditNote = (note: ClientNote) => {
    setEditingNoteId(note.id);
    setEditingText(note.note);
  };

  const handleSaveEdit = async () => {
    if (!editingText.trim()) {
      toast.error("Note cannot be empty.");
      return;
    }
    if (editingNoteId === null) return;

    setUpdating(true);
    try {
      const updatedNote = await crmApi.updateNoteForClient(clientId, editingNoteId, { note: editingText });
      setNotes(notes.map(note => note.id === editingNoteId ? updatedNote : note));
      setEditingNoteId(null);
      setEditingText("");
      toast.success("Note updated successfully.");
    } catch (error) {
      toast.error("Failed to update note.");
    } finally {
      setUpdating(false);
    }
  };

  const handleCancelEdit = () => {
    setEditingNoteId(null);
    setEditingText("");
  };

  const handleDeleteNote = async () => {
    if (!noteToDelete) return;

    setDeleting(true);
    try {
      await crmApi.deleteNoteForClient(clientId, noteToDelete.id);
      setNotes(notes.filter(note => note.id !== noteToDelete.id));
      toast.success("Note deleted successfully.");
    } catch (error) {
      toast.error("Failed to delete note.");
    } finally {
      setDeleting(false);
      setNoteToDelete(null);
    }
  };

  return (
    <>
      <Card className="w-full max-w-2xl mx-auto mt-6">
        <CardHeader>
          <CardTitle>Client Notes</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <Textarea
                placeholder="Add a new note..."
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
                rows={3}
              />
              <Button onClick={handleAddNote} disabled={submitting} className="mt-2">
                {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Add Note
              </Button>
            </div>
            {loading ? (
              <div className="flex items-center justify-center h-24">
                  <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            ) : (
              <div className="space-y-4">
                {notes.length > 0 ? (
                  notes.map((note) => (
                    <div key={note.id} className="p-3 bg-muted rounded-lg">
                      {editingNoteId === note.id ? (
                        <div className="space-y-2">
                          <Textarea
                            value={editingText}
                            onChange={(e) => setEditingText(e.target.value)}
                            rows={3}
                          />
                          <div className="flex gap-2">
                            <Button 
                              size="sm" 
                              onClick={handleSaveEdit} 
                              disabled={updating}
                            >
                              {updating ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Save className="h-4 w-4" />
                              )}
                            </Button>
                            <Button 
                              size="sm" 
                              variant="outline" 
                              onClick={handleCancelEdit}
                              disabled={updating}
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <div>
                          <div className="flex justify-between items-start">
                            <p className="text-sm flex-1">{note.note}</p>
                            <div className="flex gap-1 ml-2">
                              <Button 
                                size="sm" 
                                variant="ghost" 
                                onClick={() => handleEditNote(note)}
                                className="h-8 w-8 p-0"
                              >
                                <Edit className="h-4 w-4" />
                              </Button>
                              <Button 
                                size="sm" 
                                variant="ghost" 
                                onClick={() => setNoteToDelete(note)}
                                className="h-8 w-8 p-0 text-red-500 hover:text-red-700"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                          <p className="text-xs text-muted-foreground mt-1">
                            {new Date(note.created_at).toLocaleString()}
                            {note.updated_at !== note.created_at && (
                              <span className="ml-2">(edited {new Date(note.updated_at).toLocaleString()})</span>
                            )}
                          </p>
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">No notes for this client yet.</p>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Dialog open={!!noteToDelete} onOpenChange={() => setNoteToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Note</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p>Are you sure you want to delete this note? This action cannot be undone.</p>
            <div className="mt-2 p-2 bg-muted rounded text-sm">
              "{noteToDelete?.note}"
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNoteToDelete(null)}>
              Cancel
            </Button>
            <Button 
              variant="destructive" 
              onClick={handleDeleteNote}
              disabled={deleting}
            >
              {deleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}