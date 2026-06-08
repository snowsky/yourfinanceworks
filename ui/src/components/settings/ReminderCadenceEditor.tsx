import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { X, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

type When = "before" | "on" | "after";

interface ReminderCadenceEditorProps {
    value: number[];
    onChange: (next: number[]) => void;
    disabled?: boolean;
}

/** Human label for a day-offset relative to the due date. */
export function cadenceLabel(offset: number, t: TFunction): string {
    if (offset === 0) return t("settings.reminder_on_due", "On the due date") as string;
    const n = Math.abs(offset);
    return (offset < 0
        ? t("settings.reminder_before_due", "{{count}} day(s) before due", { count: n })
        : t("settings.reminder_after_due", "{{count}} day(s) after due", { count: n })) as string;
}

export const ReminderCadenceEditor: React.FC<ReminderCadenceEditorProps> = ({
    value,
    onChange,
    disabled = false,
}) => {
    const { t } = useTranslation();
    const [days, setDays] = useState<string>("3");
    const [when, setWhen] = useState<When>("after");

    const sorted = [...value].sort((a, b) => a - b);

    const addOffset = () => {
        const n = parseInt(days, 10);
        if (when !== "on" && (isNaN(n) || n < 1)) return;
        const offset = when === "on" ? 0 : when === "before" ? -Math.abs(n) : Math.abs(n);
        if (value.includes(offset)) return;
        onChange([...value, offset].sort((a, b) => a - b));
    };

    const removeOffset = (offset: number) => {
        onChange(value.filter((o) => o !== offset));
    };

    return (
        <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
                {sorted.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                        {t("settings.reminder_no_schedule", "No reminders scheduled yet.")}
                    </p>
                ) : (
                    sorted.map((offset) => (
                        <Badge key={offset} variant="secondary" className="gap-1.5 py-1 pl-2.5 pr-1">
                            {cadenceLabel(offset, t)}
                            {!disabled && (
                                <button
                                    type="button"
                                    onClick={() => removeOffset(offset)}
                                    className="rounded-sm p-0.5 hover:bg-background/60"
                                    aria-label={t("common.remove", "Remove")}
                                >
                                    <X className="h-3 w-3" />
                                </button>
                            )}
                        </Badge>
                    ))
                )}
            </div>

            {!disabled && (
                <div className="flex flex-wrap items-center gap-2">
                    <Select value={when} onValueChange={(v: string) => setWhen(v as When)}>
                        <SelectTrigger className="w-[150px]">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="before">{t("settings.reminder_when_before", "Before due")}</SelectItem>
                            <SelectItem value="on">{t("settings.reminder_when_on", "On due date")}</SelectItem>
                            <SelectItem value="after">{t("settings.reminder_when_after", "After due")}</SelectItem>
                        </SelectContent>
                    </Select>
                    {when !== "on" && (
                        <Input
                            type="number"
                            min={1}
                            value={days}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setDays(e.target.value)}
                            className="w-20"
                            aria-label={t("settings.reminder_days", "Days")}
                        />
                    )}
                    <Button type="button" variant="outline" size="sm" onClick={addOffset}>
                        <Plus className="h-3.5 w-3.5 mr-1" />
                        {t("settings.reminder_add", "Add reminder")}
                    </Button>
                </div>
            )}
        </div>
    );
};
