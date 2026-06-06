from fastapi import APIRouter

from services.graph_service import fetch_outlook_emails, get_graph_token

router = APIRouter(prefix="/graph")


@router.get("/test")
def graph_test():
    token = get_graph_token()
    return {"token_received": token[:20]}


@router.get("/emails")
def graph_emails():
    try:
        data = fetch_outlook_emails()

        return {
            "status": "success",
            "graph_response": data,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }