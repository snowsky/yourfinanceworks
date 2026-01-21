# MCP Troubleshooting Guide

Solutions to common issues when setting up and using the Invoice Application MCP server.

## 🔧 Quick Diagnosis

Start with the validation script to identify issues:

```bash
cd api/MCP
python scripts/validate_mcp_setup.py
```

This will test your setup and provide specific guidance for any problems found.

## ❓ Common Issues and Solutions

### Installation Issues

#### **Python Module Not Found**
```
ModuleNotFoundError: No module named 'fastmcp'
```

**Cause:** Required dependencies not installed

**Solution:**
```bash
cd api/MCP
pip install -r requirements.txt
```

**Alternative:** Install in a virtual environment
```bash
python -m venv mcp_env
source mcp_env/bin/activate  # On Windows: mcp_env\Scripts\activate
pip install -r requirements.txt
```

#### **Import Errors**
```
ImportError: cannot import name 'InvoiceTools'
```

**Cause:** Python path issues or incorrect working directory

**Solution:**
```bash
# Ensure you're in the api directory
cd api
python -m MCP

# Or use the launcher script
python launch_mcp.py
```

### Configuration Issues

#### **Environment Variables Not Loading**
```
INVOICE_API_EMAIL is not configured
```

**Cause:** Missing `.env` file or incorrect format

**Solution:**
```bash
# Copy the example file
cd api/MCP
cp example.env .env

# Edit with your actual credentials
nano .env  # or use your preferred editor
```

**Verify format:**
```env
INVOICE_API_BASE_URL=http://localhost:8000/api
INVOICE_API_EMAIL=your_actual_email@example.com
INVOICE_API_PASSWORD=your_actual_password
```

#### **Default Values Still Present**
```
Email and password are required but still have default values
```

**Cause:** Using placeholder values instead of real credentials

**Solution:** Replace the example values in your `.env` file:
- Change `your_email@example.com` to your actual email
- Change `your_secure_password` to your actual password

### Authentication Issues

#### **Login Failed**
```
Authentication failed: Invalid credentials
```

**Cause:** Incorrect email/password or API not accessible

**Solutions:**
1. **Verify credentials** - Test login in the web interface
2. **Check API URL** - Ensure the API is running at the specified URL
3. **Test API connectivity:**
   ```bash
   curl http://localhost:8000/api/health
   ```

#### **Connection Refused**
```
ConnectionError: Connection refused
```

**Cause:** API server not running or wrong URL

**Solutions:**
1. **Start the API server:**
   ```bash
   cd api
   uvicorn main:app --reload --port 8000
   ```

2. **Verify the URL** - Check that the API is accessible:
   ```bash
   curl http://localhost:8000/api/docs
   ```

3. **Check firewall settings** - Ensure port 8000 is not blocked

### Claude Desktop Issues

#### **MCP Server Not Showing**
Claude Desktop doesn't show the Invoice Application connection

**Cause:** Configuration file not found or incorrect format

**Solutions:**
1. **Check config location:**
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

2. **Validate JSON format:**
   ```bash
   python -m json.tool ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

3. **Restart Claude Desktop** completely (quit and reopen)

#### **Path Issues**
```
FileNotFoundError: [Errno 2] No such file or directory: '/path/to/launch_mcp.py'
```

**Cause:** Incorrect path in configuration

**Solution:** Use absolute paths:
```json
{
  "mcpServers": {
    "invoice-app": {
      "command": "python",
      "args": ["/Users/yourname/dev/invoice_app/api/launch_mcp.py"]
    }
  }
}
```

**Get the correct path:**
```bash
cd api
pwd  # Copy this output
```

#### **Permission Errors**
```
PermissionError: [Errno 13] Permission denied
```

**Cause:** File permissions or virtual environment issues

**Solutions:**
1. **Make script executable:**
   ```bash
   chmod +x api/launch_mcp.py
   ```

2. **Use virtual environment Python:**
   ```json
   {
     "mcpServers": {
       "invoice-app": {
         "command": "/Users/yourname/dev/invoice_app/mcp_env/bin/python"
       }
     }
   }
   ```

### Performance Issues

#### **Slow Responses**
MCP tools are taking too long to respond

**Cause:** Network latency or API performance

**Solutions:**
1. **Check API performance:**
   ```bash
   curl -w "@curl-format.txt" http://localhost:8000/api/clients
   ```

2. **Increase timeout:**
   ```bash
   export REQUEST_TIMEOUT=60
   python -m MCP
   ```

3. **Use pagination for large datasets:**
   ```
   List clients with limit 50
   ```

#### **Memory Issues**
MCP server using too much memory

**Cause:** Large datasets or memory leaks

**Solutions:**
1. **Use pagination in requests**
2. **Restart MCP server periodically**
3. **Monitor with verbose logging:**
   ```bash
   python -m MCP --verbose
   ```

## 🔍 Debugging Tools

### Enable Verbose Logging
```bash
python -m MCP --verbose
```

### Test API Connection
```bash
# Test basic connectivity
curl http://localhost:8000/api/health

# Test authentication
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "password": "yourpass"}'
```

### Check Dependencies
```bash
cd api/MCP
pip list | grep -E "(fastmcp|httpx|pydantic)"
```

### Validate Configuration
```bash
cd api/MCP
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print('Email:', os.getenv('INVOICE_API_EMAIL')); print('API URL:', os.getenv('INVOICE_API_BASE_URL'))"
```

## 🆘 Getting Help

### Information to Collect
When asking for help, provide:

1. **Error messages** (full output)
2. **Configuration** (sanitized `.env` file)
3. **System info:**
   ```bash
   python --version
   pip list | grep fastmcp
   ```
4. **Validation script output**

### Common Debugging Commands

```bash
# Check if API is running
curl http://localhost:8000/api/docs

# Test MCP imports
cd api/MCP
python -c "from MCP.tools import InvoiceTools; print('Imports OK')"

# Run validation
python scripts/validate_mcp_setup.py

# Test with verbose output
python -m MCP --verbose --email your@email.com --password yourpass
```

### Log Files

Check these locations for log files:

- **MCP Server:** Console output (use `--verbose`)
- **Claude Desktop:** 
  - **macOS:** `~/Library/Logs/Claude/`
  - **Windows:** `%APPDATA%\Claude\logs\`
- **API Server:** Check your API server's log configuration

## 🔄 Recovery Steps

### Reset Configuration
```bash
cd api/MCP
# Backup current config
cp .env .env.backup

# Start fresh
cp example.env .env
# Edit .env with your credentials
```

### Reinstall Dependencies
```bash
cd api/MCP
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

### Clear Authentication Cache
```bash
cd api/MCP
rm -f .mcp_token
# This will force re-authentication on next run
```

## 📋 Prevention Tips

1. **Use virtual environments** to avoid dependency conflicts
2. **Keep credentials secure** - don't commit `.env` files
3. **Test changes** with the validation script before deploying
4. **Monitor logs** regularly for early issue detection
5. **Update dependencies** to get security fixes and improvements

## 🎯 Advanced Troubleshooting

### Network Issues
```bash
# Check if port is accessible
telnet localhost 8000

# Check firewall rules (macOS)
sudo pfctl -s rules | grep 8000

# Check network connectivity
ping localhost
```

### Process Monitoring
```bash
# Check if MCP is running
ps aux | grep python

# Check API server
ps aux | grep uvicorn

# Port usage
lsof -i :8000
```

### Database Issues
If you suspect database problems:

1. **Check API database connection**
2. **Verify API server logs for database errors**
3. **Test API endpoints directly** (bypass MCP)

### Performance Profiling
```bash
# Install profiling tools
pip install line_profiler memory_profiler

# Profile the MCP server
python -m cProfile -o profile.stats -m MCP --verbose
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative'); p.print_stats(20)"
```

---

**Still having issues?** Run the validation script first, then check the [documentation](README.md) or [quick start guide](QUICK_START.md) for additional guidance.
