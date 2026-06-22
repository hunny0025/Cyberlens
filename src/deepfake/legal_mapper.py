"""
CyberLens — Legal Mapper
===========================
Maps deepfake detection and intent analysis results to specific
Indian IT Act, BNS, and other applicable legal sections.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.deepfake.detector import DeepfakeResult
from src.deepfake.intent_analyzer import IntentResult

logger = logging.getLogger("cyberlens.deepfake.legal")


@dataclass
class LegalMapping:
    """Legal sections and actions mapped to detected intent."""
    primary_section: str
    all_sections: List[str] = field(default_factory=list)
    description: str = ""
    fir_recommended: bool = False
    urgency: str = "MEDIUM"
    action_steps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "primary_section": self.primary_section,
            "all_sections": self.all_sections,
            "description": self.description,
            "fir_recommended": self.fir_recommended,
            "urgency": self.urgency,
            "action_steps": self.action_steps,
        }


# ── Legal section database ──────────────────────────────────────────────

LEGAL_DATABASE = {
    "NCII": {
        "primary": "IT Act Section 66E — Violation of Privacy",
        "sections": [
            "IT Act Section 66E — Punishment for violation of privacy (capturing/publishing private images)",
            "BNS Section 77 — Voyeurism",
            "IT Act Section 67 — Publishing obscene material electronically",
            "IT Act Section 67A — Publishing sexually explicit material",
            "IT Act Section 67B — Publishing child sexually exploitative material",
        ],
        "description": (
            "Creation/distribution of non-consensual intimate images using deepfake "
            "technology. Violates privacy rights under IT Act §66E and constitutes "
            "voyeurism under BNS §77. If material involves minors, POCSO Act applies "
            "with enhanced penalties."
        ),
        "fir": True,
        "actions": [
            "1. Immediately preserve all digital evidence (screenshots, URLs, metadata)",
            "2. File FIR under IT Act §66E and BNS §77",
            "3. Request emergency takedown from platform via I4C",
            "4. If minor involved: invoke POCSO Act §14/15 and inform NCPCR",
            "5. Request ISP-level blocking of content through DoT",
            "6. Coordinate with Cyber Crime Investigation Cell for forensic analysis",
            "7. Apply for victim protection order if identity is known",
        ],
    },
    "NCII_MINOR": {
        "primary": "POCSO Act Section 14 — Using child for pornographic purposes",
        "sections": [
            "POCSO Act Section 14 — Using child for pornographic purposes",
            "POCSO Act Section 15 — Storage of child pornographic material",
            "IT Act Section 67B — Publishing child sexually exploitative material",
            "IT Act Section 66E — Violation of privacy",
            "BNS Section 77 — Voyeurism",
            "Protection of Children from Sexual Offences Act 2012 (POCSO)",
        ],
        "description": (
            "CRITICAL: Deepfake material involving a minor. Falls under POCSO Act "
            "with mandatory minimum sentences. Non-bailable offence. Immediate "
            "intervention required."
        ),
        "fir": True,
        "actions": [
            "⚠️ CRITICAL — IMMEDIATE ACTION REQUIRED ⚠️",
            "1. File ZERO FIR immediately — POCSO is a cognizable, non-bailable offence",
            "2. Inform District Child Protection Officer (DCPO) within 24 hours",
            "3. Notify NCPCR (National Commission for Protection of Child Rights)",
            "4. Emergency content takedown via I4C CSAM reporting channel",
            "5. Seize all devices of suspect for forensic examination",
            "6. Contact CBI Cybercrime Cell if inter-state network suspected",
            "7. Ensure victim identity protection under POCSO §23",
        ],
    },
    "POLITICAL": {
        "primary": "IT Act Section 66D — Cheating by personation using computer resource",
        "sections": [
            "IT Act Section 66D — Cheating by personation using computer resource",
            "Representation of the People Act 1951 — Section 171C (undue influence at elections)",
            "IT Act Section 66 — Computer related offences",
            "BNS Section 356 — Defamation",
            "IT Act Section 69A — Power to block websites (through MEITY)",
        ],
        "description": (
            "Political deepfake designed to spread misinformation or defame political "
            "figures. Violates IT Act §66D and may constitute electoral offence under "
            "the Representation of the People Act during election periods."
        ),
        "fir": True,
        "actions": [
            "1. Document and preserve deepfake content with metadata",
            "2. File FIR under IT Act §66D (personation)",
            "3. Report to Election Commission if during election period",
            "4. Request platform takedown + I4C coordination",
            "5. Notify MEITY for potential Section 69A blocking order",
            "6. Alert PIB Fact Check Unit for official debunking",
            "7. Coordinate with local SP/DCP for investigation",
        ],
    },
    "DEFAMATION": {
        "primary": "BNS Section 356 — Defamation",
        "sections": [
            "BNS Section 356 — Defamation (criminal)",
            "IT Act Section 66D — Cheating by personation",
            "IT Act Section 66C — Identity theft",
            "IT Act Section 79 — Intermediary liability (platform responsibility)",
        ],
        "description": (
            "Deepfake content used for criminal defamation — creating false "
            "narratives about individuals using AI-manipulated images/video. "
            "Prosecutable under BNS §356 and IT Act §66C/66D."
        ),
        "fir": True,
        "actions": [
            "1. Preserve evidence with timestamps and source URLs",
            "2. File FIR under BNS §356 and IT Act §66C",
            "3. Request content removal under IT Act §79 (intermediary notice)",
            "4. Obtain court order for platform data disclosure if needed",
            "5. Coordinate forensic analysis to prove manipulation",
            "6. Support victim in filing civil defamation suit if desired",
        ],
    },
    "SCAM": {
        "primary": "IT Act Section 66D — Cheating by personation using computer resource",
        "sections": [
            "IT Act Section 66D — Cheating by personation",
            "IT Act Section 66C — Identity theft",
            "IPC Section 420 / BNS Section 318 — Cheating",
            "Public Gambling Act 1867 (for betting scams)",
            "SEBI Act (for investment fraud)",
            "PMCS Banning Act 1978 (for Ponzi schemes)",
        ],
        "description": (
            "Online scam involving financial fraud through fake betting platforms, "
            "investment schemes, or impersonation of legitimate customer care services. "
            "Multiple sections of IT Act and IPC/BNS apply."
        ),
        "fir": True,
        "actions": [
            "1. Block reported phone numbers, UPI IDs, and URLs",
            "2. File FIR under IT Act §66D and BNS §318 (cheating)",
            "3. Coordinate with bank/UPI provider to freeze scam accounts",
            "4. Report to I4C (cybercrime.gov.in) for national database",
            "5. Alert telecom providers to disconnect scam numbers",
            "6. If investment scam: report to SEBI",
            "7. If betting: invoke Public Gambling Act provisions",
        ],
    },
    "UNKNOWN": {
        "primary": "Under review — insufficient evidence for specific section",
        "sections": [
            "IT Act Section 66 — Computer related offences (generic)",
        ],
        "description": (
            "Content flagged for review but insufficient evidence to map to "
            "a specific legal section. Requires manual officer review."
        ),
        "fir": False,
        "actions": [
            "1. Flag for manual officer review",
            "2. Preserve content for further analysis",
            "3. Consult with legal team for section applicability",
        ],
    },
}


class LegalMapper:
    """Maps deepfake/intent results to Indian legal sections.

    Uses the LEGAL_DATABASE to provide exact IT Act, BNS, POCSO, and
    other applicable sections based on detected intent category.
    """

    def map_to_law(
        self,
        deepfake_result: Optional[DeepfakeResult],
        intent_result: IntentResult,
    ) -> LegalMapping:
        """Map analysis results to applicable legal sections.

        Args:
            deepfake_result: Result from deepfake detector (can be None).
            intent_result: Result from intent analyzer.

        Returns:
            LegalMapping with sections, description, and action steps.
        """
        category = intent_result.intent_category

        # Special case: NCII with minor indicators
        if category == "NCII" and intent_result.urgency_level == "CRITICAL":
            # Check if minor-related
            if any("MINOR" in r.upper() for r in intent_result.reasoning):
                category = "NCII_MINOR"

        # Look up legal database
        legal_info = LEGAL_DATABASE.get(category, LEGAL_DATABASE["UNKNOWN"])

        # Determine urgency
        urgency = intent_result.urgency_level
        if deepfake_result and deepfake_result.deepfake_probability > 0.8:
            # Escalate urgency for high-confidence deepfakes
            urgency_levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            idx = urgency_levels.index(urgency)
            if idx < len(urgency_levels) - 1:
                urgency = urgency_levels[idx + 1]

        mapping = LegalMapping(
            primary_section=legal_info["primary"],
            all_sections=legal_info["sections"],
            description=legal_info["description"],
            fir_recommended=legal_info["fir"],
            urgency=urgency,
            action_steps=legal_info["actions"],
        )

        logger.info(
            "Legal mapping: %s → %s (FIR=%s, urgency=%s)",
            category, mapping.primary_section,
            mapping.fir_recommended, mapping.urgency,
        )
        return mapping
