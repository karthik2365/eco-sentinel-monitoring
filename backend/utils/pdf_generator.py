"""
PDF Generator Utility

Generates PDF documents from HTML content using xhtml2pdf.
"""

import logging
import os
from typing import Optional
from io import BytesIO

from xhtml2pdf import pisa

from config import Config

logger = logging.getLogger(__name__)


# Get the backend directory (parent of utils folder)
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def link_callback(uri: str, rel: str) -> str:
    """
    Convert URIs to absolute file paths for xhtml2pdf.
    
    This handles:
    - Absolute file paths (pass through)
    - HTTP URLs pointing to our static folder (convert to file path)
    - Relative paths (resolve relative to backend directory)
    
    Args:
        uri: The URI from the HTML (could be URL or path)
        rel: Relative path (not used, but required by xhtml2pdf)
        
    Returns:
        Absolute file path to the resource
    """
    # If it's already an absolute file path that exists, use it
    if os.path.isabs(uri) and os.path.exists(uri):
        return uri
    
    # Handle HTTP URLs pointing to our local static files
    # e.g., http://localhost:5000/static/images/analysis/...
    if uri.startswith('http://') or uri.startswith('https://'):
        # Extract the path after /static/
        if '/static/' in uri:
            static_path = uri.split('/static/')[-1]
            abs_path = os.path.join(BACKEND_DIR, 'static', static_path)
            if os.path.exists(abs_path):
                logger.debug(f"Resolved URL {uri} to {abs_path}")
                return abs_path
        # For external URLs, return as-is (xhtml2pdf will try to fetch, but may fail)
        logger.warning(f"Cannot resolve external URL: {uri}")
        return uri
    
    # Handle relative paths (e.g., /static/images/...)
    if uri.startswith('/static/'):
        static_path = uri[8:]  # Remove '/static/' prefix
        abs_path = os.path.join(BACKEND_DIR, 'static', static_path)
        if os.path.exists(abs_path):
            logger.debug(f"Resolved relative path {uri} to {abs_path}")
            return abs_path
    
    # Handle paths that include 'static' somewhere
    if 'static' in uri:
        # Split on 'static' and take everything after
        parts = uri.split('static')
        if len(parts) > 1:
            static_path = parts[-1].lstrip('/\\')
            abs_path = os.path.join(BACKEND_DIR, 'static', static_path)
            if os.path.exists(abs_path):
                logger.debug(f"Resolved path {uri} to {abs_path}")
                return abs_path
    
    # Default: try to resolve relative to backend directory
    abs_path = os.path.join(BACKEND_DIR, uri.lstrip('/'))
    if os.path.exists(abs_path):
        return abs_path
    
    logger.warning(f"Could not resolve URI: {uri}")
    return uri


def generate_pdf(html_content: str, filename: str) -> Optional[str]:
    """
    Generate a PDF from HTML content.
    
    Args:
        html_content: Complete HTML document to convert
        filename: Output filename (e.g., 'report_1.pdf')
        
    Returns:
        URL path to the generated PDF, or None on failure
    """
    try:
        # Ensure upload folder exists
        if not os.path.exists(Config.UPLOAD_FOLDER):
            os.makedirs(Config.UPLOAD_FOLDER)
            logger.info(f"Created upload folder: {Config.UPLOAD_FOLDER}")
        
        file_path = os.path.join(Config.UPLOAD_FOLDER, filename)
        
        # Generate PDF with link callback to resolve image paths
        with open(file_path, "wb") as pdf_file:
            pisa_status = pisa.CreatePDF(
                html_content,
                dest=pdf_file,
                encoding='utf-8',
                link_callback=link_callback
            )
        
        if pisa_status.err:
            logger.error(f"PDF generation errors: {pisa_status.err}")
            return None
        
        logger.info(f"PDF generated successfully: {filename}")
        return f"/reports/{filename}"
        
    except OSError as e:
        logger.error(f"File system error generating PDF: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating PDF: {e}")
        return None


def get_report_path(filename: str) -> str:
    """
    Get the full file system path for a report.
    
    Args:
        filename: Report filename
        
    Returns:
        Full path to the report file
    """
    return os.path.join(Config.UPLOAD_FOLDER, filename)


def report_exists(filename: str) -> bool:
    """
    Check if a report file exists.
    
    Args:
        filename: Report filename
        
    Returns:
        True if the file exists, False otherwise
    """
    return os.path.exists(get_report_path(filename))
