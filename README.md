# YourFinanceWORKS

![License: AGPL v3](https://img.shields.io/badge/License-AGPLv3-blue.svg)
![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)
![React: 18+](https://img.shields.io/badge/React-18+-61DAFB.svg?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6.svg?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-5.0-646CFF.svg?logo=vite&logoColor=white)

A modern, AI-powered multi-tenant financial management system. YourFinanceWORKS empowers businesses with professional invoicing, automated expense tracking through OCR, and deep business intelligence powered by the Model Context Protocol (MCP).

## ⚡ Quick Start (Docker)

```bash
# 1. Clone and enter
git clone git@github.com:snowsky/yourfinanceworks.git
cd yourfinanceworks

# 2. Configure environment
cp api/.env.example.full .env
# Edit .env with your settings (especially database credentials)

# 3. Spin up the entire stack
docker-compose up -d

# 4. Create a Super User (optional if you plan to sign up first)
docker-compose exec api python scripts/create_super_user.py
```

The first user to sign up in a fresh system is automatically granted Super User privileges and assigned the `admin` role.

## 📚 Documentation

- **[Documentation Hub](docs/README.md)**
- **[Features Overview](docs/features/README.md)**
- **[AI Assistant Usage](docs/user-guide/AI_ASSISTANT_USAGE.md)**
- **[Super Admin System Guide](docs/admin-guide/SUPER_ADMIN_SYSTEM.md)**
- **[Testing Guide](TESTING.md)**

## 🧩 Product Highlights

- Professional invoicing with revenue cycle insights
- OCR-powered expense intelligence and approval workflows
- MCP-backed AI assistant for business queries
- Multi-tenant architecture with audit-ready governance
- Cloud storage, batch processing, and integrations

## 🏗️ Architecture (High Level)

- **Backend**: FastAPI + PostgreSQL (database-per-tenant) + Redis + Kafka
- **Frontend**: React + TypeScript + Vite + Tailwind/ShadCN UI
- **Infrastructure**: Docker Compose for local orchestration

## 🔧 Local Development

- **Environment Setup**: [docs/developer/environment_setup.md](docs/developer/environment_setup.md)
- **Quick Start (Docker)**: See the [Quick Start](#quick-start-docker) section above.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Licensing

This project utilizes a **Split-Licensing Model** to provide maximum transparency while protecting specialized features:

1. **GNU Affero General Public License v3.0 (AGPL-3.0)**:
   - **Applies to**: `api/core/`, `ui/`, and shared project infrastructure.
   - Free to use, modify, and distribute under AGPL-3.0 terms.
   - Requires sharing source code for any network-distributed versions.
   - See [LICENSE-AGPLv3.txt](LICENSE-AGPLv3.txt) for details.

2. **Commercial License (Source Available)**:
   - **Applies to**: `api/commercial/` directory.
   - While the source code is visible, usage is restricted to licensed customers.
   - Ideal for businesses requiring enterprise features or proprietary integration.
   - Contact licensing@yourfinanceworks.com for license acquisition or visit [LICENSE-COMMERCIAL.txt](LICENSE-COMMERCIAL.txt).

## 🆘 Support

For support and questions:

1. Check the documentation
2. Review the troubleshooting guides
3. Open an issue on GitHub
4. Contact the development team
