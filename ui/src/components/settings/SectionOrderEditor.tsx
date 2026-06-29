import React from 'react';
import { GripVertical, Eye, EyeOff } from 'lucide-react';
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor,
  useSensor, useSensors, DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates,
  verticalListSortingStrategy, useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useTranslation } from 'react-i18next';
import { Label } from '@/components/ui/label';
import { SectionId, normalizeSectionOrder } from '@/lib/invoice-branding';

type ToggleKey = 'show_custom_fields' | 'show_notes';

interface SectionOrderEditorProps {
  order: SectionId[] | undefined;
  onOrderChange: (order: SectionId[]) => void;
  showCustomFields: boolean;
  showNotes: boolean;
  onToggle: (key: ToggleKey, value: boolean) => void;
}

const SECTION_LABELS: Record<SectionId, string> = {
  billto: 'settings.branding.section_billto',
  custom: 'settings.branding.section_custom_fields',
  items: 'settings.branding.section_items',
  totals: 'settings.branding.section_totals',
  notes: 'settings.branding.section_notes',
};

const TOGGLEABLE: Partial<Record<SectionId, ToggleKey>> = {
  custom: 'show_custom_fields',
  notes: 'show_notes',
};

function SortableRow({ id, label, toggle }: { id: SectionId; label: string; toggle?: React.ReactNode }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };
  return (
    <div ref={setNodeRef} style={style}
      className="flex items-center justify-between gap-2 p-2 bg-background rounded-lg border border-input">
      <div className="flex items-center gap-2">
        <button type="button" className="cursor-grab text-muted-foreground touch-none"
          aria-label="drag" {...attributes} {...listeners}>
          <GripVertical className="h-4 w-4" />
        </button>
        <span className="text-sm">{label}</span>
      </div>
      {toggle}
    </div>
  );
}

export function SectionOrderEditor({
  order, onOrderChange, showCustomFields, showNotes, onToggle,
}: SectionOrderEditorProps) {
  const { t } = useTranslation();
  const items = normalizeSectionOrder(order);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIndex = items.indexOf(active.id as SectionId);
      const newIndex = items.indexOf(over.id as SectionId);
      onOrderChange(arrayMove(items, oldIndex, newIndex));
    }
  };

  const toggleFor = (id: SectionId): React.ReactNode => {
    const key = TOGGLEABLE[id];
    if (!key) return null;
    const checked = key === 'show_custom_fields' ? showCustomFields : showNotes;
    return (
      <button type="button" onClick={() => onToggle(key, !checked)}
        aria-label={t(checked ? 'settings.branding.hide_section' : 'settings.branding.show_section')}
        className="text-muted-foreground hover:text-foreground">
        {checked ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
      </button>
    );
  };

  return (
    <div className="p-4 bg-muted/30 rounded-xl space-y-2">
      <Label className="text-sm font-semibold">{t('settings.branding.section_order')}</Label>
      <p className="text-xs text-muted-foreground">{t('settings.branding.section_order_hint')}</p>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={items} strategy={verticalListSortingStrategy}>
          <div className="space-y-2">
            {items.map((id) => (
              <SortableRow key={id} id={id} label={t(SECTION_LABELS[id])} toggle={toggleFor(id)} />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  );
}
