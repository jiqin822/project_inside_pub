import React from 'react';

interface CurrencyDisplayProps {
  amount: number;
  symbol: string;
  showLabel?: boolean;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

export const CurrencyDisplay: React.FC<CurrencyDisplayProps> = ({
  amount,
  symbol,
  showLabel = false,
  className = '',
  size = 'md',
}) => {
  const sizeClasses = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-xl',
  };

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {showLabel && <span className="text-xs font-bold text-slate-700 uppercase">Balance:</span>}
      <span className={`font-black ${sizeClasses[size]}`}>
        {symbol} {amount.toLocaleString()}
      </span>
    </div>
  );
};
