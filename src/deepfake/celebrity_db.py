"""
CyberLens — Celebrity Database
==================================
Database of known Indian public figures for deepfake detection.
Used to flag when celebrity likenesses appear in scam content
(investment scams, fake endorsements, digital arrest).

Expandable: police can add new persons via add_person().

Author: CyberLens Team — GPCSSI Internship
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("cyberlens.deepfake.celebrity_db")

DB_PATH = Path("data/celebrity_db.json")


@dataclass
class CelebrityProfile:
    """A known public figure profile."""
    name: str
    aliases: List[str] = field(default_factory=list)
    category: str = ""  # BUSINESS, POLITICS, ENTERTAINMENT, SPORTS, GOVT_OFFICIAL
    known_roles: List[str] = field(default_factory=list)
    face_embedding_path: str = ""  # Path to face embedding .npy
    reference_images: List[str] = field(default_factory=list)
    scam_association: str = ""  # What scams commonly use this person
    it_act_if_impersonated: str = ""
    active: bool = True


# ---------------------------------------------------------------------------
# Built-in celebrity database
# ---------------------------------------------------------------------------

BUILTIN_CELEBRITIES: List[CelebrityProfile] = [
    # ── Business Leaders ──────────────────────────────────────────────
    CelebrityProfile(
        name="Mukesh Ambani",
        aliases=["Ambani", "Mukesh Dhirubhai Ambani"],
        category="BUSINESS",
        known_roles=["Chairman of Reliance Industries", "Richest Indian"],
        scam_association="Fake investment schemes claiming Ambani endorsement",
        it_act_if_impersonated="IT Act §66D + IPC §420 + Copyright Act",
    ),
    CelebrityProfile(
        name="Ratan Tata",
        aliases=["Tata", "Ratan Naval Tata"],
        category="BUSINESS",
        known_roles=["Chairman Emeritus of Tata Group", "Philanthropist"],
        scam_association="Fake investment/charity schemes using Tata name",
        it_act_if_impersonated="IT Act §66D + IPC §420",
    ),
    CelebrityProfile(
        name="Gautam Adani",
        aliases=["Adani", "Adani Group"],
        category="BUSINESS",
        known_roles=["Chairman of Adani Group"],
        scam_association="Fake stock tips claiming insider info",
        it_act_if_impersonated="IT Act §66D + SEBI Act §12A",
    ),

    # ── Politicians ───────────────────────────────────────────────────
    CelebrityProfile(
        name="Narendra Modi",
        aliases=["PM Modi", "Modi ji", "Modi", "NaMo"],
        category="POLITICS",
        known_roles=["Prime Minister of India"],
        scam_association="Fake government schemes, PM Kisan scam, digital arrest",
        it_act_if_impersonated="IPC §170 + IT Act §66D + BNS §204",
    ),
    CelebrityProfile(
        name="Amit Shah",
        aliases=["Shah", "Home Minister"],
        category="POLITICS",
        known_roles=["Home Minister of India"],
        scam_association="Digital arrest scams impersonating HM office",
        it_act_if_impersonated="IPC §170 + IT Act §66D + BNS §204",
    ),

    # ── Entertainment ─────────────────────────────────────────────────
    CelebrityProfile(
        name="Amitabh Bachchan",
        aliases=["Amitabh", "Big B", "Bachchan", "KBC host"],
        category="ENTERTAINMENT",
        known_roles=["Actor", "KBC Host"],
        scam_association="Fake KBC lottery scams, fake endorsements",
        it_act_if_impersonated="IT Act §66D + IPC §420",
    ),
    CelebrityProfile(
        name="Shah Rukh Khan",
        aliases=["SRK", "Shah Rukh", "King Khan"],
        category="ENTERTAINMENT",
        known_roles=["Actor", "Film producer"],
        scam_association="Fake endorsement for investment/crypto schemes",
        it_act_if_impersonated="IT Act §66D + Copyright Act",
    ),
    CelebrityProfile(
        name="Salman Khan",
        aliases=["Salman", "Bhai"],
        category="ENTERTAINMENT",
        known_roles=["Actor"],
        scam_association="Fake endorsement scams",
        it_act_if_impersonated="IT Act §66D",
    ),

    # ── Sports ────────────────────────────────────────────────────────
    CelebrityProfile(
        name="Virat Kohli",
        aliases=["Kohli", "King Kohli", "Virat"],
        category="SPORTS",
        known_roles=["Cricketer", "Former India Captain"],
        scam_association="Fake cricket betting tips, fake endorsements",
        it_act_if_impersonated="IT Act §66D + Public Gambling Act",
    ),
    CelebrityProfile(
        name="MS Dhoni",
        aliases=["Dhoni", "MSD", "Captain Cool", "Mahi"],
        category="SPORTS",
        known_roles=["Cricketer", "Former India Captain"],
        scam_association="Fake betting apps, fake endorsements",
        it_act_if_impersonated="IT Act §66D + Public Gambling Act",
    ),
    CelebrityProfile(
        name="Sachin Tendulkar",
        aliases=["Sachin", "Master Blaster", "Tendulkar"],
        category="SPORTS",
        known_roles=["Cricketer", "Bharat Ratna"],
        scam_association="Fake investment endorsements",
        it_act_if_impersonated="IT Act §66D + IPC §420",
    ),
    CelebrityProfile(
        name="Rohit Sharma",
        aliases=["Rohit", "Hitman", "Ro"],
        category="SPORTS",
        known_roles=["Cricketer", "India Captain"],
        scam_association="Fake cricket betting, IPL prediction scams",
        it_act_if_impersonated="IT Act §66D + Public Gambling Act",
    ),

    # ── Government Officials (commonly impersonated) ──────────────────
    CelebrityProfile(
        name="CBI Director",
        aliases=["CBI Officer", "CBI Inspector"],
        category="GOVT_OFFICIAL",
        known_roles=["Director of Central Bureau of Investigation"],
        scam_association="Digital arrest scam — fake CBI notices",
        it_act_if_impersonated="IPC §170 + IT Act §66D + BNS §204",
    ),
    CelebrityProfile(
        name="ED Officer",
        aliases=["Enforcement Directorate", "ED Director"],
        category="GOVT_OFFICIAL",
        known_roles=["Enforcement Directorate official"],
        scam_association="Digital arrest — fake money laundering notices",
        it_act_if_impersonated="IPC §170 + IT Act §66D + PMLA",
    ),
    CelebrityProfile(
        name="Income Tax Officer",
        aliases=["IT Department", "Tax Officer", "IRS Officer"],
        category="GOVT_OFFICIAL",
        known_roles=["Income Tax Department official"],
        scam_association="Fake tax refund scams, digital arrest",
        it_act_if_impersonated="IPC §170 + IT Act §66D",
    ),
    CelebrityProfile(
        name="Customs Officer",
        aliases=["Customs Department", "Airport Customs"],
        category="GOVT_OFFICIAL",
        known_roles=["Customs & Excise Department official"],
        scam_association="Fake parcel/courier scam, digital arrest",
        it_act_if_impersonated="IPC §170 + IT Act §66D",
    ),
]


class CelebrityDatabase:
    """Searchable database of known Indian public figures.

    Used by deepfake detection to flag when a celebrity's likeness
    appears in suspected scam content.

    Attributes:
        profiles: List of CelebrityProfile instances.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize with built-in + any saved profiles.

        Args:
            db_path: Path to persistent JSON database.
        """
        self.db_path = db_path or DB_PATH
        self.profiles: List[CelebrityProfile] = list(BUILTIN_CELEBRITIES)
        self._name_index: Dict[str, CelebrityProfile] = {}

        # Load persisted additions
        self._load_saved()

        # Build name index
        self._build_index()

        logger.info("CelebrityDatabase: %d profiles loaded", len(self.profiles))

    def _build_index(self) -> None:
        """Build name/alias → profile index for fast lookup."""
        self._name_index.clear()
        for profile in self.profiles:
            self._name_index[profile.name.lower()] = profile
            for alias in profile.aliases:
                self._name_index[alias.lower()] = profile

    def _load_saved(self) -> None:
        """Load additional profiles from JSON file."""
        if self.db_path.exists():
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    profile = CelebrityProfile(**item)
                    # Don't duplicate built-in entries
                    if not any(p.name == profile.name for p in self.profiles):
                        self.profiles.append(profile)
                logger.info("Loaded %d saved profiles from %s", len(data), self.db_path)
            except Exception as e:
                logger.debug("Could not load saved profiles: %s", e)

    def search(self, text: str) -> List[CelebrityProfile]:
        """Search text for mentions of known celebrities.

        Checks both full names and aliases.

        Args:
            text: Text to search (OCR output, caption, etc).

        Returns:
            List of matched CelebrityProfile instances.
        """
        text_lower = text.lower()
        matches = []
        seen = set()

        for key, profile in self._name_index.items():
            if key in text_lower and profile.name not in seen:
                matches.append(profile)
                seen.add(profile.name)

        return matches

    def get_by_name(self, name: str) -> Optional[CelebrityProfile]:
        """Look up a celebrity by name or alias.

        Args:
            name: Name or alias to look up.

        Returns:
            CelebrityProfile or None.
        """
        return self._name_index.get(name.lower())

    def get_by_category(self, category: str) -> List[CelebrityProfile]:
        """Get all profiles in a category.

        Args:
            category: BUSINESS, POLITICS, ENTERTAINMENT, SPORTS, GOVT_OFFICIAL.

        Returns:
            List of matching profiles.
        """
        return [p for p in self.profiles if p.category == category]

    def add_person(self, profile: CelebrityProfile) -> None:
        """Add a new person to the database.

        Args:
            profile: CelebrityProfile to add.
        """
        # Check for duplicate
        if any(p.name == profile.name for p in self.profiles):
            logger.warning("Profile already exists: %s", profile.name)
            return

        self.profiles.append(profile)
        self._build_index()
        self._save()
        logger.info("Added new profile: %s", profile.name)

    def remove_person(self, name: str) -> bool:
        """Remove a person from the database.

        Args:
            name: Name of person to remove.

        Returns:
            True if removed, False if not found.
        """
        for i, p in enumerate(self.profiles):
            if p.name.lower() == name.lower():
                self.profiles.pop(i)
                self._build_index()
                self._save()
                logger.info("Removed profile: %s", name)
                return True
        return False

    def _save(self) -> None:
        """Persist profiles to JSON file."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Only save non-builtin profiles
        builtin_names = {p.name for p in BUILTIN_CELEBRITIES}
        custom = [
            asdict(p) for p in self.profiles
            if p.name not in builtin_names
        ]
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(custom, f, ensure_ascii=False, indent=2)

    @property
    def total_profiles(self) -> int:
        return len(self.profiles)

    @property
    def all_names(self) -> List[str]:
        return [p.name for p in self.profiles]
