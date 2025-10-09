import os
from pathlib import Path
from dotenv import load_dotenv
import json
from typing import Any
from landingai_ade import LandingAIADE

load_dotenv()

LANDING_AI_API_KEY = os.getenv("LANDING_AI_API_KEY", "NO API KEY")

print(f"LANDING_AI_API_KEY: {LANDING_AI_API_KEY}")


def parse_document(file_path: str)->dict[str, Any]:
    """
    Parse a document using the LandingAI ADE API
    """
    # Initialize the LandingAI ADE client
    client = LandingAIADE(apikey=LANDING_AI_API_KEY)

    # Parse the document using the latest DPT model
    parse_response = client.parse(
        document=Path(file_path),
        model="dpt-2-latest",
    )

    return json.loads(parse_response.model_dump_json())



def write_to_markdown(response, file_path: str):
    """
    Convert the LandingAI ADE response to markdown
    """
    with open(file_path, "w", encoding="utf-8") as f:
        # The response object has a markdown attribute
        if response.get("markdown"):
            f.write(response.get("markdown"))
        else:
            # Fallback: write string representation
            f.write(str(response.get("chunks")))

