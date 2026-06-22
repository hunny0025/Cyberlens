"""
CyberLens — QR Code Extractor
================================
Extracts and classifies all QR codes in scam images.

QR types detected:
  UPI_PAYMENT  — payee name, UPI ID, amount
  URL          — web URL (checked against threat intel)
  PHONE        — phone number
  WHATSAPP     — wa.me/ deep links
  TELEGRAM     — t.me/ deep links

Install: pip install pyzbar opencv-python-headless

Author: CyberLens Team — GPCSSI Internship
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger("cyberlens.ocr.qr")


@dataclass
class QRResult:
    """Decoded QR code result."""
    raw_value: str
    qr_type: str               # UPI_PAYMENT / URL / PHONE / WHATSAPP / TELEGRAM / UNKNOWN
    decoded_data: dict = field(default_factory=dict)
    risk_score: float = 0.0    # 0.0 – 1.0
    position: tuple = (0, 0, 0, 0)  # x, y, w, h


class QRExtractor:
    """Detects and classifies all QR codes in an image."""

    def extract_qr(self, image_path: str) -> List[QRResult]:
        """Extract all QR codes from an image.

        Args:
            image_path: Path to image file.

        Returns:
            List of QRResult for each QR code found.
        """
        raw_qrs = self._decode_qrs(image_path)
        results = []
        for raw_val, position in raw_qrs:
            qr_type, decoded_data = self._classify_qr(raw_val)
            risk = self._score_risk(qr_type, decoded_data, raw_val)
            results.append(QRResult(
                raw_value=raw_val,
                qr_type=qr_type,
                decoded_data=decoded_data,
                risk_score=risk,
                position=position,
            ))
        if results:
            logger.info("QR codes found: %d", len(results))
        return results

    def _decode_qrs(self, image_path: str) -> List[tuple]:
        """Low-level QR decoding with pyzbar + OpenCV fallback."""
        results = []

        # Try pyzbar first (best accuracy)
        try:
            import cv2
            from pyzbar import pyzbar

            img = cv2.imread(image_path)
            if img is None:
                raise ValueError(f"Cannot read image: {image_path}")

            decoded = pyzbar.decode(img)
            for obj in decoded:
                data = obj.data.decode("utf-8", errors="ignore")
                rect = obj.rect
                results.append((data, (rect.left, rect.top, rect.width, rect.height)))

            if not decoded:
                # Try preprocessed version (enhanced contrast)
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                for obj in pyzbar.decode(thresh):
                    data = obj.data.decode("utf-8", errors="ignore")
                    rect = obj.rect
                    results.append((data, (rect.left, rect.top, rect.width, rect.height)))

            return results

        except ImportError:
            logger.info("pyzbar not installed — trying OpenCV QR detector")

        # Fallback: OpenCV built-in QR detector
        try:
            import cv2
            img = cv2.imread(image_path)
            if img is None:
                return []
            detector = cv2.QRCodeDetector()
            data, points, _ = detector.detectAndDecode(img)
            if data:
                results.append((data, (0, 0, 0, 0)))
            return results
        except Exception as e:
            logger.warning("QR extraction failed: %s", e)
            return []

    def _classify_qr(self, value: str) -> tuple:
        """Classify QR code type and decode payload.

        Returns:
            (qr_type, decoded_data dict)
        """
        val = value.strip()

        # UPI Payment QR (upi://pay?pa=xxx@yyy&pn=Name&am=Amount)
        if val.startswith("upi://"):
            return self._parse_upi_qr(val)

        # WhatsApp deep link
        if "wa.me/" in val or "api.whatsapp.com" in val:
            phone = re.search(r"wa\.me/(\d+)", val)
            return ("WHATSAPP", {
                "phone": phone.group(1) if phone else "",
                "link": val,
            })

        # Telegram deep link
        if "t.me/" in val or "telegram.me/" in val:
            username = re.search(r"t\.me/([^\s/?]+)", val)
            return ("TELEGRAM", {
                "username": username.group(1) if username else "",
                "link": val,
            })

        # Phone number
        if re.match(r"^tel:\+?\d+$", val) or re.match(r"^\+91\d{10}$", val):
            return ("PHONE", {"phone": val.replace("tel:", "")})

        # General URL
        if val.startswith("http://") or val.startswith("https://"):
            parsed = urlparse(val)
            return ("URL", {"domain": parsed.netloc, "full_url": val})

        # Unknown
        return ("UNKNOWN", {"raw": val})

    def _parse_upi_qr(self, upi_url: str) -> tuple:
        """Parse UPI payment QR code."""
        try:
            parsed = urlparse(upi_url)
            params = parse_qs(parsed.query)
            return ("UPI_PAYMENT", {
                "upi_id": params.get("pa", [""])[0],
                "payee_name": params.get("pn", [""])[0],
                "amount": params.get("am", [""])[0],
                "currency": params.get("cu", ["INR"])[0],
                "full_url": upi_url,
            })
        except Exception:
            return ("UPI_PAYMENT", {"raw": upi_url})

    def _score_risk(self, qr_type: str, decoded: dict, raw: str) -> float:
        """Score risk of a QR code (0.0–1.0)."""
        base_risk = {
            "UPI_PAYMENT": 0.7,    # Any UPI QR is suspect in scam context
            "TELEGRAM": 0.8,       # Telegram links heavily used for scam funnels
            "WHATSAPP": 0.75,
            "PHONE": 0.6,
            "URL": 0.5,
            "UNKNOWN": 0.3,
        }.get(qr_type, 0.3)

        # Bump risk if amount is specified (direct payment)
        if decoded.get("amount") and float(decoded.get("amount", 0) or 0) > 0:
            base_risk = min(1.0, base_risk + 0.15)

        return round(base_risk, 2)
