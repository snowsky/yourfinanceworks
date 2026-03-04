/**
 * Plugin Icon Registry
 * ====================
 * Maps icon name strings (as used in PluginNavItem.icon) to Lucide React
 * component constructors.
 *
 * When you add a new plugin that needs an icon not listed here, just import
 * it from lucide-react and add it to the map below.
 *
 * Usage in AppSidebar:
 *   import { iconRegistry } from '@/plugins/plugin-icons';
 *   const Icon = iconRegistry[navItem.icon];
 *   if (Icon) return <Icon className="w-5 h-5" />;
 */

import {
  TrendingUp,
  FolderKanban,
  DollarSign,
  BarChart,
  Clock,
  FileText,
  Package,
  Settings,
  Users,
  Zap,
  Globe,
  Calculator,
  Bell,
  ShoppingCart,
  CreditCard,
  PieChart,
  Briefcase,
  Calendar,
  Tag,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export const iconRegistry: Record<string, LucideIcon> = {
  // Existing plugins
  TrendingUp,
  FolderKanban,
  DollarSign,

  // Common icons available for future plugins
  BarChart,
  Clock,
  FileText,
  Package,
  Settings,
  Users,
  Zap,
  Globe,
  Calculator,
  Bell,
  ShoppingCart,
  CreditCard,
  PieChart,
  Briefcase,
  Calendar,
  Tag,
};
