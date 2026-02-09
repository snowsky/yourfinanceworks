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
import { toast } from 'sonner';

const ASSET_CLASSES = ['stocks', 'bonds', 'cash', 'real_estate', 'commodities'];

const RebalancingTool: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const portfolioId = parseInt(id || '0');

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
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (error || !portfolio) {
    return (
      <div className="p-8 text-center">
        <AlertCircle className="mx-auto h-12 w-12 text-red-500 mb-4" />
        <h3 className="text-lg font-medium text-gray-900">Error Loading Portfolio</h3>
        <p className="mt-2 text-sm text-gray-500">{error || 'Portfolio not found'}</p>
        <button
          onClick={() => navigate('/investments')}
          className="mt-4 text-indigo-600 hover:text-indigo-500"
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
            className="p-2 rounded-full hover:bg-gray-100 transition-colors"
          >
            <ArrowLeft className="h-5 w-5 text-gray-500" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Asset Rebalancing</h1>
            <p className="text-sm text-gray-500">{portfolio.name} • {portfolio.portfolio_type.toUpperCase()}</p>
          </div>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={loadData}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </button>
          <button
            onClick={handleSaveTargets}
            disabled={saving}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
          >
            <Save className="h-4 w-4 mr-2" />
            {saving ? 'Saving...' : 'Save Targets'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Target Settings */}
        <div className="lg:col-span-1">
          <div className="bg-white shadow-sm border border-gray-100 rounded-xl overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 bg-gray-50/50">
              <h3 className="text-lg font-semibold text-gray-900">Target Allocation</h3>
              <p className="text-xs text-gray-500 mt-1">Set your desired asset mix</p>
            </div>
            <div className="p-6 space-y-6">
              {ASSET_CLASSES.map(ac => (
                <div key={ac}>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-sm font-medium text-gray-700 capitalize">
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
                        className="focus:ring-indigo-500 focus:border-indigo-500 block w-full pr-8 sm:text-sm border-gray-300 rounded-md"
                      />
                      <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                        <span className="text-gray-500 sm:text-sm">%</span>
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
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
                  />
                </div>
              ))}

              <div className={`p-4 rounded-lg flex items-center justify-between ${Math.abs(totalTarget - 100) < 0.01 ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'}`}>
                <div className="flex items-center">
                  <PieChart className="h-5 w-5 mr-3" />
                  <span className="font-semibold text-sm">Total Allocation</span>
                </div>
                <span className="font-bold text-lg">{totalTarget.toFixed(1)}%</span>
              </div>

              {Math.abs(totalTarget - 100) > 0.01 && (
                <div className="flex items-start bg-red-50 p-3 rounded-lg text-red-700 text-xs">
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
              <div className="bg-white shadow-sm border border-gray-100 rounded-xl overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center">
                  <h3 className="text-lg font-semibold text-gray-900">Drift Analysis</h3>
                  <div className={`flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${report.is_balanced ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'}`}>
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
                            <span className="text-sm font-medium text-gray-700 capitalize">{ac.replace('_', ' ')}</span>
                            <span className={`text-xs font-semibold px-2 py-1 rounded ${drift > 1 ? 'text-red-600 bg-red-50' : drift < -1 ? 'text-blue-600 bg-blue-50' : 'text-green-600 bg-green-50'}`}>
                              {drift > 0 ? '+' : ''}{drift.toFixed(1)}% Drift
                            </span>
                          </div>

                          <div className="relative pt-1">
                            {/* Current vs Target visualization */}
                            <div className="flex mb-2 items-center justify-between text-xs text-gray-500">
                              <div>Current: {current.toFixed(1)}%</div>
                              <div>Target: {target.toFixed(1)}%</div>
                            </div>
                            <div className="overflow-hidden h-4 text-xs flex rounded bg-gray-100">
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
              <div className="bg-white shadow-sm border border-gray-100 rounded-xl overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-100">
                  <h3 className="text-lg font-semibold text-gray-900">Recommended Actions</h3>
                  <p className="text-sm text-gray-500">Trades needed to align with target allocation</p>
                </div>
                <div className="p-6">
                  {report.recommended_actions.length > 0 ? (
                    <div className="space-y-4">
                      {report.recommended_actions.map((action, idx) => (
                        <div key={idx} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-100">
                          <div className="flex items-center space-x-4">
                            <div className={`p-2 rounded-full ${action.action_type === 'BUY' ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'}`}>
                              {action.action_type === 'BUY' ? <TrendingUp className="h-5 w-5" /> : <TrendingDown className="h-5 w-5" />}
                            </div>
                            <div>
                              <div className="font-semibold text-gray-900">
                                {action.action_type} {action.asset_class.toUpperCase().replace('_', ' ')}
                              </div>
                              <div className="text-xs text-gray-500">
                                To correct {Math.abs(action.percentage_drift).toFixed(1)}% drift
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-lg font-bold text-gray-900">
                              ${action.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </div>
                            <div className="text-xs text-gray-500 italic">Approximate Amount</div>
                          </div>
                        </div>
                      ))}

                      <div className="mt-6 p-4 bg-indigo-50 border border-indigo-100 rounded-lg">
                        <div className="flex">
                          <AlertCircle className="h-5 w-5 text-indigo-600 mr-3 flex-shrink-0" />
                          <p className="text-sm text-indigo-700">
                            <strong>Note:</strong> These are suggested buy/sell amounts for each asset class.
                            You should decide which specific securities within these classes to trade based on your investment strategy.
                          </p>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-12">
                      <CheckCircle2 className="mx-auto h-12 w-12 text-green-500 mb-4" />
                      <h4 className="text-lg font-medium text-gray-900">Portfolio is Balanced</h4>
                      <p className="mt-2 text-sm text-gray-500">Current allocation is within 1% of your targets. No actions needed.</p>
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="bg-white shadow-sm border border-gray-100 rounded-xl p-12 text-center">
              <div className="mx-auto h-16 w-16 bg-indigo-50 rounded-full flex items-center justify-center mb-4">
                <PieChart className="h-8 w-8 text-indigo-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">No Rebalancing Data</h3>
              <p className="mt-2 text-sm text-gray-500 max-w-md mx-auto">
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
