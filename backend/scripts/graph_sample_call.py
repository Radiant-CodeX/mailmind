import json
import os
import sys
from datetime import datetime, timedelta

# Ensure project root is on sys.path when running this script directly
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.services.graph import GraphClient  # noqa: E402

def main():
    try:
        g = GraphClient()
        # Diagnostic: list users visible to the app
        try:
            users = g._request("GET", "/users?$top=3")
            print('USERS:')
            print(json.dumps(users, indent=2, ensure_ascii=False))
        except Exception as ex:
            print('USERS_ERROR', str(ex))
        start = datetime.utcnow()
        end = start + timedelta(days=7)
        events = g.get_calendar_events(start, end)
        print('\nEVENTS:')
        print(json.dumps(events, indent=2, ensure_ascii=False))
    except Exception as e:
        print('ERROR', str(e))

if __name__ == '__main__':
    main()
