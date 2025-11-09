#!/usr/bin/env python3
"""
Test script to verify S3 download with path prefix from export destination.

This script simulates the S3 key construction logic used in the download endpoint.
"""

def construct_s3_key(file_path: str, tenant_id: int, path_prefix: str = None) -> str:
    """
    Construct S3 key with path prefix from export destination.
    
    Args:
        file_path: The file path stored in the database
        tenant_id: The tenant ID
        path_prefix: Optional path prefix from export destination
        
    Returns:
        The full S3 key to use for download
    """
    import re
    
    s3_key = file_path
    
    # Remove local file system prefixes if present
    # Common patterns: api/batch_files/tenant_X/, attachments/tenant_X/, etc.
    local_prefixes = [
        r'^api/batch_files/tenant_\d+/',
        r'^attachments/tenant_\d+/',
        r'^tenant_\d+/',
    ]
    
    for pattern in local_prefixes:
        s3_key = re.sub(pattern, '', s3_key)
    
    # Now check if we need to add a prefix
    # If the key already starts with the path_prefix, don't add it again
    if path_prefix:
        normalized_prefix = path_prefix.strip('/')
        if normalized_prefix and not s3_key.startswith(f'{normalized_prefix}/'):
            s3_key = f'{normalized_prefix}/{s3_key}'
    
    return s3_key


def main():
    """Test various scenarios"""
    
    print("Testing S3 key construction with path prefix\n")
    print("=" * 80)
    
    # Test case 1: File path without any prefix, with export destination prefix
    file_path = "Receipt-GoodLife.jpg"
    tenant_id = 1
    path_prefix = "f06221e5-da6b-4944-bb5d-35bd9dc0cd70"
    
    result = construct_s3_key(file_path, tenant_id, path_prefix)
    print(f"\nTest 1: File with export destination prefix")
    print(f"  Input file_path: {file_path}")
    print(f"  Tenant ID: {tenant_id}")
    print(f"  Path prefix: {path_prefix}")
    print(f"  Expected: f06221e5-da6b-4944-bb5d-35bd9dc0cd70/Receipt-GoodLife.jpg")
    print(f"  Result:   {result}")
    print(f"  Status:   {'✓ PASS' if result == 'f06221e5-da6b-4944-bb5d-35bd9dc0cd70/Receipt-GoodLife.jpg' else '✗ FAIL'}")
    
    # Test case 2: File path with tenant prefix already
    file_path = "tenant_1/expenses/123_receipt.jpg"
    tenant_id = 1
    path_prefix = "f06221e5-da6b-4944-bb5d-35bd9dc0cd70"
    
    result = construct_s3_key(file_path, tenant_id, path_prefix)
    print(f"\nTest 2: File with tenant prefix already")
    print(f"  Input file_path: {file_path}")
    print(f"  Tenant ID: {tenant_id}")
    print(f"  Path prefix: {path_prefix}")
    print(f"  Expected: tenant_1/expenses/123_receipt.jpg")
    print(f"  Result:   {result}")
    print(f"  Status:   {'✓ PASS' if result == 'tenant_1/expenses/123_receipt.jpg' else '✗ FAIL'}")
    
    # Test case 3: File path with structure (has /), no export destination prefix
    file_path = "expenses/456_receipt.jpg"
    tenant_id = 2
    path_prefix = None
    
    result = construct_s3_key(file_path, tenant_id, path_prefix)
    print(f"\nTest 3: File with structure (has /), no export destination prefix")
    print(f"  Input file_path: {file_path}")
    print(f"  Tenant ID: {tenant_id}")
    print(f"  Path prefix: {path_prefix}")
    print(f"  Expected: expenses/456_receipt.jpg (unchanged - already has structure)")
    print(f"  Result:   {result}")
    print(f"  Status:   {'✓ PASS' if result == 'expenses/456_receipt.jpg' else '✗ FAIL'}")
    
    # Test case 4: Path prefix with trailing slash
    file_path = "Receipt-Test.pdf"
    tenant_id = 1
    path_prefix = "f06221e5-da6b-4944-bb5d-35bd9dc0cd70/"
    
    result = construct_s3_key(file_path, tenant_id, path_prefix)
    print(f"\nTest 4: Path prefix with trailing slash")
    print(f"  Input file_path: {file_path}")
    print(f"  Tenant ID: {tenant_id}")
    print(f"  Path prefix: {path_prefix}")
    print(f"  Expected: f06221e5-da6b-4944-bb5d-35bd9dc0cd70/Receipt-Test.pdf")
    print(f"  Result:   {result}")
    print(f"  Status:   {'✓ PASS' if result == 'f06221e5-da6b-4944-bb5d-35bd9dc0cd70/Receipt-Test.pdf' else '✗ FAIL'}")
    
    # Test case 5: Path prefix with leading slash
    file_path = "Receipt-Test2.pdf"
    tenant_id = 1
    path_prefix = "/f06221e5-da6b-4944-bb5d-35bd9dc0cd70"
    
    result = construct_s3_key(file_path, tenant_id, path_prefix)
    print(f"\nTest 5: Path prefix with leading slash")
    print(f"  Input file_path: {file_path}")
    print(f"  Tenant ID: {tenant_id}")
    print(f"  Path prefix: {path_prefix}")
    print(f"  Expected: f06221e5-da6b-4944-bb5d-35bd9dc0cd70/Receipt-Test2.pdf")
    print(f"  Result:   {result}")
    print(f"  Status:   {'✓ PASS' if result == 'f06221e5-da6b-4944-bb5d-35bd9dc0cd70/Receipt-Test2.pdf' else '✗ FAIL'}")
    
    # Test case 6: Batch file with local path prefix
    file_path = "api/batch_files/tenant_1/f06221e5-da6b-4944-bb5d-35bd9dc0cd70/f06221e5-da6b-4944-bb5d-35bd9dc0cd70_001_20251109021726.jpeg"
    tenant_id = 1
    path_prefix = "f06221e5-da6b-4944-bb5d-35bd9dc0cd70"
    
    result = construct_s3_key(file_path, tenant_id, path_prefix)
    print(f"\nTest 6: Batch file with local path prefix")
    print(f"  Input file_path: {file_path}")
    print(f"  Tenant ID: {tenant_id}")
    print(f"  Path prefix: {path_prefix}")
    print(f"  Expected: f06221e5-da6b-4944-bb5d-35bd9dc0cd70/f06221e5-da6b-4944-bb5d-35bd9dc0cd70_001_20251109021726.jpeg")
    print(f"  Result:   {result}")
    print(f"  Status:   {'✓ PASS' if result == 'f06221e5-da6b-4944-bb5d-35bd9dc0cd70/f06221e5-da6b-4944-bb5d-35bd9dc0cd70_001_20251109021726.jpeg' else '✗ FAIL'}")
    
    # Test case 7: Batch file without path prefix (should strip local prefix only)
    file_path = "api/batch_files/tenant_2/expenses/receipt.jpg"
    tenant_id = 2
    path_prefix = None
    
    result = construct_s3_key(file_path, tenant_id, path_prefix)
    print(f"\nTest 7: Batch file without path prefix")
    print(f"  Input file_path: {file_path}")
    print(f"  Tenant ID: {tenant_id}")
    print(f"  Path prefix: {path_prefix}")
    print(f"  Expected: expenses/receipt.jpg")
    print(f"  Result:   {result}")
    print(f"  Status:   {'✓ PASS' if result == 'expenses/receipt.jpg' else '✗ FAIL'}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
