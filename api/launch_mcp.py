#!/usr/bin/env python3
"""
Launcher script for the Invoice Application MCP Server.
This script properly sets up the Python path and launches the MCP server.
"""
import sys
import os

# Add the current directory (api) to Python path so MCP module can be found
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def main():
    """Launch the MCP server with proper path setup"""
    # Import the MCP server module now that the path is set up
    from MCP.server import main as server_main
    
    # Run the MCP server - FastMCP handles everything including argument parsing
    server_main()

if __name__ == "__main__":
    main() 