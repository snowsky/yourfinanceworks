import type { FC, PointerEvent as ReactPointerEvent } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowRight,
  Expand,
  FileText,
  Grab,
  Landmark,
  Loader2,
  Network,
  Receipt,
  ScanSearch,
  Unlink,
  X,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
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

interface DragState {
  nodeId: string;
  pointerId: number;
}

const truncate = (value: string, max: number) => (
  value.length > max ? `${value.slice(0, max - 1)}...` : value
);

const isSupportedReportType = (value: string): value is SupportedReportType =>
  value === 'invoice' || value === 'expense' || value === 'statement';

const nodeColors: Record<CloudNodeType, string> = {
  statement: 'border-sky-300 bg-sky-50 text-sky-950',
  invoice: 'border-emerald-300 bg-emerald-50 text-emerald-950',
  expense: 'border-amber-300 bg-amber-50 text-amber-950',
};

const nodeMutedColors: Record<CloudNodeType, string> = {
  statement: 'border-sky-100 bg-sky-50/40 text-sky-950/50',
  invoice: 'border-emerald-100 bg-emerald-50/40 text-emerald-950/50',
  expense: 'border-amber-100 bg-amber-50/40 text-amber-950/50',
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

const buildPositionedGraph = (data: RelationshipCloudResponse): PositionedGraph => {
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
    const spacing = total <= 1 ? 50 : 72 / Math.max(total - 1, 1);
    const startY = total <= 1 ? 50 : 14;
    return {
      id: node.id,
      entityId: node.entity_id,
      type: node.type,
      title: truncate(node.title, 22),
      subtitle: truncate(node.subtitle || '', 24),
      status: node.status,
      x,
      y: total <= 1 ? 50 : Math.max(14, Math.min(86, startY + spacing * index)),
    };
  });

  return {
    nodes,
    edges: data.edges,
    stats: data.stats,
  };
};

const RelationshipGraphCanvas: FC<{
  graph: PositionedGraph;
  positions: Record<string, { x: number; y: number }>;
  setPositions: React.Dispatch<React.SetStateAction<Record<string, { x: number; y: number }>>>;
  focusedNodeId: string | null;
  setFocusedNodeId: React.Dispatch<React.SetStateAction<string | null>>;
  openNode: (node: CloudNode) => void;
  compact?: boolean;
}> = ({ graph, positions, setPositions, focusedNodeId, setFocusedNodeId, openNode, compact = false }) => {
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const [dragState, setDragState] = useState<DragState | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const mergedNodes = useMemo(
    () => graph.nodes.map((node) => ({ ...node, ...(positions[node.id] || {}) })),
    [graph.nodes, positions]
  );
  const nodeById = useMemo(
    () => new Map(mergedNodes.map((node) => [node.id, node])),
    [mergedNodes]
  );
  const edgeById = useMemo(
    () => new Map(graph.edges.map((edge) => [edge.id, edge])),
    [graph.edges]
  );

  const activeNodeId = focusedNodeId || hoveredNodeId;
  const activeEdgeId = hoveredEdgeId;

  const connectedNodeIds = useMemo(() => {
    const ids = new Set<string>();
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
  }, [activeEdgeId, activeNodeId, edgeById, graph.edges]);

  const connectedEdges = useMemo(() => {
    const ids = new Set<string>();
    graph.edges.forEach((edge) => {
      if (activeNodeId && (edge.source === activeNodeId || edge.target === activeNodeId)) {
        ids.add(edge.id);
      }
      if (activeEdgeId && edge.id === activeEdgeId) {
        ids.add(edge.id);
      }
    });
    return ids;
  }, [activeEdgeId, activeNodeId, graph.edges]);

  useEffect(() => {
    if (!dragState) return;

    const handlePointerMove = (event: PointerEvent) => {
      if (event.pointerId !== dragState.pointerId) return;
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;

      const x = ((event.clientX - rect.left) / rect.width) * 100;
      const y = ((event.clientY - rect.top) / rect.height) * 100;

      setPositions((current) => ({
        ...current,
        [dragState.nodeId]: {
          x: Math.max(8, Math.min(92, x)),
          y: Math.max(10, Math.min(90, y)),
        },
      }));
    };

    const handlePointerUp = (event: PointerEvent) => {
      if (event.pointerId === dragState.pointerId) {
        setDragState(null);
      }
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);

    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };
  }, [dragState, setPositions]);

  const startDrag = (event: ReactPointerEvent<HTMLElement>, nodeId: string) => {
    event.preventDefault();
    event.stopPropagation();
    setFocusedNodeId(nodeId);
    setDragState({ nodeId, pointerId: event.pointerId });
  };

  return (
    <div
      ref={containerRef}
      className={`relative overflow-hidden rounded-2xl border bg-gradient-to-br from-background via-muted/20 to-background ${compact ? 'min-h-[300px]' : 'min-h-[620px]'}`}
    >
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        {graph.edges.map((edge) => {
          const source = nodeById.get(edge.source);
          const target = nodeById.get(edge.target);
          if (!source || !target) return null;

          const isConnected = connectedEdges.has(edge.id);
          const shouldDim = (activeNodeId || activeEdgeId) && !isConnected;
          const stroke = isConnected ? 'hsl(var(--primary))' : 'currentColor';

          return (
            <g key={edge.id}>
              <line
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke={stroke}
                strokeWidth={isConnected ? (compact ? 0.9 : 0.7) : 0.45}
                className={shouldDim ? 'text-border/15' : 'text-border'}
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

      {mergedNodes.map((node) => {
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
            className={`absolute -translate-x-1/2 -translate-y-1/2 rounded-lg border text-left shadow-sm transition ${compact ? 'w-28 px-2.5 py-2' : 'w-40 px-3 py-2.5'} ${isFocused ? 'scale-[1.03] ring-2 ring-primary/30' : 'hover:scale-[1.02] hover:shadow-md'} ${shouldDim ? nodeMutedColors[node.type] : nodeColors[node.type]}`}
            style={{ left: `${node.x}%`, top: `${node.y}%`, opacity: shouldDim ? 0.5 : 1 }}
          >
            <div className="mb-1.5 flex items-start justify-between gap-1.5">
              <div className="rounded-md bg-white/70 p-1">
                <Icon className={compact ? 'h-3.5 w-3.5' : 'h-4 w-4'} />
              </div>
              <div className="flex items-center gap-1">
                {node.status ? (
                  <Badge variant="secondary" className={compact ? 'max-w-[54px] truncate px-1.5 py-0 text-[9px]' : 'max-w-[72px] truncate px-2 py-0 text-[10px]'}>
                    {node.status}
                  </Badge>
                ) : null}
                <span
                  className="cursor-grab rounded-md bg-white/70 p-1 text-muted-foreground hover:bg-white"
                  onPointerDown={(event) => startDrag(event, node.id)}
                >
                  <Grab className="h-3 w-3" />
                </span>
              </div>
            </div>
            <div className={compact ? 'text-[11px] font-semibold leading-tight' : 'text-sm font-semibold leading-tight'}>{node.title}</div>
            <div className={compact ? 'mt-0.5 text-[10px] opacity-80' : 'mt-1 text-xs opacity-80'}>{node.subtitle}</div>
          </button>
        );
      })}
    </div>
  );
};

export const ReportRelationshipCloud: FC<ReportRelationshipCloudProps> = ({
  reportType,
  filters,
}) => {
  const navigate = useNavigate();
  const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({});

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
    return buildPositionedGraph(cloudQuery.data as RelationshipCloudResponse);
  }, [cloudQuery.data]);

  useEffect(() => {
    if (!graph) return;
    setPositions((current) => {
      const next = { ...current };
      let changed = false;
      graph.nodes.forEach((node) => {
        if (!next[node.id]) {
          next[node.id] = { x: node.x, y: node.y };
          changed = true;
        }
      });
      Object.keys(next).forEach((key) => {
        if (!graph.nodes.some((node) => node.id === key)) {
          delete next[key];
          changed = true;
        }
      });
      return changed ? next : current;
    });
  }, [graph]);

  const nodeById = useMemo(() => {
    const mergedNodes = graph?.nodes.map((node) => ({ ...node, ...(positions[node.id] || {}) })) || [];
    return new Map(mergedNodes.map((node) => [node.id, node]));
  }, [graph?.nodes, positions]);

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
    <>
      <Card className="slide-in overflow-hidden">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Network className="h-5 w-5" />
                Relationship Cloud
              </CardTitle>
              <CardDescription>
                Open the enlarged view to inspect relationships in more space, then drag nodes to arrange the graph the way you want.
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" className="gap-2" onClick={() => setIsModalOpen(true)}>
              <Expand className="h-4 w-4" />
              Open Large View
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? (
            <div className="flex min-h-[240px] items-center justify-center rounded-xl border border-dashed">
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

              <RelationshipGraphCanvas
                graph={graph}
                positions={positions}
                setPositions={setPositions}
                focusedNodeId={focusedNodeId}
                setFocusedNodeId={setFocusedNodeId}
                openNode={openNode}
                compact
              />

              <div className="flex items-center justify-between gap-3 rounded-xl border bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <ScanSearch className="h-4 w-4" />
                  Use the large view for drag-and-drop layout editing and easier inspection.
                </div>
                <Button variant="ghost" size="sm" className="gap-1" onClick={() => setIsModalOpen(true)}>
                  View full screen
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="max-h-[92vh] max-w-[95vw] overflow-hidden p-0">
          <div className="flex h-[88vh] flex-col">
            <DialogHeader className="border-b px-6 py-4">
              <DialogTitle className="flex items-center gap-2">
                <Network className="h-5 w-5" />
                Relationship Cloud
              </DialogTitle>
              <DialogDescription>
                Drag nodes to rearrange the graph. Click a node to pin it in the inspector, then jump into the source record when you are ready.
              </DialogDescription>
            </DialogHeader>

            <div className="grid min-h-0 flex-1 gap-4 p-6 xl:grid-cols-[minmax(0,1fr)_320px]">
              <div className="min-h-0">
                {graph ? (
                  <RelationshipGraphCanvas
                    graph={graph}
                    positions={positions}
                    setPositions={setPositions}
                    focusedNodeId={focusedNodeId}
                    setFocusedNodeId={setFocusedNodeId}
                    openNode={openNode}
                  />
                ) : (
                  <div className="flex h-full items-center justify-center rounded-2xl border border-dashed text-sm text-muted-foreground">
                    No graph available.
                  </div>
                )}
              </div>

              <div className="min-h-0 overflow-auto rounded-2xl border bg-muted/20 p-4">
                {focusedNode ? (
                  <div className="space-y-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">
                          {typeLabel[focusedNode.type]}
                        </div>
                        <h3 className="text-lg font-semibold">{focusedNode.title}</h3>
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

                    <div className="rounded-xl border bg-background p-3 text-sm text-muted-foreground">
                      <div className="mb-1 flex items-center gap-2 font-medium text-foreground">
                        <Grab className="h-4 w-4" />
                        Drag support
                      </div>
                      Grab the handle on any node to move it and create a cleaner layout for inspection.
                    </div>

                    <Button className="w-full gap-2" onClick={() => openNode(focusedNode)}>
                      Open {typeLabel[focusedNode.type].toLowerCase()}
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </div>
                ) : (
                  <div className="flex h-full min-h-[260px] flex-col justify-between">
                    <div>
                      <div className="mb-2 text-sm font-medium">Relationship inspector</div>
                      <p className="text-sm text-muted-foreground">
                        Click a node in the graph to inspect its chain here. The modal gives the graph more space, and every node can be dragged into a clearer position.
                      </p>
                    </div>
                    <div className="space-y-3 text-xs text-muted-foreground">
                      <div className="flex flex-wrap gap-3">
                        <div className="inline-flex items-center gap-1"><Landmark className="h-3.5 w-3.5" /> Statement</div>
                        <div className="inline-flex items-center gap-1"><FileText className="h-3.5 w-3.5" /> Invoice</div>
                        <div className="inline-flex items-center gap-1"><Receipt className="h-3.5 w-3.5" /> Expense</div>
                      </div>
                      <div className="inline-flex items-center gap-1">
                        <Grab className="h-3.5 w-3.5" />
                        Drag handles appear on each node
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};
