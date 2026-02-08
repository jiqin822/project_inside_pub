import React from 'react';
import { TransactionStatus } from '../types/domain';
import { Check, Clock, X, Package, Archive } from 'lucide-react';

interface TransactionStatusBadgeProps {
  status: TransactionStatus;
  className?: string;
}

const statusConfig: Record<TransactionStatus, { label: string; color: string; icon: React.ReactNode }> = {
  purchased: {
    label: 'Purchased',
    color: 'bg-blue-100 text-blue-800 border-blue-300',
    icon: <Package size={12} />,
  },
  redeemed: {
    label: 'Redeemed',
    color: 'bg-green-100 text-green-800 border-green-300',
    icon: <Check size={12} />,
  },
  accepted: {
    label: 'In Progress',
    color: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    icon: <Clock size={12} />,
  },
  pending_approval: {
    label: 'Pending Approval',
    color: 'bg-orange-100 text-orange-800 border-orange-300',
    icon: <Clock size={12} />,
  },
  approved: {
    label: 'Approved',
    color: 'bg-green-100 text-green-800 border-green-300',
    icon: <Check size={12} />,
  },
  canceled: {
    label: 'Canceled',
    color: 'bg-slate-100 text-slate-800 border-slate-300',
    icon: <X size={12} />,
  },
};

export const TransactionStatusBadge: React.FC<TransactionStatusBadgeProps> = ({
  status,
  className = '',
}) => {
  const config = statusConfig[status];

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-bold uppercase border-2 rounded ${config.color} ${className}`}
    >
      {config.icon}
      {config.label}
    </span>
  );
};
