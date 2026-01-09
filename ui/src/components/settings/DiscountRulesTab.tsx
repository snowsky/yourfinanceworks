import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { Percent, Plus, Edit, Trash2, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
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
import { Button } from "@/components/ui/button";
import {
    ProfessionalCard,
    ProfessionalCardHeader,
    ProfessionalCardTitle,
    ProfessionalCardContent,
} from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";
import {
    ProfessionalTable,
    ProfessionalTableHeader,
    ProfessionalTableBody,
    ProfessionalTableRow,
    ProfessionalTableCell,
    ProfessionalTableHead,
    StatusBadge,
} from "@/components/ui/professional-table";
import { discountRulesApi, DiscountRule, DiscountRuleCreate } from "@/lib/api";
import { toast } from "sonner";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

interface DiscountRulesTabProps {
    isAdmin: boolean;
}

export const DiscountRulesTab: React.FC<DiscountRulesTabProps> = ({
    isAdmin,
}) => {
    const { t } = useTranslation();
    const queryClient = useQueryClient();

    const [showDialog, setShowDialog] = useState(false);
    const [editingRule, setEditingRule] = useState<DiscountRule | null>(null);
    const [newRule, setNewRule] = useState<DiscountRuleCreate>({
        name: "",
        min_amount: 0,
        discount_type: "percentage",
        discount_value: 0,
        is_active: true,
        priority: 0,
        currency: "USD",
    });
    const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
    const [ruleToDelete, setRuleToDelete] = useState<number | null>(null);

    const { data: discountRules = [], isLoading } = useQuery({
        queryKey: ['discountRules'],
        queryFn: () => discountRulesApi.getDiscountRules(),
        enabled: isAdmin,
    });

    const createRuleMutation = useMutation({
        mutationFn: (data: DiscountRuleCreate) => discountRulesApi.createDiscountRule(data),
        onSuccess: () => {
            toast.success(t('settings.discount_rule_created'));
            queryClient.invalidateQueries({ queryKey: ['discountRules'] });
            handleCloseDialog();
        },
        onError: () => {
            toast.error(t('settings.failed_to_create_discount_rule'));
        }
    });

    const updateRuleMutation = useMutation({
        mutationFn: ({ id, data }: { id: number; data: DiscountRuleCreate }) => discountRulesApi.updateDiscountRule(id, data),
        onSuccess: () => {
            toast.success(t('settings.discount_rule_updated'));
            queryClient.invalidateQueries({ queryKey: ['discountRules'] });
            handleCloseDialog();
        },
        onError: () => {
            toast.error(t('settings.failed_to_update_discount_rule'));
        }
    });

    const deleteRuleMutation = useMutation({
        mutationFn: (id: number) => discountRulesApi.deleteDiscountRule(id),
        onSuccess: () => {
            toast.success(t('settings.discount_rule_deleted'));
            queryClient.invalidateQueries({ queryKey: ['discountRules'] });
        },
        onError: () => {
            toast.error(t('settings.failed_to_delete_discount_rule'));
        }
    });

    const handleOpenCreateDialog = () => {
        setEditingRule(null);
        setNewRule({
            name: "",
            min_amount: 0,
            discount_type: "percentage",
            discount_value: 0,
            is_active: true,
            priority: 0,
            currency: "USD",
        });
        setShowDialog(true);
    };

    const handleOpenEditDialog = (rule: DiscountRule) => {
        setEditingRule(rule);
        setNewRule({
            name: rule.name,
            min_amount: rule.min_amount,
            discount_type: rule.discount_type,
            discount_value: rule.discount_value,
            is_active: rule.is_active,
            priority: rule.priority,
            currency: rule.currency || "USD",
        });
        setShowDialog(true);
    };

    const handleCloseDialog = () => {
        setShowDialog(false);
        setEditingRule(null);
    };

    const handleRuleChange = (field: string, value: any) => {
        setNewRule(prev => ({ ...prev, [field]: value }));
    };

    const handleSaveRule = () => {
        if (editingRule) {
            updateRuleMutation.mutate({ id: editingRule.id, data: newRule });
        } else {
            createRuleMutation.mutate(newRule);
        }
    };

    const handleDeleteClick = (id: number) => {
        setRuleToDelete(id);
        setIsDeleteDialogOpen(true);
    };

    const confirmDelete = () => {
        if (ruleToDelete !== null) {
            deleteRuleMutation.mutate(ruleToDelete, {
                onSettled: () => {
                    setIsDeleteDialogOpen(false);
                    setRuleToDelete(null);
                }
            });
        }
    };

    return (
        <>
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <ProfessionalCardTitle className="flex items-center gap-2">
                            <Percent className="w-5 h-5 text-primary" />
                            {t('settings.discount_rules.title')}
                        </ProfessionalCardTitle>
                        <ProfessionalButton
                            onClick={handleOpenCreateDialog}
                            leftIcon={<Plus className="h-4 w-4" />}
                        >
                            {t('settings.discount_rules.create_rule')}
                        </ProfessionalButton>
                    </div>
                </ProfessionalCardHeader>
                <ProfessionalCardContent>
                    {isLoading ? (
                        <div className="flex justify-center py-12">
                            <Loader2 className="h-10 w-10 animate-spin text-primary" />
                        </div>
                    ) : discountRules.length === 0 ? (
                        <div className="text-center py-12 bg-muted/10 rounded-xl border-2 border-dashed border-border">
                            <Percent className="w-12 h-12 text-muted-foreground mx-auto mb-4 opacity-20" />
                                <p className="text-muted-foreground font-medium">{t('settings.discount_rules.no_discount_rules')}</p>
                            <p className="text-sm text-muted-foreground mt-2">
                                {t('settings.discount_rules.add_discount_rules_hint')}
                            </p>
                        </div>
                    ) : (
                        <div className="rounded-xl border border-border/50 overflow-hidden">
                            <ProfessionalTable>
                                <ProfessionalTableHeader>
                                    <ProfessionalTableRow>
                                        <ProfessionalTableHead>{t('settings.discount_rules.rule_name')}</ProfessionalTableHead>
                                        <ProfessionalTableHead>{t('settings.discount_rules.min_amount')}</ProfessionalTableHead>
                                        <ProfessionalTableHead>{t('settings.discount_rules.discount')}</ProfessionalTableHead>
                                        <ProfessionalTableHead>{t('settings.discount_rules.priority')}</ProfessionalTableHead>
                                        <ProfessionalTableHead>{t('settings.discount_rules.status')}</ProfessionalTableHead>
                                        <ProfessionalTableHead className="text-right">{t('common.actions')}</ProfessionalTableHead>
                                    </ProfessionalTableRow>
                                </ProfessionalTableHeader>
                                <ProfessionalTableBody>
                                    {discountRules.map((rule: DiscountRule) => (
                                        <ProfessionalTableRow key={rule.id} interactive>
                                            <ProfessionalTableCell className="font-medium">
                                                {rule.name}
                                            </ProfessionalTableCell>
                                            <ProfessionalTableCell>
                                                {rule.min_amount} {rule.currency || 'USD'}
                                            </ProfessionalTableCell>
                                            <ProfessionalTableCell>
                                                <div className="flex items-center gap-1.5">
                                                    <Badge variant="outline" className="font-mono">
                                                        {rule.discount_type === 'percentage' ? `${rule.discount_value}%` : `${rule.discount_value} ${rule.currency || 'USD'}`}
                                                    </Badge>
                                                </div>
                                            </ProfessionalTableCell>
                                            <ProfessionalTableCell>
                                                <Badge variant="secondary">{rule.priority}</Badge>
                                            </ProfessionalTableCell>
                                            <ProfessionalTableCell>
                                                <StatusBadge status={rule.is_active ? "success" : "neutral"}>
                                                    {rule.is_active ? t('common.active') : t('common.inactive')}
                                                </StatusBadge>
                                            </ProfessionalTableCell>
                                            <ProfessionalTableCell className="text-right">
                                                <div className="flex justify-end gap-2">
                                                    <ProfessionalButton
                                                        variant="ghost"
                                                        size="icon-sm"
                                                        onClick={() => handleOpenEditDialog(rule)}
                                                    >
                                                        <Edit className="h-4 w-4" />
                                                    </ProfessionalButton>
                                                    <ProfessionalButton
                                                        variant="ghost"
                                                        size="icon-sm"
                                                        className="text-destructive hover:bg-destructive/10"
                                                        onClick={() => handleDeleteClick(rule.id)}
                                                    >
                                                        <Trash2 className="h-4 w-4" />
                                                    </ProfessionalButton>
                                                </div>
                                            </ProfessionalTableCell>
                                        </ProfessionalTableRow>
                                    ))}
                                </ProfessionalTableBody>
                            </ProfessionalTable>
                        </div>
                    )}
                </ProfessionalCardContent>
            </ProfessionalCard>

            {/* Discount Rule Dialog */}
            <Dialog open={showDialog} onOpenChange={handleCloseDialog}>
                <DialogContent className="sm:max-w-[500px]">
                    <DialogHeader>
                        <DialogTitle>
                            {editingRule ? t('settings.discount_rules.update_rule') : t('settings.discount_rules.create_rule')}
                        </DialogTitle>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="name">{t('settings.discount_rules.rule_name')}</Label>
                            <Input
                                id="name"
                                value={newRule.name}
                                onChange={(e) => handleRuleChange('name', e.target.value)}
                                placeholder={t('settings.discount_rules.rule_name_placeholder')}
                            />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="min_amount">{t('settings.min_amount')}</Label>
                                <Input
                                    id="min_amount"
                                    type="number"
                                    value={newRule.min_amount}
                                    onChange={(e) => handleRuleChange('min_amount', parseFloat(e.target.value))}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="currency">{t('settings.currency')}</Label>
                                <Select
                                    value={newRule.currency}
                                    onValueChange={(value) => handleRuleChange('currency', value)}
                                >
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="USD">USD</SelectItem>
                                        <SelectItem value="EUR">EUR</SelectItem>
                                        <SelectItem value="GBP">GBP</SelectItem>
                                        <SelectItem value="JPY">JPY</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="discount_type">{t('settings.discount_rules.discount_type')}</Label>
                                <Select
                                    value={newRule.discount_type}
                                    onValueChange={(value) => handleRuleChange('discount_type', value)}
                                >
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="percentage">{t('settings.discount_rules.percentage')}</SelectItem>
                                        <SelectItem value="fixed">{t('settings.discount_rules.fixed_amount')}</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="discount_value">{t('settings.discount_rules.discount_value')}</Label>
                                <Input
                                    id="discount_value"
                                    type="number"
                                    value={newRule.discount_value}
                                    onChange={(e) => handleRuleChange('discount_value', parseFloat(e.target.value))}
                                />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="priority">{t('settings.priority')}</Label>
                                <Input
                                    id="priority"
                                    type="number"
                                    value={newRule.priority}
                                    onChange={(e) => handleRuleChange('priority', parseInt(e.target.value))}
                                />
                            </div>
                            <div className="flex items-center space-x-2 pt-8">
                                <Switch
                                    id="is_active"
                                    checked={newRule.is_active}
                                    onCheckedChange={(checked) => handleRuleChange('is_active', checked)}
                                />
                                <Label htmlFor="is_active">{t('settings.active')}</Label>
                            </div>
                        </div>
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={handleCloseDialog}>
                            {t('common.cancel')}
                        </Button>
                        <Button
                            onClick={handleSaveRule}
                            disabled={createRuleMutation.isPending || updateRuleMutation.isPending}
                        >
                            {createRuleMutation.isPending || updateRuleMutation.isPending ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                editingRule ? t('settings.discount_rules.update_rule') : t('settings.discount_rules.create_rule')
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Delete Confirmation */}
            <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{t('settings.discount_rules.delete_confirm_title')}</AlertDialogTitle>
                        <AlertDialogDescription>
                            {t('settings.discount_rules.delete_confirm_description')}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={confirmDelete}
                            disabled={deleteRuleMutation.isPending}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            {deleteRuleMutation.isPending ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                t('common.delete')
                            )}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    );
};
