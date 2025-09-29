
import posix
import requests
from dotenv import load_dotenv
import os
load_dotenv()

EXTEND_API_KEY = os.getenv("EXTEND_API_KEY", "NO API KEY")

print(f"EXTEND_API_KEY: {EXTEND_API_KEY}")


def upload_file(file_path: str):
    """
    Upload a file to the Extend API
    """

    with open(file_path, "rb") as f:
        files = {"file": f}
        response = requests.post(
                "https://api.extend.ai/files/upload",
                files=files,
                headers={
                    "Authorization": f"Bearer {EXTEND_API_KEY}",
                    "x-extend-api-version": "2025-04-21",
                }
            )
        return response.json()

def parse_document(file_path: str):
    """
    Parse a document using the Extend API
    """


    file_id = upload_file(file_path)["file"]["id"]

    response = requests.post(
    "https://api.extend.ai/parse",
        json={
        "file": {
                "fileId": file_id
        },
        "config": {
                "target": "spatial",
                "blockOptions": {
                        "text": {
                                "signatureDetectionEnabled": True
                        },
                        "tables": {
                                "enabled": True,
                                "targetFormat": "markdown",
                                "tableHeaderContinuationEnabled": True
                        },
                        "figures": {
                                "enabled": True,
                                "figureImageClippingEnabled": True
                        }
                },
                "advancedOptions": {
                        "agenticOcrEnabled": True,
                        "pageRotationEnabled": True
                },
                "chunkingStrategy": {
                        "type": "page"
                }
        }
        },
        headers={
            "Authorization": f"Bearer {EXTEND_API_KEY}",
            "Content-Type": "application/json",
            "x-extend-api-version": "2025-04-21"
            },
    )

    return response.json()


def write_to_markdown(response: dict, file_path):
    """
    Convert the Extend API response to markdown
    """
    with open(file_path, "w") as f:
        for chunk in response.get("chunks", []):
            if chunk.get("type") == "page":
                f.write(f"---\n*Page {chunk.get('metadata').get('pageRange').get('start')}*\n---\n\n\n")
            f.write(chunk.get("content", ""))
