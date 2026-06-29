# run_all.py
# Master script — runs ALL agents and gets the final verdict

import json
import sys
import os
import requests
import base64
import blockchain_agent

VISION_AGENT_URL  = "http://localhost:3000/api/v1/prediction/b35e36c4-d499-4ca3-bfbd-c4b8c7cf333c"
VERDICT_AGENT_URL = "http://localhost:3000/api/v1/prediction/029adf8c-8493-445d-a053-a810697deec4"


def run_vision_agent(image_path):
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode("utf-8")
        ext = os.path.splitext(image_path)[1].lower()
        mime_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                     ".png": "image/png", ".gif": "image/gif",
                     ".webp": "image/webp"}.get(ext, "image/jpeg")
        payload = {
            "question": "Analyze this document for signs of forgery or tampering",
            "uploads": [{
                "data": f"data:{mime_type};base64,{image_base64}",
                "type": "file",
                "name": os.path.basename(image_path),
                "mime": mime_type
            }]
        }
        response = requests.post(VISION_AGENT_URL, json=payload,
                                 headers={"Content-Type": "application/json"})
        if response.status_code == 200:
            result_text = response.json().get("text", response.json().get("json", str(response.json())))
            try:
                if isinstance(result_text, str):
                    result_text = result_text.replace("```json", "").replace("```", "").strip()
                    return json.loads(result_text)
                return result_text
            except json.JSONDecodeError:
                return {"raw_response": result_text, "note": "Could not parse as JSON"}
        return {"error": f"Vision Agent returned status {response.status_code}", "details": response.text}
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to Flowise. Make sure Flowise is running on localhost:3000"}
    except Exception as e:
        return {"error": str(e)}


def run_ocr_agent(image_path):
    try:
        import ocr_agent
        return ocr_agent.analyze_document(image_path)
    except ImportError:
        return {"error": "ocr_agent.py not found in the same folder"}
    except Exception as e:
        return {"error": str(e)}


def run_metadata_agent(image_path):
    try:
        import metadata_agent
        return metadata_agent.analyze_metadata(image_path)
    except ImportError:
        return {"error": "metadata_agent.py not found in the same folder"}
    except Exception as e:
        return {"error": str(e)}


def run_signature_agent(image_path):
    try:
        import signature_agent
        return signature_agent.analyze_signatures(image_path)
    except ImportError:
        return {"error": "signature_agent.py not found in the same folder"}
    except Exception as e:
        return {"error": str(e)}


def get_verdict(vision_report, ocr_report, metadata_report, signature_report):
    try:
        combined_message = f"""=== VISION ANALYSIS REPORT ===
{json.dumps(vision_report, indent=2)}

=== OCR AND TEXT VALIDATION REPORT ===
{json.dumps(ocr_report, indent=2)}

=== METADATA AND ERROR LEVEL ANALYSIS REPORT ===
{json.dumps(metadata_report, indent=2)}

=== SIGNATURE AND SEAL DETECTION REPORT ===
{json.dumps(signature_report, indent=2)}"""

        response = requests.post(
            VERDICT_AGENT_URL,
            json={"question": combined_message},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            result_text = response.json().get("text", response.json().get("json", str(response.json())))
            try:
                if isinstance(result_text, str):
                    result_text = result_text.replace("```json", "").replace("```", "").strip()
                    return json.loads(result_text)
                return result_text
            except json.JSONDecodeError:
                return {"raw_response": result_text}
        return {"error": f"Verdict Agent returned status {response.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to Flowise. Make sure Flowise is running on localhost:3000"}
    except Exception as e:
        return {"error": str(e)}


def analyze_document(image_path):
    """Main function — runs all 5 agents. Returns complete report including blockchain hash."""
    if not os.path.exists(image_path):
        return {
            "error": f"File not found: {image_path}",
            "document_hash": None,
            "vision_report": {},
            "ocr_report": {},
            "metadata_report": {},
            "signature_report": {},
            "final_verdict": {
                "verdict": "ERROR",
                "confidence_percentage": 0,
                "risk_level": "UNKNOWN",
                "top_3_findings": ["File not found"],
                "detailed_explanation": f"The file {image_path} was not found.",
                "recommendations": ["Please provide a valid file path"]
            }
        }

    # Generate blockchain hash FIRST (before any processing changes anything)
    with open(image_path, "rb") as f:
        doc_hash = blockchain_agent.generate_document_hash(f.read())

    vision_report    = run_vision_agent(image_path)
    ocr_report       = run_ocr_agent(image_path)
    metadata_report  = run_metadata_agent(image_path)
    signature_report = run_signature_agent(image_path)
    final_verdict    = get_verdict(vision_report, ocr_report, metadata_report, signature_report)

    return {
        "document_hash":    doc_hash,
        "vision_report":    vision_report,
        "ocr_report":       ocr_report,
        "metadata_report":  metadata_report,
        "signature_report": signature_report,
        "final_verdict":    final_verdict
    }


def main(image_path):
    return analyze_document(image_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_all.py <image_path>")
        sys.exit(1)
    image_path = sys.argv[1]
    print("=" * 50)
    print("  DOCUMENT FORGERY DETECTION SYSTEM")
    print("=" * 50)
    print(f"\nAnalyzing: {image_path}\n" + "-" * 50)
    for i, s in enumerate([
        "Vision Agent", "OCR Agent", "Metadata Agent",
        "Signature & Seal Agent", "Final Verdict"
    ], 1):
        print(f"[{i}/5] Running {s}...")
    report = analyze_document(image_path)
    for name, key in [
        ("vision_report.json",    "vision_report"),
        ("ocr_report.json",       "ocr_report"),
        ("metadata_report.json",  "metadata_report"),
        ("signature_report.json", "signature_report"),
        ("final_verdict.json",    "final_verdict"),
    ]:
        with open(name, "w") as f:
            json.dump(report[key], f, indent=2, ensure_ascii=False)
    print(f"\nDocument Hash (SHA-256): {report.get('document_hash')}")
    print("\n" + "=" * 50 + "\n  FINAL VERDICT\n" + "=" * 50)
    print(json.dumps(report["final_verdict"], indent=2))
    print("=" * 50 + "\nAll reports saved!")
