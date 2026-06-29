# signature_agent.py
# Uses Flowise Vision LLM to detect signatures and seals — clean, smart output

import json
import sys
import os
import requests
import base64

# ============================================================
# CONFIGURATION — use the SAME Vision Agent URL as run_all.py
# ============================================================
VISION_AGENT_URL = "http://localhost:3000/api/v1/prediction/b35e36c4-d499-4ca3-bfbd-c4b8c7cf333c"
# ============================================================


SIGNATURE_PROMPT = """You are a forensic document expert specializing in signature and seal verification.

Carefully analyze this document image and return ONLY a JSON object — no explanation, no markdown.

Check for the following and return this exact structure:

{
  "signature_detection": {
    "signatures_found": <number>,
    "signatures_present": <true/false>,
    "signature_quality": "<CLEAR / PARTIAL / ABSENT>",
    "suspicious": <true/false>,
    "reason": "<one sentence explanation>"
  },
  "seal_detection": {
    "seals_found": <number>,
    "seal_types": ["<e.g. circular stamp, rectangular box, watermark>"],
    "seal_present": <true/false>,
    "suspicious": <true/false>,
    "reason": "<one sentence explanation>"
  },
  "duplication_check": {
    "duplicate_signature_suspected": <true/false>,
    "duplicate_seal_suspected": <true/false>,
    "reason": "<one sentence explanation>"
  },
  "ink_analysis": {
    "ink_appears_genuine": <true/false>,
    "ink_color_observed": "<e.g. blue, black, faded black>",
    "digitally_inserted_suspected": <true/false>,
    "reason": "<one sentence explanation>"
  },
  "overall_suspicious": <true/false>,
  "summary": "<2-3 sentence human readable summary of signature and seal findings>"
}"""


def analyze_signatures(image_path):
    """
    Send document image to Flowise Vision LLM for signature and seal analysis.
    Returns a structured JSON report.
    """
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        ext = os.path.splitext(image_path)[1].lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp"
        }
        mime_type = mime_map.get(ext, "image/jpeg")

        payload = {
            "question": SIGNATURE_PROMPT,
            "uploads": [
                {
                    "data": f"data:{mime_type};base64,{image_base64}",
                    "type": "file",
                    "name": os.path.basename(image_path),
                    "mime": mime_type
                }
            ]
        }

        response = requests.post(
            VISION_AGENT_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        if response.status_code == 200:
            raw = response.json()
            result_text = raw.get("text", raw.get("json", str(raw)))

            if isinstance(result_text, str):
                result_text = result_text.replace("```json", "").replace("```", "").strip()
                try:
                    return json.loads(result_text)
                except json.JSONDecodeError:
                    return {
                        "raw_response": result_text,
                        "overall_suspicious": False,
                        "error": "Could not parse LLM response as JSON"
                    }
            else:
                return result_text

        else:
            return {
                "error": f"Flowise returned status {response.status_code}",
                "details": response.text,
                "overall_suspicious": False
            }

    except requests.exceptions.ConnectionError:
        return {
            "error": "Cannot connect to Flowise — make sure Flowise is running on localhost:3000",
            "overall_suspicious": False
        }
    except Exception as e:
        return {"error": str(e), "overall_suspicious": False}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python signature_agent.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        sys.exit(1)

    result = analyze_signatures(image_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))
