import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  disabled,
  className = '',
  ...props
}) => {
  const baseClasses = 'font-bold uppercase tracking-widest transition-all border-2';
  
  const variantClasses = {
    primary: 'bg-slate-900 hover:bg-slate-800 text-white border-slate-900',
    secondary: 'bg-white hover:bg-slate-50 text-slate-900 border-slate-900',
    danger: 'bg-red-600 hover:bg-red-500 text-white border-red-800',
    ghost: 'bg-transparent hover:bg-slate-100 text-slate-900 border-transparent',
  };

  const sizeClasses = {
    sm: 'text-[10px] px-3 py-1.5',
    md: 'text-xs px-4 py-2',
    lg: 'text-sm px-6 py-3',
  };

  return (
    <button
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className} ${
        (disabled || isLoading) ? 'opacity-50 cursor-not-allowed' : 'active:translate-y-0.5 active:shadow-none'
      }`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <span className="flex items-center gap-2">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current"></div>
          Loading...
        </span>
      ) : (
        children
      )}
    </button>
  );
};
