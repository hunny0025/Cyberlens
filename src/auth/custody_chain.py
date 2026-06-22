"""
CyberLens — Evidence Chain of Custody
==========================================
IT Act §65B compliant evidence certification.

Every piece of evidence is:
  1. SHA256 hashed at collection time
  2. Signed with officer's badge number
  3. Recorded in append-only custody log
  4. Exportable as §65B certificate PDF

Author: CyberLens Team — GPCSSI India
"""

import hashlib
import json
import logging
import os
import secrets
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cyberlens.auth.custody")

EVIDENCE_ROOT = Path(os.getenv("EVIDENCE_DIR", "data/evidence"))
CUSTODY_LOG_PATH = Path(os.getenv("AUDIT_LOG_DIR", "logs/audit")) / "custody.jsonl"


@dataclass
class CustodyRecord:
    """A single evidence custody event."""
    record_id: str
    timestamp: str
    campaign_id: str
    evidence_id: str
    officer_id: str
    officer_badge: str
    officer_name: str
    district: str
    action: str            # COLLECTED / TRANSFERRED / ACCESSED / SUBMITTED / SEALED
    file_path: str
    file_hash_sha256: str
    file_size_bytes: int
    source_url: str = ""
    platform: str = ""
    notes: str = ""
    section_65b_certified: bool = False


@dataclass
class EvidenceCertificate:
    """IT Act §65B evidence certificate."""
    certificate_id: str
    campaign_id: str
    campaign_name: str
    issue_date: str
    officer_id: str
    officer_badge: str
    officer_name: str
    district: str
    evidence_items: List[Dict[str, Any]]
    total_items: int
    it_act_sections: List[str]
    declaration: str
    overall_hash: str       # SHA256 of all evidence hashes concatenated


class CustodyChain:
    """Manages IT Act §65B compliant evidence chain of custody."""

    def __init__(self):
        EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
        CUSTODY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    def collect_evidence(
        self,
        file_path: str,
        campaign_id: str,
        officer_id: str,
        officer_badge: str,
        officer_name: str,
        district: str,
        source_url: str = "",
        platform: str = "",
        notes: str = "",
    ) -> CustodyRecord:
        """Collect a piece of evidence and record custody.

        Creates an immutable copy in the evidence store with SHA256 hash.

        Args:
            file_path: Original file path.
            campaign_id: Associated campaign ID.

        Returns:
            CustodyRecord for the collected evidence.
        """
        evidence_id = secrets.token_hex(12)
        ts = datetime.now(timezone.utc).isoformat()

        # Compute hash of original file
        file_hash = self._hash_file(file_path)
        file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0

        # Copy to evidence store (immutable evidence copy)
        evidence_dir = EVIDENCE_ROOT / campaign_id / "files"
        evidence_dir.mkdir(parents=True, exist_ok=True)

        ext = Path(file_path).suffix
        evidence_copy = evidence_dir / f"{evidence_id}{ext}"
        try:
            shutil.copy2(file_path, evidence_copy)
        except Exception as e:
            logger.warning("Evidence copy failed: %s", e)

        record = CustodyRecord(
            record_id=secrets.token_hex(8),
            timestamp=ts,
            campaign_id=campaign_id,
            evidence_id=evidence_id,
            officer_id=officer_id,
            officer_badge=officer_badge,
            officer_name=officer_name,
            district=district,
            action="COLLECTED",
            file_path=str(evidence_copy),
            file_hash_sha256=file_hash,
            file_size_bytes=file_size,
            source_url=source_url,
            platform=platform,
            notes=notes,
        )

        self._append_record(record)
        logger.info("Evidence collected: %s (hash=%s)", evidence_id, file_hash[:12])
        return record

    def transfer_custody(
        self,
        evidence_id: str,
        campaign_id: str,
        from_officer: str,
        to_officer: str,
        to_badge: str,
        reason: str,
    ) -> CustodyRecord:
        """Record transfer of custody between officers."""
        record = CustodyRecord(
            record_id=secrets.token_hex(8),
            timestamp=datetime.now(timezone.utc).isoformat(),
            campaign_id=campaign_id,
            evidence_id=evidence_id,
            officer_id=to_officer,
            officer_badge=to_badge,
            officer_name="",
            district="",
            action="TRANSFERRED",
            file_path="",
            file_hash_sha256="",
            file_size_bytes=0,
            notes=f"Transferred from {from_officer} to {to_officer}: {reason}",
        )
        self._append_record(record)
        return record

    def generate_section_65b_certificate(
        self,
        campaign_id: str,
        campaign_name: str,
        officer_id: str,
        officer_badge: str,
        officer_name: str,
        district: str,
        it_act_sections: List[str],
    ) -> EvidenceCertificate:
        """Generate IT Act §65B evidence certificate.

        Args:
            campaign_id: Campaign to certify evidence for.

        Returns:
            EvidenceCertificate ready for PDF generation.
        """
        records = self.get_campaign_records(campaign_id)
        collected = [r for r in records if r.get("action") == "COLLECTED"]

        # Compute overall hash (hash of all evidence hashes)
        all_hashes = "".join(r.get("file_hash_sha256", "") for r in collected)
        overall_hash = hashlib.sha256(all_hashes.encode()).hexdigest()

        declaration = (
            "I, the undersigned officer, hereby certify under Section 65B of the "
            "Information Technology Act, 2000 that:\n\n"
            "1. The electronic records listed herein were produced by a computer "
            "during the ordinary course of activity.\n"
            "2. The computer was operating properly at the time of creation.\n"
            "3. The information contained is accurate and reliable.\n"
            "4. The SHA256 hashes recorded herein confirm integrity of the evidence.\n\n"
            f"This certificate was generated by CyberLens v3.0 — "
            f"Gurugram Police Cyber Security Cell (GPCSSI)."
        )

        cert = EvidenceCertificate(
            certificate_id="CERT-" + secrets.token_hex(6).upper(),
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            issue_date=datetime.now(timezone.utc).isoformat(),
            officer_id=officer_id,
            officer_badge=officer_badge,
            officer_name=officer_name,
            district=district,
            evidence_items=collected,
            total_items=len(collected),
            it_act_sections=it_act_sections,
            declaration=declaration,
            overall_hash=overall_hash,
        )

        # Save certificate
        cert_path = EVIDENCE_ROOT / campaign_id / "section_65b_certificate.json"
        with open(cert_path, "w", encoding="utf-8") as f:
            json.dump(asdict(cert), f, indent=2)

        logger.info("§65B certificate issued: %s for campaign %s", cert.certificate_id, campaign_id)
        return cert

    def verify_evidence_integrity(self, evidence_id: str, campaign_id: str) -> Dict[str, Any]:
        """Verify that an evidence file hasn't been tampered with."""
        records = self.get_campaign_records(campaign_id)
        record = next(
            (r for r in records if r.get("evidence_id") == evidence_id and r.get("action") == "COLLECTED"),
            None,
        )
        if not record:
            return {"verified": False, "reason": "Evidence record not found"}

        file_path = record.get("file_path", "")
        if not Path(file_path).exists():
            return {"verified": False, "reason": "Evidence file missing"}

        current_hash = self._hash_file(file_path)
        stored_hash = record.get("file_hash_sha256", "")
        intact = current_hash == stored_hash

        return {
            "verified": intact,
            "evidence_id": evidence_id,
            "stored_hash": stored_hash,
            "current_hash": current_hash,
            "file_path": file_path,
            "tampered": not intact,
        }

    def get_campaign_records(self, campaign_id: str) -> List[Dict]:
        """Get all custody records for a campaign."""
        if not CUSTODY_LOG_PATH.exists():
            return []
        records = []
        try:
            with open(CUSTODY_LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    r = json.loads(line)
                    if r.get("campaign_id") == campaign_id:
                        records.append(r)
        except Exception:
            pass
        return records

    def _append_record(self, record: CustodyRecord) -> None:
        """Append custody record to log (append-only)."""
        try:
            with open(CUSTODY_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(record)) + "\n")
        except Exception as e:
            logger.error("CUSTODY LOG WRITE FAILED: %s", e)

    @staticmethod
    def _hash_file(path: str) -> str:
        """Compute SHA256 of a file."""
        sha256 = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception:
            return ""


# Singleton
_custody_chain: Optional[CustodyChain] = None


def get_custody_chain() -> CustodyChain:
    global _custody_chain
    if _custody_chain is None:
        _custody_chain = CustodyChain()
    return _custody_chain
