"""
extract_pdf.py

Extracts text and images from a PDF file.
Usage: python extract_pdf.py <path_to_pdf> [--output-dir <dir>] [--skip-pages N]
                              [--min-width PX] [--min-height PX] [--min-score N]
"""

import argparse
import json
import sys
from pathlib import Path

import fitz  # pymupdf
from PIL import Image
import io
import numpy as np


# ── Scoring helpers ──────────────────────────────────────────────────────────

def laplacian_variance(img_array: np.ndarray) -> float:
    """
    Convert to grayscale, apply a Laplacian kernel, return variance of the result.
    High variance = rich edge detail.
    """
    # Weighted grayscale (ITU-R BT.601)
    if img_array.ndim == 3:
        gray = (
            img_array[..., 0] * 0.299 +
            img_array[..., 1] * 0.587 +
            img_array[..., 2] * 0.114
        )
    else:
        gray = img_array.astype(float)

    kernel = np.array([[0, 1, 0],
                       [1, -4, 1],
                       [0, 1, 0]], dtype=float)

    # Manual 2-D convolution via stride tricks (avoids scipy dependency)
    h, w = gray.shape
    # Pad by 1 pixel (zero-padding)
    padded = np.pad(gray, 1, mode="constant")
    # Build output using kernel application
    lap = np.zeros((h, w), dtype=float)
    for dy in range(3):
        for dx in range(3):
            lap += kernel[dy, dx] * padded[dy:dy + h, dx:dx + w]

    return float(np.var(lap))


def color_entropy(img_array: np.ndarray) -> float:
    """
    Compute mean Shannon entropy across RGB channels.
    High entropy = complex / varied colour distribution.
    """
    if img_array.ndim == 2:
        # Grayscale — treat as single channel
        channels = [img_array.ravel()]
    else:
        channels = [img_array[..., c].ravel() for c in range(img_array.shape[2])]

    entropies = []
    for channel in channels:
        counts, _ = np.histogram(channel, bins=256, range=(0, 256))
        total = counts.sum()
        if total == 0:
            entropies.append(0.0)
            continue
        probs = counts / total
        # Avoid log(0)
        probs = probs[probs > 0]
        entropies.append(float(-np.sum(probs * np.log2(probs))))

    return float(np.mean(entropies))


def compute_interest_score(pil_image: Image.Image) -> float:
    """
    Combined visual-interest score for a PIL image.

    Resizes to max 512px on the longest side before scoring (speed).
    Score = (laplacian_variance / 1000) * 0.6 + color_entropy * 0.4
    """
    # Resize for speed
    max_side = 512
    w, h = pil_image.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        pil_image = pil_image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # Ensure RGB (handles palette / RGBA / grayscale PDFs)
    rgb = pil_image.convert("RGB")
    arr = np.array(rgb, dtype=float)

    lap = laplacian_variance(arr) / 1000.0
    ent = color_entropy(arr)

    return lap * 0.6 + ent * 0.4


# ── Main extraction ──────────────────────────────────────────────────────────

def extract_pdf(
    pdf_path: str,
    output_dir: str = None,
    skip_pages: int = 0,
    min_width: int = 200,
    min_height: int = 200,
    min_score: float = 2.0,
    jpeg_only: bool = False,
) -> dict:
    """
    Extract text and images from a PDF.

    Args:
        skip_pages:  number of pages to skip from the beginning (e.g. cover/TOC pages).
        min_width:   minimum image width in pixels; smaller images are discarded.
        min_height:  minimum image height in pixels; smaller images are discarded.
        min_score:   minimum visual-interest score; low-scoring images are discarded.

    Returns a dict with:
        - pages:   list of {page, text} dicts
        - images:  list of {path, score} dicts for kept images
        - metadata: PDF metadata
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if output_dir is None:
        output_dir = Path("site/images")
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    result = {
        "source": pdf_path.name,
        "metadata": doc.metadata,
        "pages": [],
        "images": [],
    }

    for page_num, page in enumerate(doc, start=1):
        if page_num <= skip_pages:
            continue
        result["pages"].append({
            "page": page_num,
            "text": page.get_text(),
        })

        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            ext = base_image["ext"]

            image = Image.open(io.BytesIO(image_bytes))

            # Size filter
            if image.width < min_width or image.height < min_height:
                continue

            # Interest score filter
            score = compute_interest_score(image)
            if score < min_score:
                continue

            # JPEG-only filter: skip low-scoring PNGs (usually decorative overlays)
            if jpeg_only and ext.lower() == "png" and score < 1.0:
                continue

            image_filename = f"{pdf_path.stem}_p{page_num}_img{img_index}.{ext}"
            image_path = output_dir / image_filename
            if not image_path.exists():
                image.save(str(image_path))
            result["images"].append({
                "path": str(image_path),
                "score": round(score, 2),
            })

    doc.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="Extract text and images from a PDF.")
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("--output-dir", default="site/images", help="Directory to save extracted images")
    parser.add_argument("--skip-pages", type=int, default=0, metavar="N", help="Skip the first N pages (e.g. cover/TOC)")
    parser.add_argument("--min-width", type=int, default=200, metavar="PX", help="Minimum image width in pixels (default 200)")
    parser.add_argument("--min-height", type=int, default=200, metavar="PX", help="Minimum image height in pixels (default 200)")
    parser.add_argument("--min-score", type=float, default=2.0, metavar="N", help="Minimum visual-interest score (default 2.0)")
    parser.add_argument("--jpeg-only", action="store_true", default=False,
        help="Skip PNG images with score below 1.0 (usually decorative overlays)")
    args = parser.parse_args()

    try:
        result = extract_pdf(
            args.pdf, args.output_dir, args.skip_pages,
            args.min_width, args.min_height, args.min_score, args.jpeg_only,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
