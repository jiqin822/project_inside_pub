# Market API Integration Guide

## Frontend Integration

The market API has been integrated into the frontend `apiService.ts`. Here are the available methods:

### Economy Settings

```typescript
// Get current user's economy settings
const response = await apiService.getEconomySettings();
// Returns: { user_id, currency_name, currency_symbol }

// Update economy settings
await apiService.updateEconomySettings("Love Tokens", "🪙");
```

### Market Catalog

```typescript
// Get market catalog for a user (includes items + balance)
const market = await apiService.getUserMarket(userId);
// Returns: { items: [...], balance: number, currency_name, currency_symbol }
```

### Market Items Management

```typescript
// Create a market item (SPEND or EARN)
await apiService.createMarketItem({
  title: "Back Massage",
  description: "A relaxing back massage",
  cost: 500,
  icon: "💆",
  category: "SPEND" // or "EARN"
});

// Delete a market item (soft delete)
await apiService.deleteMarketItem(itemId);
```

### Transactions - Spend Flow

```typescript
// Purchase an item
const purchase = await apiService.purchaseItem(itemId, issuerId, idempotencyKey?);
// Returns transaction with status: "PURCHASED"

// Redeem a purchased item
await apiService.redeemItem(transactionId);
// Updates transaction status to: "REDEEMED"
```

### Transactions - Earn Flow

```typescript
// Accept a task
const task = await apiService.acceptTask(itemId, issuerId);
// Returns transaction with status: "ACCEPTED"

// Submit task for review
await apiService.submitForReview(transactionId);
// Updates transaction status to: "PENDING_APPROVAL"

// Approve task (issuer only)
await apiService.approveTask(transactionId);
// Updates transaction status to: "APPROVED" and increments balance
```

### Transaction History

```typescript
// Get all transactions for current user
const transactions = await apiService.getMyTransactions();
// Returns array of transactions grouped by issuer
```

### Transaction Cancellation

```typescript
// Cancel a transaction (either party can cancel)
await apiService.cancelTransaction(transactionId);
// Updates transaction status to: "CANCELED"
```

## Example Usage in React Component

```typescript
import { apiService } from './services/apiService';

// In your component
const [market, setMarket] = useState(null);
const [balance, setBalance] = useState(0);

useEffect(() => {
  const loadMarket = async () => {
    try {
      // Load market for a loved one
      const response = await apiService.getUserMarket(lovedOneId);
      setMarket(response.data);
      setBalance(response.data.balance);
    } catch (error) {
      console.error('Failed to load market:', error);
    }
  };
  
  loadMarket();
}, [lovedOneId]);

// Purchase an item
const handlePurchase = async (itemId: string) => {
  try {
    const response = await apiService.purchaseItem(itemId, issuerId);
    // Update balance locally
    setBalance(prev => prev - response.data.amount);
    // Show success message
  } catch (error) {
    if (error.message.includes('Insufficient balance')) {
      alert('Not enough tokens!');
    }
  }
};
```

## API Endpoints

All endpoints are prefixed with `/v1/market`:

- `GET /v1/market/me/economy` - Get economy settings
- `PUT /v1/market/me/economy` - Update economy settings
- `GET /v1/market/profiles/{userId}/market` - Get market catalog
- `POST /v1/market/items` - Create market item
- `DELETE /v1/market/items/{itemId}` - Delete market item
- `GET /v1/market/wallets/transactions` - Get transaction history
- `POST /v1/market/transactions/purchase` - Purchase item
- `POST /v1/market/transactions/{id}/redeem` - Redeem item
- `POST /v1/market/transactions/accept` - Accept task
- `POST /v1/market/transactions/{id}/submit` - Submit for review
- `POST /v1/market/transactions/{id}/approve` - Approve task
- `POST /v1/market/transactions/{id}/cancel` - Cancel transaction

## Error Handling

All methods throw errors that can be caught:

```typescript
try {
  await apiService.purchaseItem(itemId, issuerId);
} catch (error) {
  if (error.message.includes('Insufficient balance')) {
    // Handle insufficient balance
  } else if (error.message.includes('not found')) {
    // Handle item not found
  } else {
    // Handle other errors
  }
}
```

## Testing

To run the market module tests:

```bash
cd backend
poetry run pytest tests/test_market.py -v
```

Or run all tests:
```bash
make test
```
