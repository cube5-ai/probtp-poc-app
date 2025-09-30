# VQA Pipelines

Visual Question Answering (VQA) pipelines for evaluating document parsing performance using images instead of text.

## Overview

These pipelines convert PDF documents to images and use multimodal LLMs to answer questions about the content, evaluating the model's ability to extract information directly from document images.

## vqa_gemini_flash.py

A VQA pipeline using Gemini Flash 2.5 that:

1. **Converts PDFs to Images**: Uses PyMuPDF to convert each PDF page to a 200 DPI PNG image
2. **Loads Images as Parts**: Loads images as `Part.from_bytes` objects for Vertex AI
3. **Evaluates Q&A**: Answers evaluation questions using the image parts
4. **Outputs Results**: Saves results in the same JSON format as other pipelines

### Usage

```bash
cd /path/to/backend/explorations/parsers/parsers_evaluation/vqa_pipelines
python vqa_gemini_flash.py
```

### Requirements

- PyMuPDF (fitz)
- Google Gen AI SDK
- Access to Vertex AI (probtp-poc-prod project)

### Output Structure

**Images**: `output/vqa/vqa_gemini_flash/[file-name]_page_[i].png`
- Each page of the PDF is saved as a separate 200 DPI PNG image

**Evaluation Results**: `output/evals/vqa_gemini_flash.json`
- Same structure as other pipeline evaluations
- Contains verdict, explanation, confidence, and other metrics

### How It Works

1. Scans the `documents/` directory for PDF files
2. Converts each PDF to images (one per page) at 200 DPI using PyMuPDF
3. Loads all images as `Part.from_bytes` objects for Vertex AI
4. Generates Q&A pairs from `eval_data/data_0.json`
5. For each question:
   - Sends all document image parts + question to Gemini via Vertex AI
   - Gets the model's answer
   - Evaluates the answer against ground truth
6. Saves all results to JSON

### Performance

Uses async processing with batches of 5 questions at a time to:
- Maximize throughput
- Avoid rate limits
- Reduce total evaluation time

### Comparison with Text Pipelines

Unlike text-based pipelines that parse PDFs to markdown/text first, VQA pipelines:
- ✅ Test the model's visual understanding
- ✅ Preserve exact layout and formatting
- ✅ Can handle complex tables and graphics
- ❌ May be slower due to image processing
- ❌ Higher API costs for multimodal models
