import React, { useState, useEffect } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { Loader2, Download, Database, Upload } from "lucide-react";
import { settingsApi, discountRulesApi, DiscountRule, DiscountRuleCreate } from "@/lib/api";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Trash2, Edit, Plus } from "lucide-react";
import { CurrencyManager } from "@/components/ui/currency-manager";
import { CurrencySelector } from "@/components/ui/currency-selector";

const Settings = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  
  // Discount rules state
  const [discountRules, setDiscountRules] = useState<DiscountRule[]>([]);
  const [loadingDiscountRules, setLoadingDiscountRules] = useState(false);
  const [showDiscountRuleDialog, setShowDiscountRuleDialog] = useState(false);
  const [editingDiscountRule, setEditingDiscountRule] = useState<DiscountRule | null>(null);
  const [newDiscountRule, setNewDiscountRule] = useState<DiscountRuleCreate>({
    name: "",
    min_amount: 0,
    discount_type: "percentage",
    discount_value: 0,
    is_active: true,
    priority: 0,
    currency: "USD",
  });
  
  const [companyInfo, setCompanyInfo] = useState({
    name: "Your Company",
    email: "contact@yourcompany.com",
    phone: "(555) 123-4567",
    address: "123 Business Avenue, Suite 100, New York, NY 10001",
    tax_id: "12-3456789",
    logo: "",
  });

  const [invoiceSettings, setInvoiceSettings] = useState({
    prefix: "INV-",
    next_number: "0001",
    terms: "Payment due within 30 days from the date of invoice.\nLate payments are subject to a 1.5% monthly finance charge.",
    notes: "Thank you for your business!",
    send_copy: true,
    auto_reminders: true,
  });

  const [emailSettings, setEmailSettings] = useState({
    provider: "aws_ses",
    from_name: "Your Company",
    from_email: "noreply@yourcompany.com",
    enabled: false,
    // AWS SES
    aws_access_key_id: "",
    aws_secret_access_key: "",
    aws_region: "us-east-1",
    // Azure Email Services
    azure_connection_string: "",
    // Mailgun
    mailgun_api_key: "",
    mailgun_domain: "",
  });

  // Fetch settings when component mounts
  useEffect(() => {
    const fetchSettings = async () => {
      setLoading(true);
      try {
        const settings = await settingsApi.getSettings();
        
        // Update state with fetched settings
        if (settings.company_info) {
          setCompanyInfo({
            name: settings.company_info.name || companyInfo.name,
            email: settings.company_info.email || companyInfo.email,
            phone: settings.company_info.phone || companyInfo.phone,
            address: settings.company_info.address || companyInfo.address,
            tax_id: settings.company_info.tax_id || companyInfo.tax_id,
            logo: settings.company_info.logo || companyInfo.logo,
          });
        }
        
        if (settings.invoice_settings) {
          setInvoiceSettings({
            prefix: settings.invoice_settings.prefix || invoiceSettings.prefix,
            next_number: settings.invoice_settings.next_number || invoiceSettings.next_number,
            terms: settings.invoice_settings.terms || invoiceSettings.terms,
            notes: settings.invoice_settings.notes || invoiceSettings.notes,
            send_copy: settings.invoice_settings.send_copy ?? invoiceSettings.send_copy,
            auto_reminders: settings.invoice_settings.auto_reminders ?? invoiceSettings.auto_reminders,
          });
        }

        // Try to fetch email settings
        try {
          const emailConfig = await fetch('/api/email/config', {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`,
            },
          });
          
          if (emailConfig.ok) {
            const emailData = await emailConfig.json();
            setEmailSettings({
              provider: emailData.provider || emailSettings.provider,
              from_name: emailData.from_name || emailSettings.from_name,
              from_email: emailData.from_email || emailSettings.from_email,
              enabled: emailData.enabled ?? emailSettings.enabled,
              aws_access_key_id: emailData.aws_access_key_id || emailSettings.aws_access_key_id,
              aws_secret_access_key: emailData.aws_secret_access_key || emailSettings.aws_secret_access_key,
              aws_region: emailData.aws_region || emailSettings.aws_region,
              azure_connection_string: emailData.azure_connection_string || emailSettings.azure_connection_string,
              mailgun_api_key: emailData.mailgun_api_key || emailSettings.mailgun_api_key,
              mailgun_domain: emailData.mailgun_domain || emailSettings.mailgun_domain,
            });
          }
        } catch (error) {
          console.log("Email settings not configured yet");
        }
        
        // Fetch discount rules
        try {
          setLoadingDiscountRules(true);
          const rules = await discountRulesApi.getDiscountRules();
          setDiscountRules(rules);
        } catch (error) {
          console.error("Failed to fetch discount rules:", error);
          toast.error("Failed to load discount rules");
        } finally {
          setLoadingDiscountRules(false);
        }
      } catch (error) {
        console.error("Failed to fetch settings:", error);
        toast.error("Failed to load settings");
      } finally {
        setLoading(false);
      }
    };
    
    fetchSettings();
  }, []);

  const handleCompanyChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setCompanyInfo((prev) => ({ ...prev, [name]: value }));
  };

  const handleInvoiceChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setInvoiceSettings((prev) => ({ ...prev, [name]: value }));
  };

  const handleToggleChange = (name: string, checked: boolean) => {
    setInvoiceSettings((prev) => ({ ...prev, [name]: checked }));
  };

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setEmailSettings((prev) => ({ ...prev, [name]: value }));
  };

  const handleEmailProviderChange = (provider: string) => {
    setEmailSettings((prev) => ({ ...prev, provider }));
  };

  const handleEmailToggleChange = (name: string, checked: boolean) => {
    setEmailSettings((prev) => ({ ...prev, [name]: checked }));
  };

  const testEmailConfiguration = async () => {
    const testEmail = prompt("Enter email address to send test email to:");
    if (!testEmail) return;

    try {
      const response = await fetch('/api/email/test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({ test_email: testEmail }),
      });

      const result = await response.json();
      if (result.success) {
        toast.success(`Test email sent successfully to ${testEmail}`);
      } else {
        toast.error(`Failed to send test email: ${result.message}`);
      }
    } catch (error) {
      toast.error("Failed to send test email");
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // Format data for API
      const settingsData = {
        company_info: {
          name: companyInfo.name,
          email: companyInfo.email,
          phone: companyInfo.phone,
          address: companyInfo.address,
          tax_id: companyInfo.tax_id,
          logo: companyInfo.logo
        },
        invoice_settings: {
          prefix: invoiceSettings.prefix,
          next_number: invoiceSettings.next_number,
          terms: invoiceSettings.terms,
          notes: invoiceSettings.notes,
          send_copy: invoiceSettings.send_copy,
          auto_reminders: invoiceSettings.auto_reminders
        }
      };
      
      // Send to API
      await settingsApi.updateSettings(settingsData);
      
      // Save email settings separately
      try {
        await fetch('/api/email/config', {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
          },
          body: JSON.stringify(emailSettings),
        });
      } catch (error) {
        console.log("Failed to save email settings:", error);
      }
      
      toast.success("Settings saved successfully!");
    } catch (error) {
      console.error("Failed to save settings:", error);
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleExportData = async () => {
    setExporting(true);
    try {
      await settingsApi.exportData();
      toast.success("Data exported successfully!");
    } catch (error) {
      console.error("Failed to export data:", error);
      toast.error("Failed to export data. Please try again.");
    } finally {
      setExporting(false);
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      if (!file.name.endsWith('.sqlite')) {
        toast.error("Please select a SQLite file (.sqlite extension)");
        return;
      }
      setSelectedFile(file);
    }
  };

  const handleImportData = async () => {
    if (!selectedFile) {
      toast.error("Please select a file to import");
      return;
    }

    setImporting(true);
    try {
      const result = await settingsApi.importData(selectedFile);
      toast.success(`Data imported successfully! ${JSON.stringify(result.imported_counts)}`);
      setSelectedFile(null);
      // Reset the file input
      const fileInput = document.getElementById('import-file') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
    } catch (error) {
      console.error("Failed to import data:", error);
      toast.error(`Failed to import data: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setImporting(false);
    }
  };

  // Discount rules management functions
  const handleCreateDiscountRule = async () => {
    try {
      const rule = await discountRulesApi.createDiscountRule({ ...newDiscountRule, currency: newDiscountRule.currency || "USD" });
      setDiscountRules([...discountRules, rule]);
      setShowDiscountRuleDialog(false);
      setNewDiscountRule({
        name: "",
        min_amount: 0,
        discount_type: "percentage",
        discount_value: 0,
        is_active: true,
        priority: 0,
        currency: "USD",
      });
      toast.success("Discount rule created successfully!");
    } catch (error) {
      console.error("Failed to create discount rule:", error);
      toast.error("Failed to create discount rule");
    }
  };

  const handleUpdateDiscountRule = async () => {
    if (!editingDiscountRule) return;
    
    try {
      await discountRulesApi.updateDiscountRule(editingDiscountRule.id, {
        ...newDiscountRule,
        currency: newDiscountRule.currency || "USD",
      });
      // Re-fetch the full list of discount rules from the backend
      const rules = await discountRulesApi.getDiscountRules();
      setDiscountRules(rules);
      setShowDiscountRuleDialog(false);
      setEditingDiscountRule(null);
      setNewDiscountRule({
        name: "",
        min_amount: 0,
        discount_type: "percentage",
        discount_value: 0,
        is_active: true,
        priority: 0,
        currency: "USD",
      });
      toast.success("Discount rule updated successfully!");
    } catch (error) {
      console.error("Failed to update discount rule:", error);
      toast.error("Failed to update discount rule");
    }
  };

  const handleDeleteDiscountRule = async (id: number) => {
    if (!confirm("Are you sure you want to delete this discount rule?")) return;
    
    try {
      await discountRulesApi.deleteDiscountRule(id);
      setDiscountRules(discountRules.filter(rule => rule.id !== id));
      toast.success("Discount rule deleted successfully!");
    } catch (error) {
      console.error("Failed to delete discount rule:", error);
      toast.error("Failed to delete discount rule");
    }
  };

  const openEditDialog = (rule: DiscountRule) => {
    setEditingDiscountRule(rule);
    setNewDiscountRule({
      name: rule.name,
      min_amount: rule.min_amount,
      discount_type: rule.discount_type,
      discount_value: rule.discount_value,
      is_active: rule.is_active,
      priority: rule.priority,
      currency: rule.currency || "USD",
    });
    setShowDiscountRuleDialog(true);
  };

  const openCreateDialog = () => {
    setEditingDiscountRule(null);
    setNewDiscountRule({
      name: "",
      min_amount: 0,
      discount_type: "percentage",
      discount_value: 0,
      is_active: true,
      priority: 0,
      currency: "USD",
    });
    setShowDiscountRuleDialog(true);
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="h-full flex justify-center items-center">
          <Loader2 className="h-8 w-8 animate-spin mr-2" />
          <p>Loading settings...</p>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div>
          <h1 className="text-3xl font-bold">Settings</h1>
          <p className="text-muted-foreground">Manage your application preferences and configuration</p>
        </div>

        <Tabs defaultValue="company" className="w-full">
          <TabsList className="grid w-full grid-cols-6">
            <TabsTrigger value="company">Company Info</TabsTrigger>
            <TabsTrigger value="invoices">Invoice Settings</TabsTrigger>
            <TabsTrigger value="currencies">Currencies</TabsTrigger>
            <TabsTrigger value="discount-rules">Discount Rules</TabsTrigger>
            <TabsTrigger value="email">Email Settings</TabsTrigger>
            <TabsTrigger value="export">Data Management</TabsTrigger>
          </TabsList>
          
          <TabsContent value="company" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Company Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="name">Company Name</Label>
                    <Input 
                      id="name" 
                      name="name" 
                      value={companyInfo.name} 
                      onChange={handleCompanyChange} 
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="tax_id">Tax ID / EIN</Label>
                    <Input 
                      id="tax_id" 
                      name="tax_id" 
                      value={companyInfo.tax_id} 
                      onChange={handleCompanyChange} 
                    />
                  </div>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input 
                      id="email" 
                      name="email" 
                      type="email" 
                      value={companyInfo.email} 
                      onChange={handleCompanyChange} 
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="phone">Phone</Label>
                    <Input 
                      id="phone" 
                      name="phone" 
                      value={companyInfo.phone} 
                      onChange={handleCompanyChange} 
                    />
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="address">Address</Label>
                  <Textarea 
                    id="address" 
                    name="address" 
                    rows={3} 
                    value={companyInfo.address} 
                    onChange={handleCompanyChange} 
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="logo">Company Logo</Label>
                  <Input 
                    id="logo" 
                    name="logo" 
                    type="file" 
                    accept="image/*" 
                  />
                  <p className="text-sm text-muted-foreground">Recommended size: 200x200px</p>
                </div>
                
                <div className="flex justify-end">
                  <Button onClick={handleSave} disabled={saving}>
                    {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Save Changes
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
          
          <TabsContent value="invoices" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Invoice Settings</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="prefix">Invoice Number Prefix</Label>
                    <Input 
                      id="prefix" 
                      name="prefix" 
                      value={invoiceSettings.prefix} 
                      onChange={handleInvoiceChange} 
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="next_number">Next Invoice Number</Label>
                    <Input 
                      id="next_number" 
                      name="next_number" 
                      value={invoiceSettings.next_number} 
                      onChange={handleInvoiceChange} 
                    />
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="terms">Default Terms & Conditions</Label>
                  <Textarea 
                    id="terms" 
                    name="terms" 
                    rows={4} 
                    value={invoiceSettings.terms} 
                    onChange={handleInvoiceChange} 
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="notes">Default Notes</Label>
                  <Textarea 
                    id="notes" 
                    name="notes" 
                    rows={2} 
                    value={invoiceSettings.notes} 
                    onChange={handleInvoiceChange} 
                  />
                </div>
                
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label htmlFor="send_copy">Send Me a Copy</Label>
                      <p className="text-sm text-muted-foreground">Receive a copy of each invoice by email</p>
                    </div>
                    <Switch 
                      id="send_copy" 
                      checked={invoiceSettings.send_copy} 
                      onCheckedChange={(checked) => handleToggleChange('send_copy', checked)} 
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label htmlFor="auto_reminders">Automatic Reminders</Label>
                      <p className="text-sm text-muted-foreground">Send reminder emails for overdue invoices</p>
                    </div>
                    <Switch 
                      id="auto_reminders" 
                      checked={invoiceSettings.auto_reminders} 
                      onCheckedChange={(checked) => handleToggleChange('auto_reminders', checked)} 
                    />
                  </div>
                </div>
                
                <div className="flex justify-end">
                  <Button onClick={handleSave} disabled={saving}>
                    {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Save Changes
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
          
          <TabsContent value="currencies" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Currency Management</CardTitle>
              </CardHeader>
              <CardContent>
                <CurrencyManager />
              </CardContent>
            </Card>
          </TabsContent>
          
          <TabsContent value="discount-rules" className="mt-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Discount Rules</CardTitle>
                  <Button onClick={openCreateDialog} size="sm">
                    <Plus className="h-4 w-4 mr-2" />
                    Add Rule
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                {loadingDiscountRules ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin mr-2" />
                    <span className="text-sm text-muted-foreground">Loading discount rules...</span>
                  </div>
                ) : discountRules.length === 0 ? (
                  <div className="text-center py-8">
                    <p className="text-muted-foreground mb-4">No discount rules configured yet.</p>
                    <p className="text-sm text-muted-foreground">
                      Create discount rules to automatically apply discounts based on invoice totals.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {discountRules.map((rule) => (
                      <div key={rule.id} className="flex items-center justify-between p-4 border rounded-lg">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <h4 className="font-medium">{rule.name}</h4>
                            <Badge variant={rule.is_active ? "default" : "secondary"}>
                              {rule.is_active ? "Active" : "Inactive"}
                            </Badge>
                            <Badge variant="outline">Priority: {rule.priority}</Badge>
                            {/* Show currency badge */}
                            <Badge variant="secondary">{rule.currency || "USD"}</Badge>
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {rule.discount_type === "percentage" 
                              ? `${rule.discount_value}% discount` 
                              : `$${rule.discount_value} discount`
                            } when total ≥ ${rule.min_amount}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openEditDialog(rule)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleDeleteDiscountRule(rule.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
          
          <TabsContent value="email" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Email Configuration</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label htmlFor="email_enabled">Enable Email Service</Label>
                    <p className="text-sm text-muted-foreground">Enable sending invoices via email</p>
                  </div>
                  <Switch 
                    id="email_enabled" 
                    checked={emailSettings.enabled} 
                    onCheckedChange={(checked) => handleEmailToggleChange('enabled', checked)} 
                  />
                </div>

                {emailSettings.enabled && (
                  <>
                    <div className="space-y-2">
                      <Label htmlFor="provider">Email Provider</Label>
                      <Select value={emailSettings.provider} onValueChange={handleEmailProviderChange}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select email provider" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="aws_ses">AWS SES</SelectItem>
                          <SelectItem value="azure_email">Azure Email Services</SelectItem>
                          <SelectItem value="mailgun">Mailgun</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <Label htmlFor="from_name">From Name</Label>
                        <Input 
                          id="from_name" 
                          name="from_name" 
                          value={emailSettings.from_name} 
                          onChange={handleEmailChange} 
                        />
                      </div>
                      
                      <div className="space-y-2">
                        <Label htmlFor="from_email">From Email</Label>
                        <Input 
                          id="from_email" 
                          name="from_email" 
                          type="email" 
                          value={emailSettings.from_email} 
                          onChange={handleEmailChange} 
                        />
                      </div>
                    </div>

                    {emailSettings.provider === "aws_ses" && (
                      <div className="space-y-4 p-4 border rounded-lg">
                        <h4 className="font-medium">AWS SES Configuration</h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label htmlFor="aws_access_key_id">Access Key ID</Label>
                            <Input 
                              id="aws_access_key_id" 
                              name="aws_access_key_id" 
                              type="password"
                              value={emailSettings.aws_access_key_id} 
                              onChange={handleEmailChange} 
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="aws_secret_access_key">Secret Access Key</Label>
                            <Input 
                              id="aws_secret_access_key" 
                              name="aws_secret_access_key" 
                              type="password"
                              value={emailSettings.aws_secret_access_key} 
                              onChange={handleEmailChange} 
                            />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="aws_region">AWS Region</Label>
                          <Select value={emailSettings.aws_region} onValueChange={(value) => setEmailSettings(prev => ({ ...prev, aws_region: value }))}>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="us-east-1">US East (N. Virginia)</SelectItem>
                              <SelectItem value="us-west-2">US West (Oregon)</SelectItem>
                              <SelectItem value="eu-west-1">EU (Ireland)</SelectItem>
                              <SelectItem value="ap-southeast-1">Asia Pacific (Singapore)</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    )}

                    {emailSettings.provider === "azure_email" && (
                      <div className="space-y-4 p-4 border rounded-lg">
                        <h4 className="font-medium">Azure Email Services Configuration</h4>
                        <div className="space-y-2">
                          <Label htmlFor="azure_connection_string">Connection String</Label>
                          <Input 
                            id="azure_connection_string" 
                            name="azure_connection_string" 
                            type="password"
                            value={emailSettings.azure_connection_string} 
                            onChange={handleEmailChange} 
                          />
                        </div>
                      </div>
                    )}

                    {emailSettings.provider === "mailgun" && (
                      <div className="space-y-4 p-4 border rounded-lg">
                        <h4 className="font-medium">Mailgun Configuration</h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label htmlFor="mailgun_api_key">API Key</Label>
                            <Input 
                              id="mailgun_api_key" 
                              name="mailgun_api_key" 
                              type="password"
                              value={emailSettings.mailgun_api_key} 
                              onChange={handleEmailChange} 
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="mailgun_domain">Domain</Label>
                            <Input 
                              id="mailgun_domain" 
                              name="mailgun_domain" 
                              value={emailSettings.mailgun_domain} 
                              onChange={handleEmailChange} 
                            />
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="flex justify-between">
                      <Button 
                        type="button" 
                        variant="outline" 
                        onClick={testEmailConfiguration}
                      >
                        Test Configuration
                      </Button>
                      <Button onClick={handleSave} disabled={saving}>
                        {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Save Email Settings
                      </Button>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>
          
          <TabsContent value="export" className="space-y-6">
            {/* Data Overview Section */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="h-5 w-5" />
                  Data Management
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  Backup, restore, and manage your business data with complete control over your information.
                </p>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="text-center p-4 bg-blue-50 rounded-lg border border-blue-200">
                    <div className="text-2xl font-bold text-blue-600">📊</div>
                    <h3 className="font-medium text-blue-900 mt-2">Complete Backup</h3>
                    <p className="text-sm text-blue-700 mt-1">Export all your business data in one file</p>
                  </div>
                  <div className="text-center p-4 bg-green-50 rounded-lg border border-green-200">
                    <div className="text-2xl font-bold text-green-600">🔄</div>
                    <h3 className="font-medium text-green-900 mt-2">Easy Restore</h3>
                    <p className="text-sm text-green-700 mt-1">Restore from previous backups instantly</p>
                  </div>
                  <div className="text-center p-4 bg-purple-50 rounded-lg border border-purple-200">
                    <div className="text-2xl font-bold text-purple-600">🔒</div>
                    <h3 className="font-medium text-purple-900 mt-2">Data Control</h3>
                    <p className="text-sm text-purple-700 mt-1">Your data stays under your control</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Export Section */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Download className="h-5 w-5" />
                  Export Data
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  Create a complete backup of all your business data including clients, invoices, payments, and settings.
                </p>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <div>
                      <h4 className="font-medium mb-3">What will be exported:</h4>
                      <div className="space-y-2">
                        <div className="flex items-center gap-2 text-sm">
                          <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                          <span>Client information and contact details</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm">
                          <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                          <span>Complete invoice history with line items</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm">
                          <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                          <span>Payment records and transaction history</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm">
                          <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                          <span>Client notes and CRM data</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm">
                          <div className="w-2 h-2 bg-gray-500 rounded-full"></div>
                          <span>Company and application settings</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div className="space-y-4">
                    <div>
                      <h4 className="font-medium mb-3">Export Details:</h4>
                      <div className="space-y-2 text-sm text-muted-foreground">
                        <p><strong>Format:</strong> SQLite database (.sqlite)</p>
                        <p><strong>Compatibility:</strong> Works with database tools and custom applications</p>
                        <p><strong>Security:</strong> No sensitive authentication data included</p>
                        <p><strong>Size:</strong> Typically 1-10 MB depending on data volume</p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="border-t pt-4">
                  <Button 
                    onClick={handleExportData} 
                    disabled={exporting}
                    size="lg"
                    className="w-full sm:w-auto"
                  >
                    {exporting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Creating Export...
                      </>
                    ) : (
                      <>
                        <Download className="mr-2 h-4 w-4" />
                        Download Complete Backup
                      </>
                    )}
                  </Button>
                  <p className="text-xs text-muted-foreground mt-2">
                    Export includes all data from your current tenant. File will be downloaded automatically.
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Import Section */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Upload className="h-5 w-5" />
                  Import Data
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  Restore your business data from a previously exported backup file.
                </p>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <div className="text-amber-600 text-lg">⚠️</div>
                    <div>
                      <h4 className="font-medium text-amber-900 mb-1">Important Warning</h4>
                      <p className="text-sm text-amber-800">
                        Importing data will <strong>permanently replace</strong> all your current data. 
                        This action cannot be undone. We strongly recommend creating an export backup first.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <div>
                      <Label htmlFor="import-file" className="text-base font-medium">Select Backup File</Label>
                      <p className="text-sm text-muted-foreground mb-3">
                        Choose a SQLite file (.sqlite) that was previously exported from this application.
                      </p>
                      <Input
                        id="import-file"
                        type="file"
                        accept=".sqlite"
                        onChange={handleFileSelect}
                        disabled={importing}
                        className="cursor-pointer"
                      />
                      {selectedFile && (
                        <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg">
                          <div className="flex items-center gap-2 text-sm">
                            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                            <span className="font-medium">File selected:</span>
                          </div>
                          <p className="text-sm text-green-700 mt-1">
                            {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  <div className="space-y-4">
                    <div>
                      <h4 className="font-medium mb-3">Import Process:</h4>
                      <div className="space-y-2 text-sm text-muted-foreground">
                        <div className="flex items-center gap-2">
                          <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                          <span>File validation and structure check</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                          <span>Current data backup and removal</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                          <span>Import new data with ID mapping</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                          <span>Data integrity verification</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="border-t pt-4">
                  <div className="flex flex-col sm:flex-row gap-3">
                    <Button 
                      onClick={handleExportData} 
                      disabled={exporting || importing}
                      variant="outline"
                      size="lg"
                    >
                      {exporting ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Creating Backup...
                        </>
                      ) : (
                        <>
                          <Download className="mr-2 h-4 w-4" />
                          Backup Current Data First
                        </>
                      )}
                    </Button>
                    
                    <Button 
                      onClick={handleImportData} 
                      disabled={importing || !selectedFile}
                      variant="destructive"
                      size="lg"
                    >
                      {importing ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Importing Data...
                        </>
                      ) : (
                        <>
                          <Upload className="mr-2 h-4 w-4" />
                          Import & Replace Data
                        </>
                      )}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    Recommended: Always create a backup before importing to preserve your current data.
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Best Practices Section */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span className="text-lg">💡</span>
                  Best Practices & Tips
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <h4 className="font-medium mb-3 text-green-700">✅ Recommended Practices</h4>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                      <li className="flex items-start gap-2">
                        <span className="text-green-500 mt-0.5">•</span>
                        <span>Create regular backups (weekly or monthly)</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-green-500 mt-0.5">•</span>
                        <span>Always backup before importing new data</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-green-500 mt-0.5">•</span>
                        <span>Store backup files in multiple safe locations</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-green-500 mt-0.5">•</span>
                        <span>Test imports in a separate environment first</span>
                      </li>
                    </ul>
                  </div>
                  
                  <div>
                    <h4 className="font-medium mb-3 text-blue-700">🔧 Technical Information</h4>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                      <li className="flex items-start gap-2">
                        <span className="text-blue-500 mt-0.5">•</span>
                        <span>SQLite files can be opened with DB Browser for SQLite</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-blue-500 mt-0.5">•</span>
                        <span>Data can be used programmatically in custom applications</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-blue-500 mt-0.5">•</span>
                        <span>Import validates file structure before processing</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-blue-500 mt-0.5">•</span>
                        <span>New invoice numbers are generated to avoid conflicts</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Discount Rule Dialog */}
        <Dialog open={showDiscountRuleDialog} onOpenChange={setShowDiscountRuleDialog}>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>
                {editingDiscountRule ? "Edit Discount Rule" : "Create Discount Rule"}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="rule-name">Rule Name</Label>
                <Input
                  id="rule-name"
                  value={newDiscountRule.name}
                  onChange={(e) => setNewDiscountRule(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="e.g., High Value Discount, Bulk Order Discount"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="min-amount">Minimum Amount</Label>
                  <Input
                    id="min-amount"
                    type="number"
                    min="0"
                    step="0.01"
                    value={newDiscountRule.min_amount}
                    onChange={(e) => setNewDiscountRule(prev => ({ ...prev, min_amount: parseFloat(e.target.value) || 0 }))}
                    placeholder="0.00"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="priority">Priority</Label>
                  <Input
                    id="priority"
                    type="number"
                    min="0"
                    value={newDiscountRule.priority}
                    onChange={(e) => setNewDiscountRule(prev => ({ ...prev, priority: parseInt(e.target.value) || 0 }))}
                    placeholder="0"
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="discount-type">Discount Type</Label>
                  <Select
                    value={newDiscountRule.discount_type}
                    onValueChange={(value: 'percentage' | 'fixed') => 
                      setNewDiscountRule(prev => ({ ...prev, discount_type: value }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="percentage">Percentage (%)</SelectItem>
                      <SelectItem value="fixed">Fixed Amount ($)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="discount-value">
                    {newDiscountRule.discount_type === "percentage" ? "Discount Percentage" : "Discount Amount"}
                  </Label>
                  <Input
                    id="discount-value"
                    type="number"
                    min="0"
                    step={newDiscountRule.discount_type === "percentage" ? "0.01" : "0.01"}
                    value={newDiscountRule.discount_value}
                    onChange={(e) => setNewDiscountRule(prev => ({ ...prev, discount_value: parseFloat(e.target.value) || 0 }))}
                    placeholder={newDiscountRule.discount_type === "percentage" ? "5.00" : "50.00"}
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="currency">Currency</Label>
                <CurrencySelector
                  value={newDiscountRule.currency || "USD"}
                  onValueChange={(value) => setNewDiscountRule(prev => ({ ...prev, currency: value }))}
                  placeholder="Select currency"
                />
              </div>
              
              <div className="flex items-center space-x-2">
                <Switch
                  id="is-active"
                  checked={newDiscountRule.is_active}
                  onCheckedChange={(checked) => setNewDiscountRule(prev => ({ ...prev, is_active: checked }))}
                />
                <Label htmlFor="is-active">Active</Label>
              </div>
              
              <div className="flex justify-end space-x-2 pt-4">
                <Button
                  variant="outline"
                  onClick={() => setShowDiscountRuleDialog(false)}
                >
                  Cancel
                </Button>
                <Button
                  onClick={editingDiscountRule ? handleUpdateDiscountRule : handleCreateDiscountRule}
                >
                  {editingDiscountRule ? "Update Rule" : "Create Rule"}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  );
};

export default Settings;
