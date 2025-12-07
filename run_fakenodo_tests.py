#!/usr/bin/env python
"""
Standalone test runner for Fakenodo HTTP tests.
This avoids dependency issues by directly importing and testing.
"""
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
sys.path.insert(0, os.path.dirname(__file__))

# Try to run the tests
if __name__ == '__main__':
    try:
        import pytest
        # Run only the Fakenodo HTTP tests
        exit_code = pytest.main([
            'app/modules/fakenodo/tests/test_routes.py',
            '-v',
            '--tb=short',
        ])
        sys.exit(exit_code)
    except ImportError as e:
        print(f"ERROR: Missing required module: {e}")
        print("Please ensure all dependencies are installed:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
