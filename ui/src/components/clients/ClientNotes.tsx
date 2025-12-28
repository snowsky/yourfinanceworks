import React, { useState, useEffect } from "react";
import { crmApi, ClientNote, getErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ProfessionalTextarea } from "@/components/ui/professional-textarea";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { Loader2, Edit, Save, X, Trash2, Plus } from "lucide-react";
import { toast } from "sonner";
import { ProfessionalCard, ProfessionalCardContent, ProfessionalCardHeader, ProfessionalCardTitle } from "@/components/ui/professional-card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { useTranslation } from 'react-i18next';

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
  const { t } = useTranslation();

  useEffect(() => {
    const fetchNotes = async () => {
      setLoading(true);
      try {
        const data = await crmApi.getNotesForClient(clientId);
        setNotes(data);
      } catch (error) {
        toast.error(getErrorMessage(error, t));
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
      toast.error(getErrorMessage(error, t));
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
      toast.error(getErrorMessage(error, t));
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
      setNotes((notes || []).filter(note => note.id !== noteToDelete.id));
      toast.success("Note deleted successfully.");
    } catch (error) {
      toast.error(getErrorMessage(error, t));
    } finally {
      setDeleting(false);
      setNoteToDelete(null);
    }
  };

  return (
    <>
      <ProfessionalCard className="w-full max-w-4xl mx-auto mt-8 backdrop-blur-sm bg-card/95 shadow-xl border-primary/10">
        <ProfessionalCardHeader className="pb-6 border-b border-border/50">
          <ProfessionalCardTitle className="text-xl font-bold">{t('clients.client_notes')}</ProfessionalCardTitle>
        </ProfessionalCardHeader>
        <ProfessionalCardContent className="pt-6">
          <div className="space-y-6">
            <div className="space-y-4">
              <ProfessionalTextarea
                placeholder={t('clients.add_new_note')}
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
                rows={3}
                variant="filled"
              />
              <div className="flex justify-end">
                <ProfessionalButton
                  onClick={handleAddNote}
                  disabled={submitting}
                  variant="default"
                  size="sm"
                  leftIcon={submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                >
                  {t('clients.add_note')}
                </ProfessionalButton>
              </div>
            </div>

            <div className="border-t border-border/50 pt-6">
              {loading ? (
                <div className="flex items-center justify-center h-24">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : (
                <div className="space-y-4">
                  {notes.length > 0 ? (
                    notes.map((note) => (
                      <div key={note.id} className="p-4 bg-muted/40 rounded-xl border border-border/50 hover:bg-muted/60 transition-colors">
                        {editingNoteId === note.id ? (
                          <div className="space-y-3">
                            <ProfessionalTextarea
                              value={editingText}
                              onChange={(e) => setEditingText(e.target.value)}
                              rows={3}
                              className="bg-background"
                            />
                            <div className="flex gap-2 justify-end">
                              <ProfessionalButton
                                size="sm"
                                variant="outline"
                                onClick={handleCancelEdit}
                                disabled={updating}
                                leftIcon={<X className="h-4 w-4" />}
                              >
                                {t('common.cancel')}
                              </ProfessionalButton>
                              <ProfessionalButton
                                size="sm"
                                onClick={handleSaveEdit}
                                disabled={updating}
                                leftIcon={updating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                              >
                                {t('common.save')}
                              </ProfessionalButton>
                            </div>
                          </div>
                        ) : (
                          <div>
                            <div className="flex justify-between items-start gap-4">
                              <p className="text-sm flex-1 whitespace-pre-wrap">{note.note}</p>
                              <div className="flex gap-1 shrink-0">
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
                                  className="h-8 w-8 p-0 text-destructive hover:text-destructive hover:bg-destructive/10"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                            <p className="text-xs text-muted-foreground mt-2 flex items-center gap-2">
                              <span>{new Date(note.created_at).toLocaleString()}</span>
                              {note.updated_at !== note.created_at && (
                                <span className="text-xs italic opacity-70">(edited)</span>
                              )}
                            </p>
                          </div>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <p>{t('clients.no_notes_for_this_client_yet')}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>

      <Dialog open={!!noteToDelete} onOpenChange={() => setNoteToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('clients.delete_note')}</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p>{t('clients.delete_note_confirmation')}</p>
            <div className="mt-4 p-3 bg-muted/50 rounded-lg text-sm border border-border/50">
              "{noteToDelete?.note}"
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNoteToDelete(null)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteNote}
              disabled={deleting}
            >
              {deleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}