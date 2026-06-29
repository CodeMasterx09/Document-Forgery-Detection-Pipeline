# # verdict_agent.py
# # Combines all reports and uses GPT-4o to give a final verdict
 
# import json
# import sys
# from openai import OpenAI
 
# # PUT YOUR API KEY HERE
# OPENAI_API_KEY = "sk-your-api-key-here"
 
 
# def get_verdict(vision_report, ocr_report, metadata_report):
#     """Send all reports to GPT-4o for final analysis"""
#     client = OpenAI(api_key=OPENAI_API_KEY)
    
#     prompt = f"""You are a senior forensic document examiner with 20 years 
# of experience. Based on ALL the evidence below, provide your expert verdict.
 
# === VISION ANALYSIS REPORT ===
# {json.dumps(vision_report, indent=2)}
 
# === OCR & TEXT VALIDATION REPORT ===
# {json.dumps(ocr_report, indent=2)}
 
# === METADATA & ERROR LEVEL ANALYSIS REPORT ===
# {json.dumps(metadata_report, indent=2)}
 
# Provide your verdict in JSON format:
# {{
#     "verdict": "GENUINE" or "SUSPICIOUS" or "LIKELY FORGED",
#     "confidence_percentage": 0-100,
#     "risk_level": "LOW" or "MEDIUM" or "HIGH" or "CRITICAL",
#     "top_3_findings": ["finding1", "finding2", "finding3"],
#     "detailed_explanation": "paragraph explaining reasoning",
#     "recommendations": ["action1", "action2"]
# }}"""
 
#     response = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[
#             {"role": "system", "content": "Expert forensic analyst. Respond in valid JSON."},
#             {"role": "user", "content": prompt}
#         ],
#         temperature=0.1,
#         max_tokens=2000
#     )
    
#     try:
#         text = response.choices[0].message.content
#         text = text.replace("```json", "").replace("```", "").strip()
#         return json.loads(text)
#     except json.JSONDecodeError:
#         return {"verdict": "ERROR", "raw": response.choices[0].message.content}
 
 
# if __name__ == "__main__":
#     sample_vision = {"overall_visual_score": 72, "summary": "Font inconsistencies detected"}
#     sample_ocr = {"pan_validation": [{"number": "ABCDE1234F", "valid_format": True}]}
#     sample_metadata = {"editing_software_detected": [], "error_level_analysis": {"suspicious": False}}
#     result = get_verdict(sample_vision, sample_ocr, sample_metadata)
#     print(json.dumps(result, indent=2))
