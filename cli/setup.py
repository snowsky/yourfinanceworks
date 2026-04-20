from setuptools import find_packages, setup


setup(
    name="finance-agent-cli",
    version="0.1.0",
    description="REST-first investment monitoring CLI for YourFinanceWORKS",
    packages=find_packages(include=["finance_agent_cli", "finance_agent_cli.*"]),
    install_requires=["httpx>=0.28,<0.29"],
    entry_points={
        "console_scripts": [
            "finance-agent=finance_agent_cli.app:main",
        ]
    },
)
