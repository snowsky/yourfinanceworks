# YourFinanceWORKS

![License: Dual](https://img.shields.io/badge/License-Dual%20License-blue.svg)
![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)
![React: 18+](https://img.shields.io/badge/React-18+-61DAFB.svg?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6.svg?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-5.0-646CFF.svg?logo=vite&logoColor=white)

YourFinanceWORKS transforms financial futures for businesses and individuals through AI-powered automation of invoicing, expense tracking, banking reconciliation, and comprehensive business intelligence in a secure multi-tenant platform.

## 🎬 Videos

|                                            Introduction                                             |                                            Features                                            |
| :-------------------------------------------------------------------------------------------------: | :--------------------------------------------------------------------------------------------: |
| [![Introduction Video](https://img.youtube.com/vi/xP6NmpaEe6c/0.jpg)](https://youtu.be/xP6NmpaEe6c) | [![Feature Video](https://img.youtube.com/vi/Yj-WUDgdlM4/0.jpg)](https://youtu.be/Yj-WUDgdlM4) |
|                                 How to use the app & license portal                                 |                                   Product features overview                                    |

## ⚡ Quick Start (Docker)

```bash
# 1. Clone and enter
git clone git@github.com:snowsky/yourfinanceworks.git
cd yourfinanceworks

# 2. Configure environment
cp api/.env.example.full api/.env
# Edit .env with your settings (especially database credentials)

# 3. Spin up the entire stack
docker-compose up --build -d

# 4. Create a Super User (optional if you plan to sign up first)
docker-compose exec api python scripts/create_super_user.py
```

▶️ **Watch the Docker Compose setup walkthrough**: [https://youtu.be/810xppiTtAE](https://youtu.be/810xppiTtAE)

The first user to sign up in a fresh system is automatically granted Super User privileges and assigned the global `admin` role.

## 📚 Documentation

- **[Documentation Hub](docs/README.md)**
- **[Features Overview](docs/features/README.md)**
- **[AI Assistant Usage](docs/user-guide/AI_ASSISTANT_USAGE.md)**
- **[Super Admin System Guide](docs/admin-guide/SUPER_ADMIN_SYSTEM.md)**
- **[Testing Guide](TESTING.md)**

## 🧩 Product Highlights

### 💰 Revenue & Billing

- Professional invoicing with AI-powered templates and tax compliance
- Multi-provider email delivery with professional PDF attachments
- Real-time payment tracking and automated collection reminders
- Revenue cycle optimization with strategic billing insights

### 📊 Expense Intelligence & Automation

- OCR-powered receipt processing with high-accuracy data extraction
- Smart expense categorization based on vendor patterns and history
- Approval workflows with configurable rules and audit trails
- Batch processing for efficient receipt management
- AI-powered invoice OCR for automated data entry and line item extraction

### 🏦 Banking & Financial Health

- Automated bank statement processing with AI OCR transaction extraction
- Smart transaction matching for one-click reconciliation
- Real-time financial health monitoring and cash flow analysis

### 🕵️ AI-Powered Business Intelligence

- MCP-backed AI assistant for natural language business queries
- AI-powered fraud detection and risk scoring for financial documents
- Forensic auditing with anomaly detection and attachment integrity analysis
- Growth analytics with interactive dashboards and actionable recommendations
- AI prompt management with provider-specific optimizations
- Advanced document processing with vision-capable models for complex layouts

### 🏦 Enterprise & Governance

- Multi-tenant architecture with secure database-per-tenant isolation
- Role-based access control with granular permissions and governance
- Comprehensive audit trails and compliance reporting
- Advanced data export/import and backup capabilities

### 🛠️ Advanced Infrastructure

- Extensible plugin management system for custom functionality
- Investment management plugins for portfolio tracking and analysis
- Cloud storage integration with multiple provider support
- RESTful API for system integration and batch processing
- Slack integration and external transaction management
- Advanced export capabilities with multiple format support
- **MCP (Model Context Protocol)** enabling to query business data in natural language

## 🏗️ Architecture (High Level)

- **Backend**: FastAPI + PostgreSQL (database-per-tenant) + Redis + Kafka
- **Frontend**: React + TypeScript + Vite + Tailwind/ShadCN UI
- **Infrastructure**: Docker Compose for local orchestration

## 🔧 Local Development

- **Environment Setup**: [docs/developer/environment_setup.md](docs/developer/environment_setup.md)
- **Quick Start (Docker)**: See the [Quick Start](#quick-start-docker) section above.
- **Finance Agent CLI + MCP**: [docs/technical-notes/FINANCE_AGENT_CLI_AND_MCP.md](docs/technical-notes/FINANCE_AGENT_CLI_AND_MCP.md)

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
   - Contact licensing@yourfinanceworks.com or visit https://www.yourfinanceworks.com for license acquisition.
   - See [LICENSE-COMMERCIAL.txt](LICENSE-COMMERCIAL.txt) for details.

## 👋 Who Am I?

I'm a DevOps engineer who built this entire SaaS product with the help of AI — as an experiment to test a bold hypothesis: **is the SaaS business model really dying?** With AI drastically lowering the barrier to building sophisticated software, this project explores what one person with DevOps skills and AI assistance can ship, and whether indie SaaS can still compete in today's market.

If you'd like to get personalized help, code reviews, or mentoring, feel free to reach out on Codementor:

[![Contact me on Codementor](https://www.codementor.io/m-badges/snowsky/find-me-on-cm-g.svg)](https://www.codementor.io/@snowsky?refer=badge)

> ⭐ Reviews and feedback from past sessions are always appreciated!

## 🆘 Support

For support and questions:

1. Check the documentation
2. Review the troubleshooting guides
3. Open an issue on GitHub
4. Contact the development team
