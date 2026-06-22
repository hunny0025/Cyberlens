"""
CyberLens — Neo4j Graph Node & Relationship Models
=====================================================
Dataclasses for all graph entities used in criminal network analysis.

Author: CyberLens Team — GPCSSI Internship
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Node types
# ---------------------------------------------------------------------------

@dataclass
class ChannelNode:
    id: str
    name: str
    platform: str              # instagram / telegram / facebook / youtube
    subscriber_count: int = 0
    risk_score: float = 0.0    # 0–100
    first_seen: str = ""
    post_count: int = 0
    scam_category: str = ""

    def to_props(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class PhoneNumberNode:
    value: str                 # +91-XXXXXXXXXX (normalized)
    flag_count: int = 0
    carrier: str = ""
    location_hint: str = ""    # "Gurugram, Haryana" from telecom data
    first_seen: str = ""
    last_seen: str = ""

    def to_props(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class UPIIdNode:
    value: str                 # xxx@bank
    bank: str = ""
    flag_count: int = 0
    total_amount_flagged: float = 0.0
    first_seen: str = ""

    def to_props(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class TelegramUserNode:
    username: str
    role: str = "UNKNOWN"      # ADMIN / RECRUITER / VICTIM_HANDLER / MONEY_MULE / CONTENT_DISTRIBUTOR
    activity_score: float = 0.0
    channels_operated: int = 0
    first_seen: str = ""

    def to_props(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ScamCampaignNode:
    id: str
    name: str
    start_date: str = ""
    risk_level: str = "MEDIUM"   # LOW / MEDIUM / HIGH / CRITICAL
    victim_estimate: int = 0
    channel_count: int = 0
    scam_category: str = ""
    status: str = "ACTIVE"

    def to_props(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ImageNode:
    hash: str                  # SHA256 of image
    embedding_path: str = ""   # path to .npy CLIP embedding
    scam_type: str = ""
    first_seen: str = ""
    usage_count: int = 0
    phash: str = ""            # perceptual hash

    def to_props(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class DomainNode:
    url: str
    registration_date: str = ""
    is_phishing: bool = False
    virustotal_score: float = 0.0
    first_seen: str = ""

    def to_props(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class QRCodeNode:
    decoded_value: str
    qr_type: str = "UNKNOWN"   # UPI_PAYMENT / URL / PHONE / WHATSAPP / TELEGRAM
    linked_entity: str = ""    # resolved entity (UPI ID, phone, URL)
    risk_score: float = 0.0
    first_seen: str = ""

    def to_props(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


# ---------------------------------------------------------------------------
# Relationship types
# ---------------------------------------------------------------------------

RELATIONSHIP_TYPES = {
    "BELONGS_TO":        ("Channel", "ScamCampaign"),
    "USES_PHONE":        ("Channel", "PhoneNumber"),
    "USES_UPI":          ("Channel", "UPIId"),
    "SHARES_CONTENT":    ("Channel", "Image"),
    "OPERATED_BY":       ("Channel", "TelegramUser"),
    "LINKED_TO":         ("PhoneNumber", "UPIId"),
    "SIMILAR_TO":        ("Image", "Image"),          # + similarity_score prop
    "PART_OF":           ("TelegramUser", "ScamCampaign"),
    "HOSTS":             ("Domain", "Channel"),
    "CONTAINS_QR":       ("Image", "QRCode"),
    "CO_OCCURRENCE":     ("Channel", "Channel"),      # share same entity
}

# Node label → dataclass map
NODE_LABEL_MAP = {
    "Channel": ChannelNode,
    "PhoneNumber": PhoneNumberNode,
    "UPIId": UPIIdNode,
    "TelegramUser": TelegramUserNode,
    "ScamCampaign": ScamCampaignNode,
    "Image": ImageNode,
    "Domain": DomainNode,
    "QRCode": QRCodeNode,
}
