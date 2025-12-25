# YourFinanceWORKS API

This is the REST API backend for YourFinanceWORKS built with FastAPI, SQLAlchemy, and Pydantic.

## Features

- Client Management
- Invoice Management
- Payment Processing
- Database integration with SQLAlchemy
- Data validation with Pydantic
- API documentation with Swagger UI

## Recent Fixes

- Fixed CORS handling by updating the custom middleware to properly handle OPTIONS preflight requests
- Added built-in CORS middleware for better cross-origin compatibility
- Fixed SQLAlchemy query joins in the payments router by using explicit select_from() and join conditions
- Improved error handling when converting SQLAlchemy objects to dictionaries

## Setup and Installation

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Initialize the database with sample data:

```bash
python -m api.db_init
```

3. Run the API server:

```bash
uvicorn api.main:app --reload
```

The API will be available at http://localhost:8000, and the API documentation at http://localhost:8000/docs.

## API Endpoints

### Clients

- `GET /api/v1/clients/` - List all clients
- `GET /api/v1/clients/{client_id}` - Get client details
- `POST /api/v1/clients/` - Create a new client
- `PUT /api/v1/clients/{client_id}` - Update a client
- `DELETE /api/v1/clients/{client_id}` - Delete a client

### Invoices

- `GET /api/v1/invoices/` - List all invoices
- `GET /api/v1/invoices/{invoice_id}` - Get invoice details
- `POST /api/v1/invoices/` - Create a new invoice
- `PUT /api/v1/invoices/{invoice_id}` - Update an invoice
- `DELETE /api/v1/invoices/{invoice_id}` - Delete an invoice

### Payments

- `GET /api/v1/payments/` - List all payments
- `GET /api/v1/payments/{payment_id}` - Get payment details
- `POST /api/v1/payments/` - Create a new payment
- `PUT /api/v1/payments/{payment_id}` - Update a payment
- `DELETE /api/v1/payments/{payment_id}` - Delete a payment

## API Documentation

FastAPI provides automatic API documentation using Swagger UI. 
Access it at http://localhost:8000/docs when the server is running.

## Security configuration

Environment variables (recommended to set via Docker or your process manager):

- SECRET_KEY (required in production): Secret for signing JWTs. In development, set DEBUG=True to allow a temporary default.
- DEBUG (default: False): Enables dev-friendly defaults (e.g., permissive CORS when origins not provided).
- ALLOWED_ORIGINS: Comma-separated list of allowed origins for CORS, e.g. http://localhost:8080,https://app.example.com. If omitted and DEBUG=True, * is allowed.
- ALLOW_CORS_CREDENTIALS (default: False): If True, allows credentials with CORS. Must not be used with wildcard origins.
- MAX_LOGIN_ATTEMPTS (default: 5): Per-email login attempts in RATE_LIMIT_WINDOW_SECONDS.
- MAX_RESET_ATTEMPTS (default: 5): Per-email password reset requests in RATE_LIMIT_WINDOW_SECONDS.
- RATE_LIMIT_WINDOW_SECONDS (default: 60): Sliding window for the above rate limits.

File uploads:
- Attachments are saved under attachments/tenant_<id>/invoices/ with sanitized filenames.
- Max upload size enforced at 10 MB. PDFs are validated for %PDF header.

## Development

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request 

## Running the API

To start the API server:

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize the database (if not already done)
python run_init.py

# Start the server
python start.py
```

The API will be available at http://localhost:8000

## API Documentation

Once the server is running, you can access the interactive API documentation at:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

The API provides the following endpoints:

- `/api/v1/clients` - Manage clients
- `/api/v1/invoices` - Manage invoices
- `/api/v1/payments` - Manage payments

Each resource supports standard CRUD operations.

## Database

The application uses SQLite for data storage. The database file is `invoice_app.db` in the root directory.

## Sample Data

The database is initialized with sample clients, invoices, and payments when you first run the application. 