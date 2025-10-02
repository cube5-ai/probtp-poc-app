"""HTML formatting utilities for better LLM prompt readability."""
from html.parser import HTMLParser
from io import StringIO


class HTMLFormatter(HTMLParser):
    """Format HTML with proper indentation for better readability."""

    def __init__(self, remove_ids=False, truncate_tables=False, max_rows=4):
        super().__init__()
        self.output = StringIO()
        self.indent_level = 0
        self.indent_string = "  "
        self.last_was_end_tag = False
        self.remove_ids = remove_ids
        self.truncate_tables = truncate_tables
        self.max_rows = max_rows

        # Table truncation state
        self.in_table = False
        self.current_table_rows = []
        self.row_count = 0
        self.in_row = False
        self.current_row_content = StringIO()

    def handle_starttag(self, tag, attrs):
        # Handle table truncation
        if tag == 'table' and self.truncate_tables:
            self.in_table = True
            self.current_table_rows = []
            self.row_count = 0
        elif tag == 'tr' and self.in_table:
            self.in_row = True
            self.current_row_content = StringIO()

        # Filter out id attributes if requested
        if self.remove_ids:
            attrs = [(name, value) for name, value in attrs if name != 'id']

        # Store content for table rows when truncating
        if self.in_row and self.truncate_tables:
            # Add proper newline and indentation for row content
            if self.current_row_content.tell() != 0:  # Not the first element in row
                self.current_row_content.write("\n")
            self.current_row_content.write(self.indent_string * self.indent_level)
            self.current_row_content.write(f"<{tag}")
            for attr_name, attr_value in attrs:
                self.current_row_content.write(f' {attr_name}="{attr_value}"')
            self.current_row_content.write(">")
        else:
            # Add proper newline and indentation for normal output
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

        # Handle table truncation
        if tag == 'tr' and self.in_row and self.truncate_tables:
            # Complete the current row with proper formatting
            self.current_row_content.write("\n")
            self.current_row_content.write(self.indent_string * self.indent_level)
            self.current_row_content.write(f"</{tag}>")

            # Store the completed row
            self.current_table_rows.append(self.current_row_content.getvalue())
            self.row_count += 1
            self.in_row = False

        elif tag == 'table' and self.in_table and self.truncate_tables:
            # Output the truncated table
            self._output_truncated_table()
            # Add proper newline and indentation for table close
            self.output.write("\n")
            self.output.write(self.indent_string * self.indent_level)
            self.output.write(f"</{tag}>")
            self.in_table = False

        elif self.in_row and self.truncate_tables:
            # Add content to current row
            self.current_row_content.write(f"</{tag}>")

        else:
            # Normal processing
            if tag in ['tr', 'table', 'div']:
                # Add newline and indentation for block-level end tags
                self.output.write("\n")
                self.output.write(self.indent_string * self.indent_level)
            self.output.write(f"</{tag}>")

        self.last_was_end_tag = True

    def handle_data(self, data):
        # Clean up whitespace but preserve content
        cleaned = data.strip()
        if cleaned:
            if self.in_row and self.truncate_tables:
                self.current_row_content.write(cleaned)
            else:
                self.output.write(cleaned)
        self.last_was_end_tag = False

    def _output_truncated_table(self):
        """Output table with truncation if it has more than max_rows."""
        total_rows = len(self.current_table_rows)

        if total_rows <= self.max_rows * 2:
            # Table is small enough, output all rows
            for row in self.current_table_rows:
                self.output.write("\n")
                self.output.write(self.indent_string * self.indent_level)
                self.output.write(row)
        else:
            # Output first max_rows
            for i in range(self.max_rows):
                self.output.write("\n")
                self.output.write(self.indent_string * self.indent_level)
                self.output.write(self.current_table_rows[i])

            # Add ellipsis row
            self.output.write("\n")
            self.output.write(self.indent_string * self.indent_level)
            self.output.write("<tr>")
            self.output.write("\n")
            self.output.write(self.indent_string * (self.indent_level + 1))
            self.output.write("<td colspan='100%' style='text-align: center; font-style: italic;'>")
            self.output.write(f"... ({total_rows - 2 * self.max_rows} rows omitted) ...")
            self.output.write("</td>")
            self.output.write("\n")
            self.output.write(self.indent_string * self.indent_level)
            self.output.write("</tr>")

            # Output last max_rows
            for i in range(total_rows - self.max_rows, total_rows):
                self.output.write("\n")
                self.output.write(self.indent_string * self.indent_level)
                self.output.write(self.current_table_rows[i])

    def get_formatted_html(self):
        return self.output.getvalue()


def format_html_for_llm(html_content: str, remove_ids: bool = False, truncate_tables: bool = False, max_rows: int = 4) -> str:
    """
    Format HTML content for better LLM readability.

    Args:
        html_content: Raw HTML string
        remove_ids: Whether to remove id attributes from HTML elements
        truncate_tables: Whether to truncate long tables to show first/last rows with ellipsis
        max_rows: Number of rows to show at start and end when truncating tables

    Returns:
        Formatted HTML with proper indentation and optional modifications
    """
    try:
        formatter = HTMLFormatter(remove_ids=remove_ids, truncate_tables=truncate_tables, max_rows=max_rows)
        formatter.feed(html_content)
        return formatter.get_formatted_html()
    except Exception:
        # If formatting fails, return original
        return html_content
