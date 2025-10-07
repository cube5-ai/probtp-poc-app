"""Gemini client utilities for report generation."""
import os
from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig
from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
from dotenv import load_dotenv
load_dotenv()

# Global client instance (singleton pattern)
_client_instance = None
_client_instance_no_vertex = None


def get_gemini_client() -> genai.Client:
    """Get or create singleton Gemini client with Vertex AI configuration."""
    global _client_instance
    if _client_instance is None:
        # Optional: instrument with OpenInference for tracing
        try:
            GoogleGenAIInstrumentor().instrument()
        except Exception:
            pass  # Instrumentation is optional

        _client_instance = genai.Client(
            vertexai=True,
            project=os.getenv("GCP_PROJECT_ID", "probtp-poc-prod"),
            location="global",
        )
    return _client_instance


def get_gemini_client_no_vertex() -> genai.Client:
    """Get or create singleton Gemini client with Vertex AI configuration."""
    global _client_instance_no_vertex
    if _client_instance is None:
        # Optional: instrument with OpenInference for tracing
        try:
            GoogleGenAIInstrumentor().instrument()
        except Exception:
            pass  # Instrumentation is optional

        _client_instance_no_vertex = genai.Client(
            vertexai=False,
            api_key=os.getenv("GEMINI_API_KEY"),
        )
    return _client_instance_no_vertex


async def generate_with_reasoning(
    prompt: str,
    model: str = "gemini-2.5-flash",
    thinking_budget: int = 4096,
    temperature: float = 0.3,
    max_output_tokens: int = 20000,
    response_mime_type: str = "text/plain",
    response_schema: dict | None = None,
    use_vertex: bool = True,
) -> str:
    """
    Generate content with Gemini using reasoning mode (high thinking budget).

    Args:
        prompt: The prompt to send to Gemini
        model: Model name (default: gemini-2.5-flash)
        thinking_budget: Thinking budget for reasoning (default: 4096)
        temperature: Temperature for generation (default: 0.3)
        max_output_tokens: Maximum tokens to generate (default: 8000)
        response_mime_type: Response format (default: text/plain)
        response_schema: Optional Pydantic schema for structured JSON output
        use_vertex: Use Vertex AI (True) or Gemini API (False) (default: True)

    Returns:
        Generated text response
    """
    # Create client based on use_vertex flag
    client = get_gemini_client() if use_vertex else get_gemini_client_no_vertex()


    config_params = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "thinking_config": ThinkingConfig(thinking_budget=thinking_budget),
    }

    # Add response format if JSON schema provided
    if response_schema:
        config_params["response_mime_type"] = "application/json"
        config_params["response_schema"] = response_schema
    elif response_mime_type != "text/plain":
        config_params["response_mime_type"] = response_mime_type

    response = await client.aio.models.generate_content(
    model=model,
        contents=prompt,
        config=GenerateContentConfig(**config_params)
    )



    return getattr(response, "text", "").strip()
