# Contributing to YourFinanceWORKS

First off, thank you for considering contributing to YourFinanceWORKS! It's people like you that make this tool great for everyone.

## Code of Conduct

By participating in this project, you are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).

## How Can I Contribute?

### Reporting Bugs

- Check the [Issues](https://github.com/snowsky/yourfinanceworks/issues) to see if the bug has already been reported.
- If not, open a new issue. Include a clear title, a detailed description, steps to reproduce, and any relevant logs or screenshots.

### Suggesting Enhancements

- Open an issue with the tag "enhancement".
- Describe the feature you'd like to see and why it would be useful.

### Pull Requests

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. Ensure the test suite passes.
4. Make sure your code lints.
5. Issue that pull request!

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose

### Backend Setup

```bash
cd api
python -m venv venv
source venv/bin/activate  # Or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example.full .env
# Update .env with your local settings
python main.py
```

### Frontend Setup

```bash
cd ui
npm install
cp .env.example .env
npm run dev
```

### Running with Docker

```bash
cp api/.env.example.full .env
docker-compose up -d
```

## Styling and Standards

- Python: Follow PEP 8 and use `ruff` for linting.
- TypeScript: Use functional components and follow the project's existing ESLint configuration.
- CSS: Use Tailwind CSS classes.

## Licensing

By contributing, you agree that your contributions will be licensed under the project's [GPLv3 / Commercial dual-license](README.md#licensing).
