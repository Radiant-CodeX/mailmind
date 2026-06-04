from datetime import datetime, timedelta
from app.services.db import db

def check_calendar_conflict(target_time_iso: str, duration_minutes: int = 60) -> dict:
    """
    Checks if a target time conflicts with any calendar events.
    """
    try:
        # Support both YYYY-MM-DDTHH:MM:SS and simple date strings
        t_start = datetime.fromisoformat(target_time_iso.replace("Z", ""))
        t_end = t_start + timedelta(minutes=duration_minutes)
    except Exception:
        # Default fallback for simple dates (e.g. check standard working hours overlap)
        return {"conflict": False, "reason": "Could not parse ISO timestamp."}

    for event in db.get_calendar_events():
        try:
            e_start = datetime.fromisoformat(event["start"])
            e_end = datetime.fromisoformat(event["end"])
            
            # Check overlap: (StartA < EndB) and (EndA > StartB)
            if (t_start < e_end) and (t_end > e_start):
                return {
                    "conflict": True,
                    "event_title": event["title"],
                    "start": event["start"],
                    "end": event["end"],
                    "explanation": f"Conflict detected with '{event['title']}' ({e_start.strftime('%H:%M')} - {e_end.strftime('%H:%M')})"
                }
        except Exception:
            continue
            
    return {"conflict": False}
