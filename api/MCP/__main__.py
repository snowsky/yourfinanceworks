"""
Entry point for running the Invoice Application MCP Server as a module.

Usage:
    python -m MCP
    python -m MCP.server
"""
from .server import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main()) 