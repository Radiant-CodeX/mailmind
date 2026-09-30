"""
Demo mailbox for mock mode (USE_MOCK_MAIL=true).
================================================

A realistic SRMIST student inbox so the whole product can be demonstrated with
no Google account: placement drives, the exam cell, attendance warnings, fee
deadlines, faculty mail, clubs and newsletters. Dates are generated relative to
"now" so deadlines always look live, and numeric dates use the Indian DD/MM/YYYY
format that real campus mail uses.

People and companies are fictional. Phone numbers and IDs are dummies that
exercise the PII masker.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> datetime:
    return datetime.now(tz=IST)


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat() + "Z"


def _d(dt: datetime) -> str:
    """Indian numeric date, e.g. 03/10/2026."""
    return dt.strftime("%d/%m/%Y")


def _day(dt: datetime) -> str:
    return dt.strftime("%A, %d %B")


def assessment_slot() -> datetime:
    """The Nimbus online assessment: two days from now, 10:00 AM IST.

    Shared with the demo calendar so the conflict detector has a real clash.
    """
    base = _now_ist() + timedelta(days=2)
    return base.replace(hour=10, minute=0, second=0, microsecond=0)


def inbox() -> list[dict[str, Any]]:
    now = _now_ist()
    today_5pm = now.replace(hour=17, minute=0, second=0, microsecond=0)
    if today_5pm < now:
        today_5pm += timedelta(days=1)
    assessment = assessment_slot()
    exam_start = now + timedelta(days=9)
    hall_ticket_by = now + timedelta(days=3)
    fee_last_date = now + timedelta(days=4)
    advisor_meet = now + timedelta(days=1)
    review_day = now + timedelta(days=(4 - now.weekday()) % 7 or 7)  # coming Friday
    interview_confirm = (now + timedelta(days=1)).replace(hour=11, minute=0)
    hackathon_close = now + timedelta(days=6)

    def at(minutes: int = 0, hours: int = 0, days: int = 0) -> str:
        return _iso_utc(now - timedelta(minutes=minutes, hours=hours, days=days))

    return [
        {
            "email_id": "campus-1",
            "sender": "placement@srmist.edu.in",
            "sender_name": "Career Development Centre, SRMIST",
            "subject": "Nimbus Technologies Campus Drive 2026: registration closes TODAY 5 PM",
            "body": (
                "Dear Students,\n\n"
                "Nimbus Technologies is recruiting final-year B.Tech CSE / IT / ECE students for the "
                "role of Associate Software Engineer (CTC 8.5 LPA).\n\n"
                "Eligibility: 7.0 CGPA and above, no standing arrears.\n\n"
                f"1. Register on the placement portal before {today_5pm.strftime('%I:%M %p')} today "
                f"({_d(today_5pm)}). Late registrations will NOT be entertained.\n"
                f"2. Online assessment: {_d(assessment)} at 10:00 AM, Tech Park, Lab 702. "
                "Reporting time 9:30 AM with your college ID card.\n\n"
                "Students who register and do not attend will be debarred from the next two drives.\n\n"
                "Regards,\nCareer Development Centre\nSRM Institute of Science and Technology"
            ),
            "received_at": at(minutes=12),
            "is_read": False, "is_starred": True, "has_attachments": True,
        },
        {
            "email_id": "campus-2",
            "sender": "coe@srmist.edu.in",
            "sender_name": "Controller of Examinations",
            "subject": "End Semester Theory Examinations: hall ticket download and eligibility",
            "body": (
                "Dear Students,\n\n"
                f"The End Semester Theory Examinations commence on {_d(exam_start)}. Hall tickets are "
                f"available on the student portal and must be downloaded on or before {_d(hall_ticket_by)}.\n\n"
                "Students with attendance below 75% in any course will not be permitted to write the "
                "examination in that course. Students with pending fee dues will find their hall ticket withheld.\n\n"
                "Carry a printed hall ticket and your ID card to every session.\n\n"
                "Controller of Examinations\nSRMIST, Kattankulathur"
            ),
            "received_at": at(hours=1, minutes=5),
            "is_read": False, "is_starred": False, "has_attachments": True,
        },
        {
            "email_id": "campus-3",
            "sender": "meera.krishnan@srmist.edu.in",
            "sender_name": "Dr. Meera Krishnan",
            "subject": "Attendance shortage: 21CSC303J Computer Networks (68%)",
            "body": (
                "Dear Arjun,\n\n"
                "Your attendance in 21CSC303J Computer Networks currently stands at 68%, below the "
                "required 75%. If this is not regularised you will be detained from the end semester "
                "exam for this course.\n\n"
                f"Please meet me in my cabin (Tech Park, 7th floor) on {_day(advisor_meet)} between 2 and 4 PM "
                "with any medical certificates or OD letters you have.\n\n"
                "Regards,\nDr. Meera Krishnan\nAssistant Professor & Faculty Advisor, Department of CSE"
            ),
            "received_at": at(hours=2, minutes=40),
            "is_read": False, "is_starred": False, "has_attachments": False,
        },
        {
            "email_id": "campus-4",
            "sender": "talent@arcadiasystems.com",
            "sender_name": "Arcadia Systems: Talent Acquisition",
            "subject": "Shortlisted for the technical interview, please confirm your slot",
            "body": (
                "Hi Arjun,\n\n"
                "Congratulations! You have been shortlisted for the technical interview round for the "
                "Software Engineering Intern role.\n\n"
                f"Proposed slot: {_day(now + timedelta(days=3))}, 3:00 PM IST (Google Meet).\n"
                f"Please reply to confirm this slot by {interview_confirm.strftime('%I:%M %p')} tomorrow. "
                "Unconfirmed slots will be released to the next candidate.\n\n"
                "For queries call Kavya at +91 98400 12345.\n\n"
                "Best,\nKavya Raman\nTalent Acquisition, Arcadia Systems"
            ),
            "received_at": at(hours=3, minutes=15),
            "is_read": False, "is_starred": False, "has_attachments": False,
        },
        {
            "email_id": "campus-5",
            "sender": "feesection@srmist.edu.in",
            "sender_name": "Accounts: Fee Section",
            "subject": "Odd semester fee: last date without fine",
            "body": (
                "Dear Student,\n\n"
                f"This is a reminder that the last date to pay the odd semester tuition fee without "
                f"fine is {_d(fee_last_date)}. A late fee of Rs. 100 per day will be levied thereafter, and "
                "hall tickets will be withheld for students with outstanding dues.\n\n"
                "Pay online through the student portal (Fees → Online Payment).\n\n"
                "Accounts Office, SRMIST"
            ),
            "received_at": at(hours=5),
            "is_read": False, "is_starred": False, "has_attachments": False,
        },
        {
            "email_id": "campus-6",
            "sender": "rajesh.v@srmist.edu.in",
            "sender_name": "Dr. Rajesh Venkatesan",
            "subject": "Mini project Review 2: report and PPT submission",
            "body": (
                "Dear Students,\n\n"
                f"Review 2 for the mini project is scheduled on {_day(review_day)}. Please upload your "
                "report (IEEE format) and presentation to the LMS by Thursday 11:59 PM. Each team gets "
                "10 minutes followed by Q&A. Teams that do not submit will be marked absent for the review.\n\n"
                "Regards,\nDr. Rajesh Venkatesan\nAssociate Professor, Department of CSE"
            ),
            "received_at": at(hours=7, minutes=30),
            "is_read": True, "is_starred": False, "has_attachments": True,
        },
        {
            "email_id": "campus-7",
            "sender": "noreply@srmist.edu.in",
            "sender_name": "SRMIST Academia",
            "subject": "Course registration for the next semester opens Monday",
            "body": (
                "Dear Student,\n\n"
                "Course and elective registration for the next semester opens on Monday at 10 AM on "
                "the Academia portal and closes on Wednesday 5 PM. Elective seats are allotted first come, "
                "first served.\n\n"
                "This is an automated message. Please do not reply."
            ),
            "received_at": at(hours=10),
            "is_read": True, "is_starred": False, "has_attachments": False,
        },
        {
            "email_id": "campus-8",
            "sender": "ab1234@srmist.edu.in",
            "sender_name": "Coding Club SRM",
            "subject": "HackSRM 2026: team registrations open!",
            "body": (
                "Hey everyone!\n\n"
                "HackSRM is back: a 24-hour hackathon with prizes worth Rs. 1,00,000. Form teams of up "
                f"to 4 and register before {_d(hackathon_close)}. Food and swags on us!\n\n"
                "Register if interested: link in the club group.\n\nCheers,\nCoding Club"
            ),
            "received_at": at(hours=13),
            "is_read": True, "is_starred": False, "has_attachments": False,
        },
        {
            "email_id": "campus-9",
            "sender": "hostel.office@srmist.edu.in",
            "sender_name": "Hostel Office",
            "subject": "Scheduled water supply maintenance: Paari block",
            "body": (
                "Dear Residents,\n\n"
                "Water supply in Paari block will be interrupted on Saturday from 9 AM to 1 PM for tank "
                "cleaning. Please store water in advance.\n\nWarden, Hostel Office"
            ),
            "received_at": at(hours=20),
            "is_read": True, "is_starred": False, "has_attachments": False,
        },
        {
            "email_id": "campus-10",
            "sender": "newsletter@learnhub.io",
            "sender_name": "LearnHub",
            "subject": "50% off all Data Science courses: this week only!",
            "body": (
                "Upskill with industry-ready Data Science courses. Use code STUDENT50 at checkout. "
                "Offer ends Sunday.\n\nUnsubscribe | Manage preferences"
            ),
            "received_at": at(days=1, hours=2),
            "is_read": True, "is_starred": False, "has_attachments": False,
        },
        {
            "email_id": "campus-11",
            "sender": "cse.dept@srmist.edu.in",
            "sender_name": "Department of CSE",
            "subject": "Guest lecture on Generative AI: photos and slides",
            "body": (
                "Dear All,\n\nThank you for attending yesterday's guest lecture on Generative AI. Slides "
                "and photos are now available on the department drive. FYI: no action needed.\n\n"
                "Department of Computer Science and Engineering"
            ),
            "received_at": at(days=1, hours=6),
            "is_read": True, "is_starred": False, "has_attachments": False,
        },
    ]


def sent_mail() -> list[dict[str, Any]]:
    """A student's sent-mail history: gives Tone DNA a realistic voice to learn."""
    now = datetime.utcnow()

    def ago(days: int) -> str:
        return (now - timedelta(days=days)).isoformat() + "Z"

    rich = [
        ("Re: OD request for Hackathon participation",
         "Dear Ma'am,\n\nI request On Duty for 12th and 13th as I will be representing the college at "
         "the Smart India Hackathon finals. The participation letter is attached.\n\nThank you,\nArjun\n"
         "III Year CSE, Section B", 2),
        ("Re: Mini project Review 1 feedback",
         "Dear Sir,\n\nThank you for the feedback. We will add the comparison with the baseline model "
         "and update the architecture diagram before Review 2.\n\nRegards,\nArjun", 5),
        ("Re: Interview availability: Summer internship",
         "Hi Kavya,\n\nThank you for the opportunity. I confirm the slot on Thursday at 3 PM. Please let "
         "me know if anything is needed from my side before the interview.\n\nBest regards,\nArjun", 7),
        ("Re: Lab record submission",
         "Dear Ma'am,\n\nI have submitted the DBMS lab record at the department office. Apologies for "
         "the one-day delay; I was unwell.\n\nThank you,\nArjun", 9),
        ("Re: Team for HackSRM?",
         "Hey! Count me in. I can take the backend + API part. Let's sync tomorrow after the CN "
         "class.\n\nArjun", 11),
        ("Re: Bonafide certificate request",
         "Dear Sir/Madam,\n\nI request a bonafide certificate for my internship application. My "
         "details are below. Kindly let me know when I can collect it.\n\nThank you,\nArjun", 14),
        ("Re: Clarification on assignment 2",
         "Dear Sir,\n\nFor question 3, should we implement the sliding window protocol in Python or "
         "is pseudocode acceptable?\n\nThank you,\nArjun", 17),
        ("Re: Group project split",
         "Hi all,\n\nSplitting it up: I'll do the backend and deployment, Priya takes the UI, Karthik "
         "the report. Let's aim to have a demo by Friday.\n\nThanks,\nArjun", 20),
        ("Re: Placement portal registration issue",
         "Dear Sir/Madam,\n\nI am unable to register for the drive as the portal shows my CGPA "
         "incorrectly. Could you please look into this? My register number is in the attached "
         "screenshot.\n\nThank you,\nArjun", 23),
        ("Re: Research internship query",
         "Dear Professor,\n\nI am interested in your work on federated learning and would like to "
         "know if there are openings for undergraduate research interns this summer.\n\nRegards,\nArjun", 27),
    ]
    mails = [{"id": f"cs{i:02d}", "subject": s, "body": b, "sentDateTime": ago(d)}
             for i, (s, b, d) in enumerate(rich)]
    filler = [
        "Re: Class notes for Unit 3", "Re: Lab batch change", "Re: Club meeting timing",
        "Re: Project abstract", "Re: Library book renewal", "Re: Seminar topic approval",
        "Re: Internship certificate", "Re: Quiz rescheduling", "Re: Hostel room change",
        "Re: Workshop registration",
    ]
    for i, subj in enumerate(filler):
        mails.append({"id": f"cf{i:02d}", "subject": subj,
                      "body": "Thank you for the update. I will do the needful.\n\nRegards,\nArjun",
                      "sentDateTime": ago(30 + i)})
    return mails


def calendar(now_utc: datetime | None = None) -> list[dict[str, Any]]:
    """Student timetable. The CN lab deliberately overlaps the Nimbus assessment."""
    assessment = assessment_slot().astimezone(timezone.utc).replace(tzinfo=None)
    now = now_utc or datetime.utcnow()
    return [
        {"title": "21CSC303J Computer Networks: Lab (TP 703)", "start_time": assessment,
         "end_time": assessment + timedelta(hours=2), "organizer": "timetable@srmist.edu.in"},
        {"title": "Mini project meeting with guide", "start_time": now + timedelta(days=1, hours=3),
         "end_time": now + timedelta(days=1, hours=4), "organizer": "rajesh.v@srmist.edu.in"},
        {"title": "21CSC304J Compiler Design: Lecture", "start_time": now + timedelta(hours=2),
         "end_time": now + timedelta(hours=3), "organizer": "timetable@srmist.edu.in"},
    ]


def tasks() -> list[dict[str, Any]]:
    now = datetime.utcnow()
    return [
        {"id": "gtask-1", "title": "Submit DBMS lab record", "status": "needsAction",
         "due": (now + timedelta(days=1)).isoformat() + "Z"},
        {"id": "gtask-2", "title": "Pay odd semester fee", "status": "needsAction",
         "due": (now + timedelta(days=4)).isoformat() + "Z"},
    ]
