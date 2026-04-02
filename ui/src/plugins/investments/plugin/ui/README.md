# Investment Management Plugin

A comprehensive investment portfolio management plugin for YourFinanceWORKS that provides complete tracking and analytics for investment portfolios.

## Features

- **Portfolio Management**: Create and manage multiple investment portfolios (taxable, retirement, business)
- **Holdings Tracking**: Track individual investment holdings with cost basis and current valuations
- **Transaction Recording**: Record buy, sell, dividend, and other investment transactions
- **Performance Analytics**: Calculate portfolio performance metrics including gains/losses and returns
- **Asset Allocation**: Analyze portfolio composition by asset class
- **Dividend Tracking**: Monitor dividend income and payment history
- **Tax Reporting**: Export transaction data for tax preparation
- **Price Management**: Update security prices and track valuation changes

## Components

### Pages
- `InvestmentDashboard` - Main dashboard showing all portfolios and performance overview
- `CreatePortfolio` - Form to create a new investment portfolio
- `PortfolioDetail` - Detailed view of a specific portfolio with holdings management

### Components
- `HoldingsList` - Display and manage holdings within a portfolio
- `CreateHoldingDialog` - Dialog to add a new holding to a portfolio
- `EditHoldingDialog` - Dialog to edit holding details and update prices

## API Endpoints

The plugin integrates with the following backend API endpoints:

- `GET /investments/portfolios` - List all portfolios
- `POST /investments/portfolios` - Create a new portfolio
- `GET /investments/portfolios/{id}` - Get portfolio details
- `PUT /investments/portfolios/{id}` - Update portfolio
- `DELETE /investments/portfolios/{id}` - Delete portfolio

- `GET /investments/portfolios/{id}/holdings` - List holdings in a portfolio
- `POST /investments/portfolios/{id}/holdings` - Add a holding
- `GET /investments/holdings/{id}` - Get holding details
- `PUT /investments/holdings/{id}` - Update holding
- `PATCH /investments/holdings/{id}/price` - Update holding price

- `POST /investments/portfolios/{id}/transactions` - Record a transaction
- `GET /investments/portfolios/{id}/transactions` - List transactions

- `GET /investments/portfolios/{id}/performance` - Get performance metrics
- `GET /investments/portfolios/{id}/allocation` - Get asset allocation
- `GET /investments/portfolios/{id}/dividends` - Get dividend history
- `GET /investments/portfolios/{id}/tax-export` - Export tax data

## Usage

### Basic Setup

The plugin is automatically registered when the application starts if the user has a commercial license.

### Creating a Portfolio

```typescript
import { CreatePortfolio } from '@/plugins/investments';

// Navigate to /investments/portfolio/new to create a portfolio
```

### Managing Holdings

```typescript
import { HoldingsList } from '@/plugins/investments';

// Use HoldingsList component to display and manage holdings
<HoldingsList portfolioId={portfolioId} />
```

### Viewing Performance

Navigate to `/investments/portfolio/{id}` to view portfolio details including:
- Holdings list with current values and gains/losses
- Performance metrics
- Asset allocation breakdown

## License

This plugin requires a commercial license tier to access.

## Support

For issues or feature requests, please contact support@yourfinanceworks.com
