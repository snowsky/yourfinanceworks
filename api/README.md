# YourFinanceWORKS API

This is the REST API backend for YourFinanceWORKS built with **FastAPI**, **SQLAlchemy**, and **Pydantic**.

## 🚀 Quick Start

1. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize the database** (SQLite):

   ```bash
   python -m api.db_init
   ```

3. **Start the server**:

   ```bash
   uvicorn api.main:app --reload
   ```

The API will be available at `http://localhost:8000`.

## 📚 Documentation

For detailed guides and architecture, please refer to the centralized documentation hub:

- **[Main Project README](../README.md)**
- **[Developer Guide](../docs/developer/API_REFERENCE.md)**
- **[MCP Server Guide](../docs/developer/MCP_SERVER_GUIDE.md)**
- **Interactive Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs) (when running)

## 🛠️ Security & Configuration

Environment variables (set via `.env` or Docker):

- `SECRET_KEY`: Required for JWT signing.
- `DEBUG`: Enables developer-friendly CORS and error responses.
- `ALLOWED_ORIGINS`: Comma-separated list for CORS.
- `DATABASE_URL`: Optional override for the default SQLite database.

Refer to `api/config.py` for all available settings.

## 📂 Project Structure

- `api/core/`: Foundation logic, models, and shared services.
- `api/commercial/`: Advanced features and business logic.
- `api/MCP/`: FastMCP server implementation.
- `api/workers/`: Background processing tasks (OCR, Email and Anomaly Detection).
- `api/scripts/`: Database management and utility scripts.
