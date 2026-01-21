import React, { useState, useEffect } from 'react';
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
  ProfessionalCardDescription
} from '@/components/ui/professional-card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { TrendingUp, TrendingDown, Minus, Star, RefreshCw, Info, Gamepad2 } from 'lucide-react';
import { gamificationApi } from '@/lib/api';
import { useTranslation } from 'react-i18next';
import type { FinancialHealthTrend } from '@/types/gamification';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface FinancialHealthScoreProps {
  score: number;
  trend?: FinancialHealthTrend[];
  detailed?: boolean;
  showTrend?: boolean;
}

export function FinancialHealthScore({
  score,
  trend = [],
  detailed = false,
  showTrend = true
}: FinancialHealthScoreProps) {
  const { t } = useTranslation();
  const [healthData, setHealthData] = useState<any>(null);
  const [components, setComponents] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (detailed) {
      fetchDetailedHealthData();
    }
  }, [detailed]);

  const fetchDetailedHealthData = async () => {
    try {
      setLoading(true);
      const [healthScore, componentData] = await Promise.all([
        gamificationApi.getFinancialHealthScore(),
        gamificationApi.getHealthScoreComponents()
      ]);
      setHealthData(healthScore);
      setComponents(componentData);
    } catch (error) {
      console.error('Error fetching detailed health data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    if (score >= 40) return 'text-orange-600';
    return 'text-red-600';
  };

  const getScoreLabel = (score: number) => {
    if (score >= 80) return t('settings.gamification.wellness_score.labels.excellent');
    if (score >= 60) return t('settings.gamification.wellness_score.labels.good');
    if (score >= 40) return t('settings.gamification.wellness_score.labels.fair');
    return t('settings.gamification.wellness_score.labels.needs_improvement');
  };

  const getTrendIcon = () => {
    if (!trend || trend.length < 2) return <Minus className="h-4 w-4" />;

    const recent = trend[trend.length - 1]?.score || 0;
    const previous = trend[trend.length - 2]?.score || 0;

    if (recent > previous) return <TrendingUp className="h-4 w-4 text-green-600" />;
    if (recent < previous) return <TrendingDown className="h-4 w-4 text-red-600" />;
    return <Minus className="h-4 w-4 text-muted-foreground" />;
  };

  const chartData = trend.map(point => ({
    date: new Date(point.date).toLocaleDateString(),
    score: point.score
  }));

  if (detailed && loading) {
    return (
      <ProfessionalCard>
        <ProfessionalCardContent className="p-6">
          <div className="flex items-center justify-center">
            <RefreshCw className="h-5 w-5 animate-spin mr-2" />
            <span>{t('settings.gamification.loading')}</span>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  }

  return (
    <ProfessionalCard>
      <ProfessionalCardHeader>
        <ProfessionalCardTitle className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Gamepad2 className="h-5 w-5 text-purple-500" />
            <span>{t('settings.gamification.wellness_score.title')}</span>
          </div>
          {showTrend && getTrendIcon()}
        </ProfessionalCardTitle>
        <ProfessionalCardDescription>
          {t('settings.gamification.wellness_score.subtitle')}
        </ProfessionalCardDescription>
      </ProfessionalCardHeader>
      <ProfessionalCardContent className="space-y-6">
        {/* Main Score Display */}
        <div className="text-center">
          <div className="relative inline-flex items-center justify-center w-32 h-32 mb-4">
            <svg className="w-32 h-32 transform -rotate-90" viewBox="0 0 120 120">
              <circle
                cx="60"
                cy="60"
                r="50"
                stroke="currentColor"
                strokeWidth="8"
                fill="transparent"
                className="text-gray-200"
              />
              <circle
                cx="60"
                cy="60"
                r="50"
                stroke="currentColor"
                strokeWidth="8"
                fill="transparent"
                strokeDasharray={`${2 * Math.PI * 50}`}
                strokeDashoffset={`${2 * Math.PI * 50 * (1 - score / 100)}`}
                className={getScoreColor(score)}
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <div className={`text-3xl font-bold ${getScoreColor(score)}`}>
                  {Math.round(score)}
                </div>
                <div className="text-xs text-gray-600">{t('settings.gamification.wellness_score.out_of_100')}</div>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-center space-x-2">
            <Badge variant="outline" className={getScoreColor(score)}>
              {getScoreLabel(score)}
            </Badge>
            {getTrendIcon()}
          </div>
        </div>

        {/* Trend Chart */}
        {showTrend && trend.length > 1 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-gray-700">{t('settings.gamification.wellness_score.score_trend')}</h4>
            <div className="h-32">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10 }}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fontSize: 10 }}
                  />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Detailed Components */}
        {detailed && healthData && (
          <div className="space-y-4">
            {/* Disclaimer */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div className="flex items-start space-x-2">
                <Info className="h-4 w-4 text-blue-500 mt-0.5" />
                <div className="text-sm">
                  <p className="font-medium text-blue-800">{t('settings.gamification.wellness_score.disclaimer.title')}</p>
                  <p className="text-blue-600">
                    {t('settings.gamification.wellness_score.disclaimer.description')}
                  </p>
                </div>
              </div>
            </div>

            <h4 className="text-sm font-medium text-gray-700">{t('settings.gamification.wellness_score.score_components')}</h4>
            <div className="space-y-3">
              {Object.entries(healthData.components || {}).map(([key, value]) => {
                const componentScore = typeof value === 'number' ? value : 0;
                const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

                return (
                  <div key={key} className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">{label}</span>
                      <span className={`font-medium ${getScoreColor(componentScore)}`}>
                        {Math.round(componentScore)}
                      </span>
                    </div>
                    <Progress value={componentScore} className="h-2" />
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Recommendations */}
        {detailed && healthData?.recommendations && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-gray-700">Recommendations</h4>
            <div className="space-y-2">
              {healthData.recommendations.slice(0, 3).map((rec: string, index: number) => (
                <div key={index} className="flex items-start space-x-2 text-sm">
                  <Info className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                  <span className="text-gray-600">{rec}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Quick Tips */}
        {!detailed && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <h4 className="text-sm font-medium text-blue-800 mb-2">{t('settings.gamification.wellness_score.improve_score')}</h4>
            <ul className="text-xs text-blue-700 space-y-1">
              <li>• {t('settings.gamification.wellness_score.tips.daily_expenses')}</li>
              <li>• {t('settings.gamification.wellness_score.tips.weekly_budget')}</li>
              <li>• {t('settings.gamification.wellness_score.tips.invoice_followup')}</li>
              <li>• {t('settings.gamification.wellness_score.tips.receipt_upload')}</li>
            </ul>
          </div>
        )}
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
}