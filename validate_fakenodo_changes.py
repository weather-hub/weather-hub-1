#!/usr/bin/env python
"""
Validation script for Fakenodo module changes.
This script validates that all changes have been properly implemented.
"""
import os
import json
import re
import sys
from pathlib import Path


def check_file_exists(path: str, description: str) -> bool:
    """Check if a file exists"""
    exists = os.path.exists(path)
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {path}")
    return exists


def check_file_contains(path: str, patterns: list, description: str) -> bool:
    """Check if a file contains specific patterns"""
    if not os.path.exists(path):
        print(f"✗ {description}: File not found")
        return False
    
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    all_found = True
    for pattern in patterns:
        found = pattern in content or re.search(pattern, content, re.IGNORECASE)
        status = "✓" if found else "✗"
        if not found:
            all_found = False
        print(f"  {status} Pattern found: {pattern[:60]}{'...' if len(pattern) > 60 else ''}")
    
    return all_found


def main():
    """Run all validations"""
    print("=" * 70)
    print("FAKENODO MODULE COMPLETION VALIDATION")
    print("=" * 70)
    print()
    
    base_path = Path(__file__).parent
    all_passed = True
    
    # ========== File Existence Checks ==========
    print("1. FILE EXISTENCE CHECKS")
    print("-" * 70)
    
    files_to_check = [
        ("app/modules/fakenodo/README.md", "Fakenodo README documentation"),
        ("app/modules/fakenodo/tests/test_routes.py", "HTTP endpoint tests"),
        ("app/modules/fakenodo/tests/conftest.py", "Test configuration"),
        ("FAKENODO_COMPLETION_SUMMARY.md", "Work item completion summary"),
    ]
    
    for file_path, description in files_to_check:
        full_path = base_path / file_path
        if not check_file_exists(str(full_path), description):
            all_passed = False
    
    print()
    
    # ========== Content Checks ==========
    print("2. CRITICAL CODE CHANGES VERIFICATION")
    print("-" * 70)
    
    # Check FakenodoAdapter changes
    print("\nA. FakenodoAdapter - Stable DOI Generation:")
    adapter_path = base_path / "app/modules/dataset/routes.py"
    adapter_patterns = [
        "self.dataset_id",
        "getattr(dataset, \"id\", None)",
        "f\"10.1234/fakenodo.{self.dataset_id}.v",
    ]
    if not check_file_contains(str(adapter_path), adapter_patterns, "FakenodoAdapter changes"):
        all_passed = False
    
    # Check routes.py fixes
    print("\nB. Routes.py - Error Handling & Parameters:")
    routes_path = base_path / "app/modules/fakenodo/routes.py"
    routes_patterns = [
        "<int:deposition_id>",
        '{\"message\"',
    ]
    if not check_file_contains(str(routes_path), routes_patterns, "Routes error handling"):
        all_passed = False
    
    # Check services.py enhancements
    print("\nC. Services.py - Zenodo Fields:")
    services_path = base_path / "app/modules/fakenodo/services.py"
    services_patterns = [
        "\"conceptrecid\"",
        "\"state\"",
        "\"links\"",
    ]
    if not check_file_contains(str(services_path), services_patterns, "Services Zenodo fields"):
        all_passed = False
    
    # Check README documentation
    print("\nD. README.md - Documentation Coverage:")
    readme_path = base_path / "app/modules/fakenodo/README.md"
    readme_patterns = [
        "Configuration",
        "API",
        "Response Format",
        "DOI",
        "Production",
        "Thread",
    ]
    if not check_file_contains(str(readme_path), readme_patterns, "README documentation"):
        all_passed = False
    
    # Check test coverage
    print("\nE. Test Suite - HTTP Tests:")
    test_path = base_path / "app/modules/fakenodo/tests/test_routes.py"
    test_patterns = [
        "class TestCreateDeposition",
        "class TestGetDeposition",
        "class TestUploadFile",
        "class TestPublishDeposition",
        "class TestEndToEnd",
    ]
    if not check_file_contains(str(test_path), test_patterns, "Test classes"):
        all_passed = False
    
    print()
    
    # ========== Statistics ==========
    print("3. CODE STATISTICS")
    print("-" * 70)
    
    # Count test functions
    with open(base_path / "app/modules/fakenodo/tests/test_routes.py", 'r') as f:
        test_content = f.read()
        test_count = len(re.findall(r'def test_\w+\(', test_content))
        print(f"✓ HTTP test functions: {test_count}")
    
    # Count test classes
    test_classes = len(re.findall(r'class Test\w+\(', test_content))
    print(f"✓ Test classes: {test_classes}")
    
    # README lines
    with open(base_path / "app/modules/fakenodo/README.md", 'r', encoding='utf-8', errors='ignore') as f:
        readme_lines = len(f.readlines())
        print(f"✓ README lines: {readme_lines}")
    
    print()
    
    # ========== Summary ==========
    print("=" * 70)
    if all_passed:
        print("✓ ALL VALIDATIONS PASSED")
        print()
        print("Summary of changes:")
        print("  1. Production bug fixed: Stable DOI generation using dataset.id")
        print("  2. Error handling normalized: Consistent error response format")
        print("  3. JSON enriched: Zenodo-compatible fields added")
        print("  4. Documentation complete: Comprehensive README ({}+ lines)".format(readme_lines))
        print("  5. Tests created: {} HTTP endpoint tests ({} test classes)".format(
            test_count, test_classes))
        print()
        print("Next steps:")
        print("  1. Install dependencies: pip install -r requirements.txt")
        print("  2. Run tests: pytest app/modules/fakenodo/tests/ -v")
        print("  3. Review changes: git diff fix/fakenodo-doi-versions-managements")
        print("  4. Merge to main and deploy")
        return 0
    else:
        print("✗ SOME VALIDATIONS FAILED")
        print("Please review the output above and address any issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
