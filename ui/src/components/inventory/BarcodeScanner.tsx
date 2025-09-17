import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { inventoryApi, InventoryItem } from "@/lib/api";
import { toast } from "sonner";
import { Scan, Camera, CheckCircle, X, Lightbulb, AlertTriangle, Loader2 } from "lucide-react";
import { useTranslation } from 'react-i18next';

interface BarcodeValidationResult {
  valid: boolean;
  barcode: string;
  detected_type?: string;
  detected_format?: string;
  confidence?: number;
  error?: string;
}

interface BarcodeScannerProps {
  onItemFound?: (item: InventoryItem) => void;
  onBarcodeScanned?: (barcode: string) => void;
  autoClose?: boolean;
}

export const BarcodeScanner = ({
  onItemFound,
  onBarcodeScanned,
  autoClose = false
}: BarcodeScannerProps) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [manualBarcode, setManualBarcode] = useState("");
  const [validationResult, setValidationResult] = useState<BarcodeValidationResult | null>(null);
  const [foundItem, setFoundItem] = useState<InventoryItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Mock camera scanning (in a real implementation, you'd use a barcode scanning library)
  const startCameraScan = async () => {
    try {
      setScanning(true);
      // In a real implementation, you would:
      // 1. Request camera permission
      // 2. Use a barcode scanning library like QuaggaJS or ZXing
      // 3. Process the video stream for barcodes

      // For now, we'll simulate a scan
      setTimeout(() => {
        const mockBarcode = "123456789012"; // Mock UPC-A barcode
        handleBarcodeDetected(mockBarcode);
      }, 2000);
    } catch (error) {
      console.error("Camera access error:", error);
      toast.error("Camera access denied or not available");
      setScanning(false);
    }
  };

  const stopCameraScan = () => {
    setScanning(false);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
  };

  const handleBarcodeDetected = async (barcode: string) => {
    setScanning(false);
    setManualBarcode(barcode);
    await validateAndLookupBarcode(barcode);
    onBarcodeScanned?.(barcode);
  };

  const handleManualBarcodeSubmit = async () => {
    if (!manualBarcode.trim()) {
      toast.error("Please enter a barcode");
      return;
    }
    await validateAndLookupBarcode(manualBarcode.trim());
    onBarcodeScanned?.(manualBarcode.trim());
  };

  const validateAndLookupBarcode = async (barcode: string) => {
    setLoading(true);
    try {
      // First validate the barcode
      const validation = await inventoryApi.validateBarcode(barcode) as BarcodeValidationResult;
      setValidationResult(validation);

      if (validation.valid) {
        // Try to find the item by barcode
        try {
          const item = await inventoryApi.getItemByBarcode(barcode);
          setFoundItem(item);
          onItemFound?.(item);

          toast.success(`Found item: ${item.name}`);
          if (autoClose) {
            setIsOpen(false);
          }
        } catch (error) {
          // Item not found, but barcode is valid
          toast.info(`Valid barcode (${validation.detected_type}), but no item found`);
          setFoundItem(null);
        }
      } else {
        toast.error(`Invalid barcode: ${validation.error}`);
        setFoundItem(null);
      }
    } catch (error) {
      console.error("Barcode validation error:", error);
      toast.error("Failed to validate barcode");
    } finally {
      setLoading(false);
    }
  };

  const generateSuggestions = async (itemName?: string, sku?: string) => {
    if (!itemName && !sku) return;

    try {
      const response = await inventoryApi.getBarcodeSuggestions(itemName || "", sku);
      setSuggestions(response.suggestions.slice(0, 5)); // Limit to 5 suggestions
    } catch (error) {
      console.error("Failed to generate suggestions:", error);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setManualBarcode(suggestion);
  };

  const clearResults = () => {
    setValidationResult(null);
    setFoundItem(null);
    setSuggestions([]);
  };

  useEffect(() => {
    if (!isOpen) {
      stopCameraScan();
      clearResults();
    }
  }, [isOpen]);

  return (
    <>
      <Button
        variant="outline"
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-2"
      >
        <Scan className="h-4 w-4" />
        Scan Barcode
      </Button>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Scan className="h-5 w-5" />
              Barcode Scanner
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* Camera Scanning */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Camera Scan</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {scanning ? (
                  <div className="relative">
                    <div className="w-full h-48 bg-muted rounded-lg flex items-center justify-center">
                      <div className="text-center">
                        <Camera className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                        <p className="text-sm text-muted-foreground">Scanning...</p>
                        <div className="mt-2">
                          <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                        </div>
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={stopCameraScan}
                      className="absolute top-2 right-2"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ) : (
                  <Button
                    onClick={startCameraScan}
                    className="w-full"
                    disabled={loading}
                  >
                    <Camera className="h-4 w-4 mr-2" />
                    Start Camera Scan
                  </Button>
                )}
              </CardContent>
            </Card>

            {/* Manual Entry */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Manual Entry</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <Label htmlFor="barcode">Barcode</Label>
                  <Input
                    id="barcode"
                    value={manualBarcode}
                    onChange={(e) => setManualBarcode(e.target.value)}
                    placeholder="Enter barcode manually"
                    disabled={loading}
                  />
                </div>

                {suggestions.length > 0 && (
                  <div>
                    <Label className="text-xs text-muted-foreground">Suggestions</Label>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {suggestions.map((suggestion, index) => (
                        <Badge
                          key={index}
                          variant="outline"
                          className="cursor-pointer hover:bg-accent"
                          onClick={() => handleSuggestionClick(suggestion)}
                        >
                          {suggestion}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                <Button
                  onClick={handleManualBarcodeSubmit}
                  disabled={loading || !manualBarcode.trim()}
                  className="w-full"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <CheckCircle className="h-4 w-4 mr-2" />
                  )}
                  Lookup Barcode
                </Button>
              </CardContent>
            </Card>

            {/* Validation Results */}
            {validationResult && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    {validationResult.valid ? (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : (
                      <AlertTriangle className="h-4 w-4 text-red-500" />
                    )}
                    Validation Result
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>Barcode:</span>
                      <Badge variant={validationResult.valid ? "default" : "destructive"}>
                        {validationResult.barcode}
                      </Badge>
                    </div>
                    {validationResult.valid && (
                      <>
                        <div className="flex justify-between">
                          <span>Detected Type:</span>
                          <span className="font-medium">{validationResult.detected_type}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Format:</span>
                          <span className="font-medium">{validationResult.detected_format}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Confidence:</span>
                          <span className="font-medium">
                            {Math.round(validationResult.confidence * 100)}%
                          </span>
                        </div>
                      </>
                    )}
                    {!validationResult.valid && (
                      <div className="text-red-600 text-sm">
                        {validationResult.error}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Found Item */}
            {foundItem && (
              <Card className="border-green-200 bg-green-50">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm text-green-700">Item Found</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="font-medium">{foundItem.name}</div>
                    <div className="text-sm text-muted-foreground">
                      SKU: {foundItem.sku || 'N/A'} • Stock: {foundItem.current_stock}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      Price: ${foundItem.unit_price.toFixed(2)}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};
