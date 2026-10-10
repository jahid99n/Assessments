"""Editable, ordered merchant rules. Word boundaries prevent BP matching substrings."""
import re

RULES = {
    "Groceries": ["coles", "woolworths", "aldi", "iga", "harris farm", "costco"],
    "Dining": ["mcdonald", "kfc", "hungry jack", "subway", "domino", "cafe", "coffee", "restaurant", "uber eats"],
    "Transport": ["shell", "bp", "ampol", "7-eleven", "caltex", "uber", "opal", "myki"],
    "Shopping": ["kmart", "target", "big w", "bunnings", "jb hi-fi", "officeworks", "amazon"],
    "Health": ["chemist warehouse", "priceline", "pharmacy", "medical"],
}


def classify(merchant):
    for category, words in RULES.items():
        if any(re.search(r"\b" + re.escape(word) + r"\b", merchant, re.I) for word in words):
            return category
    return "Other"
