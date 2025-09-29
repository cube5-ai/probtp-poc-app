# Document Parsing with Mistral OCR - Report Generation Exploration

This exploration demonstrates how to leverage the new **parsing service abstraction layer** to process documents using **Mistral OCR** for report generation workflows on GCP.

## 🏗️ Architecture Overview

The exploration uses the comprehensive parsing service we implemented:

- **Service Abstraction**: `@backend/app/services/parsing/service.py`
- **Mistral OCR Adapter**: `@backend/app/services/parsing/adapters/mistral_ocr.py`
- **Validation Service**: `@backend/app/services/parsing/validation.py`
- **GCP Storage Integration**: `@backend/app/services/parsing/storage.py`
- **Structured Logging**: `@backend/app/core/logging.py`

## 🚀 Quick Start

### Prerequisites
```bash
# Set environment variables
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/backend-sa-key.json"
export MISTRAL_OCR_API_KEY="your-mistral-api-key"

# Start Cloud SQL proxy (if using Cloud SQL)
cloud-sql-proxy --port 5433 probtp-poc-prod:europe-west9:probtp-poc-db-prod
```

### Step-by-Step Workflow

#### 1. Setup & Configuration
```bash
cd backend/explorations/report_generation/
python 00_config_and_setup.py
```
**What it does:**
- Creates database tables
- Sets up test project
- Verifies service connections
- Prepares environment for document processing

#### 2. Upload Test Documents
```bash
python 01_upload_files.py
```
**What it does:**
- Uploads PDF files from `documents/` directory
- Creates file records in database
- Generates signed URLs for cloud storage
- Verifies successful uploads

#### 3. Parse Documents with Mistral OCR
```bash
python 02_read_and_parse_file.py
```
**What it does:**
- **Validates files** using the parsing service validation layer
- **Parses documents** with Mistral OCR via service abstraction
- **Extracts content blocks** with layout information (bounding boxes, confidence scores)
- **Stores structured results** in database for report generation
- **Logs performance metrics** with correlation IDs

#### 4. Evaluate Parsing Quality
```bash
python 02_z_evaluate_the_parsing.py
```
**What it does:**
- Analyzes parsing quality and performance metrics
- Generates comprehensive quality reports
- Shows content samples and confidence scores
- Exports detailed JSON reports for further analysis

#### 5. Generate Comparative Reports (with Langfuse Tracing)
```bash
python 03_single_shot_report.py
```
**What it does:**
- **Reconstructs documents** from parsed content blocks stored in database
- **Generates comparative reports** using Gemini AI for insurance policy analysis
- **Traces all operations** with Langfuse for comprehensive observability
- **Captures metadata** including document info, model usage, and performance metrics
- **Provides detailed insights** into report generation process and quality

## 📊 Key Features Demonstrated

### 🔧 **Service Abstraction Benefits**
- **Unified API**: Switch between parsing services without code changes
- **Built-in Validation**: Pre-flight file validation before external API calls
- **Error Handling**: Comprehensive timeout and error management
- **Performance Monitoring**: Structured logging with correlation IDs

### 🧠 **Mistral OCR Integration**
- **Document Analysis**: Extracts text, headings, lists, tables, images
- **Layout Preservation**: Maintains bounding box coordinates for positioning
- **Quality Scoring**: Provides confidence scores for each content block
- **Multi-page Support**: Handles complex documents with multiple pages

### 📈 **Quality Assessment**
- **Performance Metrics**: Processing speed, throughput, success rates
- **Content Analysis**: Block type distribution, character extraction rates
- **Confidence Tracking**: OCR accuracy and reliability scoring
- **Detailed Reporting**: JSON exports for integration with other tools

## 🎯 **Production-Ready Features**

### **Observability**
- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Performance Metrics**: Processing time, throughput, block extraction rates
- **Health Monitoring**: Service availability and response time tracking
- **Error Tracking**: Comprehensive error logging with context
- **Langfuse Tracing**: Full tracing of LLM calls with input/output monitoring
- **AI Model Observability**: Token usage, latency, and quality metrics for Gemini API calls

### **Reliability**
- **Validation Pipeline**: Pre-processing file validation
- **Timeout Management**: Configurable timeouts per service
- **Error Recovery**: Graceful handling of service failures
- **Batch Processing**: Support for multiple document processing

### **Scalability**
- **Service Abstraction**: Easy integration of additional parsing services
- **Async Processing**: Non-blocking document processing
- **Database Integration**: Structured storage of parsing results
- **GCP Native**: Built for Google Cloud Platform deployment

## 📝 **Output Examples**

### Parsing Results
```json
{
  "document_id": "doc_abc123",
  "parsing_service": "mistral_ocr",
  "status": "completed",
  "content_blocks": [
    {
      "block_type": "heading",
      "content": "Executive Summary",
      "page_number": 1,
      "confidence_score": 0.95,
      "bounding_box": {
        "x": 0.1, "y": 0.1,
        "width": 0.8, "height": 0.05
      }
    }
  ]
}
```

### Quality Report
```
📊 MISTRAL OCR PARSING QUALITY REPORT
=====================================
Total files analyzed: 5
Success rate: 100.0%
Average processing time: 3.2 seconds
Average confidence score: 0.921
Block type distribution:
- text: 45 blocks (65%)
- heading: 12 blocks (17%)
- list: 8 blocks (11%)
```

## 🔮 **Next Steps for Report Generation**

1. **Content Analysis**: Use extracted blocks for semantic analysis
2. **Template Generation**: Create report templates based on document structure
3. **Data Extraction**: Pull specific information from parsed content blocks
4. **Multi-document Processing**: Combine insights across multiple documents
5. **LLM Integration**: Use parsed structure as context for AI-powered report generation

## 🛠️ **Configuration Options**

### Environment Variables
```bash
# Required
MISTRAL_OCR_API_KEY=your-api-key
GOOGLE_APPLICATION_CREDENTIALS=path-to-service-account-key.json

# Langfuse Configuration (for tracing and observability)
# Get these keys from your Langfuse project settings: https://cloud.langfuse.com
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key-here
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key-here
LANGFUSE_HOST=https://cloud.langfuse.com  # or https://us.cloud.langfuse.com for US region

# Optional
MISTRAL_OCR_ENDPOINT=https://api.mistral-ocr.com/v1
MISTRAL_OCR_TIMEOUT=60
MISTRAL_OCR_MAX_FILE_SIZE=104857600
LOG_LEVEL=INFO
JSON_LOGGING=true
```

### Supported File Formats
- **PDF**: Primary format for document processing
- **Images**: PNG, JPG, JPEG for scanned documents
- **Size Limits**: Up to 100MB per file
- **Multi-page**: Full support for complex documents

## 🔍 **Langfuse Observability Setup**

### Setting Up Langfuse
1. **Create a Langfuse Account**: Sign up at [https://cloud.langfuse.com](https://cloud.langfuse.com)
2. **Create a Project**: Set up a new project for your report generation traces
3. **Get API Keys**: Copy your public and secret keys from project settings
4. **Set Environment Variables**: Configure the required environment variables

### What Gets Traced
- **Document Processing**: File reconstruction and content extraction
- **Gemini API Calls**: All LLM interactions with input/output capture
- **Performance Metrics**: Processing times, token usage, and success rates
- **Metadata**: Document statistics, model parameters, and execution context

### Viewing Traces
After running the report generation script, you can:
- **View Trace Timeline**: See the complete execution flow in Langfuse dashboard
- **Analyze Performance**: Review latency, token usage, and cost metrics
- **Debug Issues**: Inspect inputs, outputs, and error details
- **Track Quality**: Monitor model responses and generation quality

### Trace Data Captured
```json
{
  "input": {
    "project_id": "uuid",
    "documents_count": 2,
    "document_files": ["file1.pdf", "file2.pdf"],
    "total_pages": 15,
    "total_blocks": 342,
    "model_name": "gemini-2.5-pro"
  },
  "metadata": {
    "environment": "development",
    "script_version": "1.0.0",
    "block_types_found": ["text", "heading", "list", "table"],
    "execution_timestamp": "2025-09-26T17:30:00Z"
  },
  "output": {
    "report_generated": true,
    "report_length": 15420,
    "report_lines": 485,
    "estimated_tables": 12
  }
}
```

This exploration demonstrates a production-ready approach to document parsing using modern service abstraction patterns, comprehensive error handling, and detailed observability - perfect for building robust report generation systems on GCP.