from datetime import datetime, timedelta

class MemoryDB:
    def __init__(self):
        self.tasks = [
            {
                "id": "1",
                "title": "Review Q3 goals document",
                "status": "pending",
                "due_date": (datetime.now() + timedelta(days=2)).isoformat(),
                "email_ref": "john.doe@company.com"
            }
        ]
        
        # Prepopulate calendar meetings for tomorrow to trigger conflict detections
        tomorrow = datetime.now() + timedelta(days=1)
        self.calendar_events = [
            {
                "title": "Sprint Planning Meeting",
                "start": tomorrow.replace(hour=9, minute=0, second=0, microsecond=0).isoformat(),
                "end": tomorrow.replace(hour=10, minute=30, second=0, microsecond=0).isoformat()
            },
            {
                "title": "Project Skynet Core Architecture Review",
                "start": tomorrow.replace(hour=14, minute=0, second=0, microsecond=0).isoformat(),
                "end": tomorrow.replace(hour=15, minute=30, second=0, microsecond=0).isoformat()
            }
        ]
        
    def get_tasks(self):
        return self.tasks
        
    def add_task(self, task):
        self.tasks.append(task)
        return task
        
    def sync_all_tasks(self):
        for task in self.tasks:
            task["status"] = "synced"
        return self.tasks
        
    def get_calendar_events(self):
        return self.calendar_events

db = MemoryDB()
