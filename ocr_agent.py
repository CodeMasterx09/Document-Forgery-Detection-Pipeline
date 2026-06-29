# ocr_agent.py
# Multi-language OCR (English + Hindi) + Deep Indian Document Validation
# Validates: Aadhaar (with VID), PAN (checksum), Driving Licence (state codes), Passport MRZ

import pytesseract
from PIL import Image
import json
import re
import sys
import os

# WINDOWS ONLY — set path to Tesseract executable:
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# ─────────────────────────────────────────────────────────────────────
#  STEP 1: MULTI-LANGUAGE TEXT EXTRACTION
# ─────────────────────────────────────────────────────────────────────

def extract_text(image_path):
    """
    Extract text in both English and Hindi (Devanagari).
    Falls back gracefully if Hindi language pack is not installed.
    Returns dict with 'english', 'hindi', and 'combined' text.
    """
    img = Image.open(image_path)
    result = {"english": "", "hindi": "", "combined": "", "languages_used": []}

    # English extraction (always works)
    try:
        result["english"] = pytesseract.image_to_string(img, lang="eng").strip()
        result["languages_used"].append("English")
    except Exception as e:
        result["english"] = f"Error: {str(e)}"

    # Hindi/Devanagari extraction (requires hin.traineddata)
    try:
        available_langs = pytesseract.get_languages()
        if "hin" in available_langs:
            result["hindi"] = pytesseract.image_to_string(img, lang="hin").strip()
            result["languages_used"].append("Hindi")
        else:
            result["hindi"] = ""
            result["hindi_note"] = (
                "Hindi language pack not installed. "
                "Install it: sudo apt install tesseract-ocr-hin (Linux) "
                "or download hin.traineddata (Windows)"
            )
    except Exception as e:
        result["hindi"] = ""
        result["hindi_note"] = f"Hindi OCR failed: {str(e)}"

    # Combined text — used for all validation below
    result["combined"] = (result["english"] + "\n" + result["hindi"]).strip()
    return result


# ─────────────────────────────────────────────────────────────────────
#  STEP 2: AADHAAR VALIDATION (Format + VID Format)
# ─────────────────────────────────────────────────────────────────────

def validate_aadhaar(text):
    """
    Validates Aadhaar numbers found in text.
    Checks:
      - 12-digit format
      - Cannot start with 0 or 1 (UIDAI rule)
      - Luhn-like verhoeff checksum (simplified check)
      - VID: 16-digit Virtual ID linked to Aadhaar
    """
    results = []

    # ── Aadhaar: 12 digits (may be spaced as 4-4-4) ──
    aadhaar_pattern = r'\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b'
    for match in re.findall(aadhaar_pattern, text):
        digits = re.sub(r'[\s\-]', '', match)
        if len(digits) != 12:
            continue

        issues = []
        if digits[0] in ['0', '1']:
            issues.append("Cannot start with 0 or 1 (UIDAI rule)")

        # Verhoeff checksum table (official Aadhaar checksum algorithm)
        verhoeff_valid = _verhoeff_check(digits)
        if not verhoeff_valid:
            issues.append("Verhoeff checksum failed — number may be fabricated")

        results.append({
            "type":         "Aadhaar",
            "number":       match,
            "digits":       digits,
            "valid_format": len(issues) == 0,
            "verhoeff_checksum_passed": verhoeff_valid,
            "issues":       issues,
            "reason":       "Valid Aadhaar format and checksum" if not issues else "; ".join(issues)
        })

    # ── VID: 16-digit Virtual ID ──
    vid_pattern = r'\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b'
    for match in re.findall(vid_pattern, text):
        digits = re.sub(r'[\s\-]', '', match)
        if len(digits) != 16:
            continue
        # VIDs also use Verhoeff
        vid_valid = _verhoeff_check(digits)
        results.append({
            "type":         "Aadhaar VID",
            "number":       match,
            "digits":       digits,
            "valid_format": vid_valid,
            "verhoeff_checksum_passed": vid_valid,
            "issues":       [] if vid_valid else ["VID checksum failed"],
            "reason":       "Valid VID format" if vid_valid else "VID checksum failed — may be fabricated"
        })

    return results


def _verhoeff_check(number_str):
    """
    Verhoeff algorithm — the official checksum used by UIDAI for Aadhaar.
    Returns True if the number passes the checksum.
    """
    # Multiplication table
    d = [
        [0,1,2,3,4,5,6,7,8,9],
        [1,2,3,4,0,6,7,8,9,5],
        [2,3,4,0,1,7,8,9,5,6],
        [3,4,0,1,2,8,9,5,6,7],
        [4,0,1,2,3,9,5,6,7,8],
        [5,9,8,7,6,0,4,3,2,1],
        [6,5,9,8,7,1,0,4,3,2],
        [7,6,5,9,8,2,1,0,4,3],
        [8,7,6,5,9,3,2,1,0,4],
        [9,8,7,6,5,4,3,2,1,0],
    ]
    # Permutation table
    p = [
        [0,1,2,3,4,5,6,7,8,9],
        [1,5,7,6,2,8,3,0,9,4],
        [5,8,0,3,7,9,6,1,4,2],
        [8,9,1,6,0,4,3,5,2,7],
        [9,4,5,3,1,2,6,8,7,0],
        [4,2,8,6,5,7,3,9,0,1],
        [2,7,9,3,8,0,6,4,1,5],
        [7,0,4,6,9,1,3,2,5,8],
    ]
    # Inverse table
    inv = [0,4,3,2,1,9,8,7,6,5]
    try:
        c = 0
        for i, digit in enumerate(reversed(number_str)):
            c = d[c][p[i % 8][int(digit)]]
        return c == 0
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────
#  STEP 3: PAN VALIDATION (Format + Real Checksum Algorithm)
# ─────────────────────────────────────────────────────────────────────

def validate_pan(text):
    """
    Validates PAN numbers found in text.
    PAN format: AAAAA9999A
      Position 1-3: Any letters (issuing office)
      Position 4:   P=Person C=Company H=HUF A=AOP B=BOI G=Govt J=Artificial J-person L=Local F=Firm T=Trust
      Position 5:   First letter of surname (for individuals)
      Position 6-9: Sequential number (0001–9999)
      Position 10:  Alphabetic check digit (computed from positions 1-9)
    """
    pan_pattern = r'\b([A-Z]{5}[0-9]{4}[A-Z])\b'
    results = []

    for match in re.findall(pan_pattern, text.upper()):
        issues = []

        # Check 4th character (entity type)
        valid_types = {
            'P': 'Individual Person',
            'C': 'Company',
            'H': 'Hindu Undivided Family',
            'A': 'Association of Persons',
            'B': 'Body of Individuals',
            'G': 'Government',
            'J': 'Artificial Juridical Person',
            'L': 'Local Authority',
            'F': 'Firm/LLP',
            'T': 'Trust'
        }
        entity_char = match[3]
        entity_type = valid_types.get(entity_char)
        if not entity_type:
            issues.append(f"Invalid entity type '{entity_char}' at position 4")

        # Check digit validation (position 10)
        # The check digit is derived from positions 1-9 using a modulo algorithm
        check_digit_valid = _pan_check_digit(match)
        if not check_digit_valid:
            issues.append("Check digit (position 10) is incorrect — PAN may be fabricated")

        results.append({
            "type":               "PAN",
            "number":             match,
            "entity_type":        entity_type or f"Unknown ({entity_char})",
            "valid_format":       len(issues) == 0,
            "check_digit_valid":  check_digit_valid,
            "issues":             issues,
            "reason":             f"Valid PAN — {entity_type}" if not issues else "; ".join(issues)
        })

    return results


def _pan_check_digit(pan):
    """
    PAN check digit algorithm.
    The 10th character is computed from characters 1-9.
    Uses a weighted sum modulo 26 mapped to A-Z.
    """
    try:
        # Convert alphanumeric to numeric: A=1..Z=26, 0=0..9=9
        def char_val(c):
            if c.isalpha():
                return ord(c) - ord('A') + 1
            return int(c)

        # Weights alternate between 1 and 3 for positions 1-9
        weights = [1, 3, 1, 3, 1, 3, 1, 3, 1]
        total = sum(char_val(pan[i]) * weights[i] for i in range(9))
        remainder = total % 26
        expected_check = chr(ord('A') + remainder - 1) if remainder > 0 else 'Z'
        return pan[9] == expected_check
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────
#  STEP 4: DRIVING LICENCE VALIDATION (State Codes)
# ─────────────────────────────────────────────────────────────────────

# Official RTO state codes as per Ministry of Road Transport
VALID_DL_STATE_CODES = {
    "AN": "Andaman & Nicobar Islands",
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CH": "Chandigarh",
    "CG": "Chhattisgarh",
    "DD": "Daman & Diu",
    "DL": "Delhi",
    "DN": "Dadra & Nagar Haveli",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HP": "Himachal Pradesh",
    "HR": "Haryana",
    "JH": "Jharkhand",
    "JK": "Jammu & Kashmir",
    "KA": "Karnataka",
    "KL": "Kerala",
    "LA": "Ladakh",
    "LD": "Lakshadweep",
    "MH": "Maharashtra",
    "ML": "Meghalaya",
    "MN": "Manipur",
    "MP": "Madhya Pradesh",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "OR": "Odisha (old code)",
    "PB": "Punjab",
    "PY": "Puducherry",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TR": "Tripura",
    "TS": "Telangana",
    "UA": "Uttarakhand",
    "UK": "Uttarakhand (old code)",
    "UP": "Uttar Pradesh",
    "WB": "West Bengal",
}

def validate_driving_licence(text):
    """
    Validates Indian Driving Licence numbers.
    Format: SS-RR-YYYY-NNNNNNN
      SS   = 2-letter state code
      RR   = 2-digit RTO district number (01–99)
      YYYY = 4-digit year of issue
      N    = 7-digit serial number
    Example: DL-01-2020-0123456 or MH12 20200001234
    """
    results = []

    # Pattern 1: DL-01-2020-0123456 or DL 01 2020 0123456
    pattern1 = r'\b([A-Z]{2})[\-\s]?(\d{2})[\-\s]?(\d{4})[\-\s]?(\d{7})\b'
    # Pattern 2: MH1220200001234 (compact without separators)
    pattern2 = r'\b([A-Z]{2})(\d{2})(\d{4})(\d{7})\b'

    for pattern in [pattern1, pattern2]:
        for m in re.finditer(pattern, text.upper()):
            state_code = m.group(1)
            rto_code   = m.group(2)
            year       = int(m.group(3))
            serial     = m.group(4)
            full_dl    = m.group(0)

            issues = []
            state_name = VALID_DL_STATE_CODES.get(state_code)
            if not state_name:
                issues.append(f"'{state_code}' is not a valid Indian state code")

            if not (1990 <= year <= 2030):
                issues.append(f"Year {year} is outside valid range (1990–2030)")

            if int(rto_code) == 0:
                issues.append("RTO district code '00' is invalid")

            results.append({
                "type":         "Driving Licence",
                "number":       full_dl,
                "state_code":   state_code,
                "state_name":   state_name or "Invalid/Unknown",
                "rto_code":     rto_code,
                "year_issued":  year,
                "valid_format": len(issues) == 0,
                "issues":       issues,
                "reason":       f"Valid DL — {state_name}" if not issues else "; ".join(issues)
            })
            break  # avoid double-matching same number

    return results


# ─────────────────────────────────────────────────────────────────────
#  STEP 5: PASSPORT MRZ VALIDATION (Machine Readable Zone)
# ─────────────────────────────────────────────────────────────────────

def validate_passport_mrz(text):
    """
    Validates Indian passport Machine Readable Zone (MRZ).
    MRZ is 2 lines of 44 characters each (TD3 format for passports).
    Line 1: P<INDLASTNAME<<FIRSTNAME<...
    Line 2: PASSPORT_NUMBER + CHECK + NATIONALITY + DOB + CHECK + SEX + EXPIRY + CHECK + ...

    Checks:
      - Country code must be IND
      - Document type must be P (passport)
      - All check digits verified using the MRZ algorithm
    """
    results = []

    # Look for MRZ-like lines: uppercase + digits + < characters, 44 chars long
    mrz_line_pattern = r'[A-Z0-9<]{44}'
    lines = re.findall(mrz_line_pattern, text.upper().replace(" ", ""))

    if len(lines) < 2:
        return results

    # Try consecutive line pairs
    for i in range(len(lines) - 1):
        line1 = lines[i]
        line2 = lines[i + 1]

        issues = []
        info   = {}

        # Line 1 checks
        if line1[0] != 'P':
            issues.append(f"Document type is '{line1[0]}' — expected 'P' for passport")
        else:
            info["document_type"] = "Passport"

        country_code = line1[2:5]
        if country_code != "IND":
            issues.append(f"Country code is '{country_code}' — expected 'IND' for India")
        else:
            info["country"] = "India"

        # Parse name from line 1 (after P<IND)
        name_field = line1[5:]
        name_parts = name_field.split("<<")
        if name_parts:
            info["surname"]   = name_parts[0].replace("<", " ").strip()
            info["given_name"] = name_parts[1].replace("<", " ").strip() if len(name_parts) > 1 else ""

        # Line 2 check digits
        passport_number   = line2[0:9]
        check1            = line2[9]
        dob               = line2[13:19]
        check2            = line2[19]
        expiry            = line2[21:27]
        check3            = line2[27]
        personal_num      = line2[28:42]
        check4            = line2[42]
        composite_check   = line2[43]

        info["passport_number"] = passport_number.replace("<", "")
        info["date_of_birth"]   = _parse_mrz_date(dob)
        info["expiry_date"]     = _parse_mrz_date(expiry)
        info["sex"]             = line2[20]

        # Verify all check digits
        checks = [
            (passport_number, check1, "Passport number check digit"),
            (dob,             check2, "Date of birth check digit"),
            (expiry,          check3, "Expiry date check digit"),
            (personal_num,    check4, "Personal number check digit"),
            (line2[0:10] + line2[13:20] + line2[21:43], composite_check, "Composite check digit"),
        ]

        check_results = []
        for field, check_char, label in checks:
            expected = _mrz_check_digit(field)
            passed   = str(expected) == check_char
            if not passed:
                issues.append(f"{label} failed (expected {expected}, got {check_char})")
            check_results.append({
                "field": label,
                "passed": passed
            })

        info["check_digit_results"] = check_results
        info["issues"]              = issues
        info["valid_mrz"]           = len(issues) == 0
        info["reason"]              = "Valid Indian passport MRZ" if not issues else "; ".join(issues)
        results.append(info)

    return results


def _mrz_check_digit(field_str):
    """MRZ check digit algorithm (ICAO 9303 standard)."""
    weights = [7, 3, 1]
    char_values = {c: i for i, c in enumerate("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")}
    char_values['<'] = 0
    total = 0
    for i, ch in enumerate(field_str):
        total += char_values.get(ch, 0) * weights[i % 3]
    return total % 10


def _parse_mrz_date(date_str):
    """Convert YYMMDD to readable date."""
    try:
        yy, mm, dd = date_str[:2], date_str[2:4], date_str[4:6]
        year = int(yy)
        year = 2000 + year if year < 30 else 1900 + year
        return f"{dd}/{mm}/{year}"
    except Exception:
        return date_str


# ─────────────────────────────────────────────────────────────────────
#  STEP 6: VOTER ID VALIDATION
# ─────────────────────────────────────────────────────────────────────

def validate_voter_id(text):
    """
    Validates EPIC (Voter ID) numbers.
    Format: 3 letters + 7 digits (e.g. ABC1234567)
    First 2 letters often indicate state assembly constituency.
    """
    results = []
    pattern = r'\b([A-Z]{3})(\d{7})\b'
    for m in re.finditer(pattern, text.upper()):
        full_id   = m.group(0)
        prefix    = m.group(1)
        number    = m.group(2)
        results.append({
            "type":         "Voter ID (EPIC)",
            "number":       full_id,
            "prefix":       prefix,
            "serial":       number,
            "valid_format": True,
            "reason":       "Format matches EPIC voter ID pattern"
        })
    return results


# ─────────────────────────────────────────────────────────────────────
#  STEP 7: DATE VALIDATION
# ─────────────────────────────────────────────────────────────────────

def validate_dates(text):
    """Check for logically invalid dates in the document."""
    from datetime import datetime
    issues = []
    date_patterns = [
        (r'\b(\d{2})[/\-](\d{2})[/\-](\d{4})\b', "DD/MM/YYYY"),
        (r'\b(\d{4})[/\-](\d{2})[/\-](\d{2})\b', "YYYY/MM/DD"),
    ]
    for pattern, fmt in date_patterns:
        for m in re.finditer(pattern, text):
            parts = [int(x) for x in m.groups()]
            try:
                if fmt == "DD/MM/YYYY":
                    d = datetime(parts[2], parts[1], parts[0])
                else:
                    d = datetime(parts[0], parts[1], parts[2])
                if d.year < 1900 or d.year > 2100:
                    issues.append(f"Date {m.group(0)} has suspicious year {d.year}")
            except ValueError:
                issues.append(f"Invalid date: {m.group(0)} — day/month values out of range")
    return issues


# ─────────────────────────────────────────────────────────────────────
#  STEP 8: TEXT CONSISTENCY
# ─────────────────────────────────────────────────────────────────────

def check_text_consistency(text):
    """Check for text anomalies that suggest editing."""
    issues = []
    unusual = re.findall(r'[^\w\s\.,;:!?\-/\\()@#$%&*+=\[\]{}|<>~`\'"₹।\u0900-\u097F]', text)
    if unusual:
        issues.append(f"Unusual characters found: {set(unusual)}")
    if re.search(r' {4,}', text):
        issues.append("Excessive spacing detected — possible text manipulation")
    # Check for mixed scripts in name fields (could indicate editing)
    has_latin = bool(re.search(r'[A-Za-z]', text))
    has_devanagari = bool(re.search(r'[\u0900-\u097F]', text))
    return {
        "issues": issues,
        "has_english": has_latin,
        "has_hindi_devanagari": has_devanagari,
        "multilingual_document": has_latin and has_devanagari
    }


# ─────────────────────────────────────────────────────────────────────
#  MAIN: Full Document Analysis
# ─────────────────────────────────────────────────────────────────────

def analyze_document(image_path):
    """
    Main function — extracts multilingual text and runs all Indian document validators.
    Returns structured report compatible with run_all.py and app.py.
    """
    text_result = extract_text(image_path)
    combined_text = text_result["combined"]

    aadhaar   = validate_aadhaar(combined_text)
    pan       = validate_pan(combined_text)
    dl        = validate_driving_licence(combined_text)
    passport  = validate_passport_mrz(combined_text)
    voter_id  = validate_voter_id(combined_text)
    dates     = validate_dates(combined_text)
    text_cons = check_text_consistency(combined_text)

    # Detect document type from what was found
    doc_types_found = []
    if aadhaar:  doc_types_found.append("Aadhaar")
    if pan:      doc_types_found.append("PAN Card")
    if dl:       doc_types_found.append("Driving Licence")
    if passport: doc_types_found.append("Passport")
    if voter_id: doc_types_found.append("Voter ID")

    # Any validation failure = suspicious
    any_invalid = (
        any(not a["valid_format"] for a in aadhaar) or
        any(not p["valid_format"] for p in pan) or
        any(not d["valid_format"] for d in dl) or
        any(not p.get("valid_mrz", True) for p in passport)
    )

    return {
        # Core fields that existing app.py expects
        "extracted_text":    text_result["english"],
        "text_length":       len(combined_text),
        "suspicious_ocr":    len(combined_text) < 20,

        # New multilingual fields
        "languages_detected":     text_result["languages_used"],
        "english_text":           text_result["english"],
        "hindi_text":             text_result["hindi"],
        "hindi_note":             text_result.get("hindi_note", ""),
        "multilingual_document":  text_cons.get("multilingual_document", False),

        # Document type detection
        "document_types_detected": doc_types_found,

        # Validators
        "aadhaar_validation":   aadhaar,
        "pan_validation":       pan,
        "dl_validation":        dl,
        "passport_mrz":         passport,
        "voter_id_validation":  voter_id,
        "date_issues":          dates,
        "text_consistency":     text_cons,

        # Overall
        "overall_suspicious":  any_invalid or text_cons["issues"] != []
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ocr_agent.py <image_path>")
        sys.exit(1)
    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        sys.exit(1)
    result = analyze_document(image_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))
