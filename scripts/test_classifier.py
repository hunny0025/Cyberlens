"""Quick test of the 14-class scam classifier."""
import os
os.environ["TRANSFORMERS_NO_TF"] = "1"

from src.classifier.scam_classifier import ScamClassifier

c = ScamClassifier("models/scam_classifier")
print(f"Loaded: {c.is_loaded} | Categories: {c.category_count}\n")

tests = [
    ("IPL betting tips! Win 50000 daily! Join VIP group!", "real_money_betting"),
    ("Guaranteed returns! Invest 10000 get 50000 in 30 days!", "investment_scam"),
    ("Instant loan approved 50000! No documents! Pay processing fee!", "loan_scam"),
    ("Work from home earn 5000 daily! Simple typing job!", "job_scam"),
    ("KBC winner! Your number selected for 25 lakh prize!", "lottery_scam"),
    ("Your SBI account suspended! Call helpline 9876543210!", "fake_customer_care"),
    ("CBI officer calling. Your Aadhaar linked to money laundering. Digital arrest.", "fake_govt_official"),
    ("Mukesh Ambani secret investment plan! Double your money!", "fake_celebrity_endorsement"),
    ("I have your private video. Pay 10000 or I send to all contacts.", "sextortion_threat"),
    ("Buy Instagram followers 10K for just 500 rupees!", "fake_followers_sale"),
    ("First copy Gucci Louis Vuitton bags! Original quality 500 only!", "counterfeit_products"),
    ("Free movies download HD! Torrent links latest Bollywood!", "piracy_links"),
    ("Premium weed available! Home delivery! WhatsApp order!", "drug_sale"),
    ("This is just a random text that should not match any scam keywords.", "unknown"),
]

print(f"{'Input':<60} {'Expected':<30} {'Predicted':<30} {'Conf':>8} {'Status'}")
print("-" * 140)

correct = 0
for text, expected in tests:
    r = c.predict(text)
    status = "PASS" if r.category_id == expected else "FAIL"
    if r.category_id == expected:
        correct += 1
    print(f"{text[:58]:<60} {expected:<30} {r.category_id:<30} {r.confidence:>7.1%} {status}")

print(f"\n{'='*140}")
print(f"Results: {correct}/{len(tests)} correct ({correct/len(tests)*100:.0f}%)")
