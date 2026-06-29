# metadata_agent.py
# Analyzes hidden metadata and does Error Level Analysis

import json
import sys
import os
from PIL import Image
from PIL.ExifTags import TAGS
import io


def extract_metadata(image_path):
    """Extract EXIF metadata from the image"""
    try:
        img = Image.open(image_path)
        metadata = {}
        metadata["format"] = img.format
        metadata["size"] = f"{img.size[0]}x{img.size[1]}"
        metadata["mode"] = img.mode
        exif_data = img._getexif()
        if exif_data:
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if isinstance(value, bytes):
                    try:
                        value = value.decode('utf-8', errors='ignore')
                    except:
                        value = str(value)
                metadata[str(tag_name)] = str(value)
        else:
            metadata["exif_present"] = False
        return metadata
    except Exception as e:
        return {"error": str(e)}


def check_editing_software(metadata):
    """Check if any editing software signatures are found"""
    suspicious_software = [
        "photoshop", "gimp", "paint.net", "pixlr",
        "canva", "illustrator", "corel", "affinity",
        "snapseed", "lightroom", "adobe", "photoscape"
    ]
    findings = []
    for key, value in metadata.items():
        value_lower = str(value).lower()
        for software in suspicious_software:
            if software in value_lower:
                findings.append({
                    "field": key,
                    "value": value,
                    "software_detected": software,
                    "suspicious": True
                })
    return findings


def error_level_analysis(image_path):
    """Simple Error Level Analysis (ELA)"""
    try:
        original = Image.open(image_path).convert('RGB')
        buffer = io.BytesIO()
        original.save(buffer, 'JPEG', quality=95)
        buffer.seek(0)
        resaved = Image.open(buffer).convert('RGB')
        width, height = original.size
        total_diff = 0
        max_diff = 0
        min_diff = 255 * 3
        sample_points = []
        step = max(1, min(width, height) // 50)
        for x in range(0, width, step):
            for y in range(0, height, step):
                orig_pixel = original.getpixel((x, y))
                resaved_pixel = resaved.getpixel((x, y))
                diff = sum(abs(o - r) for o, r in zip(orig_pixel, resaved_pixel))
                total_diff += diff
                max_diff = max(max_diff, diff)
                min_diff = min(min_diff, diff)
                sample_points.append(diff)
        avg_diff = total_diff / len(sample_points) if sample_points else 0
        variance = sum((d - avg_diff) ** 2 for d in sample_points) / len(sample_points)
        ela_result = {
            "average_error_level": round(avg_diff, 2),
            "max_error_level": max_diff,
            "min_error_level": min_diff,
            "error_variance": round(variance, 2),
            "samples_analyzed": len(sample_points),
        }
        if variance > 500:
            ela_result["interpretation"] = "HIGH variance - LIKELY EDITED"
            ela_result["suspicious"] = True
        elif variance > 200:
            ela_result["interpretation"] = "MODERATE variance - POSSIBLY EDITED"
            ela_result["suspicious"] = True
        else:
            ela_result["interpretation"] = "LOW variance - appears original"
            ela_result["suspicious"] = False
        return ela_result
    except Exception as e:
        return {"error": str(e), "suspicious": False}


def check_file_properties(image_path):
    """Check file-level properties"""
    try:
        stat = os.stat(image_path)
        file_size = stat.st_size
        result = {
            "file_size_bytes": file_size,
            "file_size_readable": f"{file_size / 1024:.1f} KB",
        }
        if file_size < 10000:
            result["suspicious_size"] = True
            result["size_note"] = "File is very small"
        elif file_size > 10000000:
            result["suspicious_size"] = True
            result["size_note"] = "File is very large"
        else:
            result["suspicious_size"] = False
        return result
    except Exception as e:
        return {"error": str(e)}


def analyze_metadata(image_path):
    """Main function - complete metadata analysis"""
    metadata = extract_metadata(image_path)
    software_check = check_editing_software(metadata)
    ela_result = error_level_analysis(image_path)
    file_props = check_file_properties(image_path)
    result = {
        "metadata": metadata,
        "editing_software_detected": software_check,
        "error_level_analysis": ela_result,
        "file_properties": file_props,
        "overall_suspicious": (
            len(software_check) > 0 or
            ela_result.get("suspicious", False) or
            file_props.get("suspicious_size", False)
        )
    }
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python metadata_agent.py <image_path>")
        sys.exit(1)
    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        sys.exit(1)
    result = analyze_metadata(image_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))
