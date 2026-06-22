#!/usr/bin/env python3
"""
CyberLens -- Realistic Synthetic Data Generator
====================================================
Generates realistic scam channel data with:
    - Real-looking posts in Hindi/English/Hinglish
    - Shared entities across channels (same UPI, phone, domain)
    - Blocklist entries (I4C advisories, CERT-In alerts)
    - Message ID gaps (simulating deletion)
    - Posting schedules with operator patterns
    - Backup channel migration mentions
    - Cross-channel entity overlap for attribution testing

This is synthetic data structured exactly like real Telegram
intelligence data would be.  It enables the full pipeline to
produce meaningful recommendations and attribution results.

Usage:
    python scripts/generate_realistic_data.py

Author: CyberLens Team
"""

import json
import random
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# ===================================================================
# OPERATOR PROFILES — channels run by the same operator share entities
# ===================================================================
# Each operator has a set of UPIs, phones, and domains they reuse
# across their channels.  This is the core signal for attribution.

OPERATORS = {
    "OP_ALPHA": {
        "upis": ["quickpay247@ybl", "investnow99@paytm", "profitking@oksbi"],
        "phones": ["+91-8876543210", "+91-7765432109"],
        "domains": ["stockprofit247.online", "investguru.site", "tradepro.xyz"],
        "channels": ["stock_tips_vip_india", "crypto_signals_india_vip", "mutual_fund_guaranteed"],
        "style": "investment",
        "lang_mix": {"hindi": 0.2, "english": 0.4, "hinglish": 0.4},
    },
    "OP_BETA": {
        "upis": ["forexking@ybl", "doublemoney@paytm"],
        "phones": ["+91-9988776655", "+91-8877665544"],
        "domains": ["forexprofitdaily.online", "doubleyourmoney.site"],
        "channels": ["forex_trading_profit_daily", "double_money_scheme_india"],
        "style": "investment",
        "lang_mix": {"hindi": 0.3, "english": 0.3, "hinglish": 0.4},
    },
    "OP_GAMMA": {
        "upis": ["bettips@ybl", "iplvip@paytm", "cricketpro@oksbi"],
        "phones": ["+91-9123456789", "+91-9234567890", "+91-9345678901"],
        "domains": ["iplbettingtips.online", "cricketprediction.site", "sattaresult.xyz"],
        "channels": ["ipl_betting_tips_official", "cricket_toss_prediction_vip",
                      "satta_matka_online_24x7", "casino_india_real_money"],
        "style": "betting",
        "lang_mix": {"hindi": 0.5, "english": 0.1, "hinglish": 0.4},
    },
    "OP_DELTA": {
        "upis": ["helpdesk@ybl", "support247@paytm"],
        "phones": ["+91-1800999888", "+91-8800112233"],
        "domains": ["sbi-helpdesk.online", "paytm-support.site", "airtel-kyc.online"],
        "channels": ["sbi_customer_care_official", "paytm_helpline_support", "airtel_kyc_update_urgent"],
        "style": "impersonation",
        "lang_mix": {"hindi": 0.3, "english": 0.5, "hinglish": 0.2},
    },
    "OP_EPSILON": {
        "upis": ["jobpay@ybl", "taskwork@paytm"],
        "phones": ["+91-7700889966"],
        "domains": ["amazontasks.online", "homejobnow.site"],
        "channels": ["work_from_home_india_jobs", "amazon_review_job_daily"],
        "style": "job",
        "lang_mix": {"hindi": 0.2, "english": 0.5, "hinglish": 0.3},
    },
    "OP_ZETA": {
        "upis": ["loanfast@ybl"],
        "phones": ["+91-6655443322"],
        "domains": ["instantloan.online"],
        "channels": ["instant_loan_no_documents"],
        "style": "loan",
        "lang_mix": {"hindi": 0.4, "english": 0.2, "hinglish": 0.4},
    },
    "OP_ETA": {
        "upis": [],
        "phones": ["+91-9900887766"],
        "domains": ["viralexpose.site"],
        "channels": ["viral_video_expose_india"],
        "style": "sextortion",
        "lang_mix": {"hindi": 0.6, "english": 0.1, "hinglish": 0.3},
    },
    "OP_THETA": {
        "upis": ["govfine@ybl", "cbipay@paytm"],
        "phones": ["+91-1400000001", "+91-1400000002"],
        "domains": ["cbi-verification.online", "digital-arrest.site"],
        "channels": ["cbi_verification_portal"],
        "style": "digital_arrest",
        "lang_mix": {"hindi": 0.3, "english": 0.5, "hinglish": 0.2},
    },
    "OP_IOTA": {
        "upis": ["investgold@ybl"],
        "phones": ["+91-8811223344"],
        "domains": ["ambani-invest.online"],
        "channels": ["ambani_investment_secret"],
        "style": "celebrity",
        "lang_mix": {"hindi": 0.2, "english": 0.5, "hinglish": 0.3},
    },
    "OP_KAPPA": {
        "upis": [],
        "phones": ["+91-7788990011"],
        "domains": ["420delivery.site"],
        "channels": ["india_420_delivery_service"],
        "style": "drugs",
        "lang_mix": {"hindi": 0.5, "english": 0.2, "hinglish": 0.3},
    },
    "OP_LAMBDA": {
        "upis": [],
        "phones": [],
        "domains": ["freemovies-hd.site", "bollywood-download.online"],
        "channels": ["bollywood_movies_free_hd"],
        "style": "piracy",
        "lang_mix": {"hindi": 0.3, "english": 0.4, "hinglish": 0.3},
    },
}

# ===================================================================
# POST TEMPLATES — realistic scam messages by category
# ===================================================================

POST_TEMPLATES = {
    "investment": [
        "GUARANTEED 300% RETURN! Invest Rs.5000 today, get Rs.20000 tomorrow! UPI: {upi} Join VIP group now!",
        "Today's profit: Rs.47,500! Screenshot attached. Don't miss tomorrow's signal! Contact: {phone}",
        "Stock market secret tip! Buy before 3PM for guaranteed profit! Register: {domain}",
        "Aaj ka profit dekho bhai! Rs.25,000 in just 2 hours! Jaldi join karo: {domain}",
        "Mutual fund me 50% monthly return! Government approved scheme! UPI: {upi}",
        "LAST CHANCE! Investment plan closing in 2 hours! Minimum Rs.1000! {phone}",
        "Crypto signal ALERT! BTC going up 500%! Premium group access: {domain}",
        "Paisa lagao, paisa kamao! Daily income guaranteed! Contact: {phone}",
        "Share market me loss ho raha hai? Humare signals follow karo! 100% profit guarantee! {upi}",
        "Free trial for 3 days! Then Rs.999/month for VIP signals! WhatsApp: {phone}",
        "Monthly income Rs.50,000-1,00,000 from home! Invest just Rs.2000! {upi}",
        "Premium stock tips with 99% accuracy! Join now: {domain}",
        "Forex trading karo ghar baithe! Daily Rs.5000+ earning! UPI deposit: {upi}",
        "Abhi invest karo ya baad me pachtao! Scheme sirf 24 hours! {phone}",
        "New backup channel - join karo jaldi: @{backup_channel}",
    ],
    "betting": [
        "IPL MATCH PREDICTION! Today's toss winner 100% fixed! Join VIP: {phone}",
        "Satta matka open to close! Today number: {satta_num}. Payment: {upi}",
        "Cricket betting tips - guaranteed win! Deposit via: {domain}",
        "IPL ka paisa banao! Aaj ka match fixed hai! Contact: {phone}",
        "Casino online! Real money games! Minimum deposit Rs.500! {domain}",
        "Toss prediction VIP group! 95% success rate! Join: {phone}",
        "Aaj ka IPL tip 100% pakka! Session rate bhi milega! UPI: {upi}",
        "Satta king result live! Gali, Desawar, Ghaziabad! {domain}",
        "Book kar lo bhai! Match fix hai aaj! Advance payment: {upi}",
        "Online rummy, teen patti, poker! Win lakhs daily! Register: {domain}",
        "Match prediction with proof! Previous results dekho: {domain}",
        "New channel join karo - old wala band ho jayega: @{backup_channel}",
    ],
    "impersonation": [
        "SBI Customer Care: Your account will be blocked in 24 hours. Call now: {phone}",
        "Paytm Helpline: KYC update required immediately! Click: {domain}",
        "URGENT: Your Airtel SIM will be deactivated! Update KYC: {domain}",
        "Dear Customer, your bank account has been flagged. Contact support: {phone}",
        "SBI Alert: Suspicious transaction detected. Verify now or account freeze: {domain}",
        "Paytm wallet blocked due to RBI guidelines. Unblock here: {domain}",
        "Your PAN card linked to fraud account. Call helpline: {phone}",
        "Aapka SBI account suspend hone wala hai! Jaldi call karo: {phone}",
        "KYC expire ho gaya! 48 ghante me update karo: {domain}",
        "Customer care se baat karo turant! Number: {phone}. UPI refund: {upi}",
    ],
    "job": [
        "Work from Home! Earn Rs.5000-15000 daily! No experience needed! Apply: {domain}",
        "Amazon Review Task! Earn Rs.500 per review! Start now: {phone}",
        "Data entry job! Rs.30000/month! No interview! WhatsApp: {phone}",
        "Copy paste karke kamao Rs.1000/hour! Register karo: {domain}",
        "YouTube video like karo, Rs.50 per like! Payment via UPI: {upi}",
        "Telegram admin job! Rs.25000/month! Contact: {phone}",
        "Simple typing job from home! Daily payment! Apply: {domain}",
        "Ghar baithe kamao! Mobile se kaam karo! {phone}",
        "Instagram reels dekhke kamao! Rs.200 per reel! Join: {domain}",
        "Registration fee sirf Rs.299! Lifetime earning! UPI: {upi}",
    ],
    "loan": [
        "Instant Loan! No documents required! Amount: Rs.5000-500000! Apply: {domain}",
        "Personal loan 0% interest! Approved in 5 minutes! {phone}",
        "Aadhaar card pe loan! No CIBIL check! Contact: {phone}",
        "Emergency loan needed? Get cash in 10 minutes! {domain}",
        "Loan Rs.50000 bina guarantee! Aaj hi apply karo: {domain}",
        "Business loan without collateral! Low EMI! Call: {phone}",
    ],
    "sextortion": [
        "Private video leaked! Pay Rs.10000 or it goes viral! {phone}",
        "Tumhari photo mere paas hai! Delete karwana hai to pay karo: {upi}",
        "We have your browsing history! Pay immediately: {upi}",
    ],
    "digital_arrest": [
        "CBI NOTICE: You are under digital arrest! Fine: Rs.50000! Pay via: {upi}",
        "Enforcement Directorate: Your Aadhaar is linked to money laundering! Call: {phone}",
        "URGENT: Arrest warrant issued! Contact officer immediately: {phone}",
        "Aapke naam pe FIR darj hai! Video call pe pesh ho: {phone}",
        "Digital arrest order! Pay penalty or face arrest: {upi}",
        "Income Tax Department: Suspicious transactions found! Pay penalty: {domain}",
    ],
    "celebrity": [
        "Mukesh Ambani's SECRET investment plan! Guaranteed crores! Register: {domain}",
        "Ratan Tata ne bataya - invest Rs.5000, kamao Rs.5 lakh! {domain}",
        "Elon Musk's crypto scheme now in India! Limited slots! {phone}",
        "MS Dhoni endorses this trading app! Sign up: {domain}",
    ],
    "drugs": [
        "Premium quality available! Delivery pan India! Contact: {phone}",
        "All items available! Discreet packaging! WhatsApp: {phone}",
        "Cash on delivery! No traces! {phone}",
    ],
    "piracy": [
        "Latest Bollywood movies HD! Free download: {domain}",
        "New releases same day! No ads! Join channel for links!",
        "Hollywood dubbed in Hindi! 4K quality! {domain}",
        "OTT content free! Netflix, Amazon, Disney+! {domain}",
    ],
    "legitimate_govt": [
        "PM Modi addresses the nation on economic reforms. Watch live on DD National.",
        "New digital India initiative launched. 50 lakh beneficiaries in first phase.",
        "Cybercrime helpline 1930 now operational 24x7. Report fraud immediately.",
        "PIB Fact Check: This viral message about RBI is FAKE. Do not forward.",
        "Government launches new scholarship scheme for SC/ST students.",
    ],
    "legitimate_news": [
        "Breaking: Supreme Court delivers landmark judgment on privacy rights.",
        "Sensex closes at 78,500. IT stocks lead the rally.",
        "ISRO successfully launches Chandrayaan-4 mission from Sriharikota.",
        "IMD predicts heavy rainfall in Maharashtra for next 3 days.",
        "India beats Australia in T20 World Cup semi-final.",
        "Budget 2025: Finance Minister announces tax relief for middle class.",
        "Delhi Metro Yellow Line services disrupted due to technical issue.",
    ],
    "legitimate_education": [
        "NPTEL course on Machine Learning starts next week. Register at nptel.ac.in",
        "UGC NET exam dates announced for December 2025. Check ugcnet.nta.ac.in",
        "Python 3.13 released with new performance improvements.",
        "Linux kernel 6.12 brings improved hardware support.",
        "New GATE 2026 syllabus available. Download from gate.iitd.ac.in",
    ],
    "legitimate_finance": [
        "RBI keeps repo rate unchanged at 6.5%. Monetary policy committee review.",
        "SEBI introduces new framework for algorithmic trading registration.",
        "RBI circular: Banks must complete KYC re-verification by March 2026.",
        "SEBI investor awareness: Always verify registration at sebi.gov.in",
    ],
}

# ===================================================================
# LEGITIMATE CHANNEL DEFINITIONS
# ===================================================================

LEGITIMATE_CHANNELS = {
    "PIaborgin": {"style": "legitimate_govt", "lang_mix": {"english": 0.6, "hindi": 0.4}},
    "myaborgin": {"style": "legitimate_govt", "lang_mix": {"english": 0.5, "hindi": 0.5}},
    "inabordiancybercrimecc": {"style": "legitimate_govt", "lang_mix": {"english": 0.7, "hindi": 0.3}},
    "ndabortvfeed": {"style": "legitimate_news", "lang_mix": {"english": 0.8, "hindi": 0.2}},
    "timeaborsofindia": {"style": "legitimate_news", "lang_mix": {"english": 0.9, "hindi": 0.1}},
    "theaborhindu": {"style": "legitimate_news", "lang_mix": {"english": 0.95, "hindi": 0.05}},
    "bbcaborhindi": {"style": "legitimate_news", "lang_mix": {"english": 0.3, "hindi": 0.7}},
    "reuaborters": {"style": "legitimate_news", "lang_mix": {"english": 1.0}},
    "npabortel_official": {"style": "legitimate_education", "lang_mix": {"english": 0.9, "hindi": 0.1}},
    "ugaborc_net_updates": {"style": "legitimate_education", "lang_mix": {"english": 0.7, "hindi": 0.3}},
    "pythaboron": {"style": "legitimate_education", "lang_mix": {"english": 1.0}},
    "linaborux": {"style": "legitimate_education", "lang_mix": {"english": 1.0}},
    "rbi_officaborial": {"style": "legitimate_finance", "lang_mix": {"english": 0.85, "hindi": 0.15}},
    "sebi_invaborestor_education": {"style": "legitimate_finance", "lang_mix": {"english": 0.9, "hindi": 0.1}},
}


def generate_timestamp(base_date, day_offset, hour):
    """Generate an ISO timestamp."""
    dt = base_date + timedelta(days=day_offset, hours=hour, minutes=random.randint(0, 59))
    return dt.isoformat() + "Z"


def generate_posting_schedule(style):
    """Generate a 24-hour posting schedule based on operator style."""
    schedule = [0] * 24
    if style in ("investment", "celebrity"):
        # Market hours focused
        for h in [9, 10, 11, 12, 13, 14, 15]:
            schedule[h] = random.randint(5, 15)
        for h in [19, 20, 21]:
            schedule[h] = random.randint(2, 8)
    elif style == "betting":
        # Evening/night focused (match times)
        for h in [14, 15, 16, 17, 18, 19, 20, 21, 22, 23]:
            schedule[h] = random.randint(3, 12)
    elif style == "impersonation":
        # Business hours
        for h in [9, 10, 11, 12, 14, 15, 16, 17]:
            schedule[h] = random.randint(3, 10)
    elif style == "job":
        # Morning focused
        for h in [8, 9, 10, 11, 12, 13]:
            schedule[h] = random.randint(4, 12)
    elif style in ("digital_arrest", "sextortion"):
        # Late night pressure
        for h in [20, 21, 22, 23, 0, 1]:
            schedule[h] = random.randint(2, 8)
    elif "legitimate" in style:
        # Normal business hours, consistent
        for h in [9, 10, 11, 12, 13, 14, 15, 16, 17]:
            schedule[h] = random.randint(2, 5)
    else:
        for h in range(24):
            schedule[h] = random.randint(0, 5)
    return schedule


def generate_posts(style, upis, phones, domains, channel_name, n_posts=50):
    """Generate realistic posts for a channel."""
    templates = POST_TEMPLATES.get(style, POST_TEMPLATES.get("investment"))
    base_date = datetime(2025, 5, 1)
    posts = []
    msg_id = 1

    # Operator channels that share a name for backup mentions
    backup_channels = [
        f"backup_{channel_name}_2", f"{channel_name}_new",
        f"{channel_name}_vip", f"official_{channel_name}",
    ]

    for i in range(n_posts):
        template = random.choice(templates)

        # Fill placeholders
        text = template
        if "{upi}" in text:
            text = text.replace("{upi}", random.choice(upis) if upis else "pay@upi")
        if "{phone}" in text:
            text = text.replace("{phone}", random.choice(phones) if phones else "+91-XXXXXXXXXX")
        if "{domain}" in text:
            text = text.replace("{domain}", random.choice(domains) if domains else "example.com")
        if "{backup_channel}" in text:
            text = text.replace("{backup_channel}", random.choice(backup_channels))
        if "{satta_num}" in text:
            text = text.replace("{satta_num}", f"{random.randint(10, 99)}-{random.randint(100, 999)}-{random.randint(10, 99)}")

        # Simulate message ID gaps (deletion)
        if random.random() < 0.2:  # 20% deletion rate
            msg_id += random.randint(2, 5)
        else:
            msg_id += 1

        day_offset = i // (n_posts // 30 + 1)
        hour = random.choice([h for h, c in enumerate(generate_posting_schedule(style)) if c > 0] or [12])

        posts.append({
            "message_id": msg_id,
            "text": text,
            "timestamp": generate_timestamp(base_date, day_offset, hour),
            "views": random.randint(50, 5000),
            "forwards": random.randint(0, 200),
            "has_media": random.random() < 0.4,
        })

    return posts


def extract_entities_from_posts(posts, upis, phones, domains):
    """Simulate entity extraction from posts."""
    found_upis = set()
    found_phones = set()
    found_urls = set()
    found_qr = []

    for post in posts:
        text = post.get("text", "")
        for u in upis:
            if u in text:
                found_upis.add(u)
        for p in phones:
            if p in text:
                found_phones.add(p)
        for d in domains:
            if d in text:
                found_urls.add(f"http://{d}")

    # Simulate some QR code mentions
    if upis and random.random() < 0.3:
        found_qr.append(f"upi://pay?pa={random.choice(upis)}")

    return {
        "upis": list(found_upis),
        "phones": list(found_phones),
        "urls": list(found_urls),
        "qr_mentions": found_qr,
        "telegram_links": [],
    }


def build_channel(channel_name, operator, ground_truth):
    """Build a complete channel data object."""
    style = operator["style"]
    upis = operator["upis"]
    phones = operator["phones"]
    domains = operator["domains"]

    n_posts = random.randint(30, 80)
    posts = generate_posts(style, upis, phones, domains, channel_name, n_posts)
    entities = extract_entities_from_posts(posts, upis, phones, domains)
    schedule = generate_posting_schedule(style)

    return {
        "channel_metadata": {
            "username": channel_name,
            "title": channel_name.replace("_", " ").title(),
            "subscriber_count": random.randint(500, 50000),
            "creation_date": "2024-{:02d}-{:02d}T00:00:00Z".format(
                random.randint(1, 12), random.randint(1, 28)
            ),
        },
        "posts": posts,
        "entities_found": entities,
        "posting_schedule": schedule,
        "language_distribution": operator.get("lang_mix", {}),
        "media_ratio": round(random.uniform(0.2, 0.6), 2),
        "forward_ratio": round(random.uniform(0.05, 0.3), 2),
        "growth_snapshots": [
            {"date": f"2025-05-{d:02d}", "subscribers": random.randint(1000, 50000)}
            for d in range(1, 31, 5)
        ],
        "ground_truth_label": ground_truth["label"],
        "ground_truth_category": ground_truth["category"],
        "ground_truth_source": ground_truth["source"],
        "data_source": "synthetic_realistic_v2",
        "cross_reference": {
            "matched_blocked_domains": [],
            "matched_blocked_urls": [],
            "matched_blocked_channels": [],
            "blocked_entity_count": 0,
        },
    }


def build_legitimate_channel(channel_name, info, ground_truth):
    """Build a legitimate channel data object."""
    style = info["style"]
    n_posts = random.randint(30, 60)
    posts = generate_posts(style, [], [], [], channel_name, n_posts)

    # Legitimate channels have NO scam entities
    schedule = generate_posting_schedule(style)

    return {
        "channel_metadata": {
            "username": channel_name,
            "title": channel_name.replace("_", " ").title(),
            "subscriber_count": random.randint(50000, 500000),
            "creation_date": "2023-{:02d}-{:02d}T00:00:00Z".format(
                random.randint(1, 12), random.randint(1, 28)
            ),
        },
        "posts": posts,
        "entities_found": {"upis": [], "phones": [], "urls": [], "qr_mentions": [], "telegram_links": []},
        "posting_schedule": schedule,
        "language_distribution": info.get("lang_mix", {}),
        "media_ratio": round(random.uniform(0.1, 0.3), 2),
        "forward_ratio": round(random.uniform(0.01, 0.1), 2),
        "growth_snapshots": [
            {"date": f"2025-05-{d:02d}", "subscribers": random.randint(100000, 500000)}
            for d in range(1, 31, 5)
        ],
        "ground_truth_label": ground_truth["label"],
        "ground_truth_category": ground_truth["category"],
        "ground_truth_source": ground_truth["source"],
        "data_source": "synthetic_realistic_v2",
        "cross_reference": {
            "matched_blocked_domains": [],
            "matched_blocked_urls": [],
            "matched_blocked_channels": [],
            "blocked_entity_count": 0,
        },
    }


GROUND_TRUTH_MAP = {
    "stock_tips_vip_india": {"label": "CONFIRMED_SCAM", "category": "investment_scam", "source": "I4C Advisory 2024"},
    "crypto_signals_india_vip": {"label": "CONFIRMED_SCAM", "category": "investment_scam", "source": "Times of India"},
    "mutual_fund_guaranteed": {"label": "CONFIRMED_SCAM", "category": "investment_scam", "source": "SEBI advisory"},
    "forex_trading_profit_daily": {"label": "CONFIRMED_SCAM", "category": "investment_scam", "source": "RBI advisory"},
    "double_money_scheme_india": {"label": "CONFIRMED_SCAM", "category": "investment_scam", "source": "NCRP advisory"},
    "ipl_betting_tips_official": {"label": "CONFIRMED_SCAM", "category": "real_money_betting", "source": "Delhi Police"},
    "cricket_toss_prediction_vip": {"label": "CONFIRMED_SCAM", "category": "real_money_betting", "source": "I4C"},
    "satta_matka_online_24x7": {"label": "CONFIRMED_SCAM", "category": "real_money_betting", "source": "UP Police"},
    "casino_india_real_money": {"label": "CONFIRMED_SCAM", "category": "real_money_betting", "source": "MHA advisory"},
    "sbi_customer_care_official": {"label": "CONFIRMED_SCAM", "category": "fake_customer_care", "source": "SBI statement"},
    "paytm_helpline_support": {"label": "CONFIRMED_SCAM", "category": "fake_customer_care", "source": "I4C"},
    "airtel_kyc_update_urgent": {"label": "CONFIRMED_SCAM", "category": "fake_customer_care", "source": "TRAI advisory"},
    "work_from_home_india_jobs": {"label": "CONFIRMED_SCAM", "category": "job_scam", "source": "NDTV"},
    "amazon_review_job_daily": {"label": "CONFIRMED_SCAM", "category": "job_scam", "source": "Bengaluru Police"},
    "instant_loan_no_documents": {"label": "CONFIRMED_SCAM", "category": "loan_scam", "source": "RBI advisory"},
    "viral_video_expose_india": {"label": "CONFIRMED_SCAM", "category": "sextortion_threat", "source": "I4C"},
    "cbi_verification_portal": {"label": "CONFIRMED_SCAM", "category": "fake_govt_official", "source": "PMO advisory"},
    "ambani_investment_secret": {"label": "CONFIRMED_SCAM", "category": "fake_celebrity_endorsement", "source": "NDTV"},
    "india_420_delivery_service": {"label": "CONFIRMED_SCAM", "category": "drug_sale", "source": "NCB"},
    "bollywood_movies_free_hd": {"label": "CONFIRMED_SCAM", "category": "piracy_links", "source": "I4C"},
    # Legitimate
    "PIaborgin": {"label": "CONFIRMED_LEGITIMATE", "category": "government", "source": "Official PIB"},
    "myaborgin": {"label": "CONFIRMED_LEGITIMATE", "category": "government", "source": "Official MyGov"},
    "inabordiancybercrimecc": {"label": "CONFIRMED_LEGITIMATE", "category": "government", "source": "I4C official"},
    "ndabortvfeed": {"label": "CONFIRMED_LEGITIMATE", "category": "news", "source": "NDTV official"},
    "timeaborsofindia": {"label": "CONFIRMED_LEGITIMATE", "category": "news", "source": "TOI official"},
    "theaborhindu": {"label": "CONFIRMED_LEGITIMATE", "category": "news", "source": "The Hindu official"},
    "bbcaborhindi": {"label": "CONFIRMED_LEGITIMATE", "category": "news", "source": "BBC Hindi official"},
    "reuaborters": {"label": "CONFIRMED_LEGITIMATE", "category": "news", "source": "Reuters official"},
    "npabortel_official": {"label": "CONFIRMED_LEGITIMATE", "category": "education", "source": "NPTEL official"},
    "ugaborc_net_updates": {"label": "CONFIRMED_LEGITIMATE", "category": "education", "source": "UGC NET official"},
    "pythaboron": {"label": "CONFIRMED_LEGITIMATE", "category": "technology", "source": "Python community"},
    "linaborux": {"label": "CONFIRMED_LEGITIMATE", "category": "technology", "source": "Linux community"},
    "rbi_officaborial": {"label": "CONFIRMED_LEGITIMATE", "category": "finance", "source": "RBI official"},
    "sebi_invaborestor_education": {"label": "CONFIRMED_LEGITIMATE", "category": "finance", "source": "SEBI official"},
}


def generate_i4c_advisories():
    """Generate realistic I4C advisory blocklist data."""
    advisories = [
        {
            "advisory_id": "I4C-2024-INV-001",
            "date": "2024-08-15",
            "title": "Fraudulent Investment Channels on Telegram",
            "blocked_domains": ["stockprofit247.online", "investguru.site", "tradepro.xyz",
                                "forexprofitdaily.online", "doubleyourmoney.site"],
            "blocked_urls": ["http://stockprofit247.online", "http://investguru.site/register"],
            "blocked_channels": ["stock_tips_vip_india", "crypto_signals_india_vip",
                                 "forex_trading_profit_daily"],
            "blocked_upis": ["quickpay247@ybl", "investnow99@paytm", "forexking@ybl"],
            "blocked_phones": ["+91-8876543210", "+91-9988776655"],
        },
        {
            "advisory_id": "I4C-2024-BET-002",
            "date": "2024-09-20",
            "title": "Online Betting and Gambling Channels",
            "blocked_domains": ["iplbettingtips.online", "cricketprediction.site", "sattaresult.xyz"],
            "blocked_urls": ["http://iplbettingtips.online", "http://sattaresult.xyz"],
            "blocked_channels": ["ipl_betting_tips_official", "satta_matka_online_24x7"],
            "blocked_upis": ["bettips@ybl", "iplvip@paytm"],
            "blocked_phones": ["+91-9123456789", "+91-9234567890"],
        },
        {
            "advisory_id": "I4C-2024-IMP-003",
            "date": "2024-10-05",
            "title": "Fake Customer Care and Impersonation Channels",
            "blocked_domains": ["sbi-helpdesk.online", "paytm-support.site", "airtel-kyc.online"],
            "blocked_urls": ["http://sbi-helpdesk.online", "http://paytm-support.site"],
            "blocked_channels": ["sbi_customer_care_official", "paytm_helpline_support"],
            "blocked_upis": ["helpdesk@ybl", "support247@paytm"],
            "blocked_phones": ["+91-1800999888", "+91-8800112233"],
        },
        {
            "advisory_id": "I4C-2024-JOB-004",
            "date": "2024-11-10",
            "title": "Task-Based Job Fraud Channels",
            "blocked_domains": ["amazontasks.online", "homejobnow.site"],
            "blocked_urls": ["http://amazontasks.online"],
            "blocked_channels": ["work_from_home_india_jobs"],
            "blocked_upis": ["jobpay@ybl", "taskwork@paytm"],
            "blocked_phones": ["+91-7700889966"],
        },
        {
            "advisory_id": "I4C-2025-DA-005",
            "date": "2025-01-15",
            "title": "Digital Arrest Scam Channels",
            "blocked_domains": ["cbi-verification.online", "digital-arrest.site"],
            "blocked_urls": ["http://cbi-verification.online"],
            "blocked_channels": ["cbi_verification_portal"],
            "blocked_upis": ["govfine@ybl", "cbipay@paytm"],
            "blocked_phones": ["+91-1400000001", "+91-1400000002"],
        },
    ]
    return advisories


def generate_certin_alerts():
    """Generate CERT-In alert data."""
    alerts = [
        {
            "alert_id": "CIAD-2024-0234",
            "date": "2024-07-20",
            "title": "Phishing domains targeting Indian banking customers",
            "domains": ["sbi-helpdesk.online", "hdfc-update.online", "icici-security.site",
                        "paytm-support.site", "phonepe-verify.online"],
            "ips": ["185.234.218.71", "45.133.1.42", "103.224.182.250"],
        },
        {
            "alert_id": "CIAD-2024-0301",
            "date": "2024-09-15",
            "title": "Fraudulent investment platform domains",
            "domains": ["stockprofit247.online", "investguru.site", "cryptosignal-india.online",
                        "forexprofitdaily.online", "tradepro.xyz"],
            "ips": ["91.215.85.123", "185.215.113.45"],
        },
        {
            "alert_id": "CIAD-2025-0089",
            "date": "2025-02-01",
            "title": "Digital arrest scam infrastructure",
            "domains": ["cbi-verification.online", "digital-arrest.site",
                        "enforcement-directorate.online", "income-tax-notice.site"],
            "ips": ["45.95.169.88", "185.234.218.90"],
        },
    ]
    return alerts


def main():
    print("=" * 70)
    print("  CyberLens -- Realistic Data Generator")
    print("=" * 70)

    # 1. Generate I4C advisories
    advisories = generate_i4c_advisories()
    gt_dir = DATA_DIR / "ground_truth"
    gt_dir.mkdir(parents=True, exist_ok=True)

    with open(gt_dir / "i4c_advisories.json", "w", encoding="utf-8") as f:
        json.dump(advisories, f, indent=2)
    print(f"  I4C advisories: {len(advisories)} advisories written")

    # Count blocked entities
    total_domains = sum(len(a.get("blocked_domains", [])) for a in advisories)
    total_upis = sum(len(a.get("blocked_upis", [])) for a in advisories)
    total_phones = sum(len(a.get("blocked_phones", [])) for a in advisories)
    total_channels = sum(len(a.get("blocked_channels", [])) for a in advisories)
    print(f"    Blocked: {total_domains} domains, {total_upis} UPIs, "
          f"{total_phones} phones, {total_channels} channels")

    # 2. Generate CERT-In alerts
    certin = generate_certin_alerts()
    with open(gt_dir / "certin_alerts.json", "w", encoding="utf-8") as f:
        json.dump(certin, f, indent=2)
    print(f"  CERT-In alerts: {len(certin)} alerts written")

    # 3. Generate channel data
    channels = []

    # Scam channels (from operators)
    for op_name, op in OPERATORS.items():
        for ch_name in op["channels"]:
            gt = GROUND_TRUTH_MAP.get(ch_name, {
                "label": "CONFIRMED_SCAM", "category": "unknown", "source": "synthetic"
            })
            channel = build_channel(ch_name, op, gt)

            # Add blocklist cross-references
            for adv in advisories:
                for d in channel["entities_found"].get("urls", []):
                    for bd in adv.get("blocked_domains", []):
                        if bd in d:
                            channel["cross_reference"]["matched_blocked_domains"].append(bd)
                for ch in adv.get("blocked_channels", []):
                    if ch == ch_name:
                        channel["cross_reference"]["matched_blocked_channels"].append(ch)

            channel["cross_reference"]["blocked_entity_count"] = (
                len(channel["cross_reference"]["matched_blocked_domains"]) +
                len(channel["cross_reference"]["matched_blocked_channels"])
            )

            channels.append(channel)
            print(f"  Scam channel: @{ch_name} ({op_name}) -> "
                  f"{len(channel['posts'])} posts, "
                  f"{len(channel['entities_found'].get('upis', []))} UPIs, "
                  f"{len(channel['entities_found'].get('phones', []))} phones")

    # Legitimate channels
    for ch_name, info in LEGITIMATE_CHANNELS.items():
        gt = GROUND_TRUTH_MAP.get(ch_name, {
            "label": "CONFIRMED_LEGITIMATE", "category": "unknown", "source": "synthetic"
        })
        channel = build_legitimate_channel(ch_name, info, gt)
        channels.append(channel)
        print(f"  Legit channel: @{ch_name} -> {len(channel['posts'])} posts")

    # 4. Write training dataset
    dataset = {
        "metadata": {
            "version": "6.0",
            "generated_at": datetime.now().isoformat(),
            "total_channels": len(channels),
            "scam_channels": sum(1 for c in channels if c["ground_truth_label"] == "CONFIRMED_SCAM"),
            "legitimate_channels": sum(1 for c in channels if c["ground_truth_label"] == "CONFIRMED_LEGITIMATE"),
            "total_posts": sum(len(c["posts"]) for c in channels),
            "blocked_entities": {
                "domains": total_domains,
                "upis": total_upis,
                "phones": total_phones,
                "channels": total_channels,
            },
            "operator_count": len(OPERATORS),
            "note": "Synthetic data with realistic structure. Entities, posts, and operator "
                    "profiles are fabricated but structurally identical to real Telegram intelligence.",
        },
        "channels": channels,
    }

    processed_dir = DATA_DIR / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    with open(processed_dir / "training_dataset.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, default=str)

    total_posts = sum(len(c["posts"]) for c in channels)
    print(f"\n  Dataset written: {len(channels)} channels, {total_posts} total posts")
    print(f"  Output: {processed_dir / 'training_dataset.json'}")

    # 5. Summary statistics
    print("\n  Operator Attribution Test Pairs:")
    for op_name, op in OPERATORS.items():
        if len(op["channels"]) >= 2:
            shared = len(op["upis"]) + len(op["phones"]) + len(op["domains"])
            print(f"    {op_name}: {len(op['channels'])} channels, {shared} shared entities")

    print("\n" + "=" * 70)
    print("  Data generation complete!")
    print("  Next: python scripts/run_intelligence_pipeline.py --attribution")
    print("=" * 70)


if __name__ == "__main__":
    main()
