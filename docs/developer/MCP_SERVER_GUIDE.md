# MCP Server Documentation

The YourFinanceWORKS project includes a modern **FastMCP** server that allows AI assistants (like Claude) to interact directly with your financial data through the Model Context Protocol.

## Quick Links

- **Main Guide**: [api/MCP/README.md](../../api/MCP/README.md) - Setup, architecture, and tool reference.
- **Change Log**: [api/MCP/CHANGES.md](../../api/MCP/CHANGES.md) - History of MCP server updates.
- **Internal Notes**: [api/MCP/scripts/Notes.md](../../api/MCP/scripts/Notes.md) - Technical implementation details for MCP scripts.

## Overview

The MCP server acts as a bridge between the Invoice Application API and AI clients. It provides a suite of tools for:

- **Client & Invoice Management**: Search, list, and create operations.
- **Financial Analytics**: Querying outstanding balances and overdue items.
- **Expense & Inventory**: Tracking spending and stock levels.
- **Banking Reconciliation**: Reviewing and matching bank transactions.

For integration guides and detailed tool signatures, refer to the [MCP README](../../api/MCP/README.md).
