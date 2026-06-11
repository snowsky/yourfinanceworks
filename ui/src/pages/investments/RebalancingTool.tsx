import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Save,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  CheckCircle2,
  PieChart
} from 'lucide-react';
import { investmentApi, InvestmentPortfolio, RebalanceReport } from '@/lib/api';
import { useLocaleFormatter } from '@/i18n/formatters';
import { toast } from 'sonner';

const ASSET_CLASSES = ['stocks', 'bonds', 'cash', 'real_estate', 'commodities'];

const RebalancingTool: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const portfolioId = parseInt(id || '0');
  const formatter = useLocaleFormatter();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [portfolio, setPortfolio] = useState<InvestmentPortfolio | null>(null);
  const [report, setReport] = useState<RebalanceReport | null>(null);
  const [targets, setTargets] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, [portfolioId]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [pData, rData] = await Promise.all([
        investmentApi.get(portfolioId),
        investmentApi.getRebalanceReport(portfolioId).catch(err => {
          if (err.response?.status === 422) {
            return null; // No targets set yet
          }
          throw err;
        })
      ]);

      setPortfolio(pData);
      setReport(rData);

      // Initialize targets from portfolio or report or defaults
      if (pData.target_allocations) {
        setTargets(pData.target_allocations);
      } else if (rData?.target_allocations) {
        setTargets(rData.target_allocations);
      } else {
        // Default targets
        setTargets({
          'stocks': 60,
          'bonds': 30,
          'cash': 10
        });
      }
    } catch (err: any) {
      console.error('Error loading rebalancing data:', err);
      setError(err.message || 'Failed to load rebalancing data');
      toast.error('Failed to load portfolio data');
    } finally {
      setLoading(false);
    }
  };

  const handleTargetChange = (assetClass: string, value: string) => {
    const numValue = parseFloat(value) || 0;
    setTargets(prev => ({
      ...prev,
      [assetClass]: numValue
    }));
  };

  const handleSaveTargets = async () => {
    const total = Object.values(targets).reduce((sum, val) => sum + val, 0);
    if (Math.abs(total - 100) > 0.01 && total !== 0) {
      toast.error('Total allocation must sum to 100%');
      return;
    }

    try {
      setSaving(true);
      await investmentApi.update(portfolioId, {
        target_allocations: targets
      });
      toast.success('Target allocations saved');
      loadData(); // Reload to get updated report
    } catch (err: any) {
      toast.error(err.message || 'Failed to save targets');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error || !portfolio) {
    return (
      <div className="p-8 text-center">
        <AlertCircle className="mx-auto h-12 w-12 text-destructive mb-4" />
        <h3 className="text-lg font-medium text-foreground">Error Loading Portfolio</h3>
        <p className="mt-2 text-sm text-muted-foreground">{error || 'Portfolio not found'}</p>
        <button
          onClick={() => navigate('/investments')}
          className="mt-4 text-primary hover:text-primary/80"
        >
          Back to Dashboard
        </button>
      </div>
    );
  }

  const totalTarget = Object.values(targets).reduce((sum, val) => sum + val, 0);

  return (
    <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate(`/investments/portfolios/${portfolioId}`)}
            className="p-2 rounded-full hover:bg-muted transition-colors"
          >
            <ArrowLeft className="h-5 w-5 text-muted-foreground" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Asset Rebalancing</h1>
            <p className="text-sm text-muted-foreground">{portfolio.name} • {portfolio.portfolio_type.toUpperCase()}</p>
          </div>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={loadData}
            className="inline-flex items-center px-4 py-2 border border-border rounded-md shadow-sm text-sm font-medium text-muted-foreground bg-card hover:bg-muted focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </button>
          <button
            onClick={handleSaveTargets}
            disabled={saving}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-primary-foreground bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50"
          >
            <Save className="h-4 w-4 mr-2" />
            {saving ? 'Saving...' : 'Save Targets'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Target Settings */}
        <div className="lg:col-span-1">
          <div className="bg-card shadow-sm border border-border rounded-xl overflow-hidden">
            <div className="px-6 py-4 border-b border-border bg-muted/50">
              <h3 className="text-lg font-semibold text-foreground">Target Allocation</h3>
              <p className="text-xs text-muted-foreground mt-1">Set your desired asset mix</p>
            </div>
            <div className="p-6 space-y-6">
              {ASSET_CLASSES.map(ac => (
                <div key={ac}>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-sm font-medium text-muted-foreground capitalize">
                      {ac.replace('_', ' ')}
                    </label>
                    <div className="relative rounded-md shadow-sm w-24">
                      <input
                        type="number"
                        min="0"
                        max="100"
                        step="0.1"
                        value={targets[ac] || 0}
                        onChange={(e) => handleTargetChange(ac, e.target.value)}
                        className="focus:ring-primary focus:border-primary block w-full pr-8 sm:text-sm border-input rounded-md"
                      />
                      <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                        <span className="text-muted-foreground sm:text-sm">%</span>
                      </div>
                    </div>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="1"
                    value={targets[ac] || 0}
                    onChange={(e) => handleTargetChange(ac, e.target.value)}
                    className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  />
                </div>
              ))}

              <div className={`p-4 rounded-lg flex items-center justify-between ${Math.abs(totalTarget - 100) < 0.01 ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning'}`}>
                <div className="flex items-center">
                  <PieChart className="h-5 w-5 mr-3" />
                  <span className="font-semibold text-sm">Total Allocation</span>
                </div>
                <span className="font-bold text-lg">{totalTarget.toFixed(1)}%</span>
              </div>

              {Math.abs(totalTarget - 100) > 0.01 && (
                <div className="flex items-start bg-destructive/10 p-3 rounded-lg text-destructive text-xs">
                  <AlertCircle className="h-4 w-4 mr-2 flex-shrink-0" />
                  <span>Total must equal exactly 100% for rebalancing analysis to work correctly.</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Drift & Recommendations */}
        <div className="lg:col-span-2 space-y-8">
          {report ? (
            <>
              {/* Drift Analysis */}
              <div className="bg-card shadow-sm border border-border rounded-xl overflow-hidden">
                <div className="px-6 py-4 border-b border-border flex justify-between items-center">
                  <h3 className="text-lg font-semibold text-foreground">Drift Analysis</h3>
                  <div className={`flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${report.is_balanced ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning'}`}>
                    {report.is_balanced ? <CheckCircle2 className="h-3 w-3 mr-1" /> : <AlertCircle className="h-3 w-3 mr-1" />}
                    {report.is_balanced ? 'Target Met' : 'Drift Detected'}
                  </div>
                </div>
                <div className="p-6">
                  <div className="space-y-6">
                    {ASSET_CLASSES.filter(ac => report.current_allocations[ac] > 0 || report.target_allocations[ac] > 0).map(ac => {
                      const current = report.current_allocations[ac] || 0;
                      const target = report.target_allocations[ac] || 0;
                      const drift = report.drifts[ac] || 0;

                      return (
                        <div key={ac}>
                          <div className="flex justify-between items-end mb-2">
                            <span className="text-sm font-medium text-muted-foreground capitalize">{ac.replace('_', ' ')}</span>
                            <span className={`text-xs font-semibold px-2 py-1 rounded ${drift > 1 ? 'text-red-600 bg-red-50' : drift < -1 ? 'text-blue-600 bg-blue-50' : 'text-green-600 bg-green-50'}`}>
                              {drift > 0 ? '+' : ''}{drift.toFixed(1)}% Drift
                            </span>
                          </div>

                          <div className="relative pt-1">
                            {/* Current vs Target visualization */}
                            <div className="flex mb-2 items-center justify-between text-xs text-muted-foreground">
                              <div>Current: {current.toFixed(1)}%</div>
                              <div>Target: {target.toFixed(1)}%</div>
                            </div>
                            <div className="overflow-hidden h-4 text-xs flex rounded bg-muted">
                              <div
                                style={{ width: `${current}%` }}
                                className={`shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center transition-all duration-500 ${drift > 1 ? 'bg-amber-500' : drift < -1 ? 'bg-indigo-400' : 'bg-green-500'}`}
                              ></div>
                            </div>
                            {/* Target marker */}
                            <div
                              className="absolute top-5 h-6 w-0.5 bg-gray-900 z-10"
                              style={{ left: `${target}%`, transform: 'translateY(-50%)' }}
                              title={`Target: ${target}%`}
                            ></div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Actionable Trade Recommendations */}
              <div className="bg-card shadow-sm border border-border rounded-xl overflow-hidden">
                <div className="px-6 py-4 border-b border-border">
                  <h3 className="text-lg font-semibold text-foreground">Recommended Actions</h3>
                  <p className="text-sm text-muted-foreground">Trades needed to align with target allocation</p>
                </div>
                <div className="p-6">
                  {report.recommended_actions.length > 0 ? (
                    <div className="space-y-4">
                      {report.recommended_actions.map((action, idx) => (
                        <div key={idx} className="flex items-center justify-between p-4 bg-muted rounded-lg border border-border">
                          <div className="flex items-center space-x-4">
                            <div className={`p-2 rounded-full ${action.action_type === 'BUY' ? 'bg-success/10 text-success' : 'bg-destructive/10 text-destructive'}`}>
                              {action.action_type === 'BUY' ? <TrendingUp className="h-5 w-5" /> : <TrendingDown className="h-5 w-5" />}
                            </div>
                            <div>
                              <div className="font-semibold text-foreground">
                                {action.action_type} {action.asset_class.toUpperCase().replace('_', ' ')}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                To correct {Math.abs(action.percentage_drift).toFixed(1)}% drift
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-lg font-bold text-foreground">
                              {formatter.formatCurrency(action.amount)}
                            </div>
                            <div className="text-xs text-muted-foreground italic">Approximate Amount</div>
                          </div>
                        </div>
                      ))}

                      <div className="mt-6 p-4 bg-primary/10 border border-primary/30 rounded-lg">
                        <div className="flex">
                          <AlertCircle className="h-5 w-5 text-primary mr-3 flex-shrink-0" />
                          <p className="text-sm text-primary">
                            <strong>Note:</strong> These are suggested buy/sell amounts for each asset class.
                            You should decide which specific securities within these classes to trade based on your investment strategy.
                          </p>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-12">
                      <CheckCircle2 className="mx-auto h-12 w-12 text-success mb-4" />
                      <h4 className="text-lg font-medium text-foreground">Portfolio is Balanced</h4>
                      <p className="mt-2 text-sm text-muted-foreground">Current allocation is within 1% of your targets. No actions needed.</p>
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="bg-card shadow-sm border border-border rounded-xl p-12 text-center">
              <div className="mx-auto h-16 w-16 bg-primary/10 rounded-full flex items-center justify-center mb-4">
                <PieChart className="h-8 w-8 text-primary" />
              </div>
              <h3 className="text-lg font-semibold text-foreground">No Rebalancing Data</h3>
              <p className="mt-2 text-sm text-muted-foreground max-w-md mx-auto">
                Set and save your target allocations on the left to see drift analysis and trade recommendations.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RebalancingTool;
