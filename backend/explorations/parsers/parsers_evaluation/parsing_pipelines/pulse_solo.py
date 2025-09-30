import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

PULSE_API_KEY = os.getenv("PULSE_API_KEY", "NO API KEY")
BASE_URL = "https://dev.api.runpulse.com"

print(f"PULSE_API_KEY: {PULSE_API_KEY}")


def parse_document(file_path: str) -> dict:
    """
    Parse a document using the Pulse API
    Uploads the file and extracts content with figure extraction enabled
    """
    url = f"{BASE_URL}/extract"
    headers = {"x-api-key": PULSE_API_KEY}

    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'extract_figure': 'true',
                'figure_description': 'false',
                'return_html': 'false'
            }

            response = requests.post(url, files=files, data=data, headers=headers)
            response.raise_for_status()

        result = response.json()

        # Handle large documents (>70 pages) that return a URL
        if result.get('is_url'):
            print(f"Large document detected. Fetching from: {result['url']}")
            content_response = requests.get(result['url'])
            content_response.raise_for_status()
            result = content_response.json()

        # Wrap result in a standard format for consistency
        return {
            "content": result,
            "metadata": {
                "source": file_path,
                "parser": "pulse_solo"
            }
        }

    except requests.exceptions.RequestException as e:
        print(f"Error calling Pulse API for {file_path}: {e}")
        return {
            "content": {},
            "metadata": {
                "source": file_path,
                "parser": "pulse_solo",
                "error": str(e)
            }
        }
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return {
            "content": {},
            "metadata": {
                "source": file_path,
                "parser": "pulse_solo",
                "error": str(e)
            }
        }


def write_to_markdown(response: dict, file_path: str):
    """
    Convert the Pulse API response to markdown file
    """
    try:
        with open(file_path, "w", encoding='utf-8') as f:
            content = response.get("content", {})

            # Write metadata header
            metadata = response.get("metadata", {})
            f.write("# Pulse API Extraction\n\n")
            f.write(f"**Source:** {metadata.get('source', 'Unknown')}\n")
            f.write(f"**Parser:** {metadata.get('parser', 'pulse_solo')}\n\n")
            f.write("---\n\n")

            # Handle different possible response structures
            if isinstance(content, dict):
                # If content has a 'text' or 'markdown' field, use it
                if 'text' in content:
                    f.write(content['text'])
                elif 'markdown' in content:
                    f.write(content['markdown'])
                elif 'content' in content:
                    f.write(str(content['content']))
                else:
                    # Write the entire JSON as formatted markdown
                    f.write("## Extracted Content\n\n")
                    f.write("```json\n")
                    f.write(json.dumps(content, indent=2, ensure_ascii=False))
                    f.write("\n```\n")
            elif isinstance(content, str):
                f.write(content)
            else:
                f.write(str(content))

    except Exception as e:
        print(f"Error writing markdown to {file_path}: {e}")
