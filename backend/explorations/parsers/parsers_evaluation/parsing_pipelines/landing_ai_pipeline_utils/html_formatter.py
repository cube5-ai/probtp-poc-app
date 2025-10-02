"""HTML formatting utilities for better LLM prompt readability."""
from html.parser import HTMLParser
from io import StringIO


class HTMLFormatter(HTMLParser):
    """Format HTML with proper indentation for better readability."""
    
    def __init__(self):
        super().__init__()
        self.output = StringIO()
        self.indent_level = 0
        self.indent_string = "  "
        self.last_was_end_tag = False
        
    def handle_starttag(self, tag, attrs):
        # Add newline and indentation
        if self.last_was_end_tag:
            self.output.write("\n")
        self.output.write(self.indent_string * self.indent_level)
        
        # Write tag with attributes
        self.output.write(f"<{tag}")
        for attr_name, attr_value in attrs:
            self.output.write(f' {attr_name}="{attr_value}"')
        self.output.write(">")
        
        # Increase indent for nested tags
        if tag not in ['br', 'img', 'input', 'hr']:
            self.indent_level += 1
        
        self.last_was_end_tag = False
        
    def handle_endtag(self, tag):
        # Decrease indent
        if tag not in ['br', 'img', 'input', 'hr']:
            self.indent_level -= 1
        
        # Add newline and indentation for block-level end tags
        if tag in ['tr', 'table', 'div']:
            self.output.write("\n" + self.indent_string * self.indent_level)
        
        self.output.write(f"</{tag}>")
        self.last_was_end_tag = True
        
    def handle_data(self, data):
        # Clean up whitespace but preserve content
        cleaned = data.strip()
        if cleaned:
            self.output.write(cleaned)
        self.last_was_end_tag = False
        
    def get_formatted_html(self):
        return self.output.getvalue()


def format_html_for_llm(html_content: str) -> str:
    """
    Format HTML content for better LLM readability.
    
    Args:
        html_content: Raw HTML string
        
    Returns:
        Formatted HTML with proper indentation
    """
    try:
        formatter = HTMLFormatter()
        formatter.feed(html_content)
        return formatter.get_formatted_html()
    except Exception:
        # If formatting fails, return original
        return html_content

