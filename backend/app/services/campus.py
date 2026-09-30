"""
Campus domain knowledge (SRMIST KTR by default).
================================================

MailMind's triage, classification, commitment extraction and drafting were
tuned for enterprise mail. On a campus the stakes are different: a missed
placement-drive registration, hall-ticket download or fee deadline has a hard,
irreversible cost, and the senders who matter are the Controller of
Examinations, the Career Development Centre, HODs and faculty advisors — not a
CEO.

This module is the single source of that knowledge. Both the LLM prompts and
the deterministic (no-AI) fallbacks read from here, so behaviour stays
consistent whether or not a student has configured an API key.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.config.settings import settings


@lru_cache(maxsize=512)
def _kw_re(keyword: str) -> re.Pattern[str]:
    """Whole-word matcher so 'hod' doesn't hit 'method' and 'fee' not 'feedback'."""
    kw = keyword.strip().lower()
    return re.compile(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])")


def _has(text: str, keyword: str) -> bool:
    return bool(_kw_re(keyword).search(text))


def _hits(text: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for kw in keywords if _has(text, kw))

# ─────────────────────────────────────────────────────────────────────────────
# Email categories
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Category:
    id: str
    label: str
    description: str
    keywords: tuple[str, ...]


# Ordered: when keyword scores tie, the earlier (more consequential) wins.
CATEGORIES: tuple[Category, ...] = (
    Category(
        "placement", "Placements & Internships",
        "placement drives, internships, recruiter mail, CDC/T&P notices, shortlists, offer letters",
        ("placement", "recruitment", "recruiter", "campus drive", "drive", "internship", "intern",
         "shortlist", "shortlisted", "pre-placement", "ppt", "offer letter", "ctc", "lpa",
         "career development", "cdc", "training and placement", "t&p", "aptitude test",
         "online assessment", "interview", "hiring", "job opening", "superset", "resume", "eligibility"),
    ),
    Category(
        "exams", "Exams & Results",
        "exam schedules, hall tickets, seating, results, revaluation, arrears, CAT/FAT/end-semester",
        ("exam", "examination", "hall ticket", "admit card", "seating", "timetable for exam",
         "results", "result", "revaluation", "re-evaluation", "arrear", "supplementary",
         "end semester", "end-semester", "cycle test", "cat-1", "cat-2", "fat", "internal assessment",
         "controller of examinations", "coe", "grade", "marksheet", "invigilation"),
    ),
    Category(
        "academics", "Academics",
        "courses, assignments, labs, projects, attendance, course registration, faculty advisor notes",
        ("assignment", "submission", "submit", "lab", "laboratory", "project", "review",
         "attendance", "course registration", "enrolment", "enrollment", "elective", "syllabus",
         "lecture", "class", "classes", "timetable", "faculty advisor", "academic advisor",
         "mentor", "credits", "semester", "thesis", "viva", "record note", "practical"),
    ),
    Category(
        "fees", "Fees & Scholarships",
        "fee payment, dues, fines, refunds, scholarships, financial aid",
        ("fee", "fees", "payment", "dues", "fine", "penalty", "refund", "scholarship",
         "financial aid", "receipt", "challan", "tuition", "hostel fee", "late fee"),
    ),
    Category(
        "administrative", "Administrative",
        "official circulars, certificates, ID cards, documents, verification, institutional notices",
        ("circular", "notice", "notification", "bonafide", "certificate", "id card",
         "document", "verification", "registrar", "office of", "compliance", "undertaking",
         "form", "no dues", "migration", "transcript", "leave", "od", "on duty"),
    ),
    Category(
        "events", "Events & Clubs",
        "club activities, symposiums, hackathons, workshops, fests, seminars, guest lectures",
        ("event", "hackathon", "symposium", "workshop", "webinar", "seminar", "fest",
         "club", "competition", "guest lecture", "talk", "register now", "meetup", "conference",
         "cultural", "technical fest", "aaruush", "milan"),
    ),
    Category(
        "research", "Research",
        "papers, publications, conferences, research proposals, PhD and grant matters",
        ("research", "paper", "publication", "journal", "manuscript", "reviewer", "phd",
         "doctoral", "grant", "proposal", "patent", "citation", "scopus"),
    ),
    Category(
        "campus_life", "Hostel & Campus Life",
        "hostel, mess, transport, library, sports, health centre, campus facilities",
        ("hostel", "mess", "warden", "transport", "bus", "library", "sports", "gym",
         "health centre", "medical", "wifi", "maintenance", "room allotment"),
    ),
    Category(
        "personal", "Personal",
        "direct one-to-one mail from a classmate, faculty member or contact expecting a reply",
        ("could you", "can you", "would you", "please let me know", "are you free"),
    ),
    Category(
        "promotions", "Promotions & Newsletters",
        "newsletters, marketing, course ads, social notifications, spam-like bulk mail",
        ("unsubscribe", "newsletter", "% off", "sale", "offer ends", "promo", "discount",
         "limited time", "webinar series", "view in browser", "manage preferences"),
    ),
)

CATEGORY_IDS: tuple[str, ...] = tuple(c.id for c in CATEGORIES) + ("other",)
_CATEGORY_BY_ID = {c.id: c for c in CATEGORIES}

# Categories where missing the email has a hard cost — never dampen these.
HIGH_STAKES_CATEGORIES = frozenset({"placement", "exams", "fees", "academics", "administrative"})


def category_label(category_id: str | None) -> str:
    cat = _CATEGORY_BY_ID.get((category_id or "").lower())
    return cat.label if cat else "Other"


def normalise_category(raw: Any) -> str:
    """Map a model's free-text category onto a known id ('other' if unknown)."""
    value = str(raw or "").strip().lower().replace(" ", "_").replace("-", "_").replace("&", "and")
    if value in CATEGORY_IDS:
        return value
    aliases = {
        "placements": "placement", "internship": "placement", "internships": "placement",
        "career": "placement", "jobs": "placement", "job": "placement", "recruitment": "placement",
        "exam": "exams", "examination": "exams", "results": "exams", "result": "exams",
        "academic": "academics", "coursework": "academics", "assignment": "academics",
        "fee": "fees", "finance": "fees", "fees_finance": "fees", "scholarship": "fees",
        "admin": "administrative", "circular": "administrative", "notice": "administrative",
        "event": "events", "clubs": "events", "club": "events",
        "hostel": "campus_life", "campus": "campus_life", "transport": "campus_life",
        "newsletter": "promotions", "marketing": "promotions", "spam": "promotions",
        "promotion": "promotions", "social": "promotions",
    }
    return aliases.get(value, "other")


def categorize(sender: str, subject: str, body: str) -> str:
    """Deterministic category from keywords (used when no AI is configured)."""
    text = f" {subject} {subject} {body[:1500]} ".lower()  # subject counts double
    best_id, best_hits = "other", 0
    for cat in CATEGORIES:
        hits = _hits(text, cat.keywords)
        if hits > best_hits:
            best_id, best_hits = cat.id, hits
    if best_id == "promotions" and is_campus_sender(sender):
        # Official mail with an unsubscribe footer is still official.
        others = [c for c in CATEGORIES if c.id != "promotions"]
        scored = max(others, key=lambda c: _hits(text, c.keywords))
        best_id = scored.id if _hits(text, scored.keywords) else "administrative"
    return best_id


# ─────────────────────────────────────────────────────────────────────────────
# Sender authority
# ─────────────────────────────────────────────────────────────────────────────

# (score, label, keywords) — checked top-down against the sender's address and
# display name, then subject/signature. Scores are the 'authority' axis value.
AUTHORITY_TIERS: tuple[tuple[float, str, tuple[str, ...]], ...] = (
    (1.00, "University leadership",
     ("vice chancellor", "vice-chancellor", "pro vice", "pro-vice", "registrar", "dean",
      "director", "controller of examinations", "coe")),
    (0.92, "Head of Department / Placement office",
     ("head of department", "hod", "placement officer", "placement cell",
      "career development centre", "career development center", "cdc", "training and placement",
      "t&p", "placement", "placements", "careers", "director (career", "director - career")),
    (0.82, "Faculty",
     ("professor", "asst. prof", "assistant professor", "associate professor", "faculty advisor",
      "faculty adviser", "academic advisor", "class coordinator", "year coordinator",
      "course coordinator", "programme coordinator", "program coordinator", "mentor", "hod office")),
    (0.75, "Institutional office",
     ("examination cell", "exam cell", "academic section", "academic office", "accounts",
      "fee section", "finance office", "hostel office", "warden", "proctor", "admissions",
      "examcell", "office of", "administration", "admin", "office", "helpdesk", "erp", "academia")),
    (0.62, "Recruiter / company HR",
     ("talent acquisition", "talent", "recruit", "recruiting", "recruitment", "hr team", "hr",
      "human resources", "campus hiring", "hiring", "university relations", "careers")),
)

# SRM student addresses look like ab1234@srmist.edu.in (letters + digits).
_STUDENT_LOCALPART_RE = re.compile(r"^[a-z]{1,4}\d{3,5}$")


def sender_domain(sender: str) -> str:
    email = _extract_address(sender)
    return email.split("@", 1)[1] if "@" in email else ""


def _extract_address(sender: str) -> str:
    sender = (sender or "").strip().lower()
    m = re.search(r"<([^>]+)>", sender)
    return (m.group(1) if m else sender).strip()


def is_campus_sender(sender: str) -> bool:
    domain = sender_domain(sender)
    return any(domain == d or domain.endswith("." + d) for d in settings.campus_domain_set)


def is_student_address(sender: str) -> bool:
    address = _extract_address(sender)
    local = address.split("@", 1)[0] if "@" in address else address
    return is_campus_sender(sender) and bool(_STUDENT_LOCALPART_RE.match(local))


def score_authority(sender: str, subject: str = "", body: str = "") -> dict[str, Any]:
    """Campus-aware authority axis. Returns {axis, raw_score, explanation, role}.

    Institutional titles only count from an official campus address — a Gmail
    user whose display name is "Dean" must not outrank a real faculty member.
    """
    sender_l = (sender or "").lower().replace(".", " ").replace("_", " ")
    subject_l = (subject or "").lower()
    # Signatures sit at the end; greetings at the start. Scan both, not the middle.
    body_l = (body or "").lower()
    signature = f"{body_l[:300]} {body_l[-600:]}"
    campus = is_campus_sender(sender)

    if campus:
        for score, label, keywords in AUTHORITY_TIERS[:-1]:  # all institutional tiers
            if any(_has(sender_l, kw) for kw in keywords):
                return _authority(score, _FROM.get(label, f"From {label}"), label)
        for score, label, keywords in AUTHORITY_TIERS[:-1]:
            if any(_has(subject_l, kw) or _has(signature, kw) for kw in keywords):
                return _authority(score - 0.04, _FROM.get(label, f"From {label}"), label)
        if is_student_address(sender):
            return _authority(0.38, "From a fellow student or club", "Student")
        # Letters-only local part on an official domain: a named faculty/staff box.
        return _authority(0.66, f"From an official {settings.campus_short_name} address", "Campus office")

    rec_score, rec_label, rec_keywords = AUTHORITY_TIERS[-1]
    if any(_has(sender_l, kw) or _has(signature, kw) for kw in rec_keywords):
        return _authority(rec_score, "From a recruiter", rec_label)
    consumer = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
                "rediffmail.com", "protonmail.com", "live.com"}
    domain = sender_domain(sender)
    if domain and domain not in consumer:
        return _authority(0.35, f"From an outside organisation ({domain})", "External")
    return _authority(0.2, "From a personal or unknown address", "External")


_FROM = {
    "University leadership": "From university leadership",
    "Head of Department / Placement office": "From the HOD or placement office",
    "Faculty": "From faculty",
    "Institutional office": "From a university office",
}


def _authority(score: float, explanation: str, role: str) -> dict[str, Any]:
    return {"axis": "authority", "raw_score": round(max(0.0, min(1.0, score)), 3),
            "explanation": explanation, "role": role}


# ─────────────────────────────────────────────────────────────────────────────
# Urgency vocabulary
# ─────────────────────────────────────────────────────────────────────────────

# Consequence language specific to campus life. Hitting one of these means
# ignoring the email has a real academic / career cost.
CAMPUS_CONSEQUENCE_TERMS: tuple[str, ...] = (
    "debarred", "debar", "detained", "detention", "attendance shortage", "shortage of attendance",
    "below 75", "not eligible", "ineligible", "disciplinary", "suspension", "suspended",
    "penalty", "fine", "late fee", "will not be permitted", "will not be allowed",
    "no further extension", "strictly", "mandatory", "compulsory", "last date", "final reminder",
    "final call", "deadline", "closes today", "closing today", "window closes", "before the deadline",
    "withheld", "blocked", "cancelled", "rejected", "absent",
)

# Terms that make an email high-stakes even when it comes from a no-reply
# address (placement portals and the exam cell often send from no-reply).
CAMPUS_CRITICAL_TERMS: tuple[str, ...] = (
    "placement", "drive", "shortlist", "interview", "register", "registration", "apply",
    "hall ticket", "admit card", "exam", "result", "fee", "payment", "deadline", "last date",
    "attendance", "submission", "submit", "eligibility", "offer letter", "assessment",
    "reporting time", "report to", "venue",
)


def has_campus_critical_signal(subject: str, body: str) -> bool:
    text = f"{subject} {body[:2000]}".lower()
    return any(_has(text, term) for term in CAMPUS_CRITICAL_TERMS)


def consequence_hits(text: str) -> list[str]:
    low = (text or "").lower()
    return [t for t in CAMPUS_CONSEQUENCE_TERMS if _has(low, t)]


# ─────────────────────────────────────────────────────────────────────────────
# Prompt context
# ─────────────────────────────────────────────────────────────────────────────


def role_context(profile: dict[str, Any] | None) -> str:
    """One paragraph telling the model whose inbox this is."""
    profile = profile or {}
    role = profile.get("role") or "student"
    dept = profile.get("department")
    year = profile.get("year_of_study")
    campus = settings.campus_name
    if role == "faculty":
        who = "a faculty member"
        cares = ("student requests and escalations, department and HOD directives, exam-cell "
                 "duties (question papers, invigilation, mark entry), committee work, research "
                 "deadlines, and administrative circulars with compliance dates")
    elif role == "staff":
        who = "an administrative staff member"
        cares = ("directives from university leadership and the registrar, office deadlines, "
                 "student and parent queries, circulars and compliance dates")
    else:
        who = "a student"
        if year:
            who = f"a year-{year} student"
        cares = ("placement and internship drives (registration cut-offs, shortlists, assessments, "
                 "interview slots), exams (schedules, hall tickets, results, revaluation), fee and "
                 "scholarship deadlines, attendance warnings, assignment and project submissions, "
                 "and requests from faculty")
    dept_part = f" in the {dept} department" if dept else ""
    return (
        f"This inbox belongs to {who}{dept_part} at {campus}. "
        f"What matters most to them: {cares}. Missing such an email can cost a placement "
        f"opportunity, exam eligibility, or a fine — treat that as the real urgency. Club "
        f"promotions, newsletters and general announcements with no action are low priority."
    )


def categories_prompt_list() -> str:
    return "\n".join(f"  {c.id}: {c.description}" for c in CATEGORIES) + \
        "\n  other: anything that fits none of the above"


def authority_prompt_guide() -> str:
    return (
        "Authority on campus (highest first): Vice Chancellor / Registrar / Deans / Controller of "
        "Examinations → HOD and the placement office (CDC / Training & Placement) → faculty, faculty "
        "advisors and coordinators → institutional offices (exam cell, accounts, hostel) → company "
        "recruiters → fellow students and clubs → external/unknown senders. "
        f"Official {settings.campus_short_name} domains: {', '.join(sorted(settings.campus_domain_set))}."
    )


def draft_etiquette(profile: dict[str, Any] | None, recipient: str | None) -> str:
    """Tone guidance for replies, based on who is writing to whom."""
    role = (profile or {}).get("role") or "student"
    authority = score_authority(recipient or "")
    senior = authority["raw_score"] >= 0.75
    if role == "student" and senior:
        return (
            "You are a student writing to faculty or a university office. Be respectful and "
            "concise: open with 'Dear Sir/Madam,' or 'Dear Professor <surname>,' as appropriate, "
            "state the purpose in the first sentence, never use slang or emojis, and close with "
            "'Thank you,' or 'Regards,' followed by your name. Do not invent a register number, "
            "section or department — only use them if they appear in the email."
        )
    if role == "student" and authority["role"] == "Recruiter / company HR":
        return (
            "You are a student replying to a recruiter. Be professional, prompt and specific: "
            "confirm availability or requested details clearly, and thank them for the opportunity."
        )
    if role == "faculty" and authority["role"] == "Student":
        return (
            "You are a faculty member replying to a student. Be clear, kind and direct; give "
            "specific next steps and dates where relevant."
        )
    return "Match the formality of the incoming email; be clear and concise."


# ─────────────────────────────────────────────────────────────────────────────
# Routine notifications (bank alerts, OTPs, receipts, deliveries, social)
# ─────────────────────────────────────────────────────────────────────────────

_NOTIFICATION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("transaction", re.compile(
        r"\b(debited|credited|transaction alert|txn|upi|imps|neft|rtgs|a/c\s*(no\.?)?\s*x+|"
        r"account\s+x{2,}\d+|available balance|avl bal|has been (debited|credited)|"
        r"payment (received|successful|of rs)|amount of (inr|rs\.?))\b", re.I)),
    ("otp", re.compile(r"\b(otp|one[- ]time password|verification code|login code)\b", re.I)),
    ("receipt", re.compile(
        r"\b(receipt|invoice|order (confirmed|placed|shipped|delivered)|out for delivery|"
        r"your order|booking confirmed|e-?ticket)\b", re.I)),
    ("statement", re.compile(r"\b(e-?statement|account statement|monthly statement)\b", re.I)),
    ("security", re.compile(r"\b(new (sign-?in|login)|signed in from|security alert for)\b", re.I)),
    ("social", re.compile(
        r"\b(liked your|commented on|new follower|connection request|endorsed you|"
        r"viewed your profile|people you may know|jobs you may be interested)\b", re.I)),
]

# Signals that a notification genuinely needs the reader (fraud, blocks, dues).
_NOTIFICATION_URGENT = re.compile(
    r"\b(suspicious|fraud|unauthori[sz]ed|account (has been )?(blocked|frozen|suspended)|"
    r"card (has been )?blocked|kyc (pending|expir\w*)|overdue|payment failed|"
    r"insufficient (funds|balance)|emi (due|bounce\w*)|bounced)\b", re.I)


def notification_kind(subject: str, body: str) -> str | None:
    """Name the kind of routine notification this is, or None for normal mail.

    Routine alerts mention dates and amounts, which rule-based scoring reads as
    deadlines and requests. They are records of something that already
    happened, so they should rank low unless they carry a real warning.
    """
    text = (subject or "") + "\n" + (body or "")[:1500]
    if _NOTIFICATION_URGENT.search(text):
        return None
    for kind, pattern in _NOTIFICATION_PATTERNS:
        if pattern.search(text):
            return kind
    return None


NOTIFICATION_WORDING = {
    "transaction": "A record of a payment that already happened",
    "otp": "A one-time code, nothing to act on later",
    "receipt": "A receipt or order update",
    "statement": "A routine statement",
    "security": "A routine sign-in notice",
    "social": "A social notification",
}
