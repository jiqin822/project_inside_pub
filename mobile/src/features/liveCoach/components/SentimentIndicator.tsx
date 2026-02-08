import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface SentimentIndicatorProps {
  sentiment: string;
  className?: string;
}

export const SentimentIndicator: React.FC<SentimentIndicatorProps> = ({
  sentiment,
  className = '',
}) => {
  const getSentimentConfig = (sentiment: string) => {
    const lower = sentiment.toLowerCase();
    if (lower.includes('positive') || lower.includes('happy') || lower.includes('joy')) {
      return {
        icon: <TrendingUp size={16} className="text-green-600" />,
        bg: 'bg-green-50 border-green-200',
        text: 'text-green-800',
        label: 'Positive',
      };
    }
    if (lower.includes('negative') || lower.includes('sad') || lower.includes('angry')) {
      return {
        icon: <TrendingDown size={16} className="text-red-600" />,
        bg: 'bg-red-50 border-red-200',
        text: 'text-red-800',
        label: 'Negative',
      };
    }
    return {
      icon: <Minus size={16} className="text-slate-600" />,
      bg: 'bg-slate-50 border-slate-200',
      text: 'text-slate-800',
      label: 'Neutral',
    };
  };

  const config = getSentimentConfig(sentiment);

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 border-2 rounded-lg ${config.bg} ${config.text} ${className}`}>
      {config.icon}
      <span className="text-xs font-bold uppercase">{config.label}</span>
    </div>
  );
};
