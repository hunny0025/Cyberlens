#!/usr/bin/env python3
"""
CyberLens — Synthetic Indian Scam Dataset Generator (14-Category)
==================================================================
Generates realistic synthetic scam records for training the CyberLens
scam classifier. Produces Hindi, English, and Hinglish scam messages
across all 14 categories defined in configs/scam_categories.yaml.

Usage:
    python scripts/generate_dataset.py --num-samples 1400
    python scripts/generate_dataset.py --num-samples 2800 --output-dir data/synthetic

Author: CyberLens Team — GPCSSI Internship
"""

import argparse
import json
import logging
import random
import string
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cyberlens.datagen")

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ScamRecord:
    """A single synthetic scam record."""
    id: str
    category: str          # category ID matching scam_categories.yaml
    text_content: str
    image_text: str
    phone_numbers: List[str]
    upi_ids: List[str]
    urls: List[str]
    it_act_section: str
    severity: str
    language: str


# ---------------------------------------------------------------------------
# All 14 category definitions (IDs match scam_categories.yaml exactly)
# ---------------------------------------------------------------------------

CATEGORIES = [
    "real_money_betting",
    "investment_scam",
    "loan_scam",
    "job_scam",
    "lottery_scam",
    "fake_customer_care",
    "fake_govt_official",
    "fake_celebrity_endorsement",
    "sextortion_threat",
    "child_exploitation",
    "drug_sale",
    "fake_followers_sale",
    "counterfeit_products",
    "piracy_links",
]

IT_ACT_MAP = {
    "real_money_betting": "IT Act §66D + Public Gambling Act 1867",
    "investment_scam": "IT Act §66D + IPC §420 + SEBI Act",
    "loan_scam": "IT Act §66D + RBI Guidelines",
    "job_scam": "IT Act §66D + IPC §420",
    "lottery_scam": "IT Act §66D + IPC §420",
    "fake_customer_care": "IT Act §66C + §66D + IPC §419",
    "fake_govt_official": "IPC §170 + IT Act §66D + BNS §204",
    "fake_celebrity_endorsement": "IT Act §66D + IPC §420 + Copyright Act",
    "sextortion_threat": "IT Act §66E + BNS §77 + IT Act §67",
    "child_exploitation": "POCSO Act §14/15 + IT Act §67B",
    "drug_sale": "NDPS Act 1985 + IT Act §66",
    "fake_followers_sale": "IT Act §66 + Platform ToS violation",
    "counterfeit_products": "Trademark Act 1999 + Consumer Protection Act 2019",
    "piracy_links": "IT Act §66 + Copyright Act 1957 §63",
}

SEVERITY_MAP = {
    "real_money_betting": "HIGH",
    "investment_scam": "HIGH",
    "loan_scam": "HIGH",
    "job_scam": "MEDIUM",
    "lottery_scam": "MEDIUM",
    "fake_customer_care": "HIGH",
    "fake_govt_official": "CRITICAL",
    "fake_celebrity_endorsement": "HIGH",
    "sextortion_threat": "CRITICAL",
    "child_exploitation": "CRITICAL",
    "drug_sale": "CRITICAL",
    "fake_followers_sale": "LOW",
    "counterfeit_products": "MEDIUM",
    "piracy_links": "MEDIUM",
}


# ===========================================================================
# Template pools — all 14 categories × 3 languages + image texts
# ===========================================================================

# ── 1. real_money_betting ─────────────────────────────────────────────────

TEMPLATES = {}  # category_id -> {"en": [...], "hi": [...], "hg": [...], "img": [...]}

TEMPLATES["real_money_betting"] = {
    "en": [
        "🏏 LIVE IPL BETTING! Win ₹{amount} every match! Join now on {url}. Contact {phone} for VIP tips. Pay via {upi}. 100% guaranteed profit!",
        "⚽ Cricket Betting Expert Group! Yesterday's profit: ₹{amount}. Today's match prediction ready. WhatsApp {phone}. Join {url} to start winning BIG!",
        "🎰 Play Real Money Fantasy Cricket! Better than Dream11! Deposit ₹500, get ₹5000 bonus! Download app: {url}. Support: {phone}",
        "💰 TOSS PREDICTION 100% SURE! IPL Match {match_num} — Win ₹{amount} guaranteed. WhatsApp {phone} now. Deposit via {upi}",
        "🏆 Join India's #1 Betting Group! ₹{amount} daily profit! Session & Match prediction! Contact {phone}. Register: {url}. Pay: {upi}",
        "🔥 IPL JACKPOT! Minimum bet ₹1000, Maximum return ₹{amount}! Today's sure shot: {team1} vs {team2}. Call {phone}. {url}",
        "⭐ PREMIUM BETTING TIPS — 95% accuracy! Yesterday 5/5 correct! Join Telegram: {url}. WhatsApp {phone} for free demo tip!",
        "🎯 Live Casino + Cricket Betting! Deposit ₹{deposit}, play with ₹{bonus}! Instant withdrawal via {upi}. Register: {url}",
        "💎 VIP MATCH PREDICTION GROUP — Only serious players! ROI 300% monthly. Entry fee ₹{amount}. WhatsApp {phone}. {url}",
        "🏏 Satta Matka online! Daily results & chart available. Play now at {url}. Minimum ₹500. Support: {phone}. Pay: {upi}",
    ],
    "hi": [
        "🏏 IPL BETTING शुरू हो गई! हर मैच में ₹{amount} कमाओ! अभी join करो {url}. WhatsApp करो {phone}. Payment {upi} पर भेजो!",
        "⚽ क्रिकेट सट्टा Expert Group! कल का प्रॉफिट: ₹{amount}. आज का prediction तैयार है. WhatsApp {phone}. Join करो {url}",
        "💰 100% SURE TOSS PREDICTION! IPL मैच {match_num} — ₹{amount} guaranteed जीतो. अभी WhatsApp करो {phone}. Pay करो {upi} पर",
        "🔥 भारत का सबसे बड़ा बेटिंग ग्रुप! रोज ₹{amount} कमाओ! Session और Match prediction! Contact {phone}. Register: {url}",
        "🎯 LIVE सट्टा ODDS — हर बॉल, हर ओवर! Minimum ₹1000 से शुरू करो! {url} पर register करो. Call {phone}",
        "💎 VIP बेटिंग टिप्स — 95% accuracy! कल 5 में से 5 सही! Telegram join करो: {url}. WhatsApp {phone}",
        "🏆 Dream11 से बेहतर! REAL MONEY जीतो! ₹500 deposit करो, ₹5000 bonus पाओ! Download: {url}. Support: {phone}",
        "⭐ IPL JACKPOT! ₹{amount} daily income! {team1} vs {team2} — sure shot prediction! Call {phone}. Pay: {upi}",
    ],
    "hg": [
        "🏏 Bhai IPL BETTING start ho gayi! Daily ₹{amount} kama! Join karo {url}. WhatsApp {phone}. Payment bhejo {upi} pe!",
        "⚽ Cricket ka BOSS group! Kal ka profit ₹{amount} tha! Aaj ka match ready hai. WhatsApp kar {phone}. Link: {url}",
        "💰 Abhi join karo aur paisa kamao! 100% SURE prediction! ₹{amount} guaranteed! WhatsApp {phone}. Pay via {upi}",
        "🔥 Sabse bada betting group! Roz ₹{amount} easy money! Session rate milega! Contact {phone}. Register: {url}. UPI: {upi}",
        "🎯 IPL Match {match_num} — TOSS PREDICTION 100% pakka! ₹{amount} win karo! Call {phone}. Join {url}",
        "💎 VIP Betting Tips — accuracy 95%! Kal 5 out of 5 correct the! Telegram join karo: {url}. WhatsApp {phone}",
        "🏆 Dream11 jaisa but REAL MONEY! ₹500 daalo, ₹5000 bonus lo! App download: {url}. Help: {phone}",
        "⭐ LIVE ODDS mil rahe hain! {team1} vs {team2} aaj! Minimum bet ₹1000! {url} pe register karo. {phone} pe call karo",
        "🎰 Casino + Cricket COMBO offer! Deposit ₹{deposit}, play with ₹{bonus}! Turant withdrawal {upi} pe! Register: {url}",
    ],
    "img": [
        "🏏 IPL LIVE BETTING\nWIN ₹{amount} DAILY\nJOIN NOW: {url}\n100% GUARANTEED",
        "⚽ CRICKET BETTING VIP GROUP\nCONTACT: {phone}\nMINIMUM BET: ₹1000",
        "💰 TOSS PREDICTION\n100% SURE SHOT\n{team1} vs {team2}\nWHATSAPP: {phone}",
        "🔥 REAL MONEY GAMING\nBETTER THAN DREAM11\nDOWNLOAD APP\n{url}",
        "🎰 JACKPOT OFFER\nDEPOSIT ₹500 GET ₹5000 BONUS\nREGISTER: {url}",
    ],
}

# ── 2. investment_scam ────────────────────────────────────────────────────

TEMPLATES["investment_scam"] = {
    "en": [
        "📈 GUARANTEED RETURNS! Invest ₹{amount} today, get ₹{return_amount} in 30 days! Bharat Investment Group — trusted by {num_users} investors. Register: {url}. Call {phone}",
        "💹 Stock Market VIP Tips! 100% profit guarantee! Yesterday's tip gave {percent}% return! Join premium group: {url}. WhatsApp {phone}. Pay via {upi}",
        "🏦 SBI Fixed Deposit Special Scheme — {percent}% annual return GUARANTEED! Limited time offer. Register: {url}. Call {phone}",
        "💰 Mutual Fund investment with GUARANTEED 50% return in 6 months! RBI approved scheme. Invest via {upi}. Details: {url}. Support: {phone}",
        "📊 Forex Trading Robot — Automatic profit ₹{amount}/day! No experience needed! Free trial: {url}. WhatsApp {phone}",
        "💎 Crypto Investment Plan — Double your Bitcoin in 48 hours! Verified by blockchain! {url}. Support: {phone}. UPI deposit: {upi}",
        "🏆 Gold Trading Scheme — Buy at discount, sell at profit! ₹{amount} minimum. Contact: {phone}. Portal: {url}",
        "📈 Paisa double in 30 din! Government approved investment scheme! ₹{amount} invest karo, ₹{return_amount} pao! {url}. Call {phone}",
        "💹 Zero risk trading platform! Join {num_users} happy investors! Monthly returns {percent}%! {url}. {phone}",
        "🎯 Binary Options — Win 95% trades! India's #1 trading platform! Minimum deposit ₹{deposit}. Register: {url}. {phone}",
    ],
    "hi": [
        "📈 गारंटीड रिटर्न! आज ₹{amount} invest करो, 30 दिन में ₹{return_amount} पाओ! Register: {url}. Call {phone}",
        "💹 शेयर बाजार VIP टिप्स! 100% प्रॉफिट गारंटी! कल की टिप से {percent}% return मिला! Join करो: {url}. WhatsApp {phone}",
        "🏦 SBI फिक्स्ड डिपॉजिट स्पेशल स्कीम — {percent}% सालाना रिटर्न गारंटीड! Register: {url}. Call {phone}",
        "💰 म्यूचुअल फंड में invest करो — 6 महीने में 50% GUARANTEED return! {upi} से invest करो. {url}. {phone}",
        "📊 पैसा डबल करो 30 दिन में! सरकारी मान्यता प्राप्त योजना! ₹{amount} invest करो, ₹{return_amount} पाओ! {url}",
        "💎 क्रिप्टो इन्वेस्टमेंट — 48 घंटे में Bitcoin double! {url}. Support: {phone}. UPI: {upi}",
        "🎯 Forex Trading Robot — हर दिन ₹{amount} automatic profit! कोई experience नहीं चाहिए! {url}. WhatsApp {phone}",
        "🏆 गोल्ड ट्रेडिंग स्कीम — छूट पर खरीदो, मुनाफे पर बेचो! ₹{amount} minimum. {phone}. {url}",
    ],
    "hg": [
        "📈 GUARANTEED RETURN bhai! ₹{amount} invest karo aaj, 30 din mein ₹{return_amount} milega! {url}. Call {phone}",
        "💹 Stock Market ke VIP tips! 100% profit guarantee! Kal ki tip se {percent}% return aaya! Join karo: {url}. WhatsApp {phone}",
        "💰 Paisa double karo 30 din mein! Government approved scheme hai! ₹{amount} daalo, ₹{return_amount} lo! {url}. {phone}",
        "🏦 SBI ka special FD scheme — {percent}% annual return GUARANTEED! Limited time hai. Register: {url}. Call {phone}",
        "📊 Forex Robot se daily ₹{amount} kamao! Automatic profit! Free trial: {url}. WhatsApp {phone}",
        "💎 Crypto mein invest karo — 48 hours mein Bitcoin double! {url}. Help: {phone}. UPI: {upi}",
        "🎯 Groww Premium Research — stock picks with {percent}% accuracy! Join: {url}. WhatsApp: {phone}",
        "🏆 Gold trading scheme — discount pe kharido, profit pe becho! ₹{amount} minimum. {phone}. {url}",
        "📈 Mutual Fund mein guaranteed 50% return! RBI approved! {upi} se invest karo. {url}. {phone}",
    ],
    "img": [
        "📈 GUARANTEED RETURNS\nINVEST ₹{amount}\nGET ₹{return_amount} IN 30 DAYS",
        "💹 BHARAT INVESTMENT GROUP\nTRUSTED BY {num_users} INVESTORS\nJOIN NOW: {url}",
        "🏦 SBI SPECIAL FD SCHEME\n{percent}% ANNUAL RETURN\nCALL: {phone}",
        "💰 पैसा डबल करो 30 दिन में\nGOVERNMENT APPROVED\n{url}",
        "📊 FOREX TRADING ROBOT\nDAILY PROFIT ₹{amount}\nFREE TRIAL",
    ],
}

# ── 3. loan_scam ──────────────────────────────────────────────────────────

TEMPLATES["loan_scam"] = {
    "en": [
        "🏦 INSTANT LOAN APPROVED! Get ₹{amount} in just 5 minutes! No documents needed! Download app: {url}. Call {phone}. Processing fee via {upi}",
        "💰 Personal Loan at 0% interest! ₹50,000 to ₹10,00,000 available! No CIBIL check! Apply now: {url}. WhatsApp: {phone}",
        "📱 Your loan of ₹{amount} has been pre-approved by {bank}! Pay processing fee ₹{deposit} via {upi} to receive funds. {url}. {phone}",
        "🔥 Emergency Loan in 2 minutes! Aadhaar + PAN only! ₹{amount} directly to your bank! Download: {url}. Support: {phone}",
        "⚡ FLASH LOAN OFFER! Low CIBIL score? No problem! Get ₹{amount} instantly! Small advance fee ₹{deposit} required. {url}. {phone}",
        "🏦 RBI Licensed Lender — Instant cash loan! No collateral! Apply: {url}. Pay ₹{deposit} registration. WhatsApp: {phone}",
        "💳 Credit Card against loan! ₹{amount} limit! No income proof needed! Activate: {url}. Fees: {upi}. Call: {phone}",
        "📋 Loan restructuring available! Reduce EMI by 50%! Government scheme! Apply: {url}. Helpline: {phone}. Fee via {upi}",
    ],
    "hi": [
        "🏦 तुरंत लोन अप्रूव्ड! सिर्फ 5 मिनट में ₹{amount} पाओ! कोई डॉक्यूमेंट नहीं! {url} से अप्लाई करो. Call {phone}",
        "💰 पर्सनल लोन 0% ब्याज पर! ₹50,000 से ₹10,00,000 उपलब्ध! CIBIL चेक नहीं! {url}. WhatsApp: {phone}",
        "📱 आपका ₹{amount} का लोन {bank} से प्री-अप्रूव्ड! प्रोसेसिंग फी ₹{deposit} भेजो {upi} पर. {url}. {phone}",
        "🔥 2 मिनट में इमरजेंसी लोन! सिर्फ आधार + पैन! ₹{amount} सीधे बैंक में! Download: {url}. {phone}",
        "⚡ कम CIBIL स्कोर? कोई बात नहीं! ₹{amount} तुरंत पाओ! छोटी एडवांस फी ₹{deposit}. {url}. {phone}",
        "🏦 बिना गारंटी लोन! RBI लाइसेंस्ड! ₹{amount} तक! अप्लाई करो: {url}. रजिस्ट्रेशन ₹{deposit}. {phone}",
        "💳 लोन के खिलाफ क्रेडिट कार्ड! ₹{amount} लिमिट! इनकम प्रूफ नहीं! {url}. फीस: {upi}. {phone}",
    ],
    "hg": [
        "🏦 INSTANT LOAN approved ho gaya! 5 minute mein ₹{amount} milega! No documents! {url}. Call {phone}. Fee bhejo {upi}",
        "💰 Personal Loan 0% interest pe! ₹50,000 se ₹10 lakh tak! CIBIL check nahi! Apply karo: {url}. WhatsApp: {phone}",
        "📱 Bhai tera loan ₹{amount} pre-approved hai {bank} se! Processing fee ₹{deposit} bhej {upi} pe. {url}. {phone}",
        "🔥 Emergency loan 2 minute mein! Sirf Aadhaar + PAN chahiye! ₹{amount} seedha bank mein! {url}. {phone}",
        "⚡ Low CIBIL? Tension mat le! ₹{amount} instant milega! Chhoti si advance fee ₹{deposit}. {url}. {phone}",
        "🏦 Bina guarantee loan! RBI licensed hai bhai! ₹{amount} tak available! {url}. Registration ₹{deposit}. {phone}",
        "💳 Loan ke against credit card mil raha! ₹{amount} limit! Income proof nahi chahiye! {url}. Fees: {upi}. {phone}",
        "📋 Loan restructuring scheme! EMI 50% kam hogi! Government scheme hai! {url}. Helpline: {phone}",
    ],
    "img": [
        "🏦 INSTANT LOAN\n₹{amount} IN 5 MINUTES\nNO DOCUMENTS\nDOWNLOAD: {url}",
        "💰 0% INTEREST LOAN\nNO CIBIL CHECK\nAPPLY NOW\nCALL: {phone}",
        "📱 PRE-APPROVED LOAN\n₹{amount} READY\nPAY PROCESSING FEE\nUPI: {upi}",
        "⚡ EMERGENCY LOAN\nAADHAAR + PAN ONLY\nINSTANT DISBURSEMENT\n{url}",
    ],
}

# ── 4. job_scam ───────────────────────────────────────────────────────────

TEMPLATES["job_scam"] = {
    "en": [
        "💼 WORK FROM HOME! Earn ₹{amount}/day! Simple typing job! No experience needed! Register: {url}. WhatsApp: {phone}. Pay registration fee ₹{deposit} via {upi}",
        "🏢 Amazon/Flipkart hiring work-from-home staff! Salary ₹{amount}/month! Limited vacancies! Apply: {url}. Call HR: {phone}",
        "📱 Data entry job — earn ₹{amount} daily! Just 2 hours work! Join now: {url}. Registration fee ₹{deposit}. WhatsApp: {phone}",
        "💰 Part-time job! Like YouTube videos and earn ₹500/video! Daily payment via {upi}! Start now: {url}. {phone}",
        "🔥 Google is hiring! Work from home, salary ₹{amount}/month! Apply before deadline: {url}. HR contact: {phone}",
        "⭐ Telegram task job! Complete simple tasks, earn ₹{amount}/day! No investment! Join: {url}. Support: {phone}",
        "💼 International BPO hiring! Night shift, ₹{amount}/month salary! Walk-in or online: {url}. HR: {phone}. ID fee: {upi}",
        "📋 Form filling job from home! Government data project! Earn ₹{amount}/month. Apply: {url}. Fee: ₹{deposit}. {phone}",
    ],
    "hi": [
        "💼 घर बैठे कमाओ! रोज ₹{amount} कमाओ! सिंपल टाइपिंग जॉब! कोई experience नहीं चाहिए! {url}. WhatsApp: {phone}",
        "🏢 Amazon/Flipkart में वर्क फ्रॉम होम! सैलरी ₹{amount}/महीना! सीमित vacancy! Apply करो: {url}. HR: {phone}",
        "📱 डाटा एंट्री जॉब — रोज ₹{amount} कमाओ! सिर्फ 2 घंटे काम! Join: {url}. रजिस्ट्रेशन फी ₹{deposit}. {phone}",
        "💰 पार्ट टाइम जॉब! YouTube वीडियो लाइक करो, ₹500/वीडियो कमाओ! Daily payment {upi} पर! {url}. {phone}",
        "🔥 Google में भर्ती! घर से काम, सैलरी ₹{amount}/महीना! Deadline से पहले apply करो: {url}. HR: {phone}",
        "⭐ Telegram टास्क जॉब! Simple task complete करो, रोज ₹{amount} कमाओ! {url}. Support: {phone}",
        "💼 फॉर्म भरने का काम! सरकारी डाटा प्रोजेक्ट! ₹{amount}/महीना कमाओ. {url}. फी: ₹{deposit}. {phone}",
    ],
    "hg": [
        "💼 Ghar baithe kamao bhai! Roz ₹{amount}! Simple typing job! Experience nahi chahiye! {url}. WhatsApp: {phone}",
        "🏢 Amazon/Flipkart mein WFH job! Salary ₹{amount}/month! Limited seats! Apply: {url}. HR ko call karo: {phone}",
        "📱 Data entry job — daily ₹{amount} kama! Sirf 2 ghante kaam! Join: {url}. Registration ₹{deposit}. {phone}",
        "💰 Part time job! YouTube videos like karo aur ₹500/video kamao! Daily payment {upi} pe! {url}. {phone}",
        "🔥 Google hire kar raha hai! WFH, salary ₹{amount}/month! Jaldi apply karo: {url}. HR: {phone}",
        "⭐ Telegram task job! Simple tasks karo, roz ₹{amount} kamao! No investment! {url}. {phone}",
        "💼 Form filling ka kaam! Government project hai! ₹{amount}/month! {url}. Fee: ₹{deposit}. {phone}",
        "📋 Online survey job! Har survey ke ₹{deposit} milenge! Daily ₹{amount} tak! {url}. {phone}",
    ],
    "img": [
        "💼 WORK FROM HOME\nEARN ₹{amount}/DAY\nNO EXPERIENCE NEEDED\nJOIN: {url}",
        "🏢 AMAZON HIRING\nWFH STAFF\nSALARY ₹{amount}/MONTH\nAPPLY NOW",
        "📱 DATA ENTRY JOB\n₹{amount} DAILY\n2 HOURS ONLY\nWHATSAPP: {phone}",
        "💰 PART TIME JOB\nLIKE VIDEOS EARN MONEY\nDAILY PAYMENT VIA UPI",
    ],
}

# ── 5. lottery_scam ───────────────────────────────────────────────────────

TEMPLATES["lottery_scam"] = {
    "en": [
        "🎉 CONGRATULATIONS! You've won ₹{amount} in the WhatsApp Lucky Draw 2025! Claim now: {url}. Call: {phone}. Processing fee ₹{deposit} via {upi}",
        "🏆 KBC WINNER! Dear user, your number has been selected for ₹25,00,000 prize! Call KBC office: {phone}. Verify: {url}",
        "🎊 You are the LUCKY WINNER of Jio ₹{amount} lottery! Claim before 48 hours! {url}. Tax fee ₹{deposit} via {upi}. {phone}",
        "💰 Dear customer, your {bank} account has won ₹{amount} in annual draw! Transfer fee ₹{deposit} required. Call: {phone}. {url}",
        "🎁 Amazon Gift Card worth ₹{amount} selected for you! Claim: {url}. Shipping fee ₹{deposit}. Contact: {phone}",
        "🏅 Government lottery result — Your ticket #{ref_id} won ₹{amount}! Tax payment ₹{deposit} via {upi}. Verify: {url}. {phone}",
        "🎉 Airtel/Jio SIM lucky draw! You won ₹{amount}! Call: {phone} to claim. Processing at {url}. Fee: {upi}",
        "🏆 Dear winner, your WhatsApp number selected in international lottery! Prize: ${amount}! Claim: {url}. {phone}",
    ],
    "hi": [
        "🎉 बधाई हो! आपने WhatsApp Lucky Draw 2025 में ₹{amount} जीते! अभी claim करो: {url}. Call: {phone}. फी ₹{deposit} भेजो {upi} पर",
        "🏆 KBC WINNER! आपका नंबर ₹25,00,000 के लिए select हुआ है! KBC ऑफिस: {phone}. Verify: {url}",
        "🎊 आप Jio ₹{amount} लॉटरी के LUCKY WINNER हो! 48 घंटे में claim करो! {url}. टैक्स ₹{deposit} भेजो {upi} पर. {phone}",
        "💰 आपके {bank} खाते ने सालाना ड्रॉ में ₹{amount} जीते! ट्रांसफर फी ₹{deposit} जरूरी. {phone}. {url}",
        "🎁 Amazon गिफ्ट कार्ड ₹{amount} आपके लिए select! Claim करो: {url}. शिपिंग फी ₹{deposit}. {phone}",
        "🏅 सरकारी लॉटरी — आपकी टिकट #{ref_id} में ₹{amount} जीते! टैक्स ₹{deposit} भेजो. {url}. {phone}",
        "🎉 Airtel/Jio SIM लकी ड्रॉ! आपने ₹{amount} जीते! Claim: {phone}. {url}",
    ],
    "hg": [
        "🎉 CONGRATULATIONS bhai! WhatsApp Lucky Draw mein ₹{amount} jeete! Claim karo: {url}. Call: {phone}. Fee ₹{deposit} bhejo {upi}",
        "🏆 KBC WINNER! Tera number select hua hai ₹25,00,000 ke liye! KBC office call kar: {phone}. Verify: {url}",
        "🎊 Tu Jio ₹{amount} lottery ka LUCKY WINNER hai! 48 ghante mein claim kar! {url}. Tax ₹{deposit} via {upi}. {phone}",
        "💰 Tere {bank} account ne annual draw mein ₹{amount} jeeta! Transfer fee ₹{deposit} chahiye. {phone}. {url}",
        "🎁 Amazon Gift Card ₹{amount} tere liye select hua! Claim kar: {url}. Shipping fee ₹{deposit}. {phone}",
        "🏅 Government lottery result — Teri ticket #{ref_id} mein ₹{amount} aaye! Tax ₹{deposit} bhej. {url}. {phone}",
        "🎉 Airtel/Jio SIM lucky draw! Tune ₹{amount} jeeta! Call kar claim ke liye: {phone}. {url}",
    ],
    "img": [
        "🎉 CONGRATULATIONS!\nYOU WON ₹{amount}\nWHATSAPP LUCKY DRAW\nCLAIM: {url}",
        "🏆 KBC WINNER\nPRIZE: ₹25,00,000\nCALL NOW\n{phone}",
        "🎊 JIO LOTTERY WINNER\n₹{amount} PRIZE\nCLAIM IN 48 HOURS\n{url}",
        "💰 LUCKY DRAW RESULT\nYOU WON!\nPROCESSING FEE REQUIRED\nUPI: {upi}",
    ],
}

# ── 6. fake_customer_care ─────────────────────────────────────────────────

TEMPLATES["fake_customer_care"] = {
    "en": [
        "⚠️ ALERT: Your {bank} account has been suspended! Call our helpline immediately: {phone}. Verify your identity at {url}. Do NOT share OTP with anyone except our verified agents.",
        "🔴 Your Amazon order #{order_id} has been flagged for fraud! Call Amazon Customer Care: {phone} to resolve. Refund will be processed to {upi}. Visit: {url}",
        "📱 TRAI Notice: Your mobile number will be disconnected in 24 hours due to illegal activity! Call {phone} immediately. Reference: {url}",
        "🏦 RBI ALERT: Suspicious transaction of ₹{amount} detected on your account! Call RBI fraud helpline: {phone}. Verify at {url}",
        "⚠️ Google Security Alert: Someone accessed your account from unknown device! Secure your account NOW: {url}. Call: {phone}",
        "🔴 SBI Customer Care: Your debit card has been blocked due to KYC expiry! Update KYC now: {url}. Helpline: {phone}",
        "📱 Airtel/Jio Alert: Your SIM will be blocked in 2 hours! TRAI compliance required. Call {phone}. Verify: {url}",
        "🏦 ICICI Bank Notice: ₹{amount} unauthorized transaction! Call {phone} within 1 hour. Refund via {upi}. {url}",
        "⚠️ Flipkart Refund: Your refund of ₹{amount} is pending! Process now: {url}. Customer care: {phone}. Refund to: {upi}",
        "🔴 PAN Card Alert: Your PAN has been linked to suspicious accounts! Update immediately: {url}. NSDL helpline: {phone}",
    ],
    "hi": [
        "⚠️ अलर्ट: आपका {bank} खाता सस्पेंड हो गया है! तुरंत हमारी हेल्पलाइन पर कॉल करें: {phone}. {url} पर वेरिफाई करें.",
        "🔴 आपका Amazon ऑर्डर #{order_id} fraud के लिए flag हुआ है! Amazon Customer Care कॉल करें: {phone}. Refund {upi} पर होगा.",
        "📱 TRAI नोटिस: आपका मोबाइल नंबर 24 घंटे में disconnect हो जाएगा! तुरंत कॉल करें {phone}. {url}",
        "🏦 RBI अलर्ट: ₹{amount} का संदिग्ध लेनदेन! RBI फ्रॉड हेल्पलाइन: {phone}. {url} पर verify करें",
        "⚠️ Google सुरक्षा अलर्ट: किसी ने अज्ञात डिवाइस से आपका खाता एक्सेस किया! {url}. कॉल करें: {phone}",
        "🔴 SBI Customer Care: KYC expire — डेबिट कार्ड ब्लॉक! KYC update करें: {url}. हेल्पलाइन: {phone}",
        "📱 Airtel/Jio अलर्ट: 2 घंटे में SIM ब्लॉक! TRAI compliance जरूरी. कॉल करें {phone}. {url}",
        "🏦 ICICI बैंक: ₹{amount} unauthorized transaction! 1 घंटे में {phone} पर कॉल करें. Refund {upi} पर. {url}",
    ],
    "hg": [
        "⚠️ ALERT: Aapka {bank} account suspend ho gaya hai! Abhi call karo: {phone}. Verify karo {url} pe. OTP kisi ko mat dena!",
        "🔴 Aapka Amazon order #{order_id} fraud mein flag hua! Amazon Care call karo: {phone}. Refund {upi} pe hoga. {url}",
        "📱 TRAI Notice: Aapka mobile 24 ghante mein disconnect hoga! Abhi call karo {phone}. Verify: {url}",
        "🏦 RBI ALERT: ₹{amount} ka suspicious transaction detect hua! RBI helpline: {phone}. {url} pe check karo",
        "⚠️ Google Alert: Kisi ne unknown device se account access kiya! Secure karo: {url}. Call: {phone}",
        "🔴 SBI Customer Care: KYC expire — debit card block hua! KYC update karo: {url}. Helpline: {phone}",
        "📱 Airtel/Jio Alert: 2 ghante mein SIM block! TRAI compliance zaruri. Call {phone}. {url}",
        "🏦 ICICI Bank: ₹{amount} unauthorized transaction! 1 ghante mein {phone} pe call karo. Refund {upi} pe. {url}",
        "⚠️ Flipkart Refund: ₹{amount} pending hai! Process karo: {url}. Customer care: {phone}. Refund: {upi}",
    ],
    "img": [
        "⚠️ {bank} SECURITY ALERT\nACCOUNT SUSPENDED\nCALL: {phone}",
        "🔴 AMAZON CUSTOMER CARE\nFRAUD DETECTED\nREFUND PENDING\nCALL: {phone}",
        "📱 TRAI NOTICE\nMOBILE DISCONNECTION\n24 HOURS\nVERIFY: {url}",
        "🏦 RBI FRAUD HELPLINE\n₹{amount} SUSPICIOUS\nCALL: {phone}",
        "⚠️ SBI KYC UPDATE\nDEBIT CARD BLOCKED\nUPDATE NOW\n{url}",
    ],
}

# ── 7. fake_govt_official ─────────────────────────────────────────────────

TEMPLATES["fake_govt_official"] = {
    "en": [
        "🚨 DIGITAL ARREST: This is CBI Officer {officer_name}. Your Aadhaar is linked to money laundering case #{ref_id}. You are under digital arrest. Call {phone} immediately or face imprisonment. {url}",
        "⚖️ ED NOTICE: Enforcement Directorate has frozen your {bank} accounts pending investigation. Case #{ref_id}. Contact ED helpline: {phone}. Submit documents: {url}",
        "🔴 ARREST WARRANT issued! Delhi Cyber Crime Branch — FIR #{ref_id} registered against your Aadhaar. Appear via video call: {url}. Officer: {phone}",
        "📋 Income Tax Department Notice: Tax evasion of ₹{amount} detected! Pay penalty immediately via {upi} or face prosecution. Helpline: {phone}. {url}",
        "🚨 Customs Department: Parcel #{ref_id} with illegal items seized. Your name is listed. Call customs officer: {phone}. Case details: {url}",
        "⚖️ Supreme Court order — Your bank accounts will be frozen in 2 hours. Contact legal department: {phone}. Upload KYC: {url}. Fine via {upi}",
        "🔴 Mumbai Police Cyber Cell: Your number linked to terror financing! Report to {url} immediately. Officer contact: {phone}. Case #{ref_id}",
        "📋 NARCOTICS CONTROL BUREAU: Your Aadhaar #{ref_id} flagged in drug case. Digital arrest initiated. Video call mandatory: {url}. {phone}",
    ],
    "hi": [
        "🚨 डिजिटल अरेस्ट: मैं CBI अधिकारी {officer_name} हूं. आपका आधार मनी लॉन्ड्रिंग केस #{ref_id} से जुड़ा है. तुरंत कॉल करें {phone}. {url}",
        "⚖️ ED नोटिस: प्रवर्तन निदेशालय ने आपके {bank} खाते फ्रीज कर दिए हैं. केस #{ref_id}. ED हेल्पलाइन: {phone}. दस्तावेज़ भेजें: {url}",
        "🔴 गिरफ्तारी वारंट जारी! दिल्ली साइबर क्राइम ब्रांच — FIR #{ref_id}. वीडियो कॉल से पेश हों: {url}. अधिकारी: {phone}",
        "📋 आयकर विभाग नोटिस: ₹{amount} कर चोरी पकड़ी गई! तुरंत जुर्माना भरें {upi} से. हेल्पलाइन: {phone}. {url}",
        "🚨 कस्टम विभाग: पार्सल #{ref_id} में अवैध सामान पकड़ा गया. आपका नाम है. कस्टम अधिकारी: {phone}. {url}",
        "⚖️ सुप्रीम कोर्ट आदेश — 2 घंटे में आपके खाते फ्रीज हो जाएंगे. कानूनी विभाग: {phone}. KYC अपलोड: {url}",
        "🔴 मुंबई पुलिस साइबर सेल: आपका नंबर आतंकवाद फंडिंग से जुड़ा! तुरंत रिपोर्ट करें: {url}. {phone}",
    ],
    "hg": [
        "🚨 DIGITAL ARREST: Main CBI Officer {officer_name} bol raha hoon. Tera Aadhaar money laundering case #{ref_id} se linked hai. Abhi call kar {phone}. {url}",
        "⚖️ ED NOTICE: Enforcement Directorate ne tere {bank} accounts freeze kar diye! Case #{ref_id}. ED helpline: {phone}. Documents bhej: {url}",
        "🔴 ARREST WARRANT issued! Delhi Cyber Crime — FIR #{ref_id} tera Aadhaar pe registered hai. Video call se aa: {url}. Officer: {phone}",
        "📋 Income Tax Notice: ₹{amount} tax evasion pakdi gayi! Penalty turant bhar {upi} se. Helpline: {phone}. {url}",
        "🚨 Customs Department: Parcel #{ref_id} mein illegal items pakde gaye. Tera naam hai. Call kar: {phone}. Details: {url}",
        "⚖️ Supreme Court order — 2 ghante mein tere accounts freeze honge. Legal dept: {phone}. KYC upload: {url}. Fine via {upi}",
        "🔴 Mumbai Police Cyber Cell: Tera number terror financing se linked! Turant report kar: {url}. Officer: {phone}",
        "📋 NCB: Tera Aadhaar #{ref_id} drug case mein flagged hai. Digital arrest. Video call mandatory: {url}. {phone}",
    ],
    "img": [
        "🚨 DIGITAL ARREST\nCBI OFFICER\nCASE #{ref_id}\nCALL: {phone}",
        "⚖️ ED NOTICE\nACCOUNTS FROZEN\nCONTACT IMMEDIATELY\n{phone}",
        "🔴 ARREST WARRANT\nDELHI CYBER CRIME\nFIR REGISTERED\n{url}",
        "📋 INCOME TAX NOTICE\nTAX EVASION ₹{amount}\nPAY PENALTY NOW\nUPI: {upi}",
    ],
}

# ── 8. fake_celebrity_endorsement ─────────────────────────────────────────

TEMPLATES["fake_celebrity_endorsement"] = {
    "en": [
        "📈 Mukesh Ambani's SECRET investment plan! ₹{amount} becomes ₹{return_amount} in 30 days! Endorsed by Reliance Industries! Join: {url}. WhatsApp: {phone}",
        "💰 Ratan Tata personally recommends this trading app! Invest ₹{deposit} and earn ₹{amount}/day! Download: {url}. Support: {phone}. Pay: {upi}",
        "🏆 PM Modi's Digital India Scheme — ₹{amount} direct benefit transfer! Register with Aadhaar: {url}. Helpline: {phone}",
        "⭐ Shah Rukh Khan investing in THIS app! Already earned ₹{amount}! Join now: {url}. Celebrity-backed, RBI approved! {phone}",
        "📊 Virat Kohli endorses India's #1 trading platform! {percent}% monthly returns! Register: {url}. Deposit via {upi}. Help: {phone}",
        "💎 Elon Musk's India crypto project! Double your money guaranteed! ₹{deposit} minimum! {url}. WhatsApp: {phone}",
        "🔥 MS Dhoni's secret batting tips + investment club! Join and earn ₹{amount}/month! {url}. Contact: {phone}. UPI: {upi}",
        "📈 Amitabh Bachchan reveals retirement investment secret! ₹{amount} grows to ₹{return_amount}! Exclusive: {url}. {phone}",
    ],
    "hi": [
        "📈 मुकेश अंबानी की SECRET इन्वेस्टमेंट प्लान! ₹{amount} से ₹{return_amount} 30 दिन में! Reliance Industries endorsed! {url}. {phone}",
        "💰 रतन टाटा ने personally recommend किया! ₹{deposit} invest करो, रोज ₹{amount} कमाओ! {url}. {phone}. {upi}",
        "🏆 PM मोदी डिजिटल इंडिया स्कीम — ₹{amount} डायरेक्ट बेनिफिट! आधार से register करो: {url}. {phone}",
        "⭐ शाहरुख खान इस app में invest कर रहे हैं! ₹{amount} कमा चुके! Join करो: {url}. RBI approved! {phone}",
        "📊 विराट कोहली ने India की #1 trading platform endorse की! {percent}% monthly returns! {url}. UPI: {upi}. {phone}",
        "💎 एलन मस्क का India crypto project! पैसा double guaranteed! ₹{deposit} minimum! {url}. {phone}",
        "🔥 MS धोनी का secret इन्वेस्टमेंट क्लब! ₹{amount}/महीना कमाओ! {url}. {phone}. UPI: {upi}",
    ],
    "hg": [
        "📈 Mukesh Ambani ki SECRET plan! ₹{amount} se ₹{return_amount} ban jayega 30 din mein! Reliance backed! {url}. {phone}",
        "💰 Ratan Tata ne personally recommend kiya hai ye app! ₹{deposit} daalo, daily ₹{amount} kamao! {url}. {phone}. {upi}",
        "🏆 PM Modi ka Digital India Scheme — ₹{amount} direct bank mein! Aadhaar se register: {url}. {phone}",
        "⭐ SRK is investing in THIS app bhai! ₹{amount} already kama chuke! Join: {url}. RBI approved! {phone}",
        "📊 Virat Kohli ne endorse kiya — India's #1 trading platform! {percent}% monthly returns! {url}. UPI: {upi}. {phone}",
        "💎 Elon Musk ka India crypto project! Paisa double guaranteed! ₹{deposit} minimum! {url}. WhatsApp: {phone}",
        "🔥 Dhoni ka secret investment club! Monthly ₹{amount} kama! {url}. Contact: {phone}. UPI: {upi}",
        "📈 Amitabh Bachchan ne bataya retirement ka secret! ₹{amount} se ₹{return_amount} ban jayega! {url}. {phone}",
    ],
    "img": [
        "📈 MUKESH AMBANI\nSECRET INVESTMENT\n₹{amount} → ₹{return_amount}\nJOIN: {url}",
        "💰 RATAN TATA RECOMMENDS\nTRADING APP\nEARN ₹{amount}/DAY\nDOWNLOAD NOW",
        "🏆 PM MODI SCHEME\nDIGITAL INDIA\n₹{amount} BENEFIT\nREGISTER: {url}",
        "⭐ CELEBRITY BACKED\nRBI APPROVED\n{percent}% RETURNS\n{url}",
    ],
}

# ── 9. sextortion_threat ─────────────────────────────────────────────────

TEMPLATES["sextortion_threat"] = {
    "en": [
        "🔴 I have your PRIVATE VIDEO recorded from video call! Pay ₹{amount} to {upi} in 24 hours or I will send it to all your contacts. Don't try to ignore. {phone}",
        "⚠️ Your intimate photos have been saved. If you don't send ₹{amount} via {upi}, they will be uploaded on social media. Contact: {phone}. Proof: {url}",
        "🔴 MORPHED IMAGES of you are ready to be shared with your family and colleagues. Transfer ₹{amount} now via {upi}. You have 12 hours. {phone}",
        "⚠️ I recorded our video call. Screenshots sent to you as proof. Pay ₹{amount} to {upi} or your video goes VIRAL. WhatsApp: {phone}",
        "🔴 Your browsing history and private data exposed! Pay ₹{amount} via {upi} to delete everything. Timer: 48 hours. Proof: {url}. {phone}",
        "⚠️ WARNING: Your compromising video is queued for upload to YouTube. Only ₹{amount} can stop it. UPI: {upi}. Negotiate: {phone}",
        "🔴 I have screenshots of your chats + photos. Your wife/family will receive them unless ₹{amount} via {upi}. No police — I have your data. {phone}",
        "⚠️ Adult website breach — your profile with real name exposed! Pay ₹{amount} for removal: {upi}. Deadline: 24h. Contact: {phone}",
    ],
    "hi": [
        "🔴 तुम्हारा PRIVATE VIDEO मेरे पास है! 24 घंटे में ₹{amount} भेजो {upi} पर नहीं तो सबको भेज दूंगा. {phone}",
        "⚠️ तुम्हारी intimate photos save हैं. ₹{amount} नहीं भेजोगे {upi} पर तो social media पर डाल दूंगा. {phone}",
        "🔴 तुम्हारी MORPHED IMAGES तैयार हैं. ₹{amount} अभी भेजो {upi} पर. 12 घंटे हैं. {phone}",
        "⚠️ वीडियो कॉल रिकॉर्ड कर ली. Proof भेज दिया है. ₹{amount} भेजो {upi} पर नहीं तो VIRAL हो जाएगा. {phone}",
        "🔴 तुम्हारा browsing history और private data exposed! ₹{amount} भेजो {upi} पर delete करने के लिए. 48 घंटे. {phone}",
        "⚠️ तुम्हारा video YouTube पर upload होने वाला है. ₹{amount} भेजो रुकवाने के लिए. UPI: {upi}. {phone}",
        "🔴 तुम्हारी chats और photos मेरे पास हैं. पत्नी/परिवार को भेज दूंगा अगर ₹{amount} नहीं भेजा. {upi}. {phone}",
    ],
    "hg": [
        "🔴 Tera PRIVATE VIDEO mere paas hai! 24 ghante mein ₹{amount} bhej {upi} pe nahi toh sabko bhej dunga. {phone}",
        "⚠️ Teri intimate photos saved hain. ₹{amount} nahi bhejega {upi} pe toh social media pe daal dunga. {phone}",
        "🔴 Teri MORPHED IMAGES ready hain family aur colleagues ke liye. ₹{amount} abhi transfer kar {upi} pe. 12 hours. {phone}",
        "⚠️ Video call record kar li bhai. Proof bhej diya. ₹{amount} bhej {upi} pe nahi toh VIRAL. WhatsApp: {phone}",
        "🔴 Tera browsing history aur private data exposed! ₹{amount} bhej {upi} pe delete ke liye. 48 hours. {phone}",
        "⚠️ WARNING: Tera compromising video YouTube pe upload hone wala hai. ₹{amount} se ruk jayega. UPI: {upi}. {phone}",
        "🔴 Screenshots hain tere chats + photos ke. Wife/family ko bhej dunga. ₹{amount} via {upi}. No police. {phone}",
    ],
    "img": [
        "🔴 PRIVATE VIDEO RECORDED\nPAY ₹{amount} IN 24 HOURS\nOR VIDEO GOES VIRAL\nUPI: {upi}",
        "⚠️ YOUR PHOTOS SAVED\nWILL BE SHARED\nPAY TO DELETE\n{phone}",
        "🔴 MORPHED IMAGES READY\n₹{amount} TO STOP\nDEADLINE: 12 HOURS\nUPI: {upi}",
    ],
}

# ── 10. child_exploitation ────────────────────────────────────────────────

TEMPLATES["child_exploitation"] = {
    "en": [
        "⚠️ Telegram group with underage content available. Join link: {url}. Contact admin: {phone}. New videos uploaded daily.",
        "🔴 School girl videos — private collection. Access fee ₹{deposit}. Pay via {upi}. Link: {url}. WhatsApp: {phone}",
        "⚠️ Minor content available on private channel. Membership ₹{deposit}/month via {upi}. DM admin: {phone}. Join: {url}",
        "🔴 Child videos leaked — exclusive access. Entry: ₹{deposit} via {upi}. Telegram group: {url}. Admin: {phone}",
        "⚠️ Private group — underage material. Subscription ₹{deposit}. Payment via {upi}. Access link: {url}. Contact: {phone}",
        "🔴 Hidden content — school students. Premium access ₹{deposit}. UPI: {upi}. Link sent after payment. {phone}",
    ],
    "hi": [
        "⚠️ Telegram ग्रुप — नाबालिग content. Join करो: {url}. Admin: {phone}. रोज नए videos.",
        "🔴 स्कूल लड़कियों के videos — private collection. फी ₹{deposit} भेजो {upi} पर. {url}. {phone}",
        "⚠️ नाबालिग content — private channel. ₹{deposit}/महीना {upi} पर. Admin: {phone}. Join: {url}",
        "🔴 बच्चों के videos leaked — exclusive access. ₹{deposit} भेजो {upi} पर. {url}. {phone}",
        "⚠️ Hidden content — स्कूल students. Premium ₹{deposit} भेजो. UPI: {upi}. Link मिलेगा payment के बाद. {phone}",
    ],
    "hg": [
        "⚠️ Telegram group — underage content available. Join: {url}. Admin ko contact kar: {phone}. Daily new videos.",
        "🔴 School girl videos — private collection hai. Fee ₹{deposit} bhej {upi} pe. Link: {url}. WhatsApp: {phone}",
        "⚠️ Minor content private channel pe hai. Membership ₹{deposit}/month {upi} pe. DM admin: {phone}. Join: {url}",
        "🔴 Child videos leaked — exclusive access chahiye toh ₹{deposit} bhej {upi} pe. Group: {url}. Admin: {phone}",
        "⚠️ Hidden content — school students ka. Premium ₹{deposit}. UPI: {upi}. Payment ke baad link milega. {phone}",
    ],
    "img": [
        "⚠️ PRIVATE GROUP\nUNDERAGE CONTENT\nJOIN: {url}\nADMIN: {phone}",
        "🔴 EXCLUSIVE ACCESS\nMINOR CONTENT\nFEE: ₹{deposit}\nUPI: {upi}",
        "⚠️ HIDDEN CHANNEL\nSCHOOL STUDENTS\nPREMIUM ACCESS\n{phone}",
    ],
}

# ── 11. drug_sale ─────────────────────────────────────────────────────────

TEMPLATES["drug_sale"] = {
    "en": [
        "🌿 Premium quality weed available! Home delivery across India. Order now: {url}. WhatsApp: {phone}. Payment via {upi}. Discreet packaging guaranteed.",
        "💊 Buy medications without prescription! Xanax, Tramadol, Codeine available. Order: {url}. Delivery in 24h. Contact: {phone}. Pay: {upi}",
        "🍄 Magic mushrooms, LSD tabs, MDMA crystals — top quality! Darknet trusted vendor. Order: {url}. Wickr/Telegram: {phone}",
        "🌿 Ganja delivery service — Manali strain, Kerala Gold, Idukki Gold! ₹{deposit}/10g. WhatsApp: {phone}. Order: {url}. UPI: {upi}",
        "💊 Charas, hash available. Best quality from Himachal. Nationwide delivery. Price ₹{deposit}/tola. Contact: {phone}. {url}",
        "🍄 Cocaine premium quality. Direct import. ₹{amount}/gram. Trusted since 2019. Telegram: {url}. Signal: {phone}. Crypto/UPI: {upi}",
        "🌿 Prescription drugs without doctor — Alprazolam, Diazepam, Codeine syrup. Fast delivery: {url}. WhatsApp only: {phone}",
        "💊 Party drugs available — MDMA, ecstasy, LSD. Campus delivery available. DM on Telegram: {url}. {phone}. Payment: {upi}",
    ],
    "hi": [
        "🌿 प्रीमियम गांजा उपलब्ध! पूरे भारत में होम डिलीवरी. ऑर्डर: {url}. WhatsApp: {phone}. Payment {upi} से. Discreet पैकेजिंग.",
        "💊 बिना prescription दवाइयां! Xanax, Tramadol उपलब्ध. ऑर्डर: {url}. 24 घंटे में डिलीवरी. {phone}. {upi}",
        "🌿 गांजा डिलीवरी — मनाली strain, केरला Gold! ₹{deposit}/10g. WhatsApp: {phone}. {url}. UPI: {upi}",
        "💊 चरस, हश उपलब्ध. हिमाचल से best quality. पूरे देश में डिलीवरी. ₹{deposit}/तोला. {phone}. {url}",
        "🍄 MDMA, ecstasy, LSD उपलब्ध. Campus डिलीवरी. Telegram: {url}. {phone}. Payment: {upi}",
        "🌿 कोकीन premium quality. Direct import. ₹{amount}/ग्राम. Telegram: {url}. {phone}",
    ],
    "hg": [
        "🌿 Premium maal available bhai! Home delivery all India. Order: {url}. WhatsApp: {phone}. Payment {upi} se. Discreet packaging.",
        "💊 Bina prescription dawai chahiye? Xanax, Tramadol sab available. Order: {url}. 24h delivery. {phone}. {upi}",
        "🌿 Ganja delivery — Manali strain, Kerala Gold! ₹{deposit}/10g. WhatsApp: {phone}. Order: {url}. UPI: {upi}",
        "💊 Charas, hash mil jayega. Himachal se best quality. All India delivery. ₹{deposit}/tola. {phone}. {url}",
        "🍄 Party drugs available — MDMA, ecstasy, LSD. Campus delivery bhi hai. Telegram: {url}. {phone}. Pay: {upi}",
        "🌿 Cocaine premium quality hai. Direct import. ₹{amount}/gram. Trusted vendor. {url}. {phone}. Crypto/UPI: {upi}",
        "💊 Prescription drugs bina doctor ke — Alprazolam, Codeine syrup. Fast delivery: {url}. WhatsApp: {phone}",
    ],
    "img": [
        "🌿 PREMIUM WEED\nHOME DELIVERY\nDISCREET PACKAGING\nORDER: {url}",
        "💊 MEDICATIONS\nNO PRESCRIPTION\n24H DELIVERY\nWHATSAPP: {phone}",
        "🍄 PARTY DRUGS\nMDMA LSD ECSTASY\nTELEGRAM ORDER\n{url}",
        "🌿 GANJA DELIVERY\nMANALI STRAIN\n₹{deposit}/10G\nUPI: {upi}",
    ],
}

# ── 12. fake_followers_sale ───────────────────────────────────────────────

TEMPLATES["fake_followers_sale"] = {
    "en": [
        "📈 Buy Instagram followers! 10K followers for ₹{deposit}! 100% real-looking accounts! Instant delivery! Order: {url}. WhatsApp: {phone}. Pay: {upi}",
        "🔥 YouTube subscribers cheap! 1000 subs = ₹{deposit}! Monetization guaranteed! Order: {url}. Support: {phone}",
        "⭐ Buy likes, comments, views for any platform! Instagram, YouTube, TikTok! Bulk discounts! {url}. WhatsApp: {phone}. UPI: {upi}",
        "💎 Become FAMOUS overnight! 50K followers + 10K likes package = ₹{amount}! Real engagement! {url}. {phone}",
        "📊 Social media growth service! Organic-looking followers! Instagram, Twitter, LinkedIn! Plans from ₹{deposit}/month! {url}. {phone}",
        "🔥 Telegram group members for sale! 5K members = ₹{deposit}! Active accounts! Delivery in 6 hours! {url}. {phone}. {upi}",
        "⭐ Facebook page likes boost! 10K likes = ₹{deposit}! Brand credibility instant! Order: {url}. Help: {phone}",
        "💎 Verified blue tick service! Instagram/Twitter verification for ₹{amount}! Guaranteed: {url}. DM: {phone}",
    ],
    "hi": [
        "📈 Instagram followers खरीदो! 10K followers सिर्फ ₹{deposit} में! 100% real! तुरंत delivery! {url}. WhatsApp: {phone}. Pay: {upi}",
        "🔥 YouTube subscribers सस्ते में! 1000 subs = ₹{deposit}! Monetization guaranteed! {url}. {phone}",
        "⭐ लाइक्स, कमेंट्स, views खरीदो! Instagram, YouTube, TikTok! बल्क डिस्काउंट! {url}. {phone}. {upi}",
        "💎 रातों-रात FAMOUS बनो! 50K followers + 10K likes = ₹{amount}! Real engagement! {url}. {phone}",
        "📊 Social media growth सर्विस! Organic दिखने वाले followers! ₹{deposit}/महीना! {url}. {phone}",
        "🔥 Telegram ग्रुप members बिकते हैं! 5K members = ₹{deposit}! 6 घंटे में delivery! {url}. {phone}",
    ],
    "hg": [
        "📈 Instagram followers kharido! 10K followers sirf ₹{deposit} mein! Real looking! Instant delivery! {url}. WhatsApp: {phone}. {upi}",
        "🔥 YouTube subscribers cheap mein! 1000 subs = ₹{deposit}! Monetization pakka! {url}. {phone}",
        "⭐ Likes, comments, views sab milega! Instagram, YouTube, TikTok! Bulk discount! {url}. {phone}. {upi}",
        "💎 Raat bhar mein FAMOUS ban ja! 50K followers + 10K likes = ₹{amount}! Real engagement! {url}. {phone}",
        "📊 Social media growth service! Organic looking followers! ₹{deposit}/month se start! {url}. {phone}",
        "🔥 Telegram group ke members bhi milte hain! 5K = ₹{deposit}! Active accounts! 6 ghante delivery! {url}. {phone}. {upi}",
        "⭐ Facebook page likes boost karo! 10K likes = ₹{deposit}! Brand credibility instant! {url}. {phone}",
        "💎 Verified blue tick service! Instagram/Twitter verification ₹{amount} mein! {url}. DM: {phone}",
    ],
    "img": [
        "📈 BUY FOLLOWERS\n10K = ₹{deposit}\nINSTANT DELIVERY\nORDER: {url}",
        "🔥 YOUTUBE SUBSCRIBERS\n1000 SUBS CHEAP\nMONETIZATION GUARANTEED\n{phone}",
        "⭐ LIKES COMMENTS VIEWS\nALL PLATFORMS\nBULK DISCOUNT\n{url}",
        "💎 BECOME FAMOUS\n50K FOLLOWERS\nOVERNIGHT GROWTH\n{url}",
    ],
}

# ── 13. counterfeit_products ──────────────────────────────────────────────

TEMPLATES["counterfeit_products"] = {
    "en": [
        "👜 FIRST COPY Louis Vuitton, Gucci, Prada bags! Original look, ₹{deposit} only! Same quality as ₹{amount} original! Order: {url}. WhatsApp: {phone}",
        "⌚ REPLICA Rolex, Omega watches! AAA+ quality! Swiss movement! Starting ₹{deposit}! Catalog: {url}. Order: {phone}. COD/UPI: {upi}",
        "👟 Nike, Adidas, Jordan shoes — FIRST COPY! 7A quality! ₹{deposit} only! Original price ₹{amount}! {url}. WhatsApp: {phone}",
        "📱 iPhone 16 Pro — Master Copy! Same features at ₹{deposit}! 1 year warranty! Order: {url}. Support: {phone}. Pay: {upi}",
        "👔 Branded clothes — Allen Solly, Zara, H&M at 90% off! First copy premium! ₹{deposit} onwards! {url}. {phone}",
        "💄 Branded cosmetics — MAC, Lakme, Maybelline at ₹{deposit}! Original packaging! Buy: {url}. WhatsApp: {phone}",
        "🕶️ Ray-Ban, Oakley sunglasses — FIRST COPY! UV protected! ₹{deposit}! Order: {url}. {phone}. COD available",
        "👜 Sarojini Nagar quality at wholesale price! Branded first copies! Minimum order 10 pieces! {url}. {phone}. UPI: {upi}",
    ],
    "hi": [
        "👜 FIRST COPY Louis Vuitton, Gucci बैग! Original जैसा, सिर्फ ₹{deposit}! ₹{amount} original जैसी quality! {url}. WhatsApp: {phone}",
        "⌚ REPLICA Rolex, Omega घड़ियां! AAA+ quality! Swiss movement! ₹{deposit} से! {url}. ऑर्डर: {phone}. UPI: {upi}",
        "👟 Nike, Adidas, Jordan जूते — FIRST COPY! 7A quality! ₹{deposit}! Original कीमत ₹{amount}! {url}. {phone}",
        "📱 iPhone 16 Pro — Master Copy! Same features ₹{deposit} में! 1 साल warranty! {url}. {phone}. {upi}",
        "👔 ब्रांडेड कपड़े — 90% छूट पर! First copy premium! ₹{deposit} से शुरू! {url}. {phone}",
        "💄 ब्रांडेड cosmetics — MAC, Lakme ₹{deposit} में! Original packaging! {url}. {phone}",
        "🕶️ Ray-Ban sunglasses FIRST COPY! UV protected! ₹{deposit}! {url}. {phone}. COD available",
    ],
    "hg": [
        "👜 FIRST COPY LV, Gucci bags! Original jaisa, sirf ₹{deposit}! Same quality bhai! {url}. WhatsApp: {phone}",
        "⌚ REPLICA Rolex, Omega watches! AAA+ quality! Swiss movement! ₹{deposit} se start! {url}. Order: {phone}. UPI: {upi}",
        "👟 Nike, Adidas, Jordan shoes — FIRST COPY! 7A quality! ₹{deposit} bus! Original ₹{amount} ka hai! {url}. {phone}",
        "📱 iPhone 16 Pro Master Copy! Same features sirf ₹{deposit} mein! 1 year warranty! {url}. {phone}. {upi}",
        "👔 Branded kapde — Allen Solly, Zara 90% off! First copy premium! ₹{deposit} se! {url}. {phone}",
        "💄 Branded cosmetics — MAC, Lakme ₹{deposit} mein! Original packaging! {url}. {phone}",
        "🕶️ Ray-Ban, Oakley sunglasses FIRST COPY! UV protected! ₹{deposit}! {url}. {phone}. COD hai",
        "👜 Wholesale price pe branded first copies! Sarojini quality! Min 10 pieces! {url}. {phone}. UPI: {upi}",
    ],
    "img": [
        "👜 FIRST COPY BAGS\nLV GUCCI PRADA\n₹{deposit} ONLY\nORDER: {url}",
        "⌚ REPLICA WATCHES\nROLEX OMEGA\nAAA+ QUALITY\n{phone}",
        "👟 BRANDED SHOES\nFIRST COPY 7A\n₹{deposit} ONLY\n{url}",
        "📱 IPHONE MASTER COPY\nSAME FEATURES\n₹{deposit}\n{url}",
    ],
}

# ── 14. piracy_links ─────────────────────────────────────────────────────

TEMPLATES["piracy_links"] = {
    "en": [
        "🎬 Download latest Bollywood/Hollywood movies FREE! HD quality! No registration! {url}. New releases daily! Support: {phone}",
        "📺 FREE Netflix, Hotstar, Prime accounts! Lifetime access ₹{deposit}! 100% working! Buy: {url}. WhatsApp: {phone}. Pay: {upi}",
        "🎮 Crack software — Adobe, MS Office, Windows! Free download: {url}. All versions available. Telegram: {phone}",
        "🎬 Torrent links for latest movies — {team1} new release available! HD print! Download: {url}. Join group: {phone}",
        "📺 IPTV service — 500+ live channels! Sports, movies, shows! ₹{deposit}/year! Install guide: {url}. Support: {phone}",
        "🎮 PS5/Xbox games cracked! All latest titles! Free download: {url}. Request games: {phone}. Premium fast links: {upi}",
        "🎬 OTT content FREE — all platforms! Daily updates! Telegram channel: {url}. Admin: {phone}. VIP access ₹{deposit}: {upi}",
        "📺 Spotify/YouTube Premium FREE forever! Modified APK download: {url}. Tutorial: {phone}. No root needed!",
    ],
    "hi": [
        "🎬 Latest Bollywood/Hollywood movies FREE download! HD quality! {url}. रोज नई releases! {phone}",
        "📺 FREE Netflix, Hotstar, Prime accounts! Lifetime ₹{deposit}! 100% working! {url}. WhatsApp: {phone}. {upi}",
        "🎮 Crack software — Adobe, MS Office, Windows! Free download: {url}. सब versions available. {phone}",
        "🎬 Torrent links — latest movies HD print! Download: {url}. Group join करो: {phone}",
        "📺 IPTV सर्विस — 500+ live channels! ₹{deposit}/साल! {url}. Support: {phone}",
        "🎮 PS5/Xbox games cracked! सब latest titles! Free download: {url}. Request करो: {phone}",
        "🎬 OTT content FREE — सब platforms! रोज अपडेट! Telegram: {url}. Admin: {phone}. VIP ₹{deposit}: {upi}",
    ],
    "hg": [
        "🎬 Latest movies FREE download bhai! HD quality! {url}. Daily new releases! {phone}",
        "📺 FREE Netflix, Hotstar, Prime accounts! Lifetime sirf ₹{deposit}! 100% working! {url}. WhatsApp: {phone}. {upi}",
        "🎮 Crack software — Adobe, Office, Windows! Free download: {url}. Sab versions mil jayenge. {phone}",
        "🎬 Torrent links — latest movies HD print available! Download: {url}. Group join kar: {phone}",
        "📺 IPTV service — 500+ live channels! Sports, movies sab! ₹{deposit}/year! {url}. {phone}",
        "🎮 PS5/Xbox games cracked! Latest titles sab free! {url}. Request kar: {phone}. Premium links: {upi}",
        "🎬 OTT content FREE — sab platforms ka! Daily updates! Telegram: {url}. Admin: {phone}. VIP ₹{deposit}: {upi}",
        "📺 Spotify/YouTube Premium FREE forever! Modified APK download: {url}. No root chahiye! {phone}",
    ],
    "img": [
        "🎬 FREE MOVIES\nHD DOWNLOAD\nDAILY RELEASES\n{url}",
        "📺 FREE OTT ACCOUNTS\nNETFLIX HOTSTAR PRIME\nLIFETIME ₹{deposit}\n{url}",
        "🎮 CRACK SOFTWARE\nADOBE OFFICE WINDOWS\nFREE DOWNLOAD\n{url}",
        "📺 IPTV 500+ CHANNELS\n₹{deposit}/YEAR\nSPORTS MOVIES SHOWS\n{url}",
    ],
}


# ===========================================================================
# Shared data pools
# ===========================================================================

BANKS = ["SBI", "HDFC", "ICICI", "Axis", "PNB", "Kotak", "BOB", "Canara", "Union", "IDBI"]
IPL_TEAMS = [
    "Mumbai Indians", "Chennai Super Kings", "Royal Challengers",
    "Kolkata Knight Riders", "Delhi Capitals", "Rajasthan Royals",
    "Punjab Kings", "Sunrisers Hyderabad", "Gujarat Titans", "Lucknow Super Giants",
]
OFFICER_NAMES = [
    "R.K. Sharma", "A.K. Singh", "V.P. Mishra", "S.K. Verma",
    "D.P. Gupta", "K.N. Reddy", "M.S. Rao", "P.K. Joshi",
]

UPI_HANDLES = [
    "paytm", "ybl", "oksbi", "okaxis", "okicici", "okhdfcbank",
    "upi", "apl", "axisbank", "sbi", "ibl", "boi",
]
UPI_SCAM_PREFIXES = [
    "helpdesk", "refund", "support", "customercare", "verify",
    "security", "admin", "manager", "deposit", "payment",
    "withdraw", "cashback", "bonus", "premium", "vip",
    "invest", "trading", "profit", "returns", "agent",
]

SCAM_DOMAINS = [
    "bit.ly/{code}", "t.me/{code}", "wa.me/{code}",
    "ipl-betting-{code}.com", "cricket-tips-{code}.in",
    "dream11-official-{code}.com", "invest-india-{code}.com",
    "bharat-investment-{code}.in", "sbi-kyc-update-{code}.com",
    "amazon-refund-{code}.in", "google-security-{code}.com",
    "rbi-alert-{code}.in", "trai-notice-{code}.com",
    "groww-premium-{code}.com", "zerodha-vip-{code}.in",
    "stock-tips-{code}.com", "forex-robot-{code}.in",
    "pan-update-{code}.gov.in.scam.com",
    "flipkart-refund-{code}.in", "airtel-verify-{code}.com",
    "loan-instant-{code}.in", "job-apply-{code}.com",
    "lottery-claim-{code}.in", "ed-notice-{code}.gov.in.fake.com",
    "followers-buy-{code}.com", "replica-store-{code}.in",
    "free-movies-{code}.com", "ott-free-{code}.in",
]


# ---------------------------------------------------------------------------
# Generator helpers
# ---------------------------------------------------------------------------

def _rand_phone() -> str:
    """Generate a realistic fake Indian phone number."""
    prefixes = ["91-", "91-", "+91-", "+91 ", "0"]
    prefix = random.choice(prefixes)
    first_digit = random.choice(["6", "7", "8", "9"])
    rest = "".join(random.choices(string.digits, k=9))
    return f"{prefix}{first_digit}{rest}"


def _rand_upi() -> str:
    """Generate a realistic fake UPI ID."""
    prefix = random.choice(UPI_SCAM_PREFIXES)
    handle = random.choice(UPI_HANDLES)
    suffix = random.randint(1, 999)
    return f"{prefix}{suffix}@{handle}"


def _rand_url() -> str:
    """Generate a realistic fake scam URL."""
    template = random.choice(SCAM_DOMAINS)
    code = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"https://{template.format(code=code)}"


def _rand_amount() -> int:
    """Generate a realistic amount mentioned in scam."""
    return random.choice([
        500, 1000, 2000, 5000, 10000, 15000, 25000,
        50000, 100000, 200000, 500000,
    ])


def _fill_template(template: str) -> str:
    """Fill a message template with random realistic values."""
    amount = _rand_amount()
    phone = _rand_phone()
    upi = _rand_upi()
    url = _rand_url()

    replacements = {
        "{amount}": str(amount),
        "{return_amount}": str(int(amount * random.uniform(2, 5))),
        "{phone}": phone,
        "{upi}": upi,
        "{url}": url,
        "{deposit}": str(random.choice([500, 1000, 2000, 5000])),
        "{bonus}": str(random.choice([5000, 10000, 15000, 25000])),
        "{percent}": str(random.choice([15, 20, 25, 30, 40, 50, 95, 100, 150, 200])),
        "{num_users}": str(random.choice([5000, 10000, 25000, 50000, 100000])),
        "{match_num}": str(random.randint(1, 74)),
        "{team1}": random.choice(IPL_TEAMS),
        "{team2}": random.choice(IPL_TEAMS),
        "{bank}": random.choice(BANKS),
        "{order_id}": f"{random.randint(100, 999)}-{random.randint(1000000, 9999999)}",
        "{ref_id}": f"{random.randint(100000, 999999)}",
        "{officer_name}": random.choice(OFFICER_NAMES),
    }

    result = template
    for key, value in replacements.items():
        result = result.replace(key, value)
    return result


# ---------------------------------------------------------------------------
# Record generator
# ---------------------------------------------------------------------------

LANG_MAP = {"English": "en", "Hindi": "hi", "Hinglish": "hg"}

def generate_record(record_id: int, category_id: str) -> ScamRecord:
    """Generate a single synthetic scam record.

    Args:
        record_id: Unique record index.
        category_id: Category ID matching scam_categories.yaml (e.g., 'real_money_betting').

    Returns:
        A populated ScamRecord.
    """
    # Pick language
    language = random.choices(
        ["English", "Hindi", "Hinglish"],
        weights=[0.3, 0.3, 0.4],
        k=1,
    )[0]

    cat_templates = TEMPLATES[category_id]
    lang_key = LANG_MAP[language]

    # Generate text content
    template = random.choice(cat_templates[lang_key])
    text_content = _fill_template(template)

    # Generate image text
    image_template = random.choice(cat_templates["img"])
    image_text = _fill_template(image_template)

    # Generate contact details (1-3 phones, 1-2 UPIs, 1-3 URLs)
    phone_numbers = [_rand_phone() for _ in range(random.randint(1, 3))]
    upi_ids = [_rand_upi() for _ in range(random.randint(1, 2))]
    urls = [_rand_url() for _ in range(random.randint(1, 3))]

    return ScamRecord(
        id=f"CL-SYN-{record_id:05d}",
        category=category_id,
        text_content=text_content,
        image_text=image_text,
        phone_numbers=phone_numbers,
        upi_ids=upi_ids,
        urls=urls,
        it_act_section=IT_ACT_MAP[category_id],
        severity=SEVERITY_MAP[category_id],
        language=language,
    )


def generate_dataset(num_samples: int, seed: int = 42) -> List[ScamRecord]:
    """Generate the full synthetic dataset with balanced categories.

    Args:
        num_samples: Total number of records to generate.
        seed: Random seed for reproducibility.

    Returns:
        List of ScamRecord instances.
    """
    random.seed(seed)
    num_categories = len(CATEGORIES)
    logger.info(
        "Generating %d synthetic scam records across %d categories (seed=%d)...",
        num_samples, num_categories, seed,
    )

    records: List[ScamRecord] = []
    samples_per_class = num_samples // num_categories
    remainder = num_samples % num_categories

    for idx, cat_id in enumerate(CATEGORIES):
        count = samples_per_class + (1 if idx < remainder else 0)
        for _ in range(count):
            record_id = len(records) + 1
            records.append(generate_record(record_id, cat_id))

    # Shuffle to interleave categories
    random.shuffle(records)
    logger.info("Generated %d records across %d categories.", len(records), num_categories)
    return records


# ---------------------------------------------------------------------------
# Split & save
# ---------------------------------------------------------------------------

def split_dataset(
    records: List[ScamRecord],
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
) -> Tuple[List[ScamRecord], List[ScamRecord], List[ScamRecord]]:
    """Split records into train/val/test sets."""
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, \
        "Ratios must sum to 1.0"

    n = len(records)
    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)

    train = records[:train_end]
    val = records[train_end:val_end]
    test = records[val_end:]

    logger.info("Split: train=%d, val=%d, test=%d", len(train), len(val), len(test))
    return train, val, test


def save_records(records: List[ScamRecord], filepath: Path) -> None:
    """Save records to a JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(r) for r in records]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("Saved %d records → %s", len(records), filepath)


def save_stats(
    records: List[ScamRecord],
    train: List[ScamRecord],
    val: List[ScamRecord],
    test: List[ScamRecord],
    filepath: Path,
) -> None:
    """Write dataset statistics to a text file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Category counts
    cat_counts: Dict[str, int] = {}
    for r in records:
        cat_counts[r.category] = cat_counts.get(r.category, 0) + 1

    # Language counts
    lang_counts: Dict[str, int] = {}
    for r in records:
        lang_counts[r.language] = lang_counts.get(r.language, 0) + 1

    # Severity counts
    sev_counts: Dict[str, int] = {}
    for r in records:
        sev_counts[r.severity] = sev_counts.get(r.severity, 0) + 1

    lines = [
        "=" * 60,
        "  CyberLens — Synthetic Dataset Statistics (14-Category)",
        "  Gurugram Police / GPCSSI India",
        "=" * 60,
        "",
        f"Total records:     {len(records)}",
        f"Training set:      {len(train)} ({len(train)/len(records)*100:.1f}%)",
        f"Validation set:    {len(val)} ({len(val)/len(records)*100:.1f}%)",
        f"Test set:          {len(test)} ({len(test)/len(records)*100:.1f}%)",
        "",
        "─" * 40,
        "Category Distribution:",
        "─" * 40,
    ]
    for cat_name, count in sorted(cat_counts.items()):
        pct = count / len(records) * 100
        bar = "█" * int(pct / 2)
        lines.append(f"  {cat_name:<30} {count:>4} ({pct:>5.1f}%) {bar}")

    lines += [
        "",
        "─" * 40,
        "Language Distribution:",
        "─" * 40,
    ]
    for lang, count in sorted(lang_counts.items()):
        pct = count / len(records) * 100
        lines.append(f"  {lang:<25} {count:>4} ({pct:>5.1f}%)")

    lines += [
        "",
        "─" * 40,
        "Severity Distribution:",
        "─" * 40,
    ]
    for sev, count in sorted(sev_counts.items()):
        pct = count / len(records) * 100
        lines.append(f"  {sev:<25} {count:>4} ({pct:>5.1f}%)")

    lines += [
        "",
        "─" * 40,
        "Sample Records (first 3):",
        "─" * 40,
    ]
    for r in records[:3]:
        lines.append(f"  ID: {r.id}")
        lines.append(f"  Category: {r.category}")
        lines.append(f"  Language: {r.language}")
        lines.append(f"  Severity: {r.severity}")
        lines.append(f"  Text: {r.text_content[:120]}...")
        lines.append(f"  Phones: {r.phone_numbers}")
        lines.append(f"  UPIs: {r.upi_ids}")
        lines.append("")

    lines.append("=" * 60)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info("Stats saved → %s", filepath)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="CyberLens — Synthetic Indian Scam Dataset Generator (14-Category)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/generate_dataset.py --num-samples 1400\n"
            "  python scripts/generate_dataset.py --num-samples 2800 --output-dir data/synthetic\n"
        ),
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=1400,
        help="Number of synthetic records to generate (default: 1400, i.e. 100 per category)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/synthetic",
        help="Output directory for JSON files (default: data/synthetic)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point: generate, split, and save the synthetic dataset."""
    args = parse_args()
    output_dir = Path(args.output_dir)

    logger.info("=" * 60)
    logger.info("  CyberLens — Synthetic Dataset Generator (14-Category)")
    logger.info("  Gurugram Police / GPCSSI India")
    logger.info("=" * 60)

    # Generate
    records = generate_dataset(args.num_samples, seed=args.seed)

    # Split
    train, val, test = split_dataset(records)

    # Save
    save_records(records, output_dir / "dataset.json")
    save_records(train, output_dir / "train.json")
    save_records(val, output_dir / "val.json")
    save_records(test, output_dir / "test.json")
    save_stats(records, train, val, test, output_dir / "stats.txt")

    logger.info("=" * 60)
    logger.info("  Dataset generation complete!")
    logger.info("  Output: %s", output_dir.resolve())
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
