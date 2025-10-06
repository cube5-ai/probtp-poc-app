"""
AI Schema Service
Handles AI-powered schema refinement using Google Gemini
"""
import json
import logging
import os
from typing import Dict, Any

from google import genai

logger = logging.getLogger(__name__)


class AISchemaService:
    """Service for AI-powered schema operations"""
    
    def __init__(self):
        """Initialize the AI service with Gemini client"""
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize Gemini client with Vertex AI"""
        try:
            self.client = genai.Client(
                vertexai=True,
                project=os.getenv("FIREBASE_PROJECT_ID", "probtp-poc-prod"),
                location="global",
            )
            logger.info("Gemini client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise
    
    def refine_schema(
        self, 
        schema_definition: Dict[str, Any], 
        instruction: str
    ) -> Dict[str, Any]:
        """
        Refine a schema definition using AI based on user instruction.
        
        Args:
            schema_definition: Current JSON schema definition
            instruction: User instruction for refinement
            
        Returns:
            Dict[str, Any]: Refined schema definition
            
        Raises:
            ValueError: If refinement fails or produces invalid schema
        """
        logger.info("=" * 80)
        logger.info("Starting schema refinement")
        logger.info(f"Input schema: {json.dumps(schema_definition, indent=2)}")
        logger.info(f"Instruction: {instruction}")
        
        if not self.client:
            logger.error("AI client not initialized")
            raise ValueError("AI client not initialized")
        
        # Construct the prompt for Gemini
        prompt = self._build_refinement_prompt(schema_definition, instruction)
        logger.info(f"Generated prompt length: {len(prompt)} characters")
        logger.debug(f"Full prompt:\n{prompt}")
        
        try:
            # Call Gemini API
            logger.info("Calling Gemini API...")
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={
                    "temperature": 0.3,  # Lower temperature for more consistent output
                    "max_output_tokens": 8192,
                    "response_mime_type": "application/json",  # Request JSON response
                }
            )
            logger.info("Received response from Gemini API")
            
            # Extract and parse the response
            logger.info("Parsing AI response...")
            refined_schema = self._parse_response(response)
            logger.info(f"Parsed schema: {json.dumps(refined_schema, indent=2)}")
            
            # Validate the refined schema
            logger.info("Validating refined schema structure...")
            self._validate_schema_structure(refined_schema)
            
            logger.info("Schema refined successfully!")
            logger.info("=" * 80)
            return refined_schema
            
        except Exception as e:
            logger.error(f"Schema refinement failed: {e}", exc_info=True)
            logger.error("=" * 80)
            raise ValueError(f"Failed to refine schema: {str(e)}")
    
    def _build_refinement_prompt(
        self, 
        schema_definition: Dict[str, Any], 
        instruction: str
    ) -> str:
        """Build the prompt for Gemini"""
        schema_json = json.dumps(schema_definition, indent=2)
        
        prompt = f"""You are a JSON schema expert. Your task is to refine a JSON schema based on user instructions.

Current Schema:
```json
{schema_json}
```

User Instruction:
{instruction}

Instructions:
1. Analyze the current schema and the user's instruction carefully
2. Modify the schema according to the instruction while maintaining valid JSON Schema format
3. Preserve existing fields unless explicitly asked to remove them
4. Ensure all field names are descriptive and follow camelCase convention
5. Add appropriate descriptions to new fields
6. Maintain the schema structure with "type", "properties", and optionally "required" arrays
7. If the schema has an "x-order" array, preserve it and update it to include any new fields you add
8. If the user's instruction includes reordering (e.g., "move X before Y", "reorder fields"), update the "x-order" array accordingly
9. The "x-order" array should list field names in the order they should appear in the UI
10. Return ONLY the refined schema as valid JSON, no explanations or markdown

Return the refined schema in this exact format:
{{
  "type": "object",
  "properties": {{
    "fieldName": {{
      "type": "string|number|boolean|object|array",
      "description": "field description"
    }}
  }},
  "required": ["requiredField1", "requiredField2"],
  "x-order": ["fieldName1", "fieldName2", "fieldName3"]
}}

IMPORTANT: 
- Always include "x-order" array with ALL field names in the desired display order
- For nested objects, include "x-order" within the nested object properties
- If user requests reordering, adjust the "x-order" array accordingly
- For nested objects, include "properties" and optionally "x-order" within the field definition
- For arrays, include "items" with the array element type
"""
        return prompt
    
    def _parse_response(self, response: Any) -> Dict[str, Any]:
        """Parse the Gemini response and extract the schema"""
        try:
            logger.info(f"Response type: {type(response)}")
            logger.info(f"Response attributes: {dir(response)}")
            
            # Get the text content from response
            text = None
            if hasattr(response, 'text'):
                text = response.text
                logger.info(f"Extracted text from response.text")
            elif hasattr(response, 'candidates') and response.candidates:
                text = response.candidates[0].content.parts[0].text
                logger.info(f"Extracted text from response.candidates")
            else:
                logger.error(f"Unable to extract text from response. Response: {response}")
                raise ValueError("Unable to extract text from response")
            
            logger.info(f"Raw AI response text:\n{text}")
            logger.info(f"Response length: {len(text)} characters")
            
            # Clean up the response (remove markdown code blocks if present)
            text = text.strip()
            original_text = text
            if text.startswith("```json"):
                text = text[7:]
                logger.info("Removed ```json prefix")
            if text.startswith("```"):
                text = text[3:]
                logger.info("Removed ``` prefix")
            if text.endswith("```"):
                text = text[:-3]
                logger.info("Removed ``` suffix")
            text = text.strip()
            
            if text != original_text:
                logger.info(f"Cleaned text:\n{text}")
            
            # Parse JSON
            logger.info("Attempting to parse JSON...")
            refined_schema = json.loads(text)
            logger.info(f"Successfully parsed JSON with {len(refined_schema)} top-level keys")
            logger.info(f"Keys: {list(refined_schema.keys())}")
            return refined_schema
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.error(f"Text that failed to parse:\n{text}")
            raise ValueError(f"AI returned invalid JSON: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}", exc_info=True)
            raise ValueError(f"Failed to parse AI response: {str(e)}")
    
    def _validate_schema_structure(self, schema: Dict[str, Any]) -> None:
        """Validate that the schema has required structure"""
        logger.info("Validating schema structure...")
        logger.info(f"Schema type: {type(schema)}")
        logger.info(f"Schema keys: {list(schema.keys()) if isinstance(schema, dict) else 'N/A'}")
        
        if not isinstance(schema, dict):
            logger.error(f"Schema is not a dictionary: {type(schema)}")
            raise ValueError("Schema must be a dictionary")
        
        if "type" not in schema:
            logger.error("Schema missing 'type' field")
            raise ValueError("Schema must have a 'type' field")
        
        logger.info(f"Schema type value: {schema.get('type')}")
        
        if schema.get("type") == "object" and "properties" not in schema:
            logger.error("Object schema missing 'properties' field")
            raise ValueError("Object schema must have a 'properties' field")
        
        if "properties" in schema:
            if not isinstance(schema["properties"], dict):
                logger.error(f"'properties' is not a dict: {type(schema['properties'])}")
                raise ValueError("'properties' must be a dictionary")
            logger.info(f"Schema has {len(schema['properties'])} properties")
            logger.info(f"Property names: {list(schema['properties'].keys())}")
        
        # Validate required field if present
        if "required" in schema:
            if not isinstance(schema["required"], list):
                logger.error(f"'required' is not a list: {type(schema['required'])}")
                raise ValueError("'required' must be an array")
            logger.info(f"Schema has {len(schema['required'])} required fields: {schema['required']}")
        
        logger.info("Schema structure validation passed!")

