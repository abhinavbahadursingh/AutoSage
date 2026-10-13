#!/usr/bin/env python
"""Test the enhanced dataset tools."""
import sys
sys.path.insert(0, r"D:\autoSage\backend")

from app.engine.tools.registry import get_default_registry
from app.engine.tools.builtins import register_builtins

registry = get_default_registry()
print("Tools registered:", registry.names())
print()

# Test search_dataset with catalog query
result = registry.execute("search_dataset", query="iris classification")
print("Search iris:", result)
print()

result = registry.execute("search_dataset", query="housing regression")
print("Search housing:", result)
print()

# Test download_dataset with catalog entry
result = registry.execute("download_dataset", dataset_id="ds-mock-1")
print("Download ds-mock-1:", result)
print()

# Test download_dataset with web ID (should fail gracefully)
result = registry.execute("download_dataset", dataset_id="web-0")
print("Download web-0:", result)
print()

# Test upload detection
import os
uploads_dir = r"D:\autoSage\data\uploads"
if os.path.isdir(uploads_dir):
    print("Uploads dir contents:", os.listdir(uploads_dir))
else:
    print("Uploads dir does not exist")

print("\nAll tests done!")