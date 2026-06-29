# heatmap_agent.py
# Forensic heatmap visualizations for document forgery detection
# Returns 5 heatmap views — each highlights different forgery clues

import cv2
import numpy as np
from PIL import Image
import io
import base64
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from scipy.ndimage import uniform_filter


# ─────────────────────────────────────────────
#  HELPER: PIL → OpenCV and back
# ─────────────────────────────────────────────

def pil_to_cv2(pil_img):
    """Convert PIL Image (RGB) → OpenCV array (BGR)"""
    return cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2BGR)


def cv2_to_pil(cv2_img):
    """Convert OpenCV array (BGR) → PIL Image (RGB)"""
    return Image.fromarray(cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB))


def image_to_base64(pil_img):
    """Convert PIL Image → base64 string for Streamlit display"""
    buffer = io.BytesIO()
    pil_img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


# ─────────────────────────────────────────────
#  HEATMAP 1: Edge-Based Heatmap
#  (Improved with bilateral filter and dual-pass Canny)
# ─────────────────────────────────────────────

def edge_heatmap(img_bgr):
    """
    Detects sharp edges which reveal cut-paste boundaries.
    Uses bilateral filter to preserve real edges while smoothing noise.
    """
    # Bilateral filter: smooths noise but keeps real sharp edges
    filtered = cv2.bilateralFilter(img_bgr, d=9, sigmaColor=75, sigmaSpace=75)
    gray = cv2.cvtColor(filtered, cv2.COLOR_BGR2GRAY)

    # Two-pass Canny: catches both weak and strong edges
    edges_strong = cv2.Canny(gray, 80, 200)
    edges_weak   = cv2.Canny(gray, 30, 100)
    edges_combined = cv2.addWeighted(edges_strong, 0.7, edges_weak, 0.3, 0)

    # Wider blur = smoother heat glow effect
    heat = cv2.GaussianBlur(edges_combined, (31, 31), 0)
    heat = cv2.normalize(heat, None, 0, 255, cv2.NORM_MINMAX)
    heatmap = cv2.applyColorMap(heat.astype(np.uint8), cv2.COLORMAP_JET)

    overlay = cv2.addWeighted(img_bgr, 0.55, heatmap, 0.45, 0)
    return overlay, "Edge Detection Heatmap — highlights cut/paste boundaries"


# ─────────────────────────────────────────────
#  HEATMAP 2: ELA Heatmap (Error Level Analysis)
#  Most powerful forgery detector
# ─────────────────────────────────────────────

def ela_heatmap(img_bgr):
    """
    Error Level Analysis: resaves the image at quality=90
    and amplifies the difference. Tampered regions show
    higher error levels (brighter in heatmap).
    """
    # Save at lower quality to introduce uniform compression
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
    _, encoded = cv2.imencode(".jpg", img_bgr, encode_param)
    resaved = cv2.imdecode(encoded, cv2.IMREAD_COLOR)

    # Amplify difference (multiply by 15 to make subtle differences visible)
    diff = cv2.absdiff(img_bgr, resaved)
    amplified = np.clip(diff * 15, 0, 255).astype(np.uint8)

    # Convert to grayscale heatmap
    diff_gray = cv2.cvtColor(amplified, cv2.COLOR_BGR2GRAY)
    heat = cv2.GaussianBlur(diff_gray, (15, 15), 0)
    heatmap = cv2.applyColorMap(heat, cv2.COLORMAP_JET)

    overlay = cv2.addWeighted(img_bgr, 0.5, heatmap, 0.5, 0)
    return overlay, "ELA Heatmap — red/yellow = re-compressed regions (tampered)"


# ─────────────────────────────────────────────
#  HEATMAP 3: Noise Inconsistency Heatmap
#  Real documents have uniform camera noise
# ─────────────────────────────────────────────

def noise_heatmap(img_bgr):
    """
    Extracts noise layer by subtracting a median-blurred version.
    Inconsistent noise = region came from a different source image.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)

    # Remove structure, keep only noise
    median = cv2.medianBlur(gray.astype(np.uint8), 5).astype(np.float32)
    noise = np.abs(gray - median)

    # Amplify and normalize
    noise_amplified = np.clip(noise * 10, 0, 255).astype(np.uint8)
    heat = cv2.GaussianBlur(noise_amplified, (21, 21), 0)
    heatmap = cv2.applyColorMap(heat, cv2.COLORMAP_HOT)

    overlay = cv2.addWeighted(img_bgr, 0.6, heatmap, 0.4, 0)
    return overlay, "Noise Heatmap — different noise patterns reveal spliced regions"


# ─────────────────────────────────────────────
#  HEATMAP 4: Luminance Gradient Heatmap
#  Detects brightness gradient anomalies
# ─────────────────────────────────────────────

def luminance_heatmap(img_bgr):
    """
    Maps brightness gradients across the document.
    Sudden luminance jumps in the middle of a flat region = tampered.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # Sobel gradient in both directions
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=5)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=5)
    magnitude = np.sqrt(sobelx**2 + sobely**2)

    magnitude = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    heat = cv2.GaussianBlur(magnitude, (25, 25), 0)
    heatmap = cv2.applyColorMap(heat, cv2.COLORMAP_INFERNO)

    overlay = cv2.addWeighted(img_bgr, 0.6, heatmap, 0.4, 0)
    return overlay, "Luminance Heatmap — brightness gradient anomalies reveal editing"


# ─────────────────────────────────────────────
#  HEATMAP 5: FFT Frequency Domain Analysis
#  **NEW** Detects digital compositing and resampling artifacts
# ─────────────────────────────────────────────

def fft_heatmap(img_bgr):
    """
    Fast Fourier Transform frequency domain analysis.
    Forged documents show characteristic grid patterns (bright dots)
    in the FFT spectrum from resampling/copy-paste operations.
    """
    # Convert to grayscale
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    orig_h, orig_w = gray.shape

    # Optimal size for FFT (power of 2)
    optimal_rows = cv2.getOptimalDFTSize(orig_h)
    optimal_cols = cv2.getOptimalDFTSize(orig_w)

    # Pad image
    padded = np.zeros((optimal_rows, optimal_cols), dtype=np.float32)
    padded[:orig_h, :orig_w] = gray.astype(np.float32)

    # Apply Hanning window to reduce edge artifacts
    window_rows = np.hanning(optimal_rows)
    window_cols = np.hanning(optimal_cols)
    window_2d = np.outer(window_rows, window_cols)
    windowed = padded * window_2d

    # Compute 2D FFT
    fft_result = np.fft.fft2(windowed)
    fft_shifted = np.fft.fftshift(fft_result)

    # Magnitude spectrum (log scale)
    magnitude = np.abs(fft_shifted)
    magnitude_log = np.log1p(magnitude)

    # Normalize for visualization
    mag_min = magnitude_log.min()
    mag_max = magnitude_log.max()
    if mag_max - mag_min > 0:
        magnitude_normalized = ((magnitude_log - mag_min) / (mag_max - mag_min) * 255)
    else:
        magnitude_normalized = np.zeros_like(magnitude_log)

    magnitude_normalized = magnitude_normalized.astype(np.uint8)

    # Detect suspicious peaks
    peak_data = _detect_frequency_peaks(magnitude_log, optimal_rows, optimal_cols)

    # Create custom forensic colormap
    forensic_cmap = _create_forensic_colormap_cv2()
    
    # Apply colormap
    heatmap_colored = cv2.applyColorMap(magnitude_normalized, forensic_cmap)

    # Resize back to original dimensions
    heatmap_resized = cv2.resize(heatmap_colored, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)

    # Create overlay
    overlay = cv2.addWeighted(img_bgr, 0.4, heatmap_resized, 0.6, 0)

    # Draw peak markers on overlay
    if peak_data['peaks']:
        scale_y = orig_h / optimal_rows
        scale_x = orig_w / optimal_cols
        for peak_y, peak_x in peak_data['peaks'][:10]:  # Draw top 10 peaks
            y = int(peak_y * scale_y)
            x = int(peak_x * scale_x)
            cv2.circle(overlay, (x, y), 8, (0, 0, 255), 2)

    description = (
        f"FFT Frequency Domain Analysis — "
        f"Score: {peak_data['forgery_score']}/100 | "
        f"Peaks: {peak_data['peak_count']} | "
        f"{peak_data['verdict']}"
    )

    return overlay, description


def _detect_frequency_peaks(magnitude_log, rows, cols):
    """
    Detect suspicious periodic peaks in the FFT spectrum.
    Returns analysis data including forgery score.
    """
    center_y, center_x = rows // 2, cols // 2

    # Create local mean map
    local_mean = uniform_filter(magnitude_log, size=21)
    local_std = np.sqrt(uniform_filter((magnitude_log - local_mean)**2, size=21))
    local_std[local_std == 0] = 1

    # Z-score computation
    z_score = (magnitude_log - local_mean) / local_std

    # Threshold for anomalies
    threshold = 5.0

    # Create exclusion mask
    exclude_radius = min(rows, cols) // 20
    cross_width = 5
    mask = np.ones_like(z_score, dtype=bool)

    # Exclude center region
    y_coords, x_coords = np.ogrid[:rows, :cols]
    center_mask = ((y_coords - center_y)**2 + (x_coords - center_x)**2) <= exclude_radius**2
    mask[center_mask] = False

    # Exclude cross through center
    mask[center_y - cross_width:center_y + cross_width, :] = False
    mask[:, center_x - cross_width:center_x + cross_width] = False

    # Find peaks
    peak_mask = (z_score > threshold) & mask
    peak_coords = np.argwhere(peak_mask)

    # Process peaks
    peaks = []
    if len(peak_coords) > 0:
        peak_scores = z_score[peak_mask]
        sorted_indices = np.argsort(-peak_scores)
        peak_coords = peak_coords[sorted_indices]
        peak_scores = peak_scores[sorted_indices]

        used = np.zeros(len(peak_coords), dtype=bool)
        cluster_radius = 10

        for i in range(len(peak_coords)):
            if used[i]:
                continue

            py, px = peak_coords[i]
            distances = np.sqrt((peak_coords[:, 0] - py)**2 + (peak_coords[:, 1] - px)**2)
            nearby = distances < cluster_radius
            used[nearby] = True

            peaks.append((int(py), int(px)))

            if len(peaks) >= 20:
                break

    # Calculate forgery score
    peak_count = len(peaks)

    if peak_count == 0:
        forgery_score = 5
        verdict = "CLEAN - No periodic forgery artifacts detected"
    elif peak_count <= 2:
        forgery_score = 25
        verdict = "LOW RISK - Minor frequency anomalies"
    elif peak_count <= 5:
        forgery_score = 55
        verdict = "MODERATE RISK - Periodic patterns detected"
    elif peak_count <= 10:
        forgery_score = 75
        verdict = "HIGH RISK - Multiple periodic artifacts"
    else:
        forgery_score = 95
        verdict = "CRITICAL - Strong grid pattern, highly likely forged"

    return {
        'peaks': peaks,
        'peak_count': peak_count,
        'forgery_score': forgery_score,
        'verdict': verdict
    }


def _create_forensic_colormap_cv2():
    """
    Create a custom OpenCV colormap for FFT visualization.
    Returns colormap ID for cv2.applyColorMap()
    """
    # We'll use a built-in colormap that works well for FFT
    # COLORMAP_HOT works great: black -> red -> yellow -> white
    return cv2.COLORMAP_HOT


# ─────────────────────────────────────────────
#  MAIN: Generate all 5 heatmaps
# ─────────────────────────────────────────────

def generate_all_heatmaps(image_path):
    """
    Loads image and runs all 5 forensic heatmaps.
    Returns a dict of {label: PIL Image} for display in Streamlit.
    """
    pil_img = Image.open(image_path).convert("RGB")
    img_bgr = pil_to_cv2(pil_img)

    results = {}

    generators = [
        ("1. Edge Detection",      edge_heatmap),
        ("2. ELA (Tampering)",     ela_heatmap),
        ("3. Noise Pattern",       noise_heatmap),
        ("4. Luminance Gradient",  luminance_heatmap),
        ("5. FFT Frequency Analysis", fft_heatmap),  # NEW!
    ]

    for label, fn in generators:
        try:
            overlay_bgr, description = fn(img_bgr)
            pil_result = cv2_to_pil(overlay_bgr)
            results[label] = {
                "image": pil_result,
                "description": description
            }
        except Exception as e:
            results[label] = {
                "image": None,
                "description": f"Error: {str(e)}"
            }

    return results


# ─────────────────────────────────────────────
#  ADVANCED: Full FFT Analysis with Detailed Report
#  (For judges/technical demos)
# ─────────────────────────────────────────────

def generate_detailed_fft_analysis(image_path, output_path=None):
    """
    Generate comprehensive FFT forensic analysis with multi-panel visualization.
    This creates a professional 3-panel report similar to research papers.
    
    Returns dict with:
        - fft_report_path: path to saved comprehensive analysis
        - forgery_score: numerical score (0-100)
        - verdict: text assessment
        - peak_count: number of suspicious frequencies detected
    """
    pil_img = Image.open(image_path).convert("RGB")
    img_bgr = pil_to_cv2(pil_img)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    orig_h, orig_w = gray.shape
    
    # Optimal FFT size
    optimal_rows = cv2.getOptimalDFTSize(orig_h)
    optimal_cols = cv2.getOptimalDFTSize(orig_w)
    
    # Pad and window
    padded = np.zeros((optimal_rows, optimal_cols), dtype=np.float32)
    padded[:orig_h, :orig_w] = gray.astype(np.float32)
    
    window_rows = np.hanning(optimal_rows)
    window_cols = np.hanning(optimal_cols)
    window_2d = np.outer(window_rows, window_cols)
    windowed = padded * window_2d
    
    # Compute FFT
    fft_result = np.fft.fft2(windowed)
    fft_shifted = np.fft.fftshift(fft_result)
    magnitude = np.abs(fft_shifted)
    magnitude_log = np.log1p(magnitude)
    
    # Normalize
    mag_min = magnitude_log.min()
    mag_max = magnitude_log.max()
    if mag_max - mag_min > 0:
        magnitude_normalized = ((magnitude_log - mag_min) / (mag_max - mag_min) * 255)
    else:
        magnitude_normalized = np.zeros_like(magnitude_log)
    magnitude_normalized = magnitude_normalized.astype(np.uint8)
    
    # Detect peaks
    peak_data = _detect_frequency_peaks(magnitude_log, optimal_rows, optimal_cols)
    
    # Create anomaly map
    anomaly_map = _create_anomaly_map(magnitude_log, optimal_rows, optimal_cols)
    
    # Create matplotlib figure
    fig, axes = plt.subplots(1, 3, figsize=(20, 7))
    fig.suptitle('FFT Frequency Domain Forensic Analysis', 
                 fontsize=16, fontweight='bold', color='white', y=0.98)
    fig.patch.set_facecolor('#1a1a2e')
    
    # Panel 1: Original
    axes[0].imshow(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    axes[0].set_title('Original Document', color='white', fontsize=13, pad=10)
    axes[0].axis('off')
    
    # Panel 2: FFT Spectrum
    im = axes[1].imshow(magnitude_normalized, cmap='hot', aspect='equal')
    axes[1].set_title('FFT Magnitude Spectrum', color='white', fontsize=13, pad=10)
    axes[1].axis('off')
    
    # Mark peaks
    if peak_data['peaks']:
        peak_y = [p[0] for p in peak_data['peaks'][:10]]
        peak_x = [p[1] for p in peak_data['peaks'][:10]]
        axes[1].scatter(peak_x, peak_y, s=100, facecolors='none', 
                       edgecolors='red', linewidths=2, label='Suspicious Peaks')
        axes[1].legend(loc='upper right', fontsize=9, 
                      facecolor='black', edgecolor='red', labelcolor='white')
    
    cbar = plt.colorbar(im, ax=axes[1], fraction=0.046, pad=0.04)
    cbar.set_label('Log Magnitude', color='white', fontsize=10)
    cbar.ax.yaxis.set_tick_params(color='white')
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color='white')
    
    # Panel 3: Anomaly Map
    axes[2].imshow(anomaly_map, cmap='hot', aspect='equal')
    axes[2].set_title('Anomaly Detection Map', color='white', fontsize=13, pad=10)
    axes[2].axis('off')
    
    # Add verdict text
    verdict_color = '#ff4444' if peak_data['forgery_score'] > 50 else '#44ff44'
    verdict_text = (
        f"Suspicious Peaks: {peak_data['peak_count']}\n"
        f"Forgery Score: {peak_data['forgery_score']}/100\n"
        f"Verdict: {peak_data['verdict']}"
    )
    
    fig.text(0.5, 0.02, verdict_text, ha='center', va='bottom',
             fontsize=12, color=verdict_color, fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='#0d0d1a', 
                      edgecolor=verdict_color, alpha=0.9),
             family='monospace')
    
    plt.tight_layout(rect=[0, 0.08, 1, 0.95])
    
    # Save
    if output_path is None:
        output_path = image_path.rsplit('.', 1)[0] + '_fft_analysis.png'
    
    fig.savefig(output_path, dpi=150, bbox_inches='tight', 
                facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    
    return {
        'fft_report_path': output_path,
        'forgery_score': peak_data['forgery_score'],
        'verdict': peak_data['verdict'],
        'peak_count': peak_data['peak_count']
    }


def _create_anomaly_map(magnitude_log, rows, cols):
    """Create residual map showing deviations from expected radial pattern"""
    center_y, center_x = rows // 2, cols // 2
    
    # Create radial distance map
    y_coords, x_coords = np.ogrid[:rows, :cols]
    radius_map = np.sqrt((y_coords - center_y)**2 + (x_coords - center_x)**2).astype(int)
    
    max_radius = int(np.sqrt(center_y**2 + center_x**2))
    radial_mean = np.zeros(max_radius + 1)
    radial_count = np.zeros(max_radius + 1)
    
    # Compute radial average
    flat_radius = radius_map.flatten()
    flat_mag = magnitude_log.flatten()
    
    for r, m in zip(flat_radius, flat_mag):
        if r <= max_radius:
            radial_mean[r] += m
            radial_count[r] += 1
    
    radial_count[radial_count == 0] = 1
    radial_mean /= radial_count
    
    # Reconstruct expected spectrum
    expected = np.zeros_like(magnitude_log)
    valid_mask = radius_map <= max_radius
    expected[valid_mask] = radial_mean[radius_map[valid_mask]]
    
    # Residual
    residual = magnitude_log - expected
    residual = np.maximum(residual, 0)
    
    # Normalize
    if residual.max() > 0:
        residual = (residual / residual.max() * 255).astype(np.uint8)
    else:
        residual = np.zeros_like(magnitude_log, dtype=np.uint8)
    
    return residual


# ─────────────────────────────────────────────
#  TESTING
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_image = sys.argv[1]
        print(f"Testing FFT analysis on: {test_image}")
        
        # Generate all heatmaps
        results = generate_all_heatmaps(test_image)
        
        print("\n" + "="*60)
        print("HEATMAP GENERATION RESULTS:")
        print("="*60)
        
        for label, data in results.items():
            if data['image']:
                print(f"✓ {label}")
                print(f"  {data['description']}")
            else:
                print(f"✗ {label}: {data['description']}")
        
        # Generate detailed FFT report
        print("\nGenerating detailed FFT analysis...")
        fft_result = generate_detailed_fft_analysis(test_image)
        print(f"\n✓ FFT Report saved to: {fft_result['fft_report_path']}")
        print(f"  Forgery Score: {fft_result['forgery_score']}/100")
        print(f"  Verdict: {fft_result['verdict']}")
        print("="*60 + "\n")
    else:
        print("Usage: python heatmap_agent.py <image_path>")
        print("Example: python heatmap_agent.py sample_document.png")
        
