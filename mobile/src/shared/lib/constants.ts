import type { EconomyConfig, MarketItem } from '../types/domain';

/** App-wide default currency when backend/user has not set one. */
export const DEFAULT_ECONOMY: EconomyConfig = {
  currencyName: 'Tickets',
  currencySymbol: '🎟️',
};

/** Default market items when none are configured (empty list). */
export const DEFAULT_MARKET_ITEMS: MarketItem[] = [];
