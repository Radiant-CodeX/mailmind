import datetime
import sys

import httpx

BASE = "http://127.0.0.1:8000/api"

def safe_print(name, resp):
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    print(f"\n== {name} ==\nstatus: {resp.status_code}\nbody: {body}")


def main():
    try:
        with httpx.Client(timeout=10.0) as c:
            r = c.get(f"{BASE}/health")
            safe_print("health", r)

            r = c.post(f"{BASE}/classify", json={"email_text": "Urgent: please review the contract"})
            safe_print("classify", r)

            r = c.post(f"{BASE}/rag/retrieve", json={"email_text": "Please send the monthly report and related precedents"})
            safe_print("rag_retrieve", r)

            payload = {
                "email_id": "smoke-1",
                "sender": "tester@example.com",
                "subject": "Smoke test",
                "body": "Hello from smoke test",
                "received_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            r = c.post(f"{BASE}/ingest", json=payload)
            safe_print("ingest", r)

            extract_payload = {"masked_email_text": "Please review by 2026-06-10 and approve", "thread_summary": ""}
            r = c.post(f"{BASE}/commitments/extract", json=extract_payload)
            safe_print("commitments_extract", r)

            commitments = r.json().get("commitments") if r.status_code == 200 else None
            if not commitments:
                commitments = [{
                    "id": "c1",
                    "commitment": "Please review and approve",
                    "deadline": None,
                    "confidence": 0.9,
                    "approved": True,
                }]

            confirm_payload = {"email_id": "smoke-1", "commitments": commitments}
            headers = {"X-Approval-Token": "secret-approval-token"}
            r = c.post(f"{BASE}/commitments/confirm", json=confirm_payload, headers=headers)
            safe_print("commitments_confirm", r)

    except Exception as e:
        print("Exception during smoke tests:", e)
        sys.exit(2)

if __name__ == '__main__':
    main()
