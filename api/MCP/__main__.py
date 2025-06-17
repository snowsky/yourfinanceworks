"""
Entry point for running the Invoice Application MCP Server as a module.

Usage:
    python -m MCP
"""
import sys
import os

# Add the api directory to Python path so imports work correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    # Import and run the server - now much simpler
    from MCP.server import main
    
    # Run the server - FastMCP handles everything
    main()