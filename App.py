# app.py
# Web interface for Document Forgery Detection
# Run with: streamlit run app.py

import streamlit as st
import json
import os
import tempfile
import io
from datetime import datetime
from PIL import Image
import blockchain_agent

from run_all import main as run_full_pipeline

st.set_page_config(
    page_title="Document Forgery Detector",
    page_icon="🔍",
    layout="wide"
)

st.markdown("""
<style>
    .main-header {
        text-align: center; padding: 20px;
        background: linear-gradient(135deg, #1e3c72, #2a5298);
        color: white; border-radius: 10px; margin-bottom: 30px;
    }
    .verdict-genuine   { padding:20px; background:#d4edda; border:2px solid #28a745; border-radius:10px; text-align:center; font-size:24px; }
    .verdict-suspicious{ padding:20px; background:#fff3cd; border:2px solid #ffc107; border-radius:10px; text-align:center; font-size:24px; }
    .verdict-forged    { padding:20px; background:#f8d7da; border:2px solid #dc3545; border-radius:10px; text-align:center; font-size:24px; }
    .hash-box { font-family:monospace; font-size:11px; background:#f4f4f4; padding:8px 12px;
                border-radius:6px; border:1px solid #ddd; word-break:break-all; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════

def validate_document(uploaded_file, is_pdf):
    """Validate file size, corruption, and minimum resolution."""
    file_size_kb = len(uploaded_file.getvalue()) / 1024
    if file_size_kb > 15000:
        return False, f"File too large ({file_size_kb/1024:.1f} MB). Max 15 MB."
    if file_size_kb < 10:
        return False, f"File too small ({file_size_kb:.1f} KB). Upload a valid document."
    if not is_pdf:
        try:
            image_bytes = uploaded_file.getvalue()
            img = Image.open(io.BytesIO(image_bytes))
            img.verify()
            img = Image.open(io.BytesIO(image_bytes))
            w, h = img.size
            if w < 300 or h < 300:
                return False, f"Image too low resolution ({w}x{h}px). Minimum 300x300."
        except Exception:
            return False, "File appears corrupted or is not a valid image."
    return True, "Valid"


def _render_verdict_banner(verdict_text, confidence, risk):
    if verdict_text in ["GENUINE", "AUTHENTIC"]:
        st.markdown(f'<div class="verdict-genuine">✅ {verdict_text} ({confidence}% confidence)</div>', unsafe_allow_html=True)
    elif verdict_text in ["SUSPICIOUS", "POSSIBLY_FORGED"]:
        st.markdown(f'<div class="verdict-suspicious">⚠️ {verdict_text} ({confidence}% confidence)</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="verdict-forged">❌ {verdict_text} ({confidence}% confidence)</div>', unsafe_allow_html=True)
    st.markdown(f"**Risk Level:** `{risk}`")


def _render_agent_reports(report):
    """Renders the 5 expandable agent report sections."""
    st.markdown("---")
    st.subheader("📋 Detailed Agent Reports")

    # ── Blockchain Hash ──
    doc_hash = report.get("document_hash")
    if doc_hash:
        with st.expander("🔐 Blockchain Document Hash"):
            st.markdown("This SHA-256 fingerprint uniquely identifies this exact document. If even one pixel changes, the hash will be completely different.")
            st.markdown(f'<div class="hash-box">{doc_hash}</div>', unsafe_allow_html=True)
            st.caption("Use this hash to verify the document hasn't been altered since this analysis was run.")

    # ── Vision ──
    with st.expander("👁️ Vision Agent Report"):
        vision_report = report.get("vision_report", {})
        if "error" in vision_report:
            st.error(f"Error: {vision_report['error']}")
        else:
            for key, label in [
                ("font_analysis",           "Font Analysis"),
                ("image_artifacts",         "Image Artifacts"),
                ("alignment_issues",        "Alignment"),
                ("quality_inconsistencies", "Quality"),
                ("logo_and_watermark",      "Logo & Watermark")
            ]:
                if key in vision_report:
                    item = vision_report[key]
                    icon = "🔴" if item.get("suspicious") else "🟢"
                    st.markdown(f"{icon} **{label}:** {item.get('details', item.get('finding', str(item)))}")
            if vision_report.get("overall_suspicious"):
                st.error("🔴 Vision: SUSPICIOUS")
            else:
                st.success("🟢 Vision: Clean")

    # ── OCR (Multi-language + Deep Indian Document Validation) ──
    with st.expander("📝 OCR Agent Report — Multi-Language + Indian Document Validation"):
        ocr_report = report.get("ocr_report", {})
        if "error" in ocr_report:
            st.error(f"Error: {ocr_report['error']}")
        else:
            # ── Language detection banner ──
            langs = ocr_report.get("languages_detected", ["English"])
            is_multilingual = ocr_report.get("multilingual_document", False)
            doc_types = ocr_report.get("document_types_detected", [])

            lang_str = " + ".join(langs) if langs else "English"
            st.info(f"🌐 Languages detected: **{lang_str}** | "
                    f"Document type(s): **{', '.join(doc_types) if doc_types else 'Unknown'}**")

            # ── Extracted text tabs ──
            tab_en, tab_hi = st.tabs(["🔤 English Text", "🕉️ Hindi Text"])
            with tab_en:
                eng = ocr_report.get("english_text") or ocr_report.get("extracted_text", "")
                st.text(eng[:2000] if eng else "No English text extracted")
            with tab_hi:
                hin = ocr_report.get("hindi_text", "")
                note = ocr_report.get("hindi_note", "")
                if hin:
                    st.text(hin[:2000])
                elif note:
                    st.warning(f"⚠️ {note}")
                else:
                    st.info("No Hindi text detected")

            st.markdown("---")
            st.subheader("🔍 Document Number Validation")

            # ── Aadhaar ──
            aadhaar_list = ocr_report.get("aadhaar_validation", [])
            if aadhaar_list:
                st.markdown("**Aadhaar / VID:**")
                for a in aadhaar_list:
                    icon = "🟢" if a.get("valid_format") else "🔴"
                    doc_type = a.get("type", "Aadhaar")
                    st.markdown(f"{icon} `{a.get('number')}` — [{doc_type}] {a.get('reason')}")
                    # Show checksum detail
                    checksum_ok = a.get("verhoeff_checksum_passed")
                    if checksum_ok is not None:
                        cs_icon = "✅" if checksum_ok else "❌"
                        st.caption(f"  {cs_icon} Verhoeff checksum: {'passed' if checksum_ok else 'FAILED — number may be fabricated'}")

            # ── PAN ──
            pan_list = ocr_report.get("pan_validation", [])
            if pan_list:
                st.markdown("**PAN Card:**")
                for p in pan_list:
                    icon = "🟢" if p.get("valid_format") else "🔴"
                    st.markdown(f"{icon} `{p.get('number')}` — {p.get('reason')}")
                    cd_ok = p.get("check_digit_valid")
                    if cd_ok is not None:
                        cs_icon = "✅" if cd_ok else "❌"
                        st.caption(f"  {cs_icon} Check digit: {'valid' if cd_ok else 'INVALID — PAN may be fabricated'}")
                        st.caption(f"  Entity type: {p.get('entity_type', 'N/A')}")

            # ── Driving Licence ──
            dl_list = ocr_report.get("dl_validation", [])
            if dl_list:
                st.markdown("**Driving Licence:**")
                for d in dl_list:
                    icon = "🟢" if d.get("valid_format") else "🔴"
                    st.markdown(f"{icon} `{d.get('number')}` — {d.get('reason')}")
                    st.caption(f"  State: {d.get('state_name', 'N/A')} | RTO: {d.get('rto_code', 'N/A')} | Year: {d.get('year_issued', 'N/A')}")

            # ── Passport MRZ ──
            passport_list = ocr_report.get("passport_mrz", [])
            if passport_list:
                st.markdown("**Passport MRZ:**")
                for p in passport_list:
                    icon = "🟢" if p.get("valid_mrz") else "🔴"
                    st.markdown(f"{icon} Passport `{p.get('passport_number', 'N/A')}` — {p.get('reason', '')}")
                    st.caption(f"  Name: {p.get('surname', '')} {p.get('given_name', '')} | "
                               f"DOB: {p.get('date_of_birth', 'N/A')} | "
                               f"Expiry: {p.get('expiry_date', 'N/A')} | "
                               f"Country: {p.get('country', 'N/A')}")
                    # MRZ check digits
                    check_results = p.get("check_digit_results", [])
                    if check_results:
                        all_passed = all(c["passed"] for c in check_results)
                        if all_passed:
                            st.caption("  ✅ All MRZ check digits verified")
                        else:
                            for c in check_results:
                                if not c["passed"]:
                                    st.caption(f"  ❌ {c['field']} failed")

            # ── Voter ID ──
            voter_list = ocr_report.get("voter_id_validation", [])
            if voter_list:
                st.markdown("**Voter ID (EPIC):**")
                for v in voter_list:
                    st.markdown(f"🟢 `{v.get('number')}` — {v.get('reason')}")

            # ── If nothing found ──
            if not any([aadhaar_list, pan_list, dl_list, passport_list, voter_list]):
                st.info("No Indian document numbers detected in this image.")

            # ── Date issues ──
            date_issues = ocr_report.get("date_issues", [])
            if date_issues:
                st.markdown("---")
                st.markdown("**Date Issues:**")
                for issue in date_issues:
                    st.warning(f"⚠️ {issue}")

            # ── Text consistency ──
            tc_issues = ocr_report.get("text_consistency", {}).get("issues", [])
            if tc_issues:
                st.markdown("---")
                for issue in tc_issues:
                    st.warning(f"⚠️ {issue}")

            st.markdown("---")
            if ocr_report.get("suspicious_ocr"):
                st.error("🔴 OCR: SUSPICIOUS — very little text extracted")
            elif ocr_report.get("overall_suspicious"):
                st.warning("⚠️ OCR: Some validation checks failed — review above")
            else:
                st.success("🟢 OCR: All checks passed")

    # ── Metadata ──
    with st.expander("🔬 Metadata Agent Report"):
        meta_report = report.get("metadata_report", {})
        if "error" in meta_report:
            st.error(f"Error: {meta_report['error']}")
        else:
            software = meta_report.get("editing_software_detected", [])
            if software:
                st.error("⚠️ Editing Software Detected!")
                for s in software:
                    st.warning(f"🔴 {s.get('software_detected')} found in {s.get('field')}")
            else:
                st.success("🟢 No editing software detected")
            ela = meta_report.get("error_level_analysis", {})
            if ela:
                icon = "🔴" if ela.get("suspicious") else "🟢"
                st.markdown(f"{icon} **ELA:** {ela.get('interpretation', 'N/A')}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Avg Error", ela.get("average_error_level", "N/A"))
                c2.metric("Max Error", ela.get("max_error_level", "N/A"))
                c3.metric("Variance",  ela.get("error_variance", "N/A"))
            fp = meta_report.get("file_properties", {})
            if fp:
                st.markdown(f"**File Size:** {fp.get('file_size_readable', 'N/A')}")
                if fp.get("suspicious_size"):
                    st.warning(f"⚠️ {fp.get('size_note')}")
            if meta_report.get("overall_suspicious"):
                st.error("🔴 Metadata: SUSPICIOUS")
            else:
                st.success("🟢 Metadata: Clean")

    # ── Signature ──
    with st.expander("✍️ Signature & Seal Agent Report"):
        sig = report.get("signature_report", {})
        if "error" in sig:
            st.error(f"Error: {sig['error']}")
        else:
            if sig.get("summary"):
                st.info(f"📋 {sig['summary']}")
            st.markdown("---")
            sd = sig.get("signature_detection", {})
            if sd:
                icon = "🔴" if sd.get("suspicious") else "🟢"
                present = "Found" if sd.get("signatures_present") else "Not found"
                st.markdown(f"{icon} **Signature:** {present} ({sd.get('signatures_found', 0)} detected)")
                st.markdown(f"  • Quality: `{sd.get('signature_quality', 'N/A')}`")
                st.caption(sd.get("reason", ""))
            st.markdown("---")
            seal = sig.get("seal_detection", {})
            if seal:
                icon = "🔴" if seal.get("suspicious") else "🟢"
                present = "Found" if seal.get("seal_present") else "Not found"
                st.markdown(f"{icon} **Seal/Stamp:** {present} ({seal.get('seals_found', 0)} detected)")
                if seal.get("seal_types"):
                    st.markdown(f"  • Types: {', '.join(seal['seal_types'])}")
                st.caption(seal.get("reason", ""))
            st.markdown("---")
            dup = sig.get("duplication_check", {})
            if dup:
                sig_dup  = dup.get("duplicate_signature_suspected", False)
                seal_dup = dup.get("duplicate_seal_suspected", False)
                icon = "🔴" if (sig_dup or seal_dup) else "🟢"
                st.markdown(f"{icon} **Copy-Paste Check**")
                st.markdown(f"  • Signature duplicated: {'⚠️ Yes' if sig_dup else '✅ No'}")
                st.markdown(f"  • Seal duplicated: {'⚠️ Yes' if seal_dup else '✅ No'}")
                st.caption(dup.get("reason", ""))
            st.markdown("---")
            ink = sig.get("ink_analysis", {})
            if ink:
                icon = "🔴" if ink.get("digitally_inserted_suspected") else "🟢"
                genuine = "Genuine" if ink.get("ink_appears_genuine") else "Suspicious"
                st.markdown(f"{icon} **Ink Analysis:** {genuine}")
                st.markdown(f"  • Color: `{ink.get('ink_color_observed', 'N/A')}`")
                st.markdown(f"  • Digitally inserted: {'⚠️ Suspected' if ink.get('digitally_inserted_suspected') else '✅ No'}")
                st.caption(ink.get("reason", ""))
            st.markdown("---")
            if sig.get("overall_suspicious"):
                st.error("🔴 Signature/Seal: SUSPICIOUS")
            else:
                st.success("🟢 Signature/Seal: Clean")

    with st.expander("🔧 Full Raw JSON Report"):
        st.json(report)


def _render_pdf_results(pdf_report):
    """Renders multi-page PDF analysis results."""
    page_count = pdf_report["page_count"]
    overall    = pdf_report["overall_verdict"]
    forged     = pdf_report.get("forged_page_numbers", [])
    suspicious = pdf_report.get("suspicious_page_numbers", [])
    genuine    = pdf_report.get("genuine_page_numbers", [])

    if overall in ["GENUINE", "AUTHENTIC"]:
        st.markdown(f'<div class="verdict-genuine">✅ GENUINE DOCUMENT ({page_count} pages analyzed)</div>', unsafe_allow_html=True)
    elif overall == "SUSPICIOUS":
        st.markdown(f'<div class="verdict-suspicious">⚠️ SUSPICIOUS — Check pages: {suspicious}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="verdict-forged">❌ FORGERY DETECTED — Tampered pages: {forged}</div>', unsafe_allow_html=True)

    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Pages",   page_count)
    c2.metric("✅ Genuine",    len(genuine))
    c3.metric("⚠️ Suspicious", len(suspicious))
    c4.metric("❌ Forged",     len(forged))
    st.markdown("---")

    st.subheader("📋 Page-by-Page Summary")
    hdr = st.columns([1, 2, 2, 4])
    hdr[0].markdown("**Page**")
    hdr[1].markdown("**Verdict**")
    hdr[2].markdown("**Confidence**")
    hdr[3].markdown("**Top Finding**")

    for page in pdf_report["page_results"]:
        v     = page["verdict"]
        emoji = "✅" if v in ["GENUINE", "AUTHENTIC"] else ("⚠️" if v in ["SUSPICIOUS", "POSSIBLY_FORGED"] else "❌")
        cols  = st.columns([1, 2, 2, 4])
        cols[0].markdown(f"**{page['page_number']}**")
        cols[1].markdown(f"{emoji} {v}")
        cols[2].markdown(f"{page['confidence_percentage']}%")
        cols[3].markdown(page["top_findings"][0] if page["top_findings"] else "—")

    st.markdown("---")
    st.subheader("🔍 Per-Page Detailed Reports")
    for page in pdf_report["page_results"]:
        v     = page["verdict"]
        emoji = "✅" if v in ["GENUINE", "AUTHENTIC"] else ("⚠️" if v in ["SUSPICIOUS", "POSSIBLY_FORGED"] else "❌")
        label = f"{emoji} Page {page['page_number']} — {v} ({page['confidence_percentage']}% confidence)"
        with st.expander(label):
            if page.get("explanation"):
                st.markdown(page["explanation"])
            if page.get("top_findings"):
                st.markdown("**Top Findings:**")
                for i, f in enumerate(page["top_findings"], 1):
                    st.markdown(f"{i}. {f}")
            _render_agent_reports(page["full_report"])

    # ── PDF PHASE — DOWNLOAD BUTTON ──────────────────────────
    st.markdown("---")
    st.subheader("📥 Download Forensic Report")

    most_sus = pdf_report.get("most_suspicious_page")
    if most_sus:
        try:
            import report_exporter

            # Auto-generate heatmaps for the most suspicious page to include in report
            heatmaps_for_pdf = None
            suspicious_tmp   = most_sus.get("temp_image_path")
            if suspicious_tmp and os.path.exists(suspicious_tmp):
                try:
                    import Heatmap as heatmap_agent
                    with st.spinner("Generating heatmaps for report..."):
                        heatmaps_for_pdf = heatmap_agent.generate_all_heatmaps(suspicious_tmp)
                except Exception:
                    heatmaps_for_pdf = None

            with st.spinner("Building PDF forensic report..."):
                pdf_bytes = report_exporter.generate_report(
                    report=most_sus["full_report"],
                    heatmaps=heatmaps_for_pdf,
                    document_name=f"PDF — Most Suspicious Page {most_sus['page_number']}"
                )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                label=f"📄 Download Forensic Report  (Page {most_sus['page_number']} — {most_sus['verdict']})",
                data=pdf_bytes,
                file_name=f"forensic_report_page{most_sus['page_number']}_{timestamp}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            st.caption("Report includes: verdict, findings, agent summaries, heatmaps, metadata, and OCR text.")

        except ImportError:
            st.warning("⚠️ report_exporter.py not found. Add it to your project folder to enable PDF export.")
        except Exception as e:
            st.error(f"❌ Report generation failed: {str(e)}")
    else:
        st.info("No page data available for export.")


# ════════════════════════════════════════════════════════════
#  HEADER
# ════════════════════════════════════════════════════════════

st.markdown("""
<div class="main-header">
    <h1>🔍 AI Document Forgery Detection</h1>
    <p>Multi-Agent AI Pipeline for Forensic Document Analysis</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("🤖 How It Works")
    st.markdown("""
    **5 AI Agents** analyze your document:
    
    1. 👁️ **Vision Agent** — Fonts, alignment, artifacts
    2. 📝 **OCR Agent** — Text validation (Aadhaar, PAN)
    3. 🔬 **Metadata Agent** — Editing traces & ELA
    4. ✍️ **Signature Agent** — Seals, signatures & ink
    5. 🧠 **Verdict Agent** — Final verdict
    """)
    st.markdown("---")
    st.header("🌡️ Heatmap Guide")
    st.markdown("""
    - 🔵 **Blue** = Low / genuine
    - 🟡 **Yellow** = Moderate anomaly
    - 🔴 **Red** = High anomaly / suspicious
    """)
    st.markdown("---")
    st.header("⚙️ System Status")
    try:
        import requests as _req
        _req.get("http://localhost:3000", timeout=3)
        st.success("✅ Flowise is running")
    except:
        st.error("❌ Flowise is NOT running")
        st.caption("Run `npx flowise start` in terminal")

    # Check PyMuPDF
    try:
        import fitz
        st.success("✅ PyMuPDF ready (PDF support)")
    except ImportError:
        st.warning("⚠️ PyMuPDF not installed")
        st.caption("Run: `pip install pymupdf`")

    # Check ReportLab
    try:
        from reportlab.platypus import SimpleDocTemplate
        st.success("✅ ReportLab ready (PDF export)")
    except ImportError:
        st.warning("⚠️ ReportLab not installed")
        st.caption("Run: `pip install reportlab`")


# ════════════════════════════════════════════════════════════
#  UPLOAD + ANALYSIS
# ════════════════════════════════════════════════════════════

col1, col2 = st.columns([1, 1])

if "is_pdf" not in st.session_state:
    st.session_state["is_pdf"] = False

with col1:
    st.header("📤 Upload Document")
    uploaded_file = st.file_uploader(
        "Choose a document image or PDF",
        type=["jpg", "jpeg", "png", "webp", "pdf"],
        help="Supports images (JPG/PNG/WEBP) and multi-page PDFs"
    )
    if uploaded_file:
        st.session_state["is_pdf"] = uploaded_file.name.lower().endswith(".pdf")
        file_size = len(uploaded_file.getvalue())
        st.caption(f"📁 {uploaded_file.name} | {file_size / 1024:.1f} KB")

        if st.session_state["is_pdf"]:
            st.info("📄 PDF detected — each page will be analyzed separately")
        else:
            st.image(uploaded_file, caption="Uploaded Document", use_container_width=True)

with col2:
    st.header("📊 Analysis Results")

    if uploaded_file:
        if st.button("🔍 Analyze Document", type="primary", use_container_width=True):
            tmp_path = None
            try:
                is_pdf = st.session_state["is_pdf"]
                is_valid, val_msg = validate_document(uploaded_file, is_pdf)
                if not is_valid:
                    st.error(f"❌ Validation failed: {val_msg}")
                    st.stop()

                file_ext = os.path.splitext(uploaded_file.name)[1] or ".jpg"
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name

                # ── PDF PATH ──────────────────────────────────
                if is_pdf:
                    try:
                        import pdf_agent
                    except ImportError:
                        st.error("❌ pdf_agent.py not found in the same folder.")
                        st.stop()

                    progress_bar = st.progress(0)
                    status_text  = st.empty()
                    status_text.text("📄 Converting PDF pages to images...")
                    progress_bar.progress(10)

                    pdf_report = pdf_agent.analyze_pdf(tmp_path)
                    progress_bar.progress(100)
                    status_text.text("✅ PDF Analysis Complete!")

                    st.session_state["pdf_report"] = pdf_report

                    if "error" in pdf_report:
                        err = pdf_report["error"]
                        st.error(f"❌ PDF Error: {err}")
                        if "pymupdf" in err.lower() or "fitz" in err.lower() or "poppler" in err.lower():
                            st.info("💡 Fix: run `pip install pymupdf` in your terminal, then restart the app.")
                    else:
                        # _render_pdf_results already contains the PDF download button inside it
                        _render_pdf_results(pdf_report)

                # ── IMAGE PATH ────────────────────────────────
                else:
                    progress_bar = st.progress(0)
                    status_text  = st.empty()

                    status_text.text("👁️ [1/5] Running Vision Agent...")
                    progress_bar.progress(10)
                    status_text.text("📝 [2/5] Running OCR Agent...")
                    progress_bar.progress(25)
                    status_text.text("🔬 [3/5] Running Metadata Agent...")
                    progress_bar.progress(40)
                    status_text.text("✍️ [4/5] Running Signature & Seal Agent...")
                    progress_bar.progress(60)
                    status_text.text("🧠 [5/5] Getting Final Verdict...")
                    progress_bar.progress(80)

                    report = run_full_pipeline(tmp_path)
                    progress_bar.progress(100)
                    status_text.text("✅ Analysis Complete!")

                    st.session_state["last_tmp_path"] = tmp_path
                    st.session_state["last_report"]   = report

                    if report is None:
                        st.error("❌ No report generated. Check if Flowise is running.")
                    elif "error" in report and "final_verdict" not in report:
                        st.error(f"❌ Error: {report['error']}")
                    else:
                        verdict      = report.get("final_verdict", {})
                        verdict_text = verdict.get("verdict", "UNKNOWN")
                        confidence   = verdict.get("confidence_percentage", 0)
                        risk         = verdict.get("risk_level", "UNKNOWN")

                        _render_verdict_banner(verdict_text, confidence, risk)
                        st.markdown("---")

                        findings = verdict.get("top_3_findings", [])
                        if findings:
                            st.subheader("🔍 Top Findings")
                            for i, f in enumerate(findings, 1):
                                st.markdown(f"{i}. {f}")

                        if verdict.get("detailed_explanation"):
                            st.subheader("📄 Explanation")
                            st.markdown(verdict["detailed_explanation"])

                        if verdict.get("recommendations"):
                            st.subheader("💡 Recommendations")
                            for rec in verdict["recommendations"]:
                                st.markdown(f"- {rec}")

                        _render_agent_reports(report)

                        # ── IMAGE PHASE — DOWNLOAD BUTTON ─────────────────
                        st.markdown("---")
                        st.subheader("📥 Download Forensic Report")
                        try:
                            import report_exporter

                            # Auto-generate heatmaps to include in the report
                            heatmaps_for_report = None
                            last_tmp = st.session_state.get("last_tmp_path", "")
                            if last_tmp and os.path.exists(last_tmp):
                                try:
                                    import Heatmap as heatmap_agent
                                    with st.spinner("Generating heatmaps for report..."):
                                        heatmaps_for_report = heatmap_agent.generate_all_heatmaps(last_tmp)
                                except Exception:
                                    heatmaps_for_report = None

                            with st.spinner("Building PDF forensic report..."):
                                pdf_bytes = report_exporter.generate_report(
                                    report=report,
                                    heatmaps=heatmaps_for_report,
                                    document_name=uploaded_file.name
                                )

                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            st.download_button(
                                label="📄 Download Forensic Report (PDF)",
                                data=pdf_bytes,
                                file_name=f"forensic_report_{timestamp}.pdf",
                                mime="application/pdf",
                                use_container_width=True
                            )
                            st.caption("Report includes: verdict, findings, agent summaries, heatmaps, metadata, and OCR text.")

                        except ImportError:
                            st.warning("⚠️ report_exporter.py not found. Add it to your project folder to enable PDF export.")
                        except Exception as e:
                            st.error(f"❌ Report generation failed: {str(e)}")

            except Exception as e:
                st.error(f"❌ An error occurred: {str(e)}")
                import traceback
                with st.expander("🔧 Error Details"):
                    st.code(traceback.format_exc())
            finally:
                pass  # keep tmp_path alive for heatmap section

    else:
        st.info("👈 Upload a document image or PDF to begin analysis")
        with st.expander("📌 See Sample Result"):
            st.json({
                "verdict": "GENUINE",
                "confidence_percentage": 88,
                "risk_level": "LOW",
                "top_3_findings": [
                    "All visual checks passed",
                    "No editing software in metadata",
                    "Signature and seal appear authentic"
                ],
                "document_hash": "a3f5c2e1d4b6...SHA-256 fingerprint",
                "recommendations": ["Cross-verify with issuing authority"]
            })


# ════════════════════════════════════════════════════════════
#  HEATMAP SECTION
# ════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════
#  HEATMAP SECTION
# ════════════════════════════════════════════════════════════

st.markdown("---")
st.header("🌡️ Forensic Heatmap Visualizations")
st.caption("Each heatmap highlights different forgery clues. Red/yellow = suspicious areas.")

if uploaded_file:
    # For PDFs: let user pick which page to heatmap
    if st.session_state.get("is_pdf") and st.session_state.get("pdf_report"):
        pdf_rpt   = st.session_state["pdf_report"]
        page_nums = [p["page_number"] for p in pdf_rpt["page_results"]]
        if page_nums:
            selected_page = st.selectbox(
                "Select page for heatmaps:",
                options=page_nums,
                format_func=lambda n: f"Page {n} — {pdf_rpt['page_results'][n-1]['verdict']}"
            )
            heatmap_source_path = pdf_rpt["page_results"][selected_page - 1].get("temp_image_path")
        else:
            heatmap_source_path = None
    else:
        heatmap_source_path = None

    if st.button("🔥 Generate Heatmaps", use_container_width=True):
        try:
            import Heatmap as heatmap_agent
            file_ext = os.path.splitext(uploaded_file.name)[1] or ".jpg"

            if heatmap_source_path and os.path.exists(heatmap_source_path):
                path_to_use   = heatmap_source_path
                cleanup_after = False
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    path_to_use = tmp.name
                cleanup_after = True

            with st.spinner("Generating forensic heatmaps..."):
                heatmaps = heatmap_agent.generate_all_heatmaps(path_to_use)

            heatmap_items = list(heatmaps.items())

            # ── ROW 1: First 3 heatmaps ──────────────────────────────
            st.subheader("🔬 Primary Forensic Analysis")
            r1c1, r1c2, r1c3 = st.columns(3)
            row1_cols = [r1c1, r1c2, r1c3]

            for i in range(min(3, len(heatmap_items))):
                label, data = heatmap_items[i]
                with row1_cols[i]:
                    st.markdown(f"**{label}**")
                    if data["image"]:
                        st.image(data["image"], use_container_width=True)
                    else:
                        st.error("Failed to generate")
                    st.caption(data["description"])

            # ── ROW 2: Remaining heatmaps (4th and 5th) ──────────────
            if len(heatmap_items) > 3:
                st.markdown("---")
                st.subheader("🔬 Advanced Forensic Analysis")
                
                # Centered layout for 2 heatmaps
                spacing_col, r2c1, r2c2, spacing_col2 = st.columns([0.5, 2, 2, 0.5])
                row2_cols = [r2c1, r2c2]
                
                for i in range(3, min(5, len(heatmap_items))):
                    label, data = heatmap_items[i]
                    with row2_cols[i - 3]:
                        st.markdown(f"**{label}**")
                        if data["image"]:
                            st.image(data["image"], use_container_width=True)
                        else:
                            st.error("Failed to generate")
                        st.caption(data["description"])
                        
                        # Special highlight for FFT heatmap
                        if "FFT" in label or "Frequency" in label:
                            if "Score:" in data["description"]:
                                # Extract score from description
                                import re
                                score_match = re.search(r'Score:\s*(\d+)/100', data["description"])
                                if score_match:
                                    score = int(score_match.group(1))
                                    if score > 70:
                                        st.error(f"🚨 High forgery probability: {score}/100")
                                    elif score > 40:
                                        st.warning(f"⚠️ Moderate risk: {score}/100")
                                    else:
                                        st.success(f"✅ Low risk: {score}/100")

            if cleanup_after:
                try:
                    os.unlink(path_to_use)
                except:
                    pass

        except ImportError:
            st.error("❌ Heatmap.py not found. Make sure it's in the same folder as app.py.")
        except Exception as e:
            st.error(f"❌ Heatmap error: {str(e)}")
            import traceback
            with st.expander("Error details"):
                st.code(traceback.format_exc())

    with st.expander("📖 How to Read the Heatmaps"):
        c1, c2, c3, c4, c5 = st.columns(5)  # ← CHANGED: Now 5 columns
        c1.markdown("**🌡️ Edge Detection**\nSharp edges = cut-paste boundary")
        c2.markdown("**🌡️ ELA**\nRed areas = re-compressed regions")
        c3.markdown("**🌡️ Noise Pattern**\nInconsistent grain = spliced content")
        c4.markdown("**🌡️ Luminance**\nBrightness jumps = editing")
        c5.markdown("**🌡️ FFT Analysis**\nGrid patterns = resampling artifacts")  # ← NEW

else:
    st.info("👈 Upload a document above to enable heatmap analysis")
