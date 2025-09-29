#!/usr/bin/env python3
"""
Simple test to verify PyMuPDF works for document parsing
"""

import pymupdf  # PyMuPDF
import os

# Test basic initialization
print("Testing PyMuPDF initialization...")
print(f"✓ PyMuPDF version: {pymupdf.version[0]}")

# Create a simple test PDF
test_html = """
<html>
<body>
<h1>Test Document</h1>
<p>This is a test paragraph.</p>
<ul>
    <li>First item</li>
    <li>Second item</li>
</ul>
<table>
    <tr><th>Header 1</th><th>Header 2</th></tr>
    <tr><td>Cell 1</td><td>Cell 2</td></tr>
</table>
</body>
</html>
"""

# Save test HTML
with open("test.html", "w") as f:
    f.write(test_html)

print("\nCreating PDF from HTML...")
# Create PDF from HTML
doc = pymupdf.open()  # Create new PDF
page = doc.new_page()  # Add a page

# Insert HTML content
page.insert_htmlbox(pymupdf.Rect(50, 50, 550, 750), test_html)
doc.save("test.pdf")
doc.close()

print("✓ PDF created successfully")

# Now test reading the PDF
print("\nTesting PDF reading and text extraction...")
doc = pymupdf.open("test.pdf")

if len(doc) > 0:
    print(f"✓ Document opened successfully ({len(doc)} page(s))")

    # Extract text from first page
    page = doc[0]
    text = page.get_text()

    print("\nExtracted text:")
    print("-" * 40)
    print(text)
    print("-" * 40)

    # Get page metadata
    metadata = doc.metadata
    print("\nDocument metadata:")
    for key, value in metadata.items():
        if value:
            print(f"  {key}: {value}")

    # Extract text as HTML (PyMuPDF doesn't have direct markdown export)
    print("\nExtracting as HTML...")
    html_text = page.get_text("html")
    print("HTML output (first 500 chars):")
    print("-" * 40)
    print(html_text[:500] + "..." if len(html_text) > 500 else html_text)
    print("-" * 40)

    # Also try dict format for structured data
    print("\nExtracting as structured dict...")
    dict_data = page.get_text("dict")
    print(f"✓ Extracted {len(dict_data.get('blocks', []))} text blocks")

    doc.close()
    print("\n✓ Document processing complete")
else:
    print("✗ Failed to read document")

# Clean up
os.remove("test.html")
os.remove("test.pdf")
print("\n✓ Test complete!")
