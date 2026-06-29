# pdf_agent.py
# Converts a PDF into per-page images and runs the full forgery pipeline on each page
# Uses PyMuPDF (fitz) — NO Poppler installation required
#
# Install: pip install pymupdf

import os
import tempfile
import json
from PIL import Image
import io


def pdf_to_images(pdf_path, dpi=200):
    """
    Convert each page of a PDF to a PIL Image using PyMuPDF.
    No Poppler required — works on Windows/Mac/Linux out of the box.
    DPI 200 = good quality/speed balance. Use 300 for higher accuracy (slower).
    """
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        pages = []
        zoom = dpi / 72  # PDF default is 72 DPI; scale up
        mat = fitz.Matrix(zoom, zoom)

        for page in doc:
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            pages.append(img)

        doc.close()
        return pages, None

    except ImportError:
        return None, (
            "PyMuPDF is not installed. "
            "Run: pip install pymupdf"
        )
    except Exception as e:
        return None, str(e)


def analyze_pdf(pdf_path):
    """
    Main function — runs the full 5-agent pipeline on every page of the PDF.
    Returns a dict with per-page results + overall summary.
    Called by app.py.
    """
    import run_all  # imported here to avoid circular imports

    # Step 1: Convert PDF to images
    pages, error = pdf_to_images(pdf_path)
    if error:
        return {
            "error": f"Could not read PDF: {error}",
            "page_count": 0,
            "page_results": [],
            "most_suspicious_page": None,
            "overall_verdict": "ERROR",
            "forged_page_numbers": [],
            "suspicious_page_numbers": [],
            "genuine_page_numbers": [],
            "temp_image_paths": []
        }

    page_count = len(pages)
    page_results = []
    temp_files = []

    try:
        for page_num, page_image in enumerate(pages, start=1):
            # Save page as temp JPEG for the existing agents
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".jpg", prefix=f"pdf_page_{page_num}_"
            ) as tmp:
                page_image.save(tmp.name, "JPEG", quality=95)
                temp_path = tmp.name
                temp_files.append(temp_path)

            print(f"  Analyzing page {page_num}/{page_count}...")
            report = run_all.analyze_document(temp_path)

            verdict_data = report.get("final_verdict", {})
            page_result = {
                "page_number":           page_num,
                "verdict":               verdict_data.get("verdict", "UNKNOWN"),
                "confidence_percentage": verdict_data.get("confidence_percentage", 0),
                "risk_level":            verdict_data.get("risk_level", "UNKNOWN"),
                "top_findings":          verdict_data.get("top_3_findings", []),
                "explanation":           verdict_data.get("detailed_explanation", ""),
                "full_report":           report,
                "temp_image_path":       temp_path
            }
            page_results.append(page_result)

    except Exception as e:
        for f in temp_files:
            try:
                os.unlink(f)
            except:
                pass
        return {
            "error": str(e),
            "page_count": page_count,
            "page_results": page_results,
            "most_suspicious_page": None,
            "overall_verdict": "ERROR",
            "forged_page_numbers": [],
            "suspicious_page_numbers": [],
            "genuine_page_numbers": [],
            "temp_image_paths": []
        }

    # Categorise pages
    forged_pages     = [p for p in page_results if p["verdict"] in ["FORGED", "TAMPERED", "FAKE"]]
    suspicious_pages = [p for p in page_results if p["verdict"] in ["SUSPICIOUS", "POSSIBLY_FORGED"]]
    genuine_pages    = [p for p in page_results if p["verdict"] in ["GENUINE", "AUTHENTIC"]]

    if forged_pages:
        most_suspicious = max(forged_pages, key=lambda x: x["confidence_percentage"])
        overall_verdict = "FORGED"
    elif suspicious_pages:
        most_suspicious = max(suspicious_pages, key=lambda x: x["confidence_percentage"])
        overall_verdict = "SUSPICIOUS"
    else:
        most_suspicious = page_results[0] if page_results else None
        overall_verdict = "GENUINE"

    return {
        "page_count":               page_count,
        "page_results":             page_results,
        "most_suspicious_page":     most_suspicious,
        "overall_verdict":          overall_verdict,
        "forged_page_numbers":      [p["page_number"] for p in forged_pages],
        "suspicious_page_numbers":  [p["page_number"] for p in suspicious_pages],
        "genuine_page_numbers":     [p["page_number"] for p in genuine_pages],
        "temp_image_paths":         temp_files
    }


def cleanup_temp_files(pdf_report):
    """Call this after app.py is done displaying everything"""
    for path in pdf_report.get("temp_image_paths", []):
        try:
            os.unlink(path)
        except:
            pass
