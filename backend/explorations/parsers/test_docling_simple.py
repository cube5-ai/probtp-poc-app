#!/usr/bin/env python3
"""
Simple test to verify docling works despite NumPy warnings
"""

import warnings
# Suppress NumPy warnings temporarily
warnings.filterwarnings("ignore", message=".*NumPy.*")

from docling.document_converter import DocumentConverter

# Test basic initialization
print("Testing docling initialization...")
converter = DocumentConverter()
print("✓ DocumentConverter initialized successfully")

# Test with a simple HTML string
test_html = """
<html>
<body>
<h1>Test Document</h1>
<p>This is a test paragraph.</p>
</body>
</html>
"""

# Save test HTML
with open("test.html", "w") as f:
    f.write(test_html)

print("\nTesting document conversion...")
result = converter.convert(source="test.html")

if result and result.document:
    markdown = result.document.export_to_markdown()
    print("✓ Document converted successfully")
    print("\nMarkdown output:")
    print(markdown)
else:
    print("✗ Conversion failed")

# Clean up
import os
os.remove("test.html")
print("\n✓ Test complete!")