"""
CyberLens — IT Act Legal Mapper (Comprehensive)
===================================================
Maps ALL scam categories to the complete Indian legal framework:
IT Act 2000, BNS 2023, PMLA 2002, FEMA 1999,
Consumer Protection Act 2019, TRAI/SEBI/RBI regulations.

Author: CyberLens Team — GPCSSI Internship
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("cyberlens.classifier.it_act_mapper")


@dataclass
class LegalSection:
    """A single applicable legal section."""
    section_number: str
    act_name: str
    description: str
    punishment: str
    cognizable: bool = True
    bailable: bool = False


@dataclass
class LegalMapping:
    """Complete legal mapping for a scam category."""
    category_id: str
    primary_section: LegalSection
    additional_sections: List[LegalSection] = field(default_factory=list)
    fir_recommended: bool = True
    reporting_authority: str = "I4C"
    urgency: str = "HIGH"
    action_steps: List[str] = field(default_factory=list)

    @property
    def all_sections(self) -> List[LegalSection]:
        return [self.primary_section] + self.additional_sections

    @property
    def all_section_strings(self) -> List[str]:
        return [f"{s.act_name} {s.section_number}" for s in self.all_sections]


# ---------------------------------------------------------------------------
# Legal section database
# ---------------------------------------------------------------------------

# IT Act 2000 sections
IT_66 = LegalSection("§66", "IT Act 2000", "Computer related offences", "3 years + ₹5 lakh fine")
IT_66C = LegalSection("§66C", "IT Act 2000", "Identity theft", "3 years + ₹1 lakh fine")
IT_66D = LegalSection("§66D", "IT Act 2000", "Cheating by personation using computer resource", "3 years + ₹1 lakh fine")
IT_66E = LegalSection("§66E", "IT Act 2000", "Violation of privacy — publishing private images", "3 years + ₹2 lakh fine")
IT_67 = LegalSection("§67", "IT Act 2000", "Publishing obscene material electronically", "3 years + ₹5 lakh fine (1st), 5 years + ₹10 lakh (2nd)")
IT_67A = LegalSection("§67A", "IT Act 2000", "Publishing sexually explicit material", "5 years + ₹10 lakh fine (1st)")
IT_67B = LegalSection("§67B", "IT Act 2000", "Publishing child sexual abuse material", "5 years + ₹10 lakh fine (1st), 7 years + ₹10 lakh (2nd)")
IT_69A = LegalSection("§69A", "IT Act 2000", "Power to block websites/content", "N/A — Govt power")
IT_79 = LegalSection("§79", "IT Act 2000", "Intermediary liability exemption conditions", "N/A — Safe harbour provision")

# BNS 2023 (replacing IPC)
BNS_77 = LegalSection("§77", "BNS 2023", "Criminal intimidation through electronic means", "2 years + fine")
BNS_204 = LegalSection("§204", "BNS 2023", "Impersonation of public servant", "3 years + fine")
BNS_318 = LegalSection("§318", "BNS 2023", "Cheating and dishonestly inducing delivery of property", "7 years + fine")
BNS_319 = LegalSection("§319", "BNS 2023", "Cheating by personation", "5 years + fine")
BNS_351 = LegalSection("§351", "BNS 2023", "Criminal intimidation", "2 years + fine")

# IPC sections (still referenced in many FIRs)
IPC_170 = LegalSection("§170", "IPC 1860", "Impersonating a public servant", "2 years + fine")
IPC_419 = LegalSection("§419", "IPC 1860", "Cheating by personation", "3 years + fine")
IPC_420 = LegalSection("§420", "IPC 1860", "Cheating and dishonestly inducing delivery of property", "7 years + fine")
IPC_506 = LegalSection("§506", "IPC 1860", "Criminal intimidation", "2 years + fine")

# Special Acts
GAMBLING_ACT = LegalSection("§3-5", "Public Gambling Act 1867", "Keeping common gaming house / being found gambling", "₹200 fine / 3 months")
PMLA = LegalSection("§3-4", "PMLA 2002", "Money laundering — proceeds of crime", "3-7 years + fine")
FEMA = LegalSection("§13", "FEMA 1999", "Contravention of foreign exchange regulations", "3x amount + penalty")
SEBI_ACT = LegalSection("§12A", "SEBI Act 1992", "Prohibition of fraudulent and unfair trade practices", "10 years + ₹25 crore fine")
CONSUMER_PROT = LegalSection("§2(47)", "Consumer Protection Act 2019", "Unfair trade practices", "Compensation + penalty")
TRAI_REG = LegalSection("TCCCPR", "TRAI Regulations", "Telecom Commercial Communications Customer Preference Regulations", "₹50,000 per violation")
NDPS = LegalSection("§20-29", "NDPS Act 1985", "Possession and sale of narcotics/psychotropic substances", "10-20 years + fine")
POCSO_14 = LegalSection("§14/15", "POCSO Act 2012", "Using child for pornographic purposes / storing CSAM", "5 years + fine (1st), 7 years (2nd)")
COPYRIGHT = LegalSection("§63", "Copyright Act 1957", "Offence of infringement of copyright", "6 months - 3 years + ₹50K-2L fine")
TRADEMARK = LegalSection("§103", "Trademark Act 1999", "Penalty for applying false trademarks", "6 months - 3 years + ₹50K-2L fine")

# ---------------------------------------------------------------------------
# Category → Legal mapping
# ---------------------------------------------------------------------------

LEGAL_MAPPINGS: Dict[str, LegalMapping] = {
    "real_money_betting": LegalMapping(
        category_id="real_money_betting",
        primary_section=IT_66D,
        additional_sections=[GAMBLING_ACT, IT_67, BNS_318],
        fir_recommended=True,
        reporting_authority="I4C",
        urgency="HIGH",
        action_steps=[
            "Block reported URLs and UPI IDs immediately",
            "File FIR under IT Act §66D and applicable State Gambling Act",
            "Coordinate with I4C for takedown of Telegram/WhatsApp groups",
            "Alert payment processors to freeze associated UPI IDs",
            "Submit to cybercrime.gov.in for national database entry",
        ],
    ),
    "investment_scam": LegalMapping(
        category_id="investment_scam",
        primary_section=IT_66D,
        additional_sections=[IPC_420, BNS_318, SEBI_ACT, PMLA],
        fir_recommended=True,
        reporting_authority="I4C + SEBI",
        urgency="HIGH",
        action_steps=[
            "Freeze UPI IDs and bank accounts linked to the scheme",
            "File FIR under IT Act §66D and IPC §420",
            "Report to SEBI for unauthorized investment advisory",
            "Coordinate with RBI for financial fraud investigation",
            "Submit to I4C with evidence of promised guaranteed returns",
        ],
    ),
    "loan_scam": LegalMapping(
        category_id="loan_scam",
        primary_section=IT_66D,
        additional_sections=[IPC_420, BNS_318, CONSUMER_PROT],
        fir_recommended=True,
        reporting_authority="I4C + RBI",
        urgency="HIGH",
        action_steps=[
            "Block fake loan app on Play Store / App Store",
            "File FIR under IT Act §66D and IPC §420",
            "Report to RBI for unauthorized lending activity",
            "Alert Google/Apple for app takedown",
            "Freeze linked bank accounts via PMLA provisions",
        ],
    ),
    "job_scam": LegalMapping(
        category_id="job_scam",
        primary_section=IT_66D,
        additional_sections=[IPC_420, BNS_318],
        fir_recommended=True,
        reporting_authority="I4C",
        urgency="MEDIUM",
        action_steps=[
            "Block reported URLs and phone numbers",
            "File FIR under IT Act §66D",
            "Report to cybercrime.gov.in",
            "Alert job platforms (Naukri, LinkedIn) about impersonation",
        ],
    ),
    "lottery_scam": LegalMapping(
        category_id="lottery_scam",
        primary_section=IT_66D,
        additional_sections=[IPC_420, BNS_318],
        fir_recommended=True,
        reporting_authority="I4C",
        urgency="MEDIUM",
        action_steps=[
            "Block phone numbers sending lottery messages",
            "File FIR under IT Act §66D and IPC §420",
            "Report to DoT for TRAI violation",
            "Alert payment processors about associated UPIs",
        ],
    ),
    "fake_customer_care": LegalMapping(
        category_id="fake_customer_care",
        primary_section=IT_66C,
        additional_sections=[IT_66D, IPC_419, BNS_319, TRAI_REG],
        fir_recommended=True,
        reporting_authority="I4C + DoT",
        urgency="HIGH",
        action_steps=[
            "Block reported phone numbers via TRAI DND registry",
            "File FIR under IT Act §66C (identity theft) and §66D",
            "Report fake helpline numbers to the impersonated company",
            "Alert telecom providers to disconnect scam numbers",
            "Submit victim support request to cybercrime.gov.in",
        ],
    ),
    "fake_govt_official": LegalMapping(
        category_id="fake_govt_official",
        primary_section=IPC_170,
        additional_sections=[IT_66D, BNS_204, BNS_351, IPC_506],
        fir_recommended=True,
        reporting_authority="I4C + Local Police",
        urgency="CRITICAL",
        action_steps=[
            "IMMEDIATE: Block all associated phone numbers and URLs",
            "File FIR under IPC §170 (impersonating public servant)",
            "Coordinate with cyber crime branch for tracing",
            "Alert DoT for telecom provider cooperation",
            "Issue public advisory about digital arrest scam",
        ],
    ),
    "fake_celebrity_endorsement": LegalMapping(
        category_id="fake_celebrity_endorsement",
        primary_section=IT_66D,
        additional_sections=[IPC_420, BNS_318, COPYRIGHT],
        fir_recommended=True,
        reporting_authority="I4C + SEBI",
        urgency="HIGH",
        action_steps=[
            "Take down deepfake / fake endorsement content",
            "File FIR under IT Act §66D and Copyright Act",
            "Report to SEBI if investment-related",
            "Coordinate with platform for content removal",
            "Alert celebrity's representatives",
        ],
    ),
    "sextortion_threat": LegalMapping(
        category_id="sextortion_threat",
        primary_section=IT_66E,
        additional_sections=[BNS_77, IT_67, IT_67A, IPC_506, BNS_351],
        fir_recommended=True,
        reporting_authority="I4C + Local Police",
        urgency="CRITICAL",
        action_steps=[
            "IMMEDIATE: Ensure victim safety and provide counselling contact",
            "File FIR under IT Act §66E, §67, and BNS §77",
            "Request platform to remove content immediately",
            "Trace perpetrator through payment/communication records",
            "Coordinate with NCPCR if minor involved",
        ],
    ),
    "child_exploitation": LegalMapping(
        category_id="child_exploitation",
        primary_section=POCSO_14,
        additional_sections=[IT_67B, IT_66E],
        fir_recommended=True,
        reporting_authority="I4C + NCPCR + Interpol",
        urgency="CRITICAL",
        action_steps=[
            "IMMEDIATE: Report to NCMEC / NCPCR",
            "File FIR under POCSO Act §14/15 and IT Act §67B",
            "Request immediate content takedown from platform",
            "Coordinate with Interpol ICSE database",
            "Preserve all digital evidence with chain of custody",
        ],
    ),
    "drug_sale": LegalMapping(
        category_id="drug_sale",
        primary_section=NDPS,
        additional_sections=[IT_66, IT_79],
        fir_recommended=True,
        reporting_authority="NCB + Local Police",
        urgency="CRITICAL",
        action_steps=[
            "File FIR under NDPS Act immediately",
            "Report to Narcotics Control Bureau (NCB)",
            "Request platform content takedown",
            "Coordinate with NCB for delivery interception",
            "Block associated URLs and payment channels",
        ],
    ),
    "fake_followers_sale": LegalMapping(
        category_id="fake_followers_sale",
        primary_section=IT_66,
        additional_sections=[CONSUMER_PROT],
        fir_recommended=False,
        reporting_authority="Platform + I4C",
        urgency="LOW",
        action_steps=[
            "Report to respective platform (Instagram, YouTube)",
            "Document for pattern analysis",
            "Flag associated accounts for monitoring",
        ],
    ),
    "counterfeit_products": LegalMapping(
        category_id="counterfeit_products",
        primary_section=TRADEMARK,
        additional_sections=[CONSUMER_PROT, IT_66],
        fir_recommended=True,
        reporting_authority="I4C + Brand owner",
        urgency="MEDIUM",
        action_steps=[
            "File FIR under Trademark Act §103",
            "Report to e-commerce platform for listing removal",
            "Alert brand owner's legal team",
            "Document for consumer protection complaint",
        ],
    ),
    "piracy_links": LegalMapping(
        category_id="piracy_links",
        primary_section=COPYRIGHT,
        additional_sections=[IT_66, IT_69A],
        fir_recommended=False,
        reporting_authority="I4C + MEITY",
        urgency="MEDIUM",
        action_steps=[
            "Request ISP blocking under IT Act §69A",
            "Report to content owner for DMCA takedown",
            "Submit to cybercrime.gov.in",
            "Flag for DoT domain blocking",
        ],
    ),
}


class ITActMapper:
    """Maps scam categories to the complete Indian legal framework.

    Provides legal section lookup, FIR recommendations, reporting
    authority identification, and officer action steps.
    """

    def __init__(self):
        self.mappings = LEGAL_MAPPINGS
        logger.info("ITActMapper initialized with %d categories", len(self.mappings))

    def get_mapping(self, category_id: str) -> Optional[LegalMapping]:
        """Get the full legal mapping for a category.

        Args:
            category_id: Category identifier (e.g., 'real_money_betting').

        Returns:
            LegalMapping or None if category not found.
        """
        return self.mappings.get(category_id)

    def get_primary_section(self, category_id: str) -> str:
        """Get the primary legal section string for a category."""
        mapping = self.mappings.get(category_id)
        if mapping:
            s = mapping.primary_section
            return f"{s.act_name} {s.section_number}"
        return "N/A"

    def get_all_sections(self, category_id: str) -> List[str]:
        """Get all applicable legal section strings."""
        mapping = self.mappings.get(category_id)
        if mapping:
            return mapping.all_section_strings
        return []

    def get_action_steps(self, category_id: str) -> List[str]:
        """Get recommended action steps for officers."""
        mapping = self.mappings.get(category_id)
        if mapping:
            return mapping.action_steps
        return []

    def is_fir_recommended(self, category_id: str) -> bool:
        """Check if FIR is recommended for this category."""
        mapping = self.mappings.get(category_id)
        return mapping.fir_recommended if mapping else False

    def get_reporting_authority(self, category_id: str) -> str:
        """Get the primary reporting authority."""
        mapping = self.mappings.get(category_id)
        return mapping.reporting_authority if mapping else "I4C"

    def get_urgency(self, category_id: str) -> str:
        """Get urgency level for this category."""
        mapping = self.mappings.get(category_id)
        return mapping.urgency if mapping else "MEDIUM"

    def get_punishment(self, category_id: str) -> str:
        """Get the punishment for the primary section."""
        mapping = self.mappings.get(category_id)
        if mapping:
            return mapping.primary_section.punishment
        return "N/A"
