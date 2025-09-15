import React, { useState, useEffect } from "react";
import { Package, Search, AlertTriangle, CheckCircle, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { inventoryApi, InventoryItem, InventoryCategory } from "@/lib/api";
import { getErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

interface InventoryItemSelectorProps {
  onItemSelect: (item: {
    inventory_item_id: number;
    description: string;
    price: number;
    unit_of_measure?: string;
    current_stock?: number;
    track_stock?: boolean;
  }) => void;
  selectedItemId?: number;
  className?: string;
  compact?: boolean; // New prop for compact mode
}

export const InventoryItemSelector: React.FC<InventoryItemSelectorProps> = ({
  onItemSelect,
  selectedItemId,
  className = "",
  compact = false
}) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [categories, setCategories] = useState<InventoryCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<number | "all">("all");
  const [selectedItem, setSelectedItem] = useState<InventoryItem | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchData();
    }
  }, [isOpen]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [itemsData, categoriesData] = await Promise.all([
        inventoryApi.getItems({ limit: 100 }),
        inventoryApi.getCategories()
      ]);
      setItems(itemsData.items);
      setCategories(categoriesData);
    } catch (error) {
      console.error("Failed to fetch inventory data:", error);
      toast.error(getErrorMessage(error, t));
    } finally {
      setLoading(false);
    }
  };

  const filteredItems = items.filter(item => {
    const matchesSearch = item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         item.sku?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         item.description?.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesCategory = selectedCategory === "all" || item.category_id === selectedCategory;

    return matchesSearch && matchesCategory && item.is_active;
  });

  const handleItemSelect = (item: InventoryItem) => {
    setSelectedItem(item);
  };

  const handleConfirmSelection = () => {
    if (selectedItem) {
      onItemSelect({
        inventory_item_id: selectedItem.id,
        description: selectedItem.name,
        price: selectedItem.unit_price,
        unit_of_measure: selectedItem.unit_of_measure,
        current_stock: selectedItem.current_stock,
        track_stock: selectedItem.track_stock
      });
      setIsOpen(false);
      setSelectedItem(null);
      setSearchQuery("");
      setSelectedCategory("all");
    }
  };

  const getStockStatus = (item: InventoryItem) => {
    if (!item.track_stock) return { status: 'not-tracked', label: 'Not Tracked', color: 'secondary' as const };

    if (item.current_stock <= item.minimum_stock) {
      return { status: 'critical', label: 'Low Stock', color: 'destructive' as const };
    } else if (item.current_stock <= item.minimum_stock * 1.5) {
      return { status: 'warning', label: 'Low Stock', color: 'secondary' as const };
    } else {
      return { status: 'normal', label: 'In Stock', color: 'default' as const };
    }
  };

  const currentlySelectedItem = selectedItemId ? items.find(item => item.id === selectedItemId) : null;

  return (
    <div className={className}>
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogTrigger asChild>
          <Button
            variant={compact ? "ghost" : (currentlySelectedItem ? "default" : "outline")}
            size={compact ? "sm" : "default"}
            className={compact
              ? `h-6 w-6 p-0 ${className}`
              : `w-full justify-start gap-2 ${className}`
            }
            title={compact ? "Select inventory item" : undefined}
          >
            <Package className="h-4 w-4" />
            {!compact && currentlySelectedItem ? (
              <>
                <span className="truncate">{currentlySelectedItem.name}</span>
                {currentlySelectedItem.track_stock && (
                  <Badge variant="outline" className="ml-auto">
                    Stock: {currentlySelectedItem.current_stock}
                  </Badge>
                )}
              </>
            ) : !compact && (
              <>
                <span>Select Inventory Item</span>
                <span className="ml-auto text-muted-foreground">(Optional)</span>
              </>
            )}
          </Button>
        </DialogTrigger>

        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Package className="h-5 w-5" />
              Select Inventory Item
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* Search and Filter */}
            <div className="flex gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
                <Input
                  placeholder="Search items by name, SKU, or description..."
                  className="pl-10"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <Select
                value={selectedCategory.toString()}
                onValueChange={(value) => setSelectedCategory(value === "all" ? "all" : parseInt(value))}
              >
                <SelectTrigger className="w-48">
                  <SelectValue placeholder="All Categories" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  {categories.map(category => (
                    <SelectItem key={category.id} value={category.id.toString()}>
                      {category.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Items List */}
            <div className="max-h-96 overflow-y-auto border rounded-lg">
              {loading ? (
                <div className="p-8 text-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
                  <p className="mt-2 text-muted-foreground">Loading inventory items...</p>
                </div>
              ) : filteredItems.length > 0 ? (
                <div className="divide-y">
                  {filteredItems.map((item) => {
                    const stockStatus = getStockStatus(item);
                    const isSelected = selectedItem?.id === item.id;

                    return (
                      <div
                        key={item.id}
                        className={`p-4 cursor-pointer hover:bg-muted/50 transition-colors ${
                          isSelected ? 'bg-primary/5 border-l-4 border-l-primary' : ''
                        }`}
                        onClick={() => handleItemSelect(item)}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <h4 className="font-medium truncate">{item.name}</h4>
                              <Badge variant={stockStatus.color}>
                                {stockStatus.label}
                              </Badge>
                            </div>

                            <div className="flex items-center gap-4 text-sm text-muted-foreground">
                              {item.sku && (
                                <span>SKU: {item.sku}</span>
                              )}
                              <span>Price: ${item.unit_price.toFixed(2)}</span>
                              {item.category && (
                                <span>Category: {item.category.name}</span>
                              )}
                              {item.track_stock && (
                                <span>Stock: {item.current_stock} {item.unit_of_measure}</span>
                              )}
                            </div>

                            {item.description && (
                              <p className="text-sm text-muted-foreground mt-1 truncate">
                                {item.description}
                              </p>
                            )}

                            {/* Stock Warnings */}
                            {item.track_stock && item.current_stock <= item.minimum_stock && (
                              <div className="flex items-center gap-2 mt-2 text-sm text-orange-600">
                                <AlertTriangle className="h-4 w-4" />
                                <span>Low stock alert: Only {item.current_stock} remaining</span>
                              </div>
                            )}
                          </div>

                          <div className="flex items-center gap-2 ml-4">
                            {isSelected && (
                              <CheckCircle className="h-5 w-5 text-primary" />
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="p-8 text-center">
                  <Package className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">
                    {searchQuery || selectedCategory !== "all"
                      ? "No items match your search criteria"
                      : "No inventory items found"}
                  </p>
                  <p className="text-sm text-muted-foreground mt-2">
                    {searchQuery || selectedCategory !== "all"
                      ? "Try adjusting your search or filter criteria"
                      : "Add some items to your inventory first"}
                  </p>
                </div>
              )}
            </div>

            {/* Selected Item Summary */}
            {selectedItem && (
              <div className="bg-muted/50 p-4 rounded-lg">
                <h4 className="font-medium mb-2">Selected Item:</h4>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{selectedItem.name}</p>
                    <p className="text-sm text-muted-foreground">
                      Price: ${selectedItem.unit_price.toFixed(2)}
                      {selectedItem.track_stock && ` | Stock: ${selectedItem.current_stock}`}
                    </p>
                  </div>
                  <Button onClick={handleConfirmSelection}>
                    Use This Item
                  </Button>
                </div>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button variant="outline" onClick={() => setIsOpen(false)}>
              Cancel
            </Button>
            {selectedItem && (
              <Button onClick={handleConfirmSelection}>
                Select Item
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
