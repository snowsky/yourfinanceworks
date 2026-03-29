import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import {
  DollarSign,
  Users,
  TrendingUp,
  Clock,
  AlertCircle,
  ArrowUpRight,
  ArrowDownRight,
  RefreshCw,
  Plus,
  BarChart2,
  ChevronRight,
  Zap,
} from 'lucide-react';

import { InvoiceChart } from './InvoiceChart';
import { RecentActivity } from './RecentActivity';
import { QuickActions } from './QuickActions';
import { HelpCenter } from '@/components/onboarding/HelpCenter';
import { dashboardApi } from '@/lib/api';
import { getCurrentUser } from '@/utils/auth';
import { toast } from 'sonner';

// ─── Design Tokens ────────────────────────────────────────────────────────────
const T = {
  bg:           '#09090E',
  surface:      '#0E0E17',
  card:         '#121220',
  cardHover:    '#17172A',
  border:       '#1C1C2E',
  borderMid:    '#25253A',
  gold:         '#C8A84B',
  goldBright:   '#EDD07C',
  goldDim:      'rgba(200,168,75,0.10)',
  goldGlow:     'rgba(200,168,75,0.18)',
  jade:         '#10CBA8',
  jadeDim:      'rgba(16,203,168,0.10)',
  crimson:      '#EF4060',
  crimsonDim:   'rgba(239,64,96,0.10)',
  amber:        '#F5A623',
  amberDim:     'rgba(245,166,35,0.10)',
  text:         '#E6E2D8',
  textMid:      '#9A97A0',
  textDim:      '#4A4860',
  fontSerif:    "'Cormorant Garamond', 'Georgia', serif",
  fontMono:     "'JetBrains Mono', 'IBM Plex Mono', 'Courier New', monospace",
  fontSans:     "'DM Sans', -apple-system, sans-serif",
};

// ─── Interfaces ───────────────────────────────────────────────────────────────
interface DashboardStats {
  totalIncome: Record<string, number>;
  pendingInvoices: Record<string, number>;
  totalExpenses: Record<string, number>;
  totalClients: number;
  invoicesPaid: number;
  invoicesPending: number;
  invoicesOverdue: number;
  paymentTrends: {
    onTimePaymentRate: number;
    averagePaymentTime: number;
    overdueRate: number;
  };
  trends: {
    income: { value: number; isPositive: boolean };
    pending: { value: number; isPositive: boolean };
    clients: { value: number; isPositive: boolean };
    overdue: { value: number; isPositive: boolean };
  };
}

// ─── Counter Animation Hook ───────────────────────────────────────────────────
function useCountUp(target: number, delay = 0, duration = 1400): number {
  const [value, setValue] = useState(0);
  const frame = useRef<number>(0);

  useEffect(() => {
    if (target === 0) { setValue(0); return; }

    const timeout = setTimeout(() => {
      const start = performance.now();

      const tick = (now: number) => {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 4); // ease-out quart
        setValue(Math.round(target * eased));
        if (progress < 1) {
          frame.current = requestAnimationFrame(tick);
        }
      };

      frame.current = requestAnimationFrame(tick);
    }, delay);

    return () => {
      clearTimeout(timeout);
      cancelAnimationFrame(frame.current);
    };
  }, [target, delay, duration]);

  return value;
}

// ─── Live Clock ───────────────────────────────────────────────────────────────
function useLiveClock() {
  const [time, setTime] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return time;
}

// ─── Currency formatter ───────────────────────────────────────────────────────
function formatCurrency(amounts: Record<string, number>): string {
  if (Object.keys(amounts).length === 0) return '$0.00';
  const symbols: Record<string, string> = {
    USD: '$', EUR: '€', GBP: '£', CAD: 'C$', AUD: 'A$',
    JPY: '¥', CHF: 'CHF', CNY: '¥', INR: '₹', BRL: 'R$',
    BTC: '₿', ETH: 'Ξ',
  };
  return Object.entries(amounts)
    .map(([c, v]) => `${symbols[c] ?? c}${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`)
    .join(' / ');
}

// ─── Metric Card ─────────────────────────────────────────────────────────────
interface MetricProps {
  label: string;
  value: string;
  rawValue: number;
  trend?: { value: number; isPositive: boolean };
  accentColor: string;
  accentDim: string;
  icon: React.ElementType;
  animDelay?: number;
  onClick?: () => void;
  loading?: boolean;
}

function MetricCell({
  label, value, rawValue, trend, accentColor, accentDim, icon: Icon,
  animDelay = 0, onClick, loading,
}: MetricProps) {
  const [hovered, setHovered] = useState(false);
  const count = useCountUp(rawValue, animDelay + 200);

  // For currency values, show formatted string; for counts, show animated number
  const displayValue = rawValue > 100
    ? value  // formatted currency string — use as-is
    : loading ? '—' : count.toString();

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position: 'relative',
        padding: '24px 20px 20px',
        background: hovered ? T.cardHover : T.card,
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
        transform: hovered ? 'translateY(-2px)' : 'translateY(0)',
        overflow: 'hidden',
        animation: `mlFadeUp 0.5s ease both`,
        animationDelay: `${animDelay}ms`,
      }}
    >
      {/* Gold left accent bar */}
      <div style={{
        position: 'absolute',
        left: 0, top: 0, bottom: 0,
        width: '2px',
        background: `linear-gradient(180deg, ${accentColor}, transparent)`,
        opacity: hovered ? 1 : 0.4,
        transition: 'opacity 0.2s ease',
      }} />

      {/* Scan-line on hover */}
      {hovered && (
        <div style={{
          position: 'absolute',
          left: 0, right: 0,
          height: '1px',
          background: `linear-gradient(90deg, transparent, ${accentColor}60, transparent)`,
          animation: 'mlScan 0.7s ease forwards',
          pointerEvents: 'none',
        }} />
      )}

      {/* Icon + label row */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '12px',
      }}>
        <div style={{
          fontSize: '9px',
          fontFamily: T.fontMono,
          letterSpacing: '0.18em',
          color: T.textMid,
          textTransform: 'uppercase',
        }}>
          {label}
        </div>
        <div style={{
          width: '28px', height: '28px',
          borderRadius: '6px',
          background: accentDim,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'background 0.2s',
        }}>
          <Icon size={13} color={accentColor} />
        </div>
      </div>

      {/* Value */}
      <div style={{
        fontFamily: T.fontMono,
        fontSize: rawValue > 100 ? '1.1rem' : '2rem',
        fontWeight: 600,
        color: T.text,
        lineHeight: 1,
        marginBottom: '10px',
        letterSpacing: rawValue > 100 ? '-0.02em' : '-0.03em',
        opacity: loading ? 0.4 : 1,
        transition: 'opacity 0.3s',
      }}>
        {loading ? '——' : displayValue}
      </div>

      {/* Trend */}
      {trend && !loading && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          fontSize: '11px',
          fontFamily: T.fontMono,
          color: trend.value === 0 ? T.textDim
            : trend.isPositive ? T.jade : T.crimson,
        }}>
          {trend.value > 0 && (
            trend.isPositive
              ? <ArrowUpRight size={11} />
              : <ArrowDownRight size={11} />
          )}
          <span>{trend.value > 0 ? `${trend.value}%` : 'No change'}</span>
        </div>
      )}
    </div>
  );
}

// ─── Section Header ───────────────────────────────────────────────────────────
function SectionHeader({
  title, subtitle, children,
}: { title: string; subtitle?: string; children?: React.ReactNode }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'space-between',
      marginBottom: '16px',
    }}>
      <div>
        <div style={{
          fontFamily: T.fontSerif,
          fontSize: '1.2rem',
          fontWeight: 600,
          color: T.text,
          letterSpacing: '-0.01em',
          lineHeight: 1.2,
        }}>
          {title}
        </div>
        {subtitle && (
          <div style={{
            fontFamily: T.fontSans,
            fontSize: '11px',
            color: T.textMid,
            marginTop: '3px',
            letterSpacing: '0.02em',
          }}>
            {subtitle}
          </div>
        )}
      </div>
      {children && <div>{children}</div>}
    </div>
  );
}

// ─── Divider ─────────────────────────────────────────────────────────────────
function GoldDivider() {
  return (
    <div style={{
      height: '1px',
      background: `linear-gradient(90deg, ${T.gold}40, ${T.gold}15, transparent)`,
      margin: '2px 0',
    }} />
  );
}

// ─── Progress Bar ─────────────────────────────────────────────────────────────
function ProgressBar({
  value, color, label, suffix = '%',
}: { value: number; color: string; label: string; suffix?: string }) {
  return (
    <div style={{ marginBottom: '14px' }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        marginBottom: '6px',
        fontFamily: T.fontSans,
        fontSize: '11px',
        color: T.textMid,
      }}>
        <span>{label}</span>
        <span style={{ fontFamily: T.fontMono, color: T.text }}>{value}{suffix}</span>
      </div>
      <div style={{
        height: '3px',
        background: T.border,
        borderRadius: '2px',
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${Math.min(value, 100)}%`,
          background: `linear-gradient(90deg, ${color}, ${color}80)`,
          borderRadius: '2px',
          transition: 'width 1s ease',
        }} />
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export function ProfessionalDashboard() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const clock = useLiveClock();

  const [stats, setStats] = useState<DashboardStats>({
    totalIncome: {},
    pendingInvoices: {},
    totalExpenses: {},
    totalClients: 0,
    invoicesPaid: 0,
    invoicesPending: 0,
    invoicesOverdue: 0,
    paymentTrends: { onTimePaymentRate: 0, averagePaymentTime: 0, overdueRate: 0 },
    trends: {
      income: { value: 0, isPositive: true },
      pending: { value: 0, isPositive: true },
      clients: { value: 0, isPositive: true },
      overdue: { value: 0, isPositive: false },
    },
  });
  const [loading, setLoading] = useState(true);
  const [userName, setUserName] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const s = await dashboardApi.getStats();
      setStats(s);
      const user = getCurrentUser();
      if (user) {
        setUserName(user.first_name
          ? `${user.first_name} ${user.last_name ?? ''}`.trim()
          : user.email);
      }
    } catch {
      toast.error(t('dashboard.errors.load_failed'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    let mounted = true;
    fetchData().then(() => { if (!mounted) return; });
    const interval = setInterval(() => setRefreshKey(k => k + 1), 5 * 60_000);
    const onRefresh = () => { if (mounted) fetchData(); };
    window.addEventListener('dashboard-refresh', onRefresh);
    return () => {
      mounted = false;
      clearInterval(interval);
      window.removeEventListener('dashboard-refresh', onRefresh);
    };
  }, [fetchData]);

  // Derive primary numeric values for counter animation
  const primaryIncome = Object.values(stats.totalIncome)[0] ?? 0;
  const primaryExpenses = Object.values(stats.totalExpenses)[0] ?? 0;
  const primaryPending = Object.values(stats.pendingInvoices)[0] ?? 0;

  const timeStr = clock.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const dateStr = clock.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  return (
    <div
      data-tour="dashboard-welcome"
      style={{
        background: T.bg,
        minHeight: '100%',
        color: T.text,
        fontFamily: T.fontSans,
        backgroundImage: `radial-gradient(circle, ${T.gold}0A 1px, transparent 1px)`,
        backgroundSize: '30px 30px',
        '--card': '240 10% 6%',
        '--card-foreground': '39 10% 90%',
        '--border': '240 5% 14%',
        '--muted': '240 8% 10%',
        '--muted-foreground': '240 5% 55%',
        '--background': '240 10% 4%',
        '--foreground': '39 10% 90%',
        '--primary': '43 55% 55%',
        '--primary-foreground': '240 10% 4%',
        '--secondary': '240 8% 12%',
        '--secondary-foreground': '39 10% 75%',
        '--accent': '240 8% 14%',
        '--accent-foreground': '39 10% 90%',
        '--popover': '240 10% 6%',
        '--popover-foreground': '39 10% 90%',
        '--input': '240 5% 14%',
        '--ring': '43 55% 55%',
      } as React.CSSProperties}
    >
      {/* ── Font & Animation Injection ─────────────────────────────────────── */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=JetBrains+Mono:wght@400;500;600&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&display=swap');

        @keyframes mlFadeUp {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes mlFadeIn {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
        @keyframes mlScan {
          0%   { top: 0%; opacity: 0; }
          10%  { opacity: 1; }
          90%  { opacity: 1; }
          100% { top: 100%; opacity: 0; }
        }
        @keyframes mlPulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.25; }
        }
        @keyframes mlShimmer {
          0%   { background-position: -200% center; }
          100% { background-position: 200% center; }
        }
        @keyframes mlBorderFlow {
          0%   { border-color: rgba(200,168,75,0.10); }
          50%  { border-color: rgba(200,168,75,0.28); }
          100% { border-color: rgba(200,168,75,0.10); }
        }

        .ml-chart-wrap .recharts-cartesian-grid-horizontal line,
        .ml-chart-wrap .recharts-cartesian-grid-vertical line {
          stroke: rgba(255,255,255,0.04) !important;
        }
        .ml-chart-wrap .recharts-text {
          fill: #6B6880 !important;
          font-family: 'JetBrains Mono', monospace !important;
          font-size: 10px !important;
        }
        .ml-chart-wrap .recharts-tooltip-wrapper {
          filter: none !important;
        }

        /* Force dark theme on embedded ShadCN cards */
        [data-midnight] .border {
          border-color: ${T.border} !important;
        }
        [data-midnight] [class*="bg-white"],
        [data-midnight] [class*="bg-card"] {
          background: ${T.card} !important;
        }
      `}</style>

      {/* ── Command Bar ───────────────────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 24px',
          borderBottom: `1px solid ${T.border}`,
          background: T.surface,
          animation: 'mlFadeIn 0.4s ease both',
          marginBottom: '0',
        }}
        data-tour="dashboard-header"
      >
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '28px', height: '28px',
            border: `1.5px solid ${T.gold}`,
            borderRadius: '4px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: T.fontSerif,
            fontSize: '13px',
            fontWeight: 700,
            color: T.gold,
            letterSpacing: '-0.05em',
          }}>
            YF
          </div>
          <div>
            <div style={{
              fontFamily: T.fontSans,
              fontSize: '11px',
              fontWeight: 600,
              letterSpacing: '0.14em',
              color: T.textMid,
              textTransform: 'uppercase',
            }}>
              YourFinanceWorks
            </div>
            {userName && (
              <div style={{
                fontFamily: T.fontSans,
                fontSize: '10px',
                color: T.textDim,
                marginTop: '1px',
              }}>
                {userName}
              </div>
            )}
          </div>
        </div>

        {/* Center actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <HelpCenter />
          <button
            onClick={() => { fetchData(); setRefreshKey(k => k + 1); }}
            style={{
              background: 'transparent',
              border: `1px solid ${T.border}`,
              borderRadius: '6px',
              padding: '5px 10px',
              color: T.textMid,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              fontSize: '10px',
              fontFamily: T.fontMono,
              letterSpacing: '0.06em',
              transition: 'all 0.15s',
            }}
          >
            <RefreshCw size={10} />
            REFRESH
          </button>
          <button
            onClick={() => navigate('/invoices/new')}
            style={{
              background: T.gold,
              border: 'none',
              borderRadius: '6px',
              padding: '6px 14px',
              color: T.bg,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              fontSize: '10px',
              fontFamily: T.fontMono,
              fontWeight: 600,
              letterSpacing: '0.08em',
              transition: 'all 0.15s',
            }}
          >
            <Plus size={11} />
            NEW INVOICE
          </button>
        </div>

        {/* Clock */}
        <div style={{ textAlign: 'right' }}>
          <div style={{
            fontFamily: T.fontMono,
            fontSize: '16px',
            fontWeight: 500,
            color: T.text,
            letterSpacing: '0.04em',
          }}>
            {timeStr}
          </div>
          <div style={{
            fontFamily: T.fontSans,
            fontSize: '10px',
            color: T.textMid,
            marginTop: '1px',
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            justifyContent: 'flex-end',
          }}>
            <span style={{
              width: '5px', height: '5px',
              borderRadius: '50%',
              background: T.jade,
              display: 'inline-block',
              animation: 'mlPulse 2s ease infinite',
            }} />
            {dateStr}
          </div>
        </div>
      </div>

      {/* ── Metrics Strip ─────────────────────────────────────────────────── */}
      <div
        data-tour="dashboard-stats"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(5, 1fr)',
          borderBottom: `1px solid ${T.border}`,
          background: T.surface,
        }}
      >
        {/* Vertical separators */}
        {[
          {
            label: t('dashboard.stats.total_income'),
            value: formatCurrency(stats.totalIncome),
            rawValue: primaryIncome,
            trend: stats.trends.income,
            accentColor: T.jade,
            accentDim: T.jadeDim,
            icon: DollarSign,
            delay: 0,
            onClick: () => navigate('/invoices'),
          },
          {
            label: t('dashboard.stats.total_expenses'),
            value: formatCurrency(stats.totalExpenses),
            rawValue: primaryExpenses,
            trend: undefined,
            accentColor: T.amber,
            accentDim: T.amberDim,
            icon: TrendingUp,
            delay: 80,
            onClick: () => navigate('/expenses'),
          },
          {
            label: t('dashboard.stats.pending_amount'),
            value: formatCurrency(stats.pendingInvoices),
            rawValue: primaryPending,
            trend: stats.trends.pending,
            accentColor: T.gold,
            accentDim: T.goldDim,
            icon: Clock,
            delay: 160,
            onClick: () => navigate('/invoices'),
          },
          {
            label: t('dashboard.stats.total_clients'),
            value: stats.totalClients.toString(),
            rawValue: stats.totalClients,
            trend: stats.trends.clients,
            accentColor: '#818CF8',
            accentDim: 'rgba(129,140,248,0.10)',
            icon: Users,
            delay: 240,
            onClick: () => navigate('/clients'),
          },
          {
            label: t('dashboard.stats.overdue_invoices'),
            value: stats.invoicesOverdue.toString(),
            rawValue: stats.invoicesOverdue,
            trend: stats.trends.overdue,
            accentColor: T.crimson,
            accentDim: T.crimsonDim,
            icon: AlertCircle,
            delay: 320,
            onClick: () => navigate('/invoices'),
          },
        ].map((metric, i) => (
          <div key={i} style={{
            borderRight: i < 4 ? `1px solid ${T.border}` : 'none',
          }}>
            <MetricCell
              label={metric.label}
              value={metric.value}
              rawValue={metric.rawValue}
              trend={metric.trend}
              accentColor={metric.accentColor}
              accentDim={metric.accentDim}
              icon={metric.icon}
              animDelay={metric.delay}
              onClick={metric.onClick}
              loading={loading}
            />
          </div>
        ))}
      </div>

      {/* ── Main Content ──────────────────────────────────────────────────── */}
      <div style={{ padding: '0 0 32px' }}>

        {/* Charts + Activity row */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 340px',
            gap: '0',
            borderBottom: `1px solid ${T.border}`,
          }}
          data-midnight
        >
          {/* Revenue Chart */}
          <div
            className="ml-chart-wrap"
            style={{
              padding: '28px 28px 24px',
              borderRight: `1px solid ${T.border}`,
              animation: 'mlFadeUp 0.6s ease both',
              animationDelay: '200ms',
            }}
            data-tour="dashboard-revenue-chart"
          >
            <SectionHeader
              title={t('dashboard.sections.revenue_trends')}
              subtitle="6-month invoice overview"
            >
              <button
                onClick={() => navigate('/analytics')}
                style={{
                  background: 'transparent',
                  border: `1px solid ${T.border}`,
                  borderRadius: '5px',
                  padding: '4px 10px',
                  color: T.textMid,
                  cursor: 'pointer',
                  fontSize: '10px',
                  fontFamily: T.fontMono,
                  letterSpacing: '0.08em',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                FULL REPORT <ChevronRight size={10} />
              </button>
            </SectionHeader>
            <InvoiceChart />
          </div>

          {/* Recent Activity */}
          <div
            style={{
              padding: '28px 20px 24px',
              animation: 'mlFadeUp 0.6s ease both',
              animationDelay: '280ms',
            }}
            data-tour="dashboard-recent"
          >
            <SectionHeader
              title={t('dashboard.sections.recent_activity')}
            >
              <button
                onClick={() => { setRefreshKey(k => k + 1); }}
                style={{
                  background: 'transparent',
                  border: `1px solid ${T.border}`,
                  borderRadius: '5px',
                  padding: '4px 8px',
                  color: T.textMid,
                  cursor: 'pointer',
                  lineHeight: 1,
                }}
              >
                <RefreshCw size={10} color={T.textMid} />
              </button>
            </SectionHeader>
            <RecentActivity refreshKey={refreshKey} />
          </div>
        </div>

        {/* Quick Actions */}
        <div
          style={{
            padding: '28px 28px 24px',
            borderBottom: `1px solid ${T.border}`,
            animation: 'mlFadeUp 0.6s ease both',
            animationDelay: '360ms',
          }}
          data-tour="dashboard-quick-actions"
        >
          <SectionHeader
            title={t('dashboard.quick_actions.title')}
            subtitle={t('dashboard.quick_actions.subtitle')}
          />
          <QuickActions />
        </div>

        {/* Payment Health + Business Vitals */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '0',
            animation: 'mlFadeUp 0.6s ease both',
            animationDelay: '440ms',
          }}
        >
          {/* Payment Health */}
          <div
            style={{
              padding: '28px 28px 24px',
              borderRight: `1px solid ${T.border}`,
            }}
            data-tour="dashboard-payment-trends"
          >
            <SectionHeader
              title={t('dashboard.sections.payment_trends')}
              subtitle={t('dashboard.sections.payment_trends_desc')}
            />

            <ProgressBar
              value={stats.paymentTrends.onTimePaymentRate}
              color={T.jade}
              label={t('dashboard.metrics.on_time_payments')}
            />
            <ProgressBar
              value={Math.min((stats.paymentTrends.averagePaymentTime / 60) * 100, 100)}
              color={T.gold}
              label={t('dashboard.metrics.average_payment_time')}
              suffix={` (${stats.paymentTrends.averagePaymentTime}d avg)`}
            />
            <ProgressBar
              value={stats.paymentTrends.overdueRate}
              color={T.crimson}
              label={t('dashboard.metrics.overdue_rate')}
            />

            <GoldDivider />
            <div style={{
              marginTop: '16px',
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1fr',
              gap: '8px',
            }}>
              {[
                { label: 'PAID', value: stats.invoicesPaid, color: T.jade },
                { label: 'PENDING', value: stats.invoicesPending, color: T.gold },
                { label: 'OVERDUE', value: stats.invoicesOverdue, color: T.crimson },
              ].map(item => (
                <div key={item.label} style={{
                  background: T.card,
                  border: `1px solid ${T.border}`,
                  borderRadius: '6px',
                  padding: '12px 10px',
                  textAlign: 'center',
                }}>
                  <div style={{
                    fontFamily: T.fontMono,
                    fontSize: '1.3rem',
                    fontWeight: 600,
                    color: item.color,
                  }}>
                    {item.value}
                  </div>
                  <div style={{
                    fontFamily: T.fontMono,
                    fontSize: '8px',
                    letterSpacing: '0.12em',
                    color: T.textDim,
                    marginTop: '4px',
                    textTransform: 'uppercase',
                  }}>
                    {item.label}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Business Vitals */}
          <div
            style={{ padding: '28px 28px 24px' }}
            data-tour="dashboard-business-health"
          >
            <SectionHeader
              title={t('dashboard.sections.business_health')}
              subtitle={t('dashboard.sections.business_health_desc')}
            />

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {[
                {
                  label: t('dashboard.metrics.monthly_growth'),
                  value: `${stats.trends.income.isPositive ? '+' : ''}${stats.trends.income.value}%`,
                  color: stats.trends.income.isPositive ? T.jade : T.crimson,
                  icon: TrendingUp,
                },
                {
                  label: t('dashboard.metrics.active_clients'),
                  value: stats.totalClients.toString(),
                  color: '#818CF8',
                  icon: Users,
                },
                {
                  label: t('dashboard.metrics.revenue_trend'),
                  value: `${stats.trends.income.isPositive ? '↗' : '↘'} ${stats.trends.income.value}%`,
                  color: stats.trends.income.isPositive ? T.jade : T.crimson,
                  icon: BarChart2,
                },
              ].map((item) => (
                <div key={item.label} style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px 14px',
                  background: T.card,
                  border: `1px solid ${T.border}`,
                  borderRadius: '7px',
                  transition: 'border-color 0.2s',
                }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontSize: '12px',
                    fontFamily: T.fontSans,
                    color: T.textMid,
                  }}>
                    <item.icon size={13} color={item.color} />
                    {item.label}
                  </div>
                  <span style={{
                    fontFamily: T.fontMono,
                    fontSize: '13px',
                    fontWeight: 600,
                    color: item.color,
                  }}>
                    {item.value}
                  </span>
                </div>
              ))}

              {/* Gamification teaser */}
              <div
                onClick={() => navigate('/settings?tab=gamification')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px 14px',
                  background: `linear-gradient(135deg, rgba(129,140,248,0.08), rgba(200,168,75,0.06))`,
                  border: `1px solid rgba(129,140,248,0.20)`,
                  borderRadius: '7px',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                  animation: 'mlBorderFlow 4s ease infinite',
                  marginTop: '2px',
                }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '12px',
                  fontFamily: T.fontSans,
                  color: T.textMid,
                }}>
                  <Zap size={13} color="#818CF8" />
                  <div>
                    <div style={{ color: T.text }}>{t('dashboard.metrics.gamification_score')}</div>
                    <div style={{ fontSize: '10px', marginTop: '1px' }}>{t('dashboard.metrics.gamification_desc')}</div>
                  </div>
                </div>
                <ChevronRight size={13} color={T.textDim} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
