import requests
import msal
from app.config import CLIENT_ID, TENANT_ID, GRAPH_SCOPE


def get_graph_token():
    if not CLIENT_ID:
        raise Exception("CLIENT_ID missing in .env file.")

    app_graph = msal.PublicClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    )

    flow = app_graph.initiate_device_flow(scopes=GRAPH_SCOPE)

    if "user_code" not in flow:
        raise Exception("Failed to initiate device code flow.")

    print("\n========== MICROSOFT GRAPH LOGIN ==========")
    print(flow["message"])
    print("==========================================\n", flush=True)

    result = app_graph.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        raise Exception(result.get("error_description", "Failed to obtain Graph token"))

    return result["access_token"]


def fetch_outlook_emails():
    token = get_graph_token()

    headers = {"Authorization": f"Bearer {token}"}
    url = "https://graph.microsoft.com/v1.0/me/messages?$top=10"

    response = requests.get(url, headers=headers)

    return {
        "status_code": response.status_code,
        "raw_response": response.text,
    }