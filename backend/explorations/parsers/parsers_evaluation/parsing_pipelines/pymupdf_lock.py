"""
Shared lock for pymupdf4llm to ensure thread-safety across all parsers.
pymupdf4llm is not thread-safe, so all calls to it must be synchronized.
"""
import threading

# Global lock shared across all parser modules
pymupdf_lock = threading.Lock()
