#!/usr/bin/env python3
"""
Script to fix tenant context issues in all routers.
This script removes manual set_tenant_context calls and adds get_db dependencies.
"""

import os
import re

def fix_router_file(file_path):
    """Fix tenant context issues in a router file"""
    print(f"Fixing {file_path}...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Remove set_tenant_context from imports
    content = re.sub(
        r'from core.models\.database import get_db, get_master_db, set_tenant_context',
        'from core.models.database import get_db, get_master_db',
        content
    )
    content = re.sub(
        r'from core.models\.database import get_db, set_tenant_context',
        'from core.models.database import get_db',
        content
    )
    
    # Pattern to match function definitions that need fixing
    pattern = r'async def (\w+)\([^)]*\):\s*\n\s*# Manually set tenant context and get tenant database\s*\n\s*set_tenant_context\(current_user\.tenant_id\)\s*\n\s*tenant_session = tenant_db_manager\.get_tenant_session\(current_user\.tenant_id\)\s*\n\s*db = tenant_session\(\)'
    
    def replace_function(match):
        func_name = match.group(1)
        # Find the function signature
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if f'async def {func_name}(' in line:
                # Add db: Session = Depends(get_db) to the function signature
                if 'db: Session = Depends(get_db)' not in line:
                    # Find the closing parenthesis
                    if line.endswith('):'):
                        # Insert db parameter before the closing parenthesis
                        line = line.replace('):', ', db: Session = Depends(get_db)):')
                    else:
                        # Add to the next line
                        lines[i+1] = '    db: Session = Depends(get_db),' + lines[i+1]
                break
        
        # Remove the manual tenant context setting lines
        return ''
    
    # Apply the replacement
    content = re.sub(pattern, replace_function, content, flags=re.MULTILINE | re.DOTALL)
    
    # Also remove any remaining set_tenant_context calls
    content = re.sub(
        r'\s*set_tenant_context\(current_user\.tenant_id\)\s*\n',
        '',
        content
    )
    
    # Remove tenant_session lines
    content = re.sub(
        r'\s*tenant_session = tenant_db_manager\.get_tenant_session\(current_user\.tenant_id\)\s*\n',
        '',
        content
    )
    
    # Remove db = tenant_session() lines
    content = re.sub(
        r'\s*db = tenant_session\(\)\s*\n',
        '',
        content
    )
    
    # Remove finally: db.close() blocks
    content = re.sub(
        r'\s*finally:\s*\n\s*db\.close\(\)\s*\n',
        '',
        content
    )
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def main():
    """Fix all router files"""
    router_files = [
        'api/routers/clients.py',
        'api/routers/invoices.py',
        'api/routers/payments.py',
        'api/routers/currency.py',
        'api/routers/email.py',
        'api/routers/crm.py',
        'api/routers/notifications.py',
        'api/routers/ai.py',
        'api/routers/auth.py',
        'api/routers/ai_config.py',
        'api/routers/settings.py',
        'api/routers/audit_log.py',
        'api/routers/discount_rules.py',
    ]
    
    for file_path in router_files:
        if os.path.exists(file_path):
            fix_router_file(file_path)
        else:
            print(f"⚠️ File {file_path} not found, skipping")

if __name__ == "__main__":
    main() 