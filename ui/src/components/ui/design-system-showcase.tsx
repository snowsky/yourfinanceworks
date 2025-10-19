import React, { useState } from 'react';
import {
  DollarSign,
  FileText,
  Users,
  Settings,
  Plus,
  Search,
  Download,
  Filter,
  Mail,
  Phone
} from 'lucide-react';
import InvoiceTrackingExample from '@/components/examples/InvoiceTrackingExample';
import TrackingExample from '@/components/examples/TrackingExample';

import { PageHeader, ContentSection, GridLayout, StackLayout, EmptyState } from './professional-layout';
import { ProfessionalCard, MetricCard } from './professional-card';
import { ProfessionalButton, ButtonGroup } from './professional-button';
import { ProfessionalInput, SearchInput } from './professional-input';
import { 
  ProfessionalTable, 
  ProfessionalTableHeader, 
  ProfessionalTableBody, 
  ProfessionalTableHead, 
  ProfessionalTableRow, 
  ProfessionalTableCell,
  StatusBadge,
  TableActionMenu
} from './professional-table';

export function DesignSystemShowcase() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light');

  const sampleData = [
    { id: 1, name: 'John Doe', email: 'john@example.com', status: 'active', amount: '$1,234.56' },
    { id: 2, name: 'Jane Smith', email: 'jane@example.com', status: 'pending', amount: '$2,345.67' },
    { id: 3, name: 'Bob Johnson', email: 'bob@example.com', status: 'inactive', amount: '$3,456.78' },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20">
      <div className="space-y-12 p-6 md:p-8">
        {/* Header */}
        <PageHeader
          title="Professional Design System"
          description="A comprehensive showcase of modern, sleek UI components"
          breadcrumbs={[
            { label: 'Components' },
            { label: 'Design System' }
          ]}
          actions={
            <div className="flex items-center gap-3">
              <ProfessionalButton 
                variant="outline" 
                size="sm"
                onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
              >
                Toggle {theme === 'light' ? 'Dark' : 'Light'} Mode
              </ProfessionalButton>
              <ProfessionalButton variant="gradient" size="sm">
                <Download className="h-4 w-4" />
                Export Components
              </ProfessionalButton>
            </div>
          }
        />

        {/* Buttons Section */}
        <ContentSection 
          title="Buttons" 
          description="Professional button variants with modern styling"
          variant="card"
        >
          <StackLayout direction="vertical" spacing="lg">
            {/* Primary Buttons */}
            <div>
              <h4 className="text-sm font-semibold mb-4 text-muted-foreground uppercase tracking-wide">Primary Variants</h4>
              <StackLayout direction="horizontal" spacing="md">
                <ProfessionalButton variant="default">Default</ProfessionalButton>
                <ProfessionalButton variant="gradient">Gradient</ProfessionalButton>
                <ProfessionalButton variant="success">Success</ProfessionalButton>
                <ProfessionalButton variant="warning">Warning</ProfessionalButton>
                <ProfessionalButton variant="destructive">Destructive</ProfessionalButton>
              </StackLayout>
            </div>

            {/* Secondary Buttons */}
            <div>
              <h4 className="text-sm font-semibold mb-4 text-muted-foreground uppercase tracking-wide">Secondary Variants</h4>
              <StackLayout direction="horizontal" spacing="md">
                <ProfessionalButton variant="outline">Outline</ProfessionalButton>
                <ProfessionalButton variant="secondary">Secondary</ProfessionalButton>
                <ProfessionalButton variant="ghost">Ghost</ProfessionalButton>
                <ProfessionalButton variant="glass">Glass</ProfessionalButton>
                <ProfessionalButton variant="minimal">Minimal</ProfessionalButton>
              </StackLayout>
            </div>

            {/* Sizes */}
            <div>
              <h4 className="text-sm font-semibold mb-4 text-muted-foreground uppercase tracking-wide">Sizes</h4>
              <StackLayout direction="horizontal" spacing="md" align="center">
                <ProfessionalButton size="sm">Small</ProfessionalButton>
                <ProfessionalButton size="default">Default</ProfessionalButton>
                <ProfessionalButton size="lg">Large</ProfessionalButton>
                <ProfessionalButton size="xl">Extra Large</ProfessionalButton>
              </StackLayout>
            </div>

            {/* With Icons */}
            <div>
              <h4 className="text-sm font-semibold mb-4 text-muted-foreground uppercase tracking-wide">With Icons</h4>
              <StackLayout direction="horizontal" spacing="md">
                <ProfessionalButton leftIcon={<Plus />}>Add Item</ProfessionalButton>
                <ProfessionalButton variant="outline" rightIcon={<Download />}>Export</ProfessionalButton>
                <ProfessionalButton variant="gradient" leftIcon={<Search />} rightIcon={<Filter />}>
                  Advanced Search
                </ProfessionalButton>
              </StackLayout>
            </div>

            {/* Loading State */}
            <div>
              <h4 className="text-sm font-semibold mb-4 text-muted-foreground uppercase tracking-wide">States</h4>
              <StackLayout direction="horizontal" spacing="md">
                <ProfessionalButton loading>Loading...</ProfessionalButton>
                <ProfessionalButton disabled>Disabled</ProfessionalButton>
                <ButtonGroup>
                  <ProfessionalButton variant="outline">First</ProfessionalButton>
                  <ProfessionalButton variant="outline">Second</ProfessionalButton>
                  <ProfessionalButton variant="outline">Third</ProfessionalButton>
                </ButtonGroup>
              </StackLayout>
            </div>
          </StackLayout>
        </ContentSection>

        {/* Cards Section */}
        <ContentSection 
          title="Cards & Metrics" 
          description="Professional card layouts and metric displays"
          variant="card"
        >
          <GridLayout cols={4} gap="lg" responsive>
            <MetricCard
              title="Total Revenue"
              value="$124,563"
              change={{ value: 12.5, type: 'increase' }}
              icon={DollarSign}
              description="Monthly recurring revenue"
              variant="success"
            />
            <MetricCard
              title="Active Users"
              value="2,847"
              change={{ value: 8.2, type: 'increase' }}
              icon={Users}
              description="Currently active users"
              variant="default"
            />
            <MetricCard
              title="Pending Tasks"
              value="23"
              change={{ value: 5.1, type: 'decrease' }}
              icon={FileText}
              description="Tasks awaiting completion"
              variant="warning"
            />
            <MetricCard
              title="System Load"
              value="87%"
              change={{ value: 15.3, type: 'increase' }}
              icon={Settings}
              description="Current system utilization"
              variant="danger"
            />
          </GridLayout>

          <div className="mt-8">
            <h4 className="text-sm font-semibold mb-4 text-muted-foreground uppercase tracking-wide">Card Variants</h4>
            <GridLayout cols={3} gap="md">
              <ProfessionalCard variant="default" className="p-6">
                <h3 className="font-semibold mb-2">Default Card</h3>
                <p className="text-muted-foreground text-sm">Standard card with border and subtle shadow</p>
              </ProfessionalCard>
              <ProfessionalCard variant="elevated" className="p-6">
                <h3 className="font-semibold mb-2">Elevated Card</h3>
                <p className="text-muted-foreground text-sm">Enhanced shadow for prominence</p>
              </ProfessionalCard>
              <ProfessionalCard variant="glass" className="p-6">
                <h3 className="font-semibold mb-2">Glass Card</h3>
                <p className="text-muted-foreground text-sm">Modern glassmorphism effect</p>
              </ProfessionalCard>
            </GridLayout>
          </div>
        </ContentSection>

        {/* Inputs Section */}
        <ContentSection 
          title="Form Inputs" 
          description="Professional input components with enhanced UX"
          variant="card"
        >
          <GridLayout cols={2} gap="lg">
            <StackLayout direction="vertical" spacing="md">
              <ProfessionalInput
                label="Default Input"
                placeholder="Enter your name"
                helperText="This is a helper text"
              />
              <ProfessionalInput
                label="With Left Icon"
                placeholder="Search..."
                leftIcon={<Search />}
                variant="filled"
              />
              <ProfessionalInput
                label="Password Input"
                type="password"
                placeholder="Enter password"
                variant="default"
              />
              <SearchInput
                placeholder="Search anything..."
                variant="glass"
              />
            </StackLayout>
            
            <StackLayout direction="vertical" spacing="md">
              <ProfessionalInput
                label="Email Address"
                type="email"
                placeholder="john@example.com"
                leftIcon={<Mail />}
                clearable
              />
              <ProfessionalInput
                label="Phone Number"
                type="tel"
                placeholder="+1 (555) 123-4567"
                leftIcon={<Phone />}
                variant="minimal"
              />
              <ProfessionalInput
                label="Error State"
                placeholder="Invalid input"
                error
                helperText="This field is required"
              />
              <ProfessionalInput
                label="Disabled Input"
                placeholder="Cannot edit"
                disabled
                value="Read only value"
              />
            </StackLayout>
          </GridLayout>
        </ContentSection>

        {/* Table Section */}
        <ContentSection 
          title="Data Tables" 
          description="Professional table layouts with sorting and actions"
          variant="card"
        >
          <ProfessionalTable variant="striped">
            <ProfessionalTableHeader>
              <ProfessionalTableRow>
                <ProfessionalTableHead sortable sortDirection="asc">Name</ProfessionalTableHead>
                <ProfessionalTableHead sortable>Email</ProfessionalTableHead>
                <ProfessionalTableHead>Status</ProfessionalTableHead>
                <ProfessionalTableHead sortable>Amount</ProfessionalTableHead>
                <ProfessionalTableHead>Actions</ProfessionalTableHead>
              </ProfessionalTableRow>
            </ProfessionalTableHeader>
            <ProfessionalTableBody>
              {sampleData.map((row) => (
                <ProfessionalTableRow key={row.id} interactive>
                  <ProfessionalTableCell className="font-medium">{row.name}</ProfessionalTableCell>
                  <ProfessionalTableCell>{row.email}</ProfessionalTableCell>
                  <ProfessionalTableCell>
                    <StatusBadge 
                      status={row.status === 'active' ? 'success' : row.status === 'pending' ? 'warning' : 'neutral'}
                      variant="soft"
                    >
                      {row.status}
                    </StatusBadge>
                  </ProfessionalTableCell>
                  <ProfessionalTableCell className="font-mono">{row.amount}</ProfessionalTableCell>
                  <ProfessionalTableCell>
                    <TableActionMenu
                      actions={[
                        { label: 'View Details', onClick: () => console.log('View', row.id) },
                        { label: 'Edit', onClick: () => console.log('Edit', row.id) },
                        { label: 'Delete', onClick: () => console.log('Delete', row.id), variant: 'destructive' }
                      ]}
                    />
                  </ProfessionalTableCell>
                </ProfessionalTableRow>
              ))}
            </ProfessionalTableBody>
          </ProfessionalTable>
        </ContentSection>

        {/* Layout Components */}
        <ContentSection 
          title="Layout Components" 
          description="Flexible layout utilities for consistent spacing"
          variant="card"
        >
          <StackLayout direction="vertical" spacing="lg">
            <div>
              <h4 className="text-sm font-semibold mb-4 text-muted-foreground uppercase tracking-wide">Grid Layouts</h4>
              <GridLayout cols={3} gap="md">
                <ProfessionalCard variant="minimal" className="p-4 bg-primary/5 border border-primary/20">
                  <div className="text-center">Grid Item 1</div>
                </ProfessionalCard>
                <ProfessionalCard variant="minimal" className="p-4 bg-success/5 border border-success/20">
                  <div className="text-center">Grid Item 2</div>
                </ProfessionalCard>
                <ProfessionalCard variant="minimal" className="p-4 bg-warning/5 border border-warning/20">
                  <div className="text-center">Grid Item 3</div>
                </ProfessionalCard>
              </GridLayout>
            </div>

            <div>
              <h4 className="text-sm font-semibold mb-4 text-muted-foreground uppercase tracking-wide">Stack Layouts</h4>
              <StackLayout direction="horizontal" spacing="md" justify="between" align="center">
                <div className="p-3 bg-muted rounded-lg">Horizontal Stack Item 1</div>
                <div className="p-3 bg-muted rounded-lg">Item 2</div>
                <div className="p-3 bg-muted rounded-lg">Item 3</div>
              </StackLayout>
            </div>
          </StackLayout>
        </ContentSection>

        {/* Empty State */}
        <ContentSection 
          title="Empty States" 
          description="Helpful empty state components"
          variant="card"
        >
          <EmptyState
            icon={<FileText className="h-8 w-8" />}
            title="No Data Available"
            description="There are no items to display at the moment. Create your first item to get started."
            action={
              <ProfessionalButton variant="gradient">
                <Plus className="h-4 w-4" />
                Create First Item
              </ProfessionalButton>
            }
          />
        </ContentSection>

        {/* Tracking Examples */}
        <ContentSection
          title="Tracking Examples"
          description="Interactive examples of tracking integration and business events"
          variant="card"
        >
          <div className="space-y-8">
            {/* General Tracking Example */}
            <div>
              <h3 className="text-lg font-semibold mb-4">General Tracking Example</h3>
              <p className="text-muted-foreground mb-4">Demo showing analytics and marketing tracking with consent management</p>
              <TrackingExample />
            </div>

            {/* Business Tracking Example */}
            <div>
              <h3 className="text-lg font-semibold mb-4">Invoice Tracking Example</h3>
              <p className="text-muted-foreground mb-4">Demo showing business event tracking for invoice operations</p>
              <InvoiceTrackingExample />
            </div>
          </div>
        </ContentSection>

        {/* Color Palette */}
        <ContentSection
          title="Color System"
          description="Professional color palette for financial applications"
          variant="card"
        >
          <GridLayout cols={6} gap="md">
            <div className="space-y-2">
              <div className="h-16 bg-primary rounded-lg shadow-sm"></div>
              <div className="text-center text-sm font-medium">Primary</div>
            </div>
            <div className="space-y-2">
              <div className="h-16 bg-secondary rounded-lg shadow-sm"></div>
              <div className="text-center text-sm font-medium">Secondary</div>
            </div>
            <div className="space-y-2">
              <div className="h-16 bg-success rounded-lg shadow-sm"></div>
              <div className="text-center text-sm font-medium">Success</div>
            </div>
            <div className="space-y-2">
              <div className="h-16 bg-warning rounded-lg shadow-sm"></div>
              <div className="text-center text-sm font-medium">Warning</div>
            </div>
            <div className="space-y-2">
              <div className="h-16 bg-destructive rounded-lg shadow-sm"></div>
              <div className="text-center text-sm font-medium">Destructive</div>
            </div>
            <div className="space-y-2">
              <div className="h-16 bg-muted rounded-lg shadow-sm"></div>
              <div className="text-center text-sm font-medium">Muted</div>
            </div>
          </GridLayout>
        </ContentSection>
      </div>
    </div>
  );
}
