import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Mail, Plus, X, ChevronDown, ChevronUp } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';

import {
  emailReferencesApi,
  type EmailReference,
  type EmailSearchResult,
} from '@/lib/api/email-references';

interface EmailReferencesProps {
  /** e.g. "invoice" | "expense" | "bank_statement" | "investment_portfolio" */
  documentType: string;
  documentId: number;
  /** Full path to the GET endpoint, e.g. "/invoices/42/email-references" */
  apiPath: string;
  readOnly?: boolean;
}

export function EmailReferences({
  documentType,
  documentId,
  apiPath,
  readOnly = false,
}: EmailReferencesProps) {
  const queryClient = useQueryClient();
  const queryKey = ['email-references', documentType, documentId];

  const { data: references = [], isLoading } = useQuery({
    queryKey,
    queryFn: () => emailReferencesApi.getForDocument(apiPath),
  });

  const [showLinkDialog, setShowLinkDialog] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const { data: searchResults = [], isFetching: isSearching } = useQuery({
    queryKey: ['email-search', searchQuery],
    queryFn: () => emailReferencesApi.searchEmails(searchQuery),
    enabled: searchQuery.trim().length >= 2,
  });

  const linkMutation = useMutation({
    mutationFn: (rawEmailId: number) =>
      emailReferencesApi.linkEmail(rawEmailId, {
        document_type: documentType,
        document_id: documentId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
      toast.success('Email linked');
      setShowLinkDialog(false);
      setSearchQuery('');
    },
    onError: () => toast.error('Failed to link email'),
  });

  const unlinkMutation = useMutation({
    mutationFn: (rawEmailId: number) =>
      emailReferencesApi.unlinkEmail(rawEmailId, {
        document_type: documentType,
        document_id: documentId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
      toast.success('Email unlinked');
    },
    onError: () => toast.error('Failed to unlink email'),
  });

  const alreadyLinkedIds = new Set(references.map((r) => r.raw_email_id));

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Mail className="h-4 w-4" />
          Source Emails
          {references.length > 0 && (
            <Badge variant="secondary">{references.length}</Badge>
          )}
        </CardTitle>
        {!readOnly && (
          <Button variant="outline" size="sm" onClick={() => setShowLinkDialog(true)}>
            <Plus className="h-3 w-3 mr-1" />
            Link Email
          </Button>
        )}
      </CardHeader>

      <CardContent>
        {isLoading && (
          <p className="text-sm text-muted-foreground">Loading...</p>
        )}

        {!isLoading && references.length === 0 && (
          <p className="text-sm text-muted-foreground italic">
            No emails linked to this document.
          </p>
        )}

        <div className="space-y-2">
          {references.map((ref) => (
            <EmailReferenceCard
              key={ref.reference_id}
              reference={ref}
              expanded={expandedId === ref.reference_id}
              onToggle={() =>
                setExpandedId(expandedId === ref.reference_id ? null : ref.reference_id)
              }
              onUnlink={
                readOnly
                  ? undefined
                  : () => unlinkMutation.mutate(ref.raw_email_id)
              }
            />
          ))}
        </div>
      </CardContent>

      <Dialog open={showLinkDialog} onOpenChange={(open) => {
        setShowLinkDialog(open);
        if (!open) setSearchQuery('');
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Link an Email</DialogTitle>
          </DialogHeader>
          <Input
            placeholder="Search by subject or sender..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            autoFocus
          />
          <div className="space-y-1 max-h-64 overflow-y-auto mt-2">
            {isSearching && searchQuery.trim().length >= 2 && (
              <p className="text-sm text-muted-foreground px-2">Searching...</p>
            )}
            {!isSearching && searchQuery.trim().length >= 2 && searchResults.length === 0 && (
              <p className="text-sm text-muted-foreground px-2">No emails found.</p>
            )}
            {searchResults.map((email: EmailSearchResult) => {
              const linked = alreadyLinkedIds.has(email.id);
              return (
                <div
                  key={email.id}
                  className="flex items-center justify-between p-2 rounded hover:bg-muted"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate">
                      {email.subject || '(no subject)'}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {email.sender}
                      {email.date && ` · ${new Date(email.date).toLocaleDateString()}`}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant={linked ? 'secondary' : 'default'}
                    disabled={linked || linkMutation.isPending}
                    onClick={() => linkMutation.mutate(email.id)}
                    className="ml-2 shrink-0"
                  >
                    {linked ? 'Linked' : 'Link'}
                  </Button>
                </div>
              );
            })}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}


// ---------------------------------------------------------------------------
// Sub-component
// ---------------------------------------------------------------------------

interface EmailReferenceCardProps {
  reference: EmailReference;
  expanded: boolean;
  onToggle: () => void;
  onUnlink?: () => void;
}

function EmailReferenceCard({ reference, expanded, onToggle, onUnlink }: EmailReferenceCardProps) {
  const formattedDate = reference.date
    ? new Date(reference.date).toLocaleDateString()
    : null;

  return (
    <div className="border rounded-md p-3 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="font-medium truncate">
            {reference.subject || '(no subject)'}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1 flex-wrap">
            <span>{reference.sender || 'Unknown sender'}</span>
            {formattedDate && <span>· {formattedDate}</span>}
            {reference.link_type === 'auto' && (
              <Badge variant="outline" className="text-xs py-0 h-4">auto</Badge>
            )}
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {reference.snippet && (
            <Button variant="ghost" size="icon" onClick={onToggle} className="h-6 w-6">
              {expanded
                ? <ChevronUp className="h-3 w-3" />
                : <ChevronDown className="h-3 w-3" />
              }
            </Button>
          )}
          {onUnlink && (
            <Button
              variant="ghost"
              size="icon"
              onClick={onUnlink}
              className="h-6 w-6 text-destructive hover:text-destructive"
            >
              <X className="h-3 w-3" />
            </Button>
          )}
        </div>
      </div>

      {expanded && reference.snippet && (
        <p className="mt-2 text-xs text-muted-foreground whitespace-pre-wrap border-t pt-2 font-mono">
          {reference.snippet}
        </p>
      )}
    </div>
  );
}
