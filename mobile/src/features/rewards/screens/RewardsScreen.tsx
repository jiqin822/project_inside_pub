import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { apiService } from '../../../shared/api/apiService';
import { qk } from '../../../shared/api/queryKeys';
import { EconomyConfig, MarketItem, LovedOne, Transaction, TransactionStatus, AddNotificationFn } from '../../../shared/types/domain';
import { Gift, Star, Check, X, Lock, Shield, Settings, Plus, DollarSign, Wallet, ShoppingBag, Trash2, Users, ChevronDown, User, Tag, AlertCircle, Package, Clock, Archive, ArrowLeft, Pencil, RefreshCw, Trophy } from 'lucide-react';
import { RoomHeader } from '../../../shared/ui/RoomHeader';
import { useSessionStore } from '../../../stores/session.store';
import { useRelationshipsStore } from '../../../stores/relationships.store';
import { usePendingVerificationsQuery, useUserMarketQuery } from '../api/rewards.queries';
import { useApproveTaskMutation } from '../api/rewards.mutations';

interface Props {
  onUpdateLovedOne: (id: string, updates: Partial<LovedOne>) => void;
  onUpdateProfile: (user: any) => void;
  onRefreshMarket?: (lovedOneId: string) => Promise<void>;
  onExit: () => void;
  onAddNotification?: AddNotificationFn;
}

const CURRENCY_PRESETS = [
    { name: 'Love Tokens', symbol: '🪙' },
    { name: 'Hearts', symbol: '❤️' },
    { name: 'Stars', symbol: '⭐' },
    { name: 'Flowers', symbol: '🌹' },
    { name: 'Cookies', symbol: '🍪' },
    { name: 'Gems', symbol: '💎' },
];

export const RewardsScreen: React.FC<Props> = ({ onUpdateLovedOne, onUpdateProfile, onRefreshMarket, onExit, onAddNotification }) => {
  const { me: user } = useSessionStore();
  const { relationships } = useRelationshipsStore();
  
  if (!user) {
    return null; // Should not happen, but guard against it
  }
  
  const availableLovedOnes = relationships.length > 0 ? relationships : user.lovedOnes;
  const [selectedLovedOneId, setSelectedLovedOneId] = useState<string | null>(availableLovedOnes.length > 0 ? availableLovedOnes[0].id : null);
  
  // View State
  const [viewMode, setViewMode] = useState<'market' | 'vault'>('market');
  const [marketTab, setMarketTab] = useState<'earn' | 'spend'>('spend');
  const [vaultTab, setVaultTab] = useState<'my-offers' | 'my-requests' | 'trades'>('my-offers');
  
  const [showAddModal, setShowAddModal] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);
  
  const [confirmModal, setConfirmModal] = useState<{ item: MarketItem, action: 'buy' | 'accept' } | null>(null);
  
  // New Item State
  const [newItemTitle, setNewItemTitle] = useState('');
  const [newItemDescription, setNewItemDescription] = useState('');
  const [newItemCost, setNewItemCost] = useState('');
  const [newItemIcon, setNewItemIcon] = useState('🎁');
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  
  // Track expanded descriptions for collapsible UI
  const [expandedDescriptions, setExpandedDescriptions] = useState<Set<string>>(new Set());
  
  // Common emojis for market items
  const commonEmojis = [
    '🎁', '🎉', '🎈', '🎊', '🎂', '🍰', '🍕', '🍔', '🍟', '🍕',
    '🍎', '🍊', '🍋', '🍌', '🍉', '🍇', '🍓', '🍒', '🍑', '🥭',
    '🌹', '🌺', '🌸', '🌻', '🌷', '🌼', '💐', '🌿', '🍀', '🌱',
    '⭐', '🌟', '✨', '💫', '🔥', '💎', '💍', '👑', '🎯', '🎪',
    '🎨', '🎭', '🎬', '🎤', '🎧', '🎮', '🕹️', '🎲', '🧩', '🎸',
    '🚗', '🚕', '🚙', '🚌', '🚎', '🏎️', '🚓', '🚑', '🚒', '🚐',
    '💝', '💖', '💗', '💓', '💞', '💕', '💟', '❣️', '💔', '❤️',
    '🧸', '🎀', '🎁', '🎂', '🎃', '🎄', '🎅', '🤶', '🧑‍🎄', '🎆',
    '☕', '🍵', '🧃', '🥤', '🍺', '🍻', '🥂', '🍷', '🥃', '🍸',
    '🏆', '🥇', '🥈', '🥉', '🏅', '🎖️', '🎗️', '🎫', '🎟️', '🎪'
  ];
  const [newItemCategory, setNewItemCategory] = useState<'earn' | 'spend'>('spend');
  const [selectedLovedOneIds, setSelectedLovedOneIds] = useState<string[]>([]); // Relationship IDs for availability
  const [availableToSelf, setAvailableToSelf] = useState(false); // Whether listing is available to user themselves (unchecked by default)

  // React Query: pending verifications and vault (my) market
  const queryClient = useQueryClient();
  const { data: pendingVerificationsRaw = [], isLoading: loadingVerifications } = usePendingVerificationsQuery();
  const { data: myMarketData, isLoading: loadingMyItems } = useUserMarketQuery(user.id, viewMode === 'vault');
  const approveTaskMutation = useApproveTaskMutation();

  const pendingVerifications = useMemo(() => {
    const raw = pendingVerificationsRaw as Array<{
      id: string;
      holder_id: string;
      holder_name?: string;
      metadata?: any;
      [k: string]: unknown;
    }>;
    return raw.map((tx) => {
      const holder = availableLovedOnes.find((lo) => lo.id === tx.holder_id);
      return {
        ...tx,
        holderName: holder?.name ?? tx.holder_name ?? 'Unknown',
        holderId: tx.holder_id,
        itemTitle: tx.metadata?.title ?? 'Unknown Item',
        itemIcon: tx.metadata?.icon ?? '🎁',
      };
    });
  }, [pendingVerificationsRaw, availableLovedOnes]);

  const myMarketItems: MarketItem[] = useMemo(() => {
    if (!myMarketData || typeof myMarketData !== 'object' || !Array.isArray((myMarketData as any).items)) return [];
    const items = (myMarketData as { items: any[] }).items;
    return items
      .filter((item: any) => item.is_active)
      .map((item: any) => ({
        id: item.id,
        title: item.title,
        description: item.description,
        cost: item.cost,
        icon: item.icon ?? '🎁',
        type: (item.category === 'SPEND' ? 'product' : 'quest') as 'service' | 'product' | 'quest',
        category: (item.category === 'SPEND' ? 'spend' : 'earn') as 'earn' | 'spend',
        visibleToRelationshipIds: item.visible_to_relationship_ids,
      }));
  }, [myMarketData]);

  // Derived state for the MAIN selection (used for Market view)
  const selectedLovedOne = availableLovedOnes.find(l => l.id === selectedLovedOneId);
  
  // Track last fetched loved one ID to prevent repeated fetches
  const lastFetchedLovedOneId = useRef<string | null>(null);
  
  // Ref for emoji picker to handle click outside
  const emojiPickerRef = useRef<HTMLDivElement>(null);
  
  // Close emoji picker when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (emojiPickerRef.current && !emojiPickerRef.current.contains(event.target as Node)) {
        setShowEmojiPicker(false);
      }
    };
    
    if (showEmojiPicker) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showEmojiPicker]);

  useEffect(() => {
      // Auto-select first if current selection invalid
      if (!selectedLovedOne && availableLovedOnes.length > 0) {
          setSelectedLovedOneId(availableLovedOnes[0].id);
      }
  }, [availableLovedOnes, selectedLovedOne]);

  // Refresh market data when component mounts or when switching loved ones
  useEffect(() => {
    if (onRefreshMarket && selectedLovedOneId && selectedLovedOneId !== lastFetchedLovedOneId.current) {
      const lovedOne = availableLovedOnes.find(l => l.id === selectedLovedOneId);
      if (lovedOne && !lovedOne.isPending) {
        lastFetchedLovedOneId.current = selectedLovedOneId;
        onRefreshMarket(selectedLovedOneId).catch(err => {
          console.warn('Failed to refresh market data:', err);
          // Reset on error so we can retry
          lastFetchedLovedOneId.current = null;
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedLovedOneId]); // Only refresh when selectedLovedOneId changes

  const handleApproveVerification = async (transactionId: string) => {
    try {
      await approveTaskMutation.mutateAsync(transactionId);
      if (selectedLovedOneId) {
        onRefreshMarket?.(selectedLovedOneId);
      }
      onAddNotification?.('reward', 'Bounty Approved', 'Currency transfer confirmed.');
    } catch (error: any) {
      alert(`Failed to approve verification: ${error.message || 'Unknown error'}`);
    }
  };

  const handleRefreshTrades = async () => {
    await queryClient.invalidateQueries({ queryKey: qk.pendingVerifications() });
    if (onRefreshMarket) {
      for (const lovedOne of availableLovedOnes) {
        await onRefreshMarket(lovedOne.id);
      }
    }
  };

  // --- Transactions Logic ---

  const initiateTransaction = (item: MarketItem) => {
      if (!selectedLovedOne) return;
      const balance = selectedLovedOne.balance || 0;
      
      if (item.category === 'spend') {
          // Check balance
          if (balance < item.cost) {
              alert("Insufficient funds for this item.");
              return;
          }
          setConfirmModal({ item, action: 'buy' });
      } else {
          // Check if already active
          const active = selectedLovedOne.transactions?.find(t => t.itemId === item.id && (t.status === 'accepted' || t.status === 'pending_approval'));
          if (active) {
              alert("You already have this quest active in your Vault.");
              return;
          }
          setConfirmModal({ item, action: 'accept' });
      }
  };

  const executeTransaction = async () => {
      if (!confirmModal || !selectedLovedOne || !selectedLovedOne.economy) return;
      
      const { item, action } = confirmModal;
      const currentBalance = selectedLovedOne.balance || 0;
      const currentTransactions = selectedLovedOne.transactions || [];

      if (action === 'buy') {
          // Purchase flow - call backend API
          try {
              const response = await apiService.purchaseItem(item.id, selectedLovedOne.id);
              const backendTx = response.data as {
                  id: string;
                  wallet_id: string;
                  market_item_id?: string;
                  category: string;
                  amount: number;
                  status: string;
                  metadata?: any;
                  created_at: string;
              };
              
              const newTx: Transaction = {
                  id: backendTx.id, // Use backend transaction ID
                  itemId: item.id,
                  title: item.title,
                  cost: item.cost,
                  icon: item.icon,
                  category: item.category,
                  status: 'purchased',
                  timestamp: Date.now()
              };
              
              // Deduct cost immediately for purchases
              onUpdateLovedOne(selectedLovedOne.id, { 
                  balance: currentBalance - item.cost,
                  transactions: [...currentTransactions, newTx]
              });
              onAddNotification?.('system', 'Purchase Complete', `${item.title} added to your vault.`);
          } catch (error: any) {
              alert(`Failed to purchase item: ${error.message || 'Unknown error'}`);
              return;
          }
      } else {
          // Accept task flow - call backend API
          try {
              const response = await apiService.acceptTask(item.id, selectedLovedOne.id);
              const backendTx = response.data as {
                  id: string;
                  wallet_id: string;
                  market_item_id?: string;
                  category: string;
                  amount: number;
                  status: string;
                  metadata?: any;
                  created_at: string;
              };
              
              const newTx: Transaction = {
                  id: backendTx.id, // Use backend transaction ID
                  itemId: item.id,
                  title: item.title,
                  cost: item.cost,
                  icon: item.icon,
                  category: item.category,
                  status: 'accepted',
                  timestamp: Date.now()
              };
              
              // Don't award money yet for accepting quests
              onUpdateLovedOne(selectedLovedOne.id, { 
                  transactions: [...currentTransactions, newTx]
              });
              onAddNotification?.('system', 'Quest Started', `"${item.title}" is now in your Vault.`);
          } catch (error: any) {
              alert(`Failed to accept task: ${error.message || 'Unknown error'}`);
              return;
          }
      }
      setConfirmModal(null);
  };

  // --- Vault Actions ---

  const updateTransactionStatus = (lovedOneId: string, txId: string, newStatus: TransactionStatus) => {
      const targetLovedOne = availableLovedOnes.find(l => l.id === lovedOneId);
      if (!targetLovedOne) return;

      const transactions = targetLovedOne.transactions || [];
      const tx = transactions.find(t => t.id === txId);
      if (!tx) return;

      // Handle Balance updates for completion
      let newBalance = targetLovedOne.balance || 0;
      
      // If a bounty is APPROVED, user gets paid
      if (newStatus === 'approved' && tx.status !== 'approved') {
          newBalance += tx.cost;
      }

      const updatedTransactions = transactions.map(t => 
          t.id === txId ? { ...t, status: newStatus } : t
      );

      onUpdateLovedOne(lovedOneId, {
          balance: newBalance,
          transactions: updatedTransactions
      });
  };

  // --- Listing Management ---

  const handleAddItem = async () => {
    if (!newItemTitle || !newItemCost) return;
    
    // If in vault mode, add to user's own market items
    if (viewMode === 'vault') {
      try {
        // Convert loved one IDs to relationship IDs
        // If all loved ones are selected (default), send undefined (available to all)
        // If only some are selected, send those relationship IDs
        const allLovedOneIds = availableLovedOnes.filter(lo => !lo.isPending).map(lo => lo.id);
        const allSelected = allLovedOneIds.length > 0 && 
          allLovedOneIds.length === selectedLovedOneIds.length &&
          allLovedOneIds.every(id => selectedLovedOneIds.includes(id));
        
        let relationshipIds: string[] | undefined;
        
        if (!allSelected && selectedLovedOneIds.length > 0) {
          // Only some loved ones selected - restrict availability
          relationshipIds = selectedLovedOneIds.map(loId => {
            const lovedOne = availableLovedOnes.find(lo => lo.id === loId);
            return lovedOne?.relationshipId;
          }).filter((id): id is string => id !== undefined);
          
          // If no valid relationship IDs found, default to all (undefined)
          if (relationshipIds.length === 0) {
            relationshipIds = undefined;
          }
        }
        // If all are selected or none selected, relationshipIds stays undefined (available to all)
        
        await apiService.createMarketItem({
          title: newItemTitle,
          description: newItemDescription.trim() || undefined,
          cost: parseInt(newItemCost),
          icon: newItemIcon,
          category: newItemCategory === 'spend' ? 'SPEND' : 'EARN',
          relationship_ids: relationshipIds,
        });
        // Reload user's market items
        await queryClient.invalidateQueries({ queryKey: qk.userMarket(user.id) });
        setNewItemTitle('');
        setNewItemDescription('');
        setNewItemCost('');
        setNewItemIcon('🎁');
        setSelectedLovedOneIds([]);
        setAvailableToSelf(false);
        setShowEmojiPicker(false);
        setShowAddModal(false);
      } catch (error: any) {
        alert(`Failed to create listing: ${error.message || 'Unknown error'}`);
      }
    } else {
      // Legacy: add to selected loved one's market items (for market view)
      if (!selectedLovedOne) return;
      
      const newItem: MarketItem = {
        id: Date.now().toString(),
        title: newItemTitle,
        description: newItemDescription.trim() || undefined,
        cost: parseInt(newItemCost),
        icon: newItemIcon,
        type: 'service',
        category: newItemCategory
      };

      const currentItems = selectedLovedOne.marketItems || [];
      onUpdateLovedOne(selectedLovedOne.id, { marketItems: [...currentItems, newItem] });

      setNewItemTitle('');
      setNewItemDescription('');
      setNewItemCost('');
      setNewItemIcon('🎁');
      setShowAddModal(false);
    }
  };

  const handleDeleteMyItem = async (itemId: string) => {
    try {
      await apiService.deleteMarketItem(itemId);
      // Reload user's market items
      await queryClient.invalidateQueries({ queryKey: qk.userMarket(user.id) });
    } catch (error: any) {
      alert(`Failed to delete listing: ${error.message || 'Unknown error'}`);
    }
  };

  const handleUpdateUserEconomy = (newConfig: EconomyConfig) => {
      // Update local state only (for immediate UI feedback)
      const updatedUser = { ...user, economy: newConfig };
      onUpdateProfile(updatedUser);
  };
  
  const handleSaveEconomySettings = async () => {
      try {
        // Save to backend
        await apiService.updateEconomySettings(userEconomy.currencyName, userEconomy.currencySymbol);
        // Close modal
        setShowConfigModal(false);
      } catch (error: any) {
        alert(`Failed to save economy settings: ${error.message || 'Unknown error'}`);
      }
  };

  const openAddModal = () => {
    if (viewMode === 'vault') {
      // Lock category based on vault tab - cannot be changed
      if (vaultTab === 'my-offers') {
        setNewItemCategory('spend'); // SPEND items = things I offer
      } else if (vaultTab === 'my-requests') {
        setNewItemCategory('earn'); // EARN items = things I want/accept
      }
      // By default, select all loved ones (since listings are available to all by default)
      const allLovedOneIds = user.lovedOnes
        .filter(lo => !lo.isPending)
        .map(lo => lo.id);
      setSelectedLovedOneIds(allLovedOneIds);
      // User's own checkbox is unchecked by default
      setAvailableToSelf(false);
    } else {
      setNewItemCategory(marketTab === 'earn' ? 'earn' : 'spend');
    }
    setShowAddModal(true);
  };
  
  const toggleLovedOneSelection = (lovedOneId: string) => {
    setSelectedLovedOneIds(prev => 
      prev.includes(lovedOneId)
        ? prev.filter(id => id !== lovedOneId)
        : [...prev, lovedOneId]
    );
  };
  
  // Determine if category selector should be disabled (locked based on vault tab)
  const isCategoryLocked = viewMode === 'vault' && vaultTab !== 'trades';

  if (!selectedLovedOne) {
       return (
            <div className="h-full flex flex-col bg-slate-50 items-center justify-center p-8 text-center font-sans safe-area">
                 <ShoppingBag size={48} className="text-slate-300 mb-4" />
                 <h2 className="text-xl font-black text-slate-900 uppercase">Market Closed</h2>
                 <p className="text-slate-500 font-mono text-sm mt-2">No active relationship nodes found.</p>
                 <button onClick={onExit} className="mt-6 px-6 py-3 bg-slate-900 text-white font-bold uppercase text-xs tracking-widest">Return to Dashboard</button>
            </div>
       );
  }

  // Use the selected loved one's economy for displaying costs/rewards in Market
  const currentContextEconomy = selectedLovedOne.economy || { currencyName: 'Tokens', currencySymbol: '🪙' };
  const balance = selectedLovedOne.balance || 0;
  const items = selectedLovedOne.marketItems || [];
  
  // Aggregate transactions from ALL loved ones for the global vault view
  const allTransactions = user.lovedOnes.flatMap(lo => 
      (lo.transactions || []).map(t => ({ 
          ...t, 
          lovedOneId: lo.id, 
          lovedOneName: lo.name,
          currencySymbol: lo.economy?.currencySymbol || '🪙'
      }))
  );

  // Filter transactions for the selected loved one (for logic checks in market view)
  const currentLovedOneTransactions = selectedLovedOne.transactions || [];

  // User's own economy (for editing)
  const userEconomy = user.economy || { currencyName: 'Love Tokens', currencySymbol: '🪙' };

  return (
    <div className="h-screen flex flex-col bg-slate-50 overflow-hidden font-sans relative" style={{ height: '100vh', width: '100vw' }}>
        {/* Background Grid */}
        <div className="fixed inset-0 z-0 pointer-events-none opacity-20" 
            style={{ 
                backgroundImage: 'linear-gradient(#1e293b 1px, transparent 1px), linear-gradient(90deg, #1e293b 1px, transparent 1px)', 
                backgroundSize: '20px 20px',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0
            }}>
        </div>

        <RoomHeader
          moduleTitle="MODULE: SERVICE OF CARE"
          moduleIcon={<Gift size={12} />}
          title="Service of Care"
          subtitle={{ text: 'ECONOMY OF CARE', colorClass: 'text-yellow-600' }}
          onClose={onExit}
          headerRight={
            <button
              onClick={() => setViewMode(viewMode === 'vault' ? 'market' : 'vault')}
              className={`flex items-center gap-2 px-3 py-1.5 text-[10px] font-bold uppercase border-2 transition-colors ${
                viewMode === 'vault'
                  ? 'bg-slate-900 text-white border-slate-900'
                  : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'
              }`}
            >
              <Package size={14} /> {viewMode === 'vault' ? 'Back' : 'My Vault'}
            </button>
          }
        />

        {/* Sub-Header (Dark) - Tabs to switch between loved ones */}
        {viewMode !== 'vault' && availableLovedOnes.length > 0 && (
            <div className="bg-slate-900 bg-opacity-100 text-white p-2 flex gap-2 z-10 overflow-x-auto">
                {availableLovedOnes.map((lo) => {
                    const isActive = selectedLovedOneId === lo.id;
                    return (
                        <button
                            key={lo.id}
                            onClick={() => setSelectedLovedOneId(lo.id)}
                            className={`shrink-0 px-4 py-2 text-[10px] font-bold uppercase tracking-widest transition-all border-2 ${
                                isActive
                                    ? 'bg-white text-slate-900 border-white shadow-[2px_2px_0px_rgba(0,0,0,0.2)]'
                                    : 'bg-slate-800 text-slate-300 border-slate-700 hover:border-slate-500 hover:text-white'
                            }`}
                        >
                            {lo.name}
                        </button>
                    );
                })}
            </div>
        )}
        
        {/* Balance Card (Visible in Market Mode) */}
        {viewMode === 'market' && (
            <div className="p-4 relative z-10 pb-0">
                <div className="bg-slate-900 text-white p-6 border-4 border-slate-900 shadow-[8px_8px_0px_rgba(0,0,0,0.2)] relative overflow-hidden group">
                    {/* Hatch Pattern */}
                    <div className="absolute inset-0 opacity-10" style={{ backgroundImage: 'repeating-linear-gradient(45deg, #fff 0, #fff 1px, transparent 0, transparent 10px)' }}></div>
                    
                    <div className="relative z-10 flex justify-between items-end">
                        <div>
                            <p className="text-slate-400 text-[10px] font-mono font-bold uppercase tracking-widest mb-1 border-b border-slate-600 pb-1 inline-block">My Balance</p>
                            <p className="text-5xl font-mono font-bold text-white tracking-tighter mt-2">{balance} <span className="text-lg text-slate-500">{currentContextEconomy.currencyName}</span></p>
                        </div>
                        <div className="text-4xl">{currentContextEconomy.currencySymbol}</div>
                    </div>
                </div>
            </div>
        )}

        {/* Navigation Tabs (Only in Market Mode) */}
        {viewMode === 'market' && (
             <div className="px-4 mt-6">
                <div className="flex border-b-2 border-slate-200 bg-white">
                    <button 
                        onClick={() => setMarketTab('spend')}
                        className={`flex-1 py-3 text-xs font-bold uppercase tracking-widest flex items-center justify-center gap-2 border-b-4 ${
                            marketTab === 'spend' ? 'border-slate-900 text-slate-900 bg-slate-50' : 'border-transparent text-slate-400 hover:text-slate-600'
                        }`}
                    >
                        <Tag size={14} /> Voucher
                    </button>
                    <button 
                        onClick={() => setMarketTab('earn')}
                        className={`flex-1 py-3 text-xs font-bold uppercase tracking-widest flex items-center justify-center gap-2 border-b-4 ${
                            marketTab === 'earn' ? 'border-emerald-600 text-emerald-700 bg-emerald-50' : 'border-transparent text-slate-400 hover:text-slate-600'
                        }`}
                    >
                        <Trophy size={14} /> Bounty
                    </button>
                </div>
            </div>
        )}

        {/* === VAULT VIEW === */}
        {viewMode === 'vault' && (
            <div className="flex-1 flex flex-col overflow-hidden relative z-10" style={{ minHeight: 0 }}>
                {/* Vault Header / Actions */}
                <div className="flex justify-between items-center p-4 pb-2">
                     <div>
                         <h2 className="text-xl font-black text-slate-900 uppercase">My Vault</h2>
                         <p className="text-[10px] font-mono text-slate-500">MANAGE MY LISTINGS & TRADES</p>
                     </div>
                     <button 
                        onClick={() => setShowConfigModal(true)}
                        className="bg-white border-2 border-slate-900 text-slate-900 px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest hover:bg-slate-50 flex items-center gap-2"
                     >
                        <span className="text-base">{userEconomy.currencySymbol}</span> My Love Currency
                     </button>
                </div>

                {/* Vault Tabs */}
                <div className="px-4 border-b-2 border-slate-200 bg-white">
                    <div className="flex">
                        <button 
                            onClick={() => setVaultTab('my-offers')}
                            className={`flex-1 py-3 text-xs font-bold uppercase tracking-widest flex items-center justify-center gap-2 border-b-4 ${
                                vaultTab === 'my-offers' ? 'border-slate-900 text-slate-900 bg-slate-50' : 'border-transparent text-slate-400 hover:text-slate-600'
                            }`}
                        >
                            <Tag size={14} /> Issue Voucher
                        </button>
                        <button 
                            onClick={() => setVaultTab('my-requests')}
                            className={`flex-1 py-3 text-xs font-bold uppercase tracking-widest flex items-center justify-center gap-2 border-b-4 ${
                                vaultTab === 'my-requests' ? 'border-emerald-600 text-emerald-700 bg-emerald-50' : 'border-transparent text-slate-400 hover:text-slate-600'
                            }`}
                        >
                            <Trophy size={14} /> Post Bounty
                        </button>
                        <div className="flex-1 flex items-center justify-center relative">
                            <button 
                                onClick={() => setVaultTab('trades')}
                                className={`w-full py-3 text-xs font-bold uppercase tracking-widest flex items-center justify-center gap-2 border-b-4 ${
                                    vaultTab === 'trades' ? 'border-indigo-600 text-indigo-700 bg-indigo-50' : 'border-transparent text-slate-400 hover:text-slate-600'
                                }`}
                            >
                                <Package size={14} /> Trades
                            </button>
                            {vaultTab === 'trades' && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleRefreshTrades();
                                    }}
                                    className="absolute right-2 p-1 hover:bg-indigo-100 rounded transition-colors"
                                    title="Refresh trades"
                                >
                                    <RefreshCw size={12} className="text-indigo-600" />
                                </button>
                            )}
                        </div>
                    </div>
                </div>

                {/* Tab Content */}
                <div className="flex-1 overflow-hidden p-4 space-y-6" style={{ minHeight: 0, overflowY: 'auto' }}>
                    {/* Tab 1: My Offers (SPEND items - things I offer to others who hold my currency) */}
                    {vaultTab === 'my-offers' && (
                        <div className="space-y-4">
                            <div className="flex justify-between items-center">
                                <div>
                                    <h3 className="text-sm font-black text-slate-900 uppercase">My Offers</h3>
                                    <p className="text-[10px] font-mono text-slate-500">Services/products I offer to others who hold my {userEconomy.currencyName}</p>
                                </div>
                                <button 
                                    onClick={openAddModal}
                                    className="bg-slate-900 text-white px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest flex items-center gap-1 hover:bg-slate-700 transition-colors"
                                >
                                    <Plus size={12} /> Add Listing
                                </button>
                            </div>
                            
                            {loadingMyItems ? (
                                <p className="text-[10px] font-mono text-slate-400 italic">Loading...</p>
                            ) : myMarketItems.filter(item => item.category === 'spend').length === 0 ? (
                                <p className="text-[10px] font-mono text-slate-400 italic">No offers yet. Click "Add Listing" to create one.</p>
                            ) : (
                                <div className="space-y-3">
                                    {myMarketItems.filter(item => item.category === 'spend').map(item => {
                                        // Get names of loved ones who can see this item
                                        const availableToNames = item.visibleToRelationshipIds && item.visibleToRelationshipIds.length > 0
                                            ? item.visibleToRelationshipIds.map(relId => {
                                                const lo = availableLovedOnes.find(l => l.relationshipId === relId);
                                                return lo?.name;
                                              }).filter((name): name is string => name !== undefined)
                                            : null; // null means available to all
                                        
                                        return (
                                            <div key={item.id} className="bg-white border-2 border-slate-900 p-4 shadow-sm relative overflow-hidden">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-3 flex-1">
                                                        <div className="text-2xl w-10 h-10 flex items-center justify-center bg-slate-100 border border-slate-200">{item.icon}</div>
                                                        <div className="flex-1">
                                                            <h4 className="font-bold text-sm uppercase text-slate-900">{item.title}</h4>
                                                            {item.description && (
                                                                <div className="mt-1">
                                                                    {expandedDescriptions.has(item.id) ? (
                                                                        <div>
                                                                            <p className="text-[10px] text-slate-600 leading-relaxed">{item.description}</p>
                                                                            <button
                                                                                onClick={(e) => {
                                                                                    e.stopPropagation();
                                                                                    setExpandedDescriptions(prev => {
                                                                                        const next = new Set(prev);
                                                                                        next.delete(item.id);
                                                                                        return next;
                                                                                    });
                                                                                }}
                                                                                className="text-[9px] text-slate-500 hover:text-slate-700 mt-1 font-mono uppercase"
                                                                            >
                                                                                Show Less
                                                                            </button>
                                                                        </div>
                                                                    ) : (
                                                                        <button
                                                                            onClick={(e) => {
                                                                                e.stopPropagation();
                                                                                setExpandedDescriptions(prev => new Set(prev).add(item.id));
                                                                            }}
                                                                            className="text-[9px] text-slate-500 hover:text-slate-700 font-mono uppercase flex items-center gap-1"
                                                                        >
                                                                            <ChevronDown size={10} /> Show Description
                                                                        </button>
                                                                    )}
                                                                </div>
                                                            )}
                                                            <p className="text-[10px] font-mono text-slate-500 mt-1">
                                                                Price: {item.cost} {userEconomy.currencySymbol}
                                                            </p>
                                                            {availableToNames ? (
                                                                <p className="text-[9px] text-slate-400 mt-1 italic">
                                                                    Available to: {availableToNames.join(', ')}
                                                                </p>
                                                            ) : (
                                                                <p className="text-[9px] text-slate-400 mt-1 italic">
                                                                    Available to: All
                                                                </p>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <button 
                                                        onClick={() => handleDeleteMyItem(item.id)}
                                                        className="bg-red-50 text-red-600 border border-red-200 px-3 py-1.5 text-[10px] font-bold uppercase hover:bg-red-100 transition-colors flex items-center gap-1"
                                                    >
                                                        <Trash2 size={12} /> Delete
                                                    </button>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Tab 2: My Requests (EARN items - things I request from others who want to earn my currency) */}
                    {vaultTab === 'my-requests' && (
                        <div className="space-y-4">
                            <div className="flex justify-between items-center">
                                <div>
                                    <h3 className="text-sm font-black text-slate-900 uppercase">My Requests</h3>
                                    <p className="text-[10px] font-mono text-slate-500">Services/products I request from others who want to earn my {userEconomy.currencyName}</p>
                                </div>
                                <button 
                                    onClick={openAddModal}
                                    className="bg-emerald-600 text-white px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest flex items-center gap-1 hover:bg-emerald-500 transition-colors"
                                >
                                    <Plus size={12} /> Add Listing
                                </button>
                            </div>
                            
                            {loadingMyItems ? (
                                <p className="text-[10px] font-mono text-slate-400 italic">Loading...</p>
                            ) : myMarketItems.filter(item => item.category === 'earn').length === 0 ? (
                                <p className="text-[10px] font-mono text-slate-400 italic">No requests yet. Click "Add Listing" to create one.</p>
                            ) : (
                                <div className="space-y-3">
                                    {myMarketItems.filter(item => item.category === 'earn').map(item => {
                                        // Get names of loved ones who can see this item
                                        const availableToNames = item.visibleToRelationshipIds && item.visibleToRelationshipIds.length > 0
                                            ? item.visibleToRelationshipIds.map(relId => {
                                                const lo = availableLovedOnes.find(l => l.relationshipId === relId);
                                                return lo?.name;
                                              }).filter((name): name is string => name !== undefined)
                                            : null; // null means available to all
                                        
                                        return (
                                            <div key={item.id} className="bg-emerald-50 border-2 border-emerald-600 p-4 shadow-sm relative overflow-hidden">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-3 flex-1">
                                                        <div className="text-2xl w-10 h-10 flex items-center justify-center bg-white border border-emerald-200">{item.icon}</div>
                                                        <div className="flex-1">
                                                            <h4 className="font-bold text-sm uppercase text-emerald-900">{item.title}</h4>
                                                            {item.description && (
                                                                <div className="mt-1">
                                                                    {expandedDescriptions.has(item.id) ? (
                                                                        <div>
                                                                            <p className="text-[10px] text-emerald-700 leading-relaxed">{item.description}</p>
                                                                            <button
                                                                                onClick={(e) => {
                                                                                    e.stopPropagation();
                                                                                    setExpandedDescriptions(prev => {
                                                                                        const next = new Set(prev);
                                                                                        next.delete(item.id);
                                                                                        return next;
                                                                                    });
                                                                                }}
                                                                                className="text-[9px] text-emerald-600 hover:text-emerald-800 mt-1 font-mono uppercase"
                                                                            >
                                                                                Show Less
                                                                            </button>
                                                                        </div>
                                                                    ) : (
                                                                        <button
                                                                            onClick={(e) => {
                                                                                e.stopPropagation();
                                                                                setExpandedDescriptions(prev => new Set(prev).add(item.id));
                                                                            }}
                                                                            className="text-[9px] text-emerald-600 hover:text-emerald-800 font-mono uppercase flex items-center gap-1"
                                                                        >
                                                                            <ChevronDown size={10} /> Show Description
                                                                        </button>
                                                                    )}
                                                                </div>
                                                            )}
                                                            <p className="text-[10px] font-mono text-emerald-600 mt-1">
                                                                Reward: {item.cost} {userEconomy.currencySymbol}
                                                            </p>
                                                            {availableToNames ? (
                                                                <p className="text-[9px] text-emerald-600 mt-1 italic">
                                                                    Available to: {availableToNames.join(', ')}
                                                                </p>
                                                            ) : (
                                                                <p className="text-[9px] text-emerald-600 mt-1 italic">
                                                                    Available to: All
                                                                </p>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <button 
                                                        onClick={() => handleDeleteMyItem(item.id)}
                                                        className="bg-red-50 text-red-600 border border-red-200 px-3 py-1.5 text-[10px] font-bold uppercase hover:bg-red-100 transition-colors flex items-center gap-1"
                                                    >
                                                        <Trash2 size={12} /> Delete
                                                    </button>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Tab 3: Trades (Transactions with loved ones) */}
                    {vaultTab === 'trades' && (
                        <div className="space-y-6">
                            {/* My Wallet Section */}
                            <div>
                                <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-2 flex items-center gap-2">
                                    <Wallet size={14} /> My Wallet
                                </h3>
                                <div className="grid grid-cols-1 gap-2">
                                    {availableLovedOnes.map(lo => (
                                        <div key={lo.id} className="bg-slate-900 text-white p-3 flex justify-between items-center shadow-sm relative overflow-hidden group">
                                            <div className="absolute inset-0 opacity-10" style={{ backgroundImage: 'repeating-linear-gradient(45deg, #fff 0, #fff 1px, transparent 0, transparent 10px)' }}></div>
                                            <div className="flex items-center gap-4 relative z-10">
                                                <div className="w-10 h-10 flex items-center justify-center text-2xl bg-white/10 rounded-full border border-white/20">
                                                    {lo.economy?.currencySymbol || '🪙'}
                                                </div>
                                                <div>
                                                    <div className="text-xl font-bold font-mono leading-none">{lo.balance || 0}</div>
                                                    <div className="text-[9px] text-slate-400 uppercase tracking-widest mt-1">
                                                        {lo.economy?.currencyName || 'Tokens'} <span className="text-slate-600 mx-1">•</span> {lo.name}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="text-[9px] font-mono text-slate-500 relative z-10">
                                                READ ONLY
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Verification Requests (For Issuer) */}
                            <div className="space-y-3">
                                <h3 className="text-xs font-bold uppercase tracking-widest text-amber-600 border-b border-amber-100 pb-2 flex items-center gap-2">
                                    <Clock size={14} /> Verification Requests
                                </h3>
                                
                                {loadingVerifications ? (
                                    <p className="text-[10px] font-mono text-slate-400 italic">Loading...</p>
                                ) : pendingVerifications.length === 0 ? (
                                    <p className="text-[10px] font-mono text-slate-400 italic">No pending verification requests.</p>
                                ) : (
                                    pendingVerifications.map((verification) => {
                                        // Find the loved one (holder) for this verification
                                        const holder = availableLovedOnes.find(lo => lo.id === verification.holderId);
                                        
                                        return (
                                            <div key={verification.id} className="bg-amber-50 border-2 border-amber-400 p-4 shadow-sm relative overflow-hidden">
                                                <div className="absolute top-0 right-0 bg-amber-100 px-2 py-0.5 text-[9px] font-bold uppercase text-amber-700 border-l border-b border-amber-200">
                                                    From: {verification.holderName}
                                                </div>
                                                <div className="flex items-center justify-between mt-2">
                                                    <div className="flex items-center gap-3 flex-1">
                                                        <div className="text-2xl w-10 h-10 flex items-center justify-center bg-white border border-amber-200">
                                                            {verification.itemIcon}
                                                        </div>
                                                        <div className="flex-1">
                                                            <h4 className="font-bold text-sm uppercase text-amber-900">{verification.itemTitle}</h4>
                                                            <p className="text-[10px] font-mono text-amber-700 mt-1">
                                                                Reward: {verification.amount} {userEconomy.currencySymbol}
                                                            </p>
                                                            <p className="text-[9px] text-amber-600 mt-1 italic">
                                                                Waiting for your confirmation
                                                            </p>
                                                        </div>
                                                    </div>
                                                    <div className="flex flex-col gap-2">
                                                        <button
                                                            onClick={() => handleApproveVerification(verification.id)}
                                                            className="bg-emerald-600 text-white text-[10px] font-bold uppercase px-3 py-2 hover:bg-emerald-500 transition-colors shadow-sm flex items-center justify-center gap-1"
                                                        >
                                                            <Check size={12} /> Confirm
                                                        </button>
                                                        <button
                                                            onClick={async () => {
                                                                try {
                                                                    await apiService.cancelTransaction(verification.id);
                                                                    await queryClient.invalidateQueries({ queryKey: qk.pendingVerifications() });
                                                                } catch (error: any) {
                                                                    alert(`Failed to cancel: ${error.message || 'Unknown error'}`);
                                                                }
                                                            }}
                                                            className="bg-red-50 text-red-600 border border-red-200 text-[9px] font-bold uppercase px-2 py-1 hover:bg-red-100 transition-colors"
                                                        >
                                                            Cancel
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })
                                )}
                            </div>

                            {/* Purchased Items (Ready to use) */}
                            <div className="space-y-3">
                                <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500 border-b border-slate-200 pb-2 flex items-center gap-2">
                                    <ShoppingBag size={14} /> Inventory (Purchased)
                                </h3>
                                
                                {allTransactions.filter(t => t.category === 'spend' && t.status === 'purchased').length === 0 && (
                                    <p className="text-[10px] font-mono text-slate-400 italic">No purchased items available.</p>
                                )}

                                {allTransactions.filter(t => t.category === 'spend' && t.status === 'purchased').map(t => (
                                     <div key={t.id} className="bg-white border-2 border-slate-900 p-4 shadow-sm relative overflow-hidden">
                                         <div className="absolute top-0 right-0 bg-slate-200 px-2 py-0.5 text-[9px] font-bold uppercase text-slate-600 border-l border-b border-slate-300">
                                             From: {t.lovedOneName}
                                         </div>
                                         <div className="flex items-center justify-between mt-2">
                                            <div className="flex items-center gap-3">
                                                <div className="text-2xl w-10 h-10 flex items-center justify-center bg-slate-100 border border-slate-200">{t.icon}</div>
                                                <div>
                                                    <h4 className="font-bold text-sm uppercase text-slate-900">{t.title}</h4>
                                                    <p className="text-[10px] font-mono text-slate-500">Purchased</p>
                                                </div>
                                            </div>
                                            <button 
                                                onClick={() => updateTransactionStatus(t.lovedOneId, t.id, 'redeemed')}
                                                className="bg-slate-900 text-white text-[10px] font-bold uppercase px-3 py-2 hover:bg-slate-700 transition-colors"
                                            >
                                                Redeem / Use
                                            </button>
                                        </div>
                                     </div>
                                ))}
                            </div>

                            {/* Active Quests (Accepted) */}
                            <div className="space-y-3 pt-4">
                                <h3 className="text-xs font-bold uppercase tracking-widest text-emerald-600 border-b border-emerald-100 pb-2 flex items-center gap-2">
                                    <Star size={14} /> Active Quests
                                </h3>

                                {allTransactions.filter(t => t.category === 'earn' && t.status === 'accepted').length === 0 && (
                                    <p className="text-[10px] font-mono text-slate-400 italic">No active quests.</p>
                                )}

                                {allTransactions.filter(t => t.category === 'earn' && t.status === 'accepted').map(t => (
                                    <div key={t.id} className="bg-emerald-50 border-2 border-emerald-600 p-4 shadow-sm relative overflow-hidden">
                                        <div className="absolute top-0 right-0 bg-emerald-100 px-2 py-0.5 text-[9px] font-bold uppercase text-emerald-700 border-l border-b border-emerald-200">
                                             For: {t.lovedOneName}
                                         </div>
                                        <div className="flex items-center justify-between mb-3 mt-2">
                                            <div className="flex items-center gap-3">
                                                <div className="text-2xl w-10 h-10 flex items-center justify-center bg-white border border-emerald-200">{t.icon}</div>
                                                <div>
                                                    <h4 className="font-bold text-sm uppercase text-emerald-900">{t.title}</h4>
                                                    <p className="text-[10px] font-mono text-emerald-600">Reward: {t.cost} {t.currencySymbol}</p>
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex gap-2">
                                            <button 
                                                onClick={() => updateTransactionStatus(t.lovedOneId, t.id, 'canceled')}
                                                className="flex-1 bg-white text-emerald-700 border border-emerald-200 text-[10px] font-bold uppercase px-3 py-2 hover:bg-red-50 hover:text-red-600 hover:border-red-200 transition-colors"
                                            >
                                                Cancel
                                            </button>
                                            <button 
                                                onClick={async () => {
                                                    try {
                                                        // Call backend API to submit for review
                                                        await apiService.submitForReview(t.id);
                                                        // Update local state
                                                        updateTransactionStatus(t.lovedOneId, t.id, 'pending_approval');
                                                        // Refresh verification requests for the issuer (if they're viewing)
                                                        if (viewMode === 'vault' && vaultTab === 'trades') {
                                                            await queryClient.invalidateQueries({ queryKey: qk.pendingVerifications() });
                                                        }
                                                    } catch (error: any) {
                                                        alert(`Failed to submit for review: ${error.message || 'Unknown error'}`);
                                                    }
                                                }}
                                                className="flex-1 bg-emerald-600 text-white text-[10px] font-bold uppercase px-3 py-2 hover:bg-emerald-500 transition-colors shadow-sm"
                                            >
                                                Mark Complete
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            {/* Pending Verification */}
                            <div className="space-y-3 pt-4">
                                <h3 className="text-xs font-bold uppercase tracking-widest text-amber-600 border-b border-amber-100 pb-2 flex items-center gap-2">
                                    <Clock size={14} /> Waiting Verification
                                </h3>

                                {allTransactions.filter(t => t.category === 'earn' && t.status === 'pending_approval').length === 0 && (
                                    <p className="text-[10px] font-mono text-slate-400 italic">No pending verifications.</p>
                                )}

                                {allTransactions.filter(t => t.category === 'earn' && t.status === 'pending_approval').map(t => (
                                    <div key={t.id} className="bg-amber-50 border-2 border-amber-400 p-4 shadow-sm opacity-90 relative overflow-hidden">
                                         <div className="absolute top-0 right-0 bg-amber-100 px-2 py-0.5 text-[9px] font-bold uppercase text-amber-700 border-l border-b border-amber-200">
                                             For: {t.lovedOneName}
                                         </div>
                                        <div className="flex items-center justify-between mt-2">
                                            <div className="flex items-center gap-3">
                                                <div className="text-2xl w-10 h-10 flex items-center justify-center bg-white border border-amber-200">{t.icon}</div>
                                                <div>
                                                    <h4 className="font-bold text-sm uppercase text-amber-900">{t.title}</h4>
                                                    <p className="text-[10px] font-mono text-amber-700">Waiting for approval</p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            {/* History (Completed/Redeemed) */}
                             <div className="space-y-3 pt-4">
                                <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 border-b border-slate-200 pb-2 flex items-center gap-2">
                                    <Archive size={14} /> History
                                </h3>
                                <div className="space-y-2 opacity-60">
                                     {allTransactions.filter(t => t.status === 'redeemed' || t.status === 'approved').map(t => (
                                         <div key={t.id} className="flex items-center justify-between text-xs border-b border-slate-100 pb-2">
                                             <div className="flex items-center gap-2">
                                                 <span>{t.icon}</span>
                                                 <div>
                                                    <span className="font-bold text-slate-600 mr-2">{t.title}</span>
                                                    <span className="text-[9px] font-mono text-slate-400">({t.lovedOneName})</span>
                                                 </div>
                                             </div>
                                             <span className="font-mono text-[9px] uppercase bg-slate-100 px-1">
                                                 {t.status === 'approved' ? `Earned ${t.cost}` : 'Redeemed'}
                                             </span>
                                         </div>
                                     ))}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        )}

        {/* === MARKET VIEW (SHOP/EARN) === */}
        {viewMode === 'market' && (
            <>
                <div className="flex-1 overflow-hidden p-4 space-y-4 relative z-10" style={{ minHeight: 0, overflowY: 'auto' }}>
                    {/* Items List */}
                    {items.filter(i => i.category === marketTab).map(item => {
                         const isAffordable = balance >= item.cost;
                         
                         // Check status in transactions (for current loved one)
                         const activeTx = currentLovedOneTransactions.find(t => t.itemId === item.id && (t.status === 'accepted' || t.status === 'pending_approval'));
                         
                         // Logic for "Greyed Out"
                         let isUnavailable = false;
                         let statusLabel = '';

                         if (marketTab === 'spend') {
                             if (!isAffordable) {
                                 isUnavailable = true;
                                 statusLabel = 'Insufficient Funds';
                             }
                         } else {
                             // Earn Tab
                             if (activeTx) {
                                 isUnavailable = true;
                                 statusLabel = activeTx.status === 'pending_approval' ? 'Pending Verification' : 'In Progress (Check Vault)';
                             }
                         }

                         return (
                            <button 
                                key={item.id} 
                                onClick={() => initiateTransaction(item)}
                                disabled={isUnavailable}
                                className={`w-full p-4 border-2 text-left relative overflow-hidden transition-all group active:translate-y-[2px] active:shadow-none ${
                                    marketTab === 'spend'
                                        ? isUnavailable
                                            ? 'bg-slate-50 border-slate-200 opacity-60 grayscale cursor-not-allowed'
                                            : 'bg-white border-slate-900 hover:bg-slate-50 shadow-[4px_4px_0px_rgba(30,41,59,1)]' 
                                        : isUnavailable
                                            ? 'bg-slate-50 border-slate-200 opacity-70 cursor-not-allowed'
                                            : 'bg-white border-emerald-600 hover:bg-emerald-50 shadow-[4px_4px_0px_#059669]'
                                }`}
                            >
                                <div className="flex items-center gap-4 relative z-10">
                                    <div className={`text-3xl w-14 h-14 flex items-center justify-center border-2 border-slate-200 bg-slate-50`}>
                                        {item.icon}
                                    </div>
                                    <div className="flex-1">
                                        <h4 className="font-bold text-lg leading-tight uppercase tracking-tight mb-1 text-slate-900">{item.title}</h4>
                                        
                                        {item.description && (
                                            <div className="mb-2">
                                                {expandedDescriptions.has(item.id) ? (
                                                    <div>
                                                        <p className="text-xs text-slate-600 leading-relaxed mb-1">{item.description}</p>
                                                        <button
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                setExpandedDescriptions(prev => {
                                                                    const next = new Set(prev);
                                                                    next.delete(item.id);
                                                                    return next;
                                                                });
                                                            }}
                                                            className="text-[10px] text-slate-500 hover:text-slate-700 font-mono uppercase"
                                                        >
                                                            Show Less
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            setExpandedDescriptions(prev => new Set(prev).add(item.id));
                                                        }}
                                                        className="text-[10px] text-slate-500 hover:text-slate-700 font-mono uppercase flex items-center gap-1"
                                                    >
                                                        <ChevronDown size={10} /> Show Description
                                                    </button>
                                                )}
                                            </div>
                                        )}
                                        
                                        <div className="flex flex-wrap items-center gap-1.5">
                                            <div className={`inline-block px-2 py-0.5 border text-[10px] font-mono font-bold uppercase ${
                                                marketTab === 'spend'
                                                    ? 'bg-slate-100 text-slate-500 border-slate-300' 
                                                    : 'bg-emerald-100 text-emerald-700 border-emerald-300'
                                            }`}>
                                                {marketTab === 'spend' ? 'COST' : 'REWARD'}: {item.cost} {currentContextEconomy.currencySymbol}
                                            </div>
                                            {statusLabel ? (
                                                <div className="inline-block px-2 py-0.5 border text-[10px] font-mono font-bold uppercase bg-slate-200 text-slate-500 border-slate-300">
                                                    {statusLabel}
                                                </div>
                                            ) : null}
                                        </div>
                                    </div>
                                </div>
                            </button>
                         );
                    })}

                    {/* Empty State */}
                    {items.filter(i => i.category === marketTab).length === 0 && (
                        <div className="text-center py-8 opacity-50">
                             <p className="text-xs font-mono uppercase text-slate-500">No active listings.</p>
                        </div>
                    )}
                </div>
            </>
        )}

        {/* User Currency Config Modal */}
        {showConfigModal && (
            <div className="absolute inset-0 z-50 bg-slate-900/90 backdrop-blur-sm flex items-center justify-center p-6 animate-fade-in">
                 <div className="bg-white w-full max-w-sm border-2 border-slate-900 p-6 shadow-2xl relative">
                     <button 
                        onClick={() => setShowConfigModal(false)}
                        className="absolute top-4 right-4 text-slate-400 hover:text-slate-900"
                     >
                        <X size={20} />
                     </button>

                     <h3 className="font-black text-xl text-slate-900 uppercase tracking-tight mb-2 flex items-center gap-2">
                         <span className="text-2xl">{userEconomy.currencySymbol}</span> My Love Currency Settings
                     </h3>
                     
                     <div className="mb-4 bg-slate-100 p-2 border border-slate-200">
                         <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Scope</span>
                         <div className="text-xs font-bold text-slate-900 uppercase">My Personal Currency</div>
                     </div>

                     <p className="text-xs text-slate-500 mb-4 font-mono leading-relaxed">
                         Customize the currency you offer to others. This is what your partner will see when they interact with you.
                     </p>
                     
                     <div className="space-y-4">
                         {/* Presets */}
                         <div>
                             <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Presets</label>
                             <div className="flex flex-wrap gap-2">
                                 {CURRENCY_PRESETS.map(preset => (
                                    <button
                                        key={preset.name}
                                        onClick={() => {
                                            handleUpdateUserEconomy({ currencyName: preset.name, currencySymbol: preset.symbol });
                                            // Auto-save when selecting a preset
                                            setTimeout(async () => {
                                                try {
                                                    await apiService.updateEconomySettings(preset.name, preset.symbol);
                                                } catch (error: any) {
                                                    console.warn('Failed to save preset:', error);
                                                }
                                            }, 0);
                                        }}
                                        className={`px-3 py-2 border-2 text-xs font-bold uppercase ${
                                            (userEconomy.currencyName === preset.name) 
                                            ? 'bg-slate-900 text-white border-slate-900' 
                                            : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'
                                        }`}
                                    >
                                         {preset.symbol}
                                    </button>
                                 ))}
                             </div>
                         </div>
                         
                         <div className="pt-4 border-t border-slate-100">
                             <div className="grid grid-cols-2 gap-4">
                                 <div>
                                     <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Name</label>
                                     <input 
                                        type="text" 
                                        value={userEconomy.currencyName}
                                        onChange={(e) => handleUpdateUserEconomy({ ...userEconomy, currencyName: e.target.value })}
                                        className="w-full border-2 border-slate-200 p-2 text-sm font-bold uppercase"
                                     />
                                 </div>
                                 <div>
                                     <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Symbol</label>
                                     <input 
                                        type="text" 
                                        value={userEconomy.currencySymbol}
                                        onChange={(e) => handleUpdateUserEconomy({ ...userEconomy, currencySymbol: e.target.value })}
                                        className="w-full border-2 border-slate-200 p-2 text-sm font-bold uppercase text-center"
                                     />
                                 </div>
                             </div>
                         </div>
                     </div>

                     <button 
                        onClick={handleSaveEconomySettings}
                        className="w-full mt-6 bg-indigo-600 text-white py-3 font-bold uppercase tracking-widest text-xs shadow-[4px_4px_0px_#312e81] border-2 border-indigo-900 active:shadow-none active:translate-y-0.5"
                     >
                         Save Configuration
                     </button>
                 </div>
            </div>
        )}

        {/* Confirmation Modal */}
        {confirmModal && (
            <div className="absolute inset-0 z-50 bg-slate-900/80 backdrop-blur-sm flex items-center justify-center p-6 animate-fade-in">
                <div className="bg-white w-full max-w-xs border-4 border-slate-900 p-6 shadow-2xl relative">
                    <div className="flex flex-col items-center text-center mb-6">
                        <div className="w-16 h-16 bg-slate-50 border-2 border-slate-900 flex items-center justify-center text-4xl mb-4">
                            {confirmModal.item.icon}
                        </div>
                        <h3 className="font-black text-lg text-slate-900 uppercase leading-tight mb-2">
                            {confirmModal.action === 'buy' ? 'Confirm Purchase' : 'Accept Quest'}
                        </h3>
                        <p className="text-sm font-mono text-slate-500 leading-relaxed">
                            {confirmModal.action === 'buy' 
                                ? `Spend ${confirmModal.item.cost} ${currentContextEconomy.currencyName} to redeem "${confirmModal.item.title}"? Item will be stored in your Vault.`
                                : `Accept "${confirmModal.item.title}"? You can view active quests in your Vault.`
                            }
                        </p>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                        <button 
                            onClick={() => setConfirmModal(null)}
                            className="py-3 border-2 border-slate-200 font-bold uppercase text-xs hover:bg-slate-50 hover:border-slate-400 transition-colors"
                        >
                            Cancel
                        </button>
                        <button 
                            onClick={executeTransaction}
                            className={`py-3 font-bold uppercase text-xs text-white border-2 border-slate-900 shadow-[2px_2px_0px_rgba(0,0,0,1)] active:translate-y-0.5 active:shadow-none transition-all ${
                                confirmModal.action === 'buy' ? 'bg-slate-900 hover:bg-slate-800' : 'bg-emerald-600 hover:bg-emerald-500 border-emerald-800'
                            }`}
                        >
                            {confirmModal.action === 'buy' ? 'Confirm' : 'Accept'}
                        </button>
                    </div>
                </div>
            </div>
        )}

        {/* Add Item Modal */}
        {showAddModal && (
            <div className="absolute inset-0 z-50 bg-slate-900/90 backdrop-blur-sm flex items-center justify-center p-6 animate-fade-in">
                <div className="bg-white w-full max-w-sm border-2 border-slate-900 p-6 shadow-2xl">
                    <h3 className="font-black text-xl uppercase tracking-tight mb-4">
                        Create New Listing
                    </h3>
                    <div className="space-y-4">
                        {/* Category Selector - Hidden when locked (vault mode) */}
                        {!isCategoryLocked && (
                            <div>
                                <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Type</label>
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => setNewItemCategory('spend')}
                                        className={`flex-1 py-2 text-xs font-bold uppercase border-2 flex items-center justify-center gap-2 ${
                                            newItemCategory === 'spend'
                                            ? 'bg-slate-900 text-white border-slate-900'
                                            : 'bg-white text-slate-400 border-slate-200'
                                        }`}
                                    >
                                        <ShoppingBag size={14} /> {viewMode === 'vault' ? 'My Offer' : 'Reward (Spend)'}
                                    </button>
                                    <button
                                        onClick={() => setNewItemCategory('earn')}
                                        className={`flex-1 py-2 text-xs font-bold uppercase border-2 flex items-center justify-center gap-2 ${
                                            newItemCategory === 'earn'
                                            ? 'bg-emerald-600 text-white border-emerald-600'
                                            : 'bg-white text-slate-400 border-slate-200'
                                        }`}
                                    >
                                        <Wallet size={14} /> {viewMode === 'vault' ? 'My Request' : 'Bounty (Earn)'}
                                    </button>
                                </div>
                                <p className="text-[9px] text-slate-400 mt-1 font-mono">
                                    {viewMode === 'vault' 
                                        ? (newItemCategory === 'spend' 
                                            ? "Service/product you offer. Others spend your currency to buy this."
                                            : "Service/product you request. Others earn your currency by completing this.")
                                        : (newItemCategory === 'spend' 
                                            ? "Something available for purchase using currency." 
                                            : "A task that awards currency upon completion.")}
                                </p>
                            </div>
                        )}
                        
                        {/* Category Display (when locked) */}
                        {isCategoryLocked && (
                            <div className="bg-slate-50 border-2 border-slate-200 p-3">
                                <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Type</label>
                                <div className={`inline-flex items-center gap-2 px-3 py-2 text-xs font-bold uppercase ${
                                    newItemCategory === 'spend'
                                        ? 'bg-slate-900 text-white'
                                        : 'bg-emerald-600 text-white'
                                }`}>
                                    {newItemCategory === 'spend' ? (
                                        <>
                                            <ShoppingBag size={14} /> My Offer
                                        </>
                                    ) : (
                                        <>
                                            <Wallet size={14} /> My Request
                                        </>
                                    )}
                                </div>
                                <p className="text-[9px] text-slate-400 mt-2 font-mono">
                                    {newItemCategory === 'spend' 
                                        ? "Service/product you offer. Others spend your currency to buy this."
                                        : "Service/product you request. Others earn your currency by completing this."}
                                </p>
                            </div>
                        )}

                        <div>
                            <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Title</label>
                            <input 
                                type="text" 
                                value={newItemTitle}
                                onChange={(e) => setNewItemTitle(e.target.value)}
                                className="w-full border-2 border-slate-200 p-2 text-sm font-bold"
                                placeholder={newItemCategory === 'spend' ? "e.g. Back Massage" : "e.g. Wash the Car"}
                            />
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Description (Optional)</label>
                            <textarea 
                                value={newItemDescription}
                                onChange={(e) => setNewItemDescription(e.target.value)}
                                className="w-full border-2 border-slate-200 p-2 text-sm min-h-[60px] resize-y"
                                placeholder="Add more details about this listing..."
                            />
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">
                                {newItemCategory === 'spend' ? 'Cost' : 'Reward Amount'} ({viewMode === 'vault' ? userEconomy.currencySymbol : currentContextEconomy.currencySymbol})
                            </label>
                            <input 
                                type="number" 
                                value={newItemCost}
                                onChange={(e) => setNewItemCost(e.target.value)}
                                className="w-full border-2 border-slate-200 p-2 text-sm font-bold"
                                placeholder="100"
                            />
                            <p className="text-[9px] text-slate-400 mt-1 font-mono">
                                Priced in {viewMode === 'vault' ? `your ${userEconomy.currencyName}` : `${selectedLovedOne?.name}'s ${currentContextEconomy.currencyName}`}
                            </p>
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Icon (Emoji)</label>
                            <div className="relative" ref={emojiPickerRef}>
                                <button
                                    type="button"
                                    onClick={() => setShowEmojiPicker(!showEmojiPicker)}
                                    className="w-full border-2 border-slate-200 p-2 text-2xl font-bold text-center bg-white hover:bg-slate-50 flex items-center justify-center gap-2"
                                >
                                    <span>{newItemIcon || '🎁'}</span>
                                    <ChevronDown size={14} className={`text-slate-400 transition-transform ${showEmojiPicker ? 'rotate-180' : ''}`} />
                                </button>
                                
                                {showEmojiPicker && (
                                    <div className="absolute z-50 mt-1 w-full bg-white border-2 border-slate-200 shadow-lg max-h-60 overflow-y-auto">
                                        <div className="p-2 grid grid-cols-8 gap-1">
                                            {commonEmojis.map((emoji, idx) => (
                                                <button
                                                    key={idx}
                                                    type="button"
                                                    onClick={() => {
                                                        setNewItemIcon(emoji);
                                                        setShowEmojiPicker(false);
                                                    }}
                                                    className={`p-2 text-xl hover:bg-slate-100 rounded transition-colors ${
                                                        newItemIcon === emoji ? 'bg-slate-200 ring-2 ring-slate-400' : ''
                                                    }`}
                                                >
                                                    {emoji}
                                                </button>
                                            ))}
                                        </div>
                                        <div className="border-t border-slate-200 p-2">
                                            <input
                                                type="text"
                                                value={newItemIcon}
                                                onChange={(e) => setNewItemIcon(e.target.value)}
                                                placeholder="Or type custom emoji"
                                                className="w-full border border-slate-300 p-1.5 text-sm text-center"
                                                onClick={(e) => e.stopPropagation()}
                                            />
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                        
                        {/* Loved Ones Availability Selector (only in vault mode) */}
                        {viewMode === 'vault' && (
                            <div>
                                <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">
                                    Available To {selectedLovedOneIds.length > 0 ? `(${selectedLovedOneIds.length} selected)` : '(All loved ones by default)'}
                                </label>
                                <div className="space-y-2 max-h-40 overflow-y-auto border-2 border-slate-200 p-2">
                                    {/* User's own entry - unchecked by default */}
                                    <label 
                                        className="flex items-center gap-2 cursor-pointer hover:bg-slate-50 p-2 rounded border-b border-slate-200 pb-2 mb-2"
                                    >
                                        <input
                                            type="checkbox"
                                            checked={availableToSelf}
                                            onChange={(e) => setAvailableToSelf(e.target.checked)}
                                            className="w-4 h-4 border-2 border-slate-300 rounded"
                                        />
                                        <span className="text-xs font-medium text-slate-700">
                                            {user.name || 'You'} <span className="text-slate-400">(self)</span>
                                        </span>
                                    </label>
                                    
                                    {/* All loved ones - checked by default */}
                                    {availableLovedOnes.filter(lo => !lo.isPending).map(lo => (
                                        <label 
                                            key={lo.id}
                                            className="flex items-center gap-2 cursor-pointer hover:bg-slate-50 p-2 rounded"
                                        >
                                            <input
                                                type="checkbox"
                                                checked={selectedLovedOneIds.includes(lo.id)}
                                                onChange={() => toggleLovedOneSelection(lo.id)}
                                                className="w-4 h-4 border-2 border-slate-300 rounded"
                                            />
                                            <span className="text-xs font-medium text-slate-700">{lo.name}</span>
                                        </label>
                                    ))}
                                    {availableLovedOnes.filter(lo => !lo.isPending).length === 0 && (
                                        <p className="text-[10px] text-slate-400 italic">No active relationships. Item will be available to all when relationships are added.</p>
                                    )}
                                </div>
                                <p className="text-[9px] text-slate-400 mt-1 font-mono">
                                    All loved ones are selected by default. Uncheck to restrict availability to specific loved ones.
                                </p>
                            </div>
                        )}
                        
                        <div className="flex gap-2 pt-2">
                            <button onClick={() => {
                                setShowAddModal(false);
                                setNewItemTitle('');
                                setNewItemDescription('');
                                setNewItemCost('');
                                setNewItemIcon('🎁');
                                setSelectedLovedOneIds([]);
                                setAvailableToSelf(false);
                                setShowEmojiPicker(false);
                            }} className="flex-1 py-3 border-2 border-slate-200 font-bold uppercase text-xs hover:bg-slate-50">Cancel</button>
                            <button onClick={handleAddItem} className="flex-1 py-3 bg-slate-900 text-white font-bold uppercase text-xs hover:bg-slate-800">Add Item</button>
                        </div>
                    </div>
                </div>
            </div>
        )}
    </div>
  )
}