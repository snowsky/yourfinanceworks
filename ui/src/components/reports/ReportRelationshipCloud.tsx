import type { FC } from 'react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowRight,
  FileText,
  Landmark,
  Loader2,
  MousePointer2,
  Network,
  Receipt,
  ScanSearch,
  Unlink,
  X,
} from 'lucide-react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { reportApi, type RelationshipCloudResponse, type ReportFilters } from '@/lib/api';

type SupportedReportType = 'invoice' | 'expense' | 'statement';
type CloudNodeType = 'statement' | 'invoice' | 'expense';

interface ReportRelationshipCloudProps {
  reportType: string;
  filters: ReportFilters;
}

interface CloudNode {
  id: string;
  entityId: number;
  type: CloudNodeType;
  title: string;
  subtitle: string;
  status?: string | null;
  x: number;
  y: number;
}

interface PositionedGraph {
  nodes: CloudNode[];
  edges: RelationshipCloudResponse['edges'];
  stats: RelationshipCloudResponse['stats'];
}

const isSupportedReportType = (value: string): value is SupportedReportType =>
  value === 'invoice' || value === 'expense' || value === 'statement';

const nodeColors: Record<CloudNodeType, string> = {
  statement: 'border-sky-300 bg-sky-50 text-sky-950',
  invoice: 'border-emerald-300 bg-emerald-50 text-emerald-950',
  expense: 'border-amber-300 bg-amber-50 text-amber-950',
};

const nodeMutedColors: Record<CloudNodeType, string> = {
  statement: 'border-sky-100 bg-sky-50/40 text-sky-950/55',
  invoice: 'border-emerald-100 bg-emerald-50/40 text-emerald-950/55',
  expense: 'border-amber-100 bg-amber-50/40 text-amber-950/55',
};

const typeLabel: Record<CloudNodeType, string> = {
  statement: 'Statement',
  invoice: 'Invoice',
  expense: 'Expense',
};

const typeIcon: Record<CloudNodeType, typeof Landmark> = {
  statement: Landmark,
  invoice: FileText,
  expense: Receipt,
};

export const ReportRelationshipCloud: FC<ReportRelationshipCloudProps> = ({
  reportType,
  filters,
}) => {
  const navigate = useNavigate();
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null);

  const enabled = isSupportedReportType(reportType);

  const cloudQuery = useQuery({
    queryKey: ['report-cloud', reportType, filters],
    queryFn: () => reportApi.getRelationshipCloud({
      report_type: reportType as SupportedReportType,
      filters,
      limit: 40,
    }),
    enabled,
    staleTime: 60_000,
  });

  const graph = useMemo<PositionedGraph | null>(() => {
    if (!cloudQuery.data) return null;
    const data = cloudQuery.data as RelationshipCloudResponse;
    const totals: Record<CloudNodeType, number> = {
      statement: data.nodes.filter((node) => node.type === 'statement').length,
      invoice: data.nodes.filter((node) => node.type === 'invoice').length,
      expense: data.nodes.filter((node) => node.type === 'expense').length,
    };
    const grouped: Record<CloudNodeType, number> = { statement: 0, invoice: 0, expense: 0 };
    const nodes = data.nodes.map((node) => {
      const index = grouped[node.type]++;
      const total = totals[node.type];
      const x = node.type === 'statement' ? 14 : node.type === 'invoice' ? 50 : 86;
      const spacing = 100 / (total + 1);
      return {
        id: node.id,
        entityId: node.entity_id,
        type: node.type,
        title: node.title,
        subtitle: node.subtitle || '',
        status: node.status,
        x,
        y: Math.max(14, Math.min(86, spacing * (index + 1))),
      };
    });
    return {
      nodes,
      edges: data.edges,
      stats: data.stats,
    };
  }, [cloudQuery.data]);

  const nodeById = useMemo(
    () => new Map(graph?.nodes.map((node) => [node.id, node]) || []),
    [graph?.nodes]
  );
  const edgeById = useMemo(
    () => new Map(graph?.edges.map((edge) => [edge.id, edge]) || []),
    [graph?.edges]
  );

  const activeNodeId = focusedNodeId || hoveredNodeId;
  const activeEdgeId = hoveredEdgeId;

  const connectedNodeIds = useMemo(() => {
    const ids = new Set<string>();
    if (!graph) return ids;
    if (activeNodeId) {
      ids.add(activeNodeId);
      graph.edges.forEach((edge) => {
        if (edge.source === activeNodeId || edge.target === activeNodeId) {
          ids.add(edge.source);
          ids.add(edge.target);
        }
      });
    }
    if (activeEdgeId) {
      const edge = edgeById.get(activeEdgeId);
      if (edge) {
        ids.add(edge.source);
        ids.add(edge.target);
      }
    }
    return ids;
  }, [activeEdgeId, activeNodeId, edgeById, graph]);

  const connectedEdges = useMemo(() => {
    const ids = new Set<string>();
    if (!graph) return ids;
    graph.edges.forEach((edge) => {
      if (activeNodeId && (edge.source === activeNodeId || edge.target === activeNodeId)) {
        ids.add(edge.id);
      }
      if (activeEdgeId && edge.id === activeEdgeId) {
        ids.add(edge.id);
      }
    });
    return ids;
  }, [activeEdgeId, activeNodeId, graph]);

  const focusedNode = focusedNodeId ? nodeById.get(focusedNodeId) || null : null;
  const focusedRelationships = useMemo(() => {
    if (!focusedNode || !graph) return [];
    return graph.edges
      .filter((edge) => edge.source === focusedNode.id || edge.target === focusedNode.id)
      .map((edge) => {
        const peerId = edge.source === focusedNode.id ? edge.target : edge.source;
        return {
          edge,
          peer: nodeById.get(peerId) || null,
        };
      })
      .filter((entry) => entry.peer);
  }, [focusedNode, graph, nodeById]);

  const openNode = (node: CloudNode) => {
    if (node.type === 'statement') navigate(`/statements?id=${node.entityId}`);
    if (node.type === 'invoice') navigate(`/invoices/${node.entityId}`);
    if (node.type === 'expense') navigate(`/expenses/${node.entityId}`);
  };

  if (!enabled) return null;

  const isLoading = cloudQuery.isLoading;
  const hasError = cloudQuery.isError;

  return (
    <Card className="slide-in overflow-hidden">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Network className="h-5 w-5" />
          Relationship Cloud
        </CardTitle>
        <CardDescription>
          Hover to highlight related records, click a node to inspect its chain, and use the inspector to jump into the source record.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-dashed">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Building relationship map...
            </div>
          </div>
        ) : hasError ? (
          <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-4 text-sm text-destructive">
            The relationship cloud could not be loaded right now.
          </div>
        ) : !graph || graph.nodes.length === 0 ? (
          <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
            No linked statement, invoice, or expense records were found for the current report filters.
          </div>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">{graph.stats.statements} statements</Badge>
              <Badge variant="outline">{graph.stats.invoices} invoices</Badge>
              <Badge variant="outline">{graph.stats.expenses} expenses</Badge>
              {graph.stats.orphan_expenses > 0 && (
                <Badge variant="secondary" className="gap-1">
                  <Unlink className="h-3 w-3" />
                  {graph.stats.orphan_expenses} orphan expenses
                </Badge>
              )}
            </div>

            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
              <div className="relative min-h-[360px] rounded-2xl border bg-gradient-to-br from-background via-muted/20 to-background">
                <div className="absolute left-4 top-4 z-10 flex items-center gap-2 rounded-full border bg-background/90 px-3 py-1 text-xs text-muted-foreground shadow-sm">
                  <MousePointer2 className="h-3.5 w-3.5" />
                  Hover nodes or links to trace a chain
                </div>
                <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
                  {graph.edges.map((edge) => {
                    const source = nodeById.get(edge.source);
                    const target = nodeById.get(edge.target);
                    if (!source || !target) return null;

                    const isConnected = connectedEdges.has(edge.id);
                    const shouldDim = (activeNodeId || activeEdgeId) && !isConnected;
                    const stroke = isConnected ? 'hsl(var(--primary))' : 'currentColor';
                    const strokeWidth = isConnected ? 0.9 : 0.5;

                    return (
                      <g key={edge.id}>
                        <line
                          x1={source.x}
                          y1={source.y}
                          x2={target.x}
                          y2={target.y}
                          stroke={stroke}
                          strokeWidth={strokeWidth}
                          className={shouldDim ? 'text-border/20' : 'text-border'}
                          strokeDasharray={edge.label === 'transaction match' ? '2 1.5' : undefined}
                        />
                        <line
                          x1={source.x}
                          y1={source.y}
                          x2={target.x}
                          y2={target.y}
                          stroke="transparent"
                          strokeWidth="4"
                          onMouseEnter={() => setHoveredEdgeId(edge.id)}
                          onMouseLeave={() => setHoveredEdgeId((current) => (current === edge.id ? null : current))}
                        />
                      </g>
                    );
                  })}
                </svg>

                {graph.nodes.map((node) => {
                  const Icon = typeIcon[node.type];
                  const isActive = connectedNodeIds.has(node.id) || (!activeNodeId && !activeEdgeId);
                  const isFocused = focusedNodeId === node.id;
                  const shouldDim = (activeNodeId || activeEdgeId) && !isActive;

                  return (
                    <button
                      key={node.id}
                      type="button"
                      onMouseEnter={() => setHoveredNodeId(node.id)}
                      onMouseLeave={() => setHoveredNodeId((current) => (current === node.id ? null : current))}
                      onClick={() => setFocusedNodeId((current) => (current === node.id ? null : node.id))}
                      className={`absolute w-40 -translate-x-1/2 -translate-y-1/2 rounded-xl border p-3 text-left shadow-sm transition ${isFocused ? 'scale-[1.03] ring-2 ring-primary/30' : 'hover:scale-[1.02] hover:shadow-md'} ${shouldDim ? nodeMutedColors[node.type] : nodeColors[node.type]}`}
                      style={{ left: `${node.x}%`, top: `${node.y}%`, opacity: shouldDim ? 0.55 : 1 }}
                    >
                      <div className="mb-2 flex items-start justify-between gap-2">
                        <div className="rounded-lg bg-white/70 p-1.5">
                          <Icon className="h-4 w-4" />
                        </div>
                        {node.status ? (
                          <Badge variant="secondary" className="max-w-[68px] truncate text-[10px]">
                            {node.status}
                          </Badge>
                        ) : null}
                      </div>
                      <div className="text-sm font-semibold leading-tight">{node.title}</div>
                      <div className="mt-1 text-xs opacity-80">{node.subtitle}</div>
                    </button>
                  );
                })}
              </div>

              <div className="rounded-2xl border bg-muted/20 p-4">
                {focusedNode ? (
                  <div className="space-y-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">
                          {typeLabel[focusedNode.type]}
                        </div>
                        <h3 className="text-base font-semibold">{focusedNode.title}</h3>
                        <p className="mt-1 text-sm text-muted-foreground">{focusedNode.subtitle}</p>
                      </div>
                      <Button variant="ghost" size="icon" onClick={() => setFocusedNodeId(null)}>
                        <X className="h-4 w-4" />
                      </Button>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      {focusedNode.status ? <Badge variant="secondary">{focusedNode.status}</Badge> : null}
                      <Badge variant="outline">ID {focusedNode.entityId}</Badge>
                    </div>

                    <div>
                      <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                        <ScanSearch className="h-4 w-4" />
                        Connected records
                      </div>
                      <div className="space-y-2">
                        {focusedRelationships.length > 0 ? (
                          focusedRelationships.map(({ edge, peer }) => {
                            if (!peer) return null;
                            const PeerIcon = typeIcon[peer.type];
                            return (
                              <button
                                key={edge.id}
                                type="button"
                                className="w-full rounded-lg border bg-background px-3 py-2 text-left transition hover:border-primary/40"
                                onClick={() => setFocusedNodeId(peer.id)}
                              >
                                <div className="mb-1 flex items-center gap-2 text-sm font-medium">
                                  <PeerIcon className="h-4 w-4" />
                                  {peer.title}
                                </div>
                                <div className="text-xs text-muted-foreground">{edge.label} • {peer.subtitle}</div>
                              </button>
                            );
                          })
                        ) : (
                          <div className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
                            No visible connected records inside the current graph scope.
                          </div>
                        )}
                      </div>
                    </div>

                    <Button className="w-full gap-2" onClick={() => openNode(focusedNode)}>
                      Open {typeLabel[focusedNode.type].toLowerCase()}
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </div>
                ) : (
                  <div className="flex h-full min-h-[220px] flex-col justify-between">
                    <div>
                      <div className="mb-2 text-sm font-medium">Relationship inspector</div>
                      <p className="text-sm text-muted-foreground">
                        Hover any node or line to highlight its path. Click a node to pin it here and browse connected records without leaving the report.
                      </p>
                    </div>
                    <div className="space-y-2 text-xs text-muted-foreground">
                      <div className="inline-flex items-center gap-1"><Landmark className="h-3.5 w-3.5" /> Statement</div>
                      <div className="inline-flex items-center gap-1"><FileText className="h-3.5 w-3.5" /> Invoice</div>
                      <div className="inline-flex items-center gap-1"><Receipt className="h-3.5 w-3.5" /> Expense</div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-end">
              <Button variant="ghost" size="sm" className="gap-1" onClick={() => navigate('/statements')}>
                Explore statements
                <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};
