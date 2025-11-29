#!/usr/bin/env python3
"""
Script to fix the malformed auth.py file.
"""

import re

def fix_auth_router():
    """Fix the auth.py file"""
    
    with open('api/routers/auth.py', 'r') as f:
        content = f.read()
    
    # Fix malformed lines
    content = re.sub(
        r'from core.services\.tenant_database_manager import tenant_db_manager    tenant_    try:',
        'from core.services.tenant_database_manager import tenant_db_manager\n    tenant_db = tenant_db_manager.get_tenant_session(current_user.tenant_id)()\n    try:',
        content
    )
    
    content = re.sub(
        r'# Log audit event in tenant database as well    tenant_db = tenant_db_manager\.get_tenant_session\(current_user\.tenant_id\)\(\)',
        '# Log audit event in tenant database as well\n    tenant_db = tenant_db_manager.get_tenant_session(current_user.tenant_id)()',
        content
    )
    
    # Fix any remaining malformed tenant_ lines
    content = re.sub(
        r'tenant_    try:',
        'tenant_db = tenant_session()\n    try:',
        content
    )
    
    # Fix any remaining malformed tenant_ lines with different patterns
    content = re.sub(
        r'tenant_        try:',
        'tenant_db = tenant_session()\n        try:',
        content
    )
    
    with open('api/routers/auth.py', 'w') as f:
        f.write(content)
    
    print("✅ Fixed auth router")

if __name__ == "__main__":
    fix_auth_router() 