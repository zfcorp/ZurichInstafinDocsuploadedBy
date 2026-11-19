from datetime import datetime
import requests

BASE_URL = "https://zurichtraining.instafin.info/submit/"
HEADERS = [
    "clientID", "accountID", "ID", "isActive", "fileID",
    "fileName", "uploadedAt", "UploadTime", "uploadedByUser", "uploadedByUserName"
]


def api_post(session, endpoint, body):
    response = session.post(BASE_URL + endpoint, json=body, timeout=(8, 45), allow_redirects=False)
    if response.status_code != 200:
        raise RuntimeError(f"{endpoint} returned HTTP {response.status_code}.")
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"{endpoint} returned an unexpected response.")
    return data

def _account_external_id(item):
    """Account number as shown in the Instafin UI (e.g. A024633)."""
    account = item.get("account") or {}
    if not isinstance(account, dict):
        account = {}
    return str(
        item.get("accountExternalId")
        or item.get("accountExternalID")
        or account.get("externalID")
        or account.get("externalId")
        or ""
    ).strip()


def _client_external_id(item):
    """Return external client ID. Internal numeric clientId is NOT interchangeable."""
    client = item.get("client") or {}
    if not isinstance(client, dict):
        client = {}
    return str(
        item.get("clientExternalId")
        or item.get("clientExternalID")
        or client.get("externalID")
        or client.get("externalId")
        or ""
    ).strip()


def find_client_from_account(session, account_id):
    """Resolve external account number through the documented 'accounts' filter.

    The official ExportAllAccounts request example uses:
        {"filter": {"accounts": ["A000558"]}}
    Check the returned account for an exact match before selecting a client.
    """
    account_id = account_id.strip()
    body = {"filter": {"accounts": [account_id]}}

    # The Search endpoint returns accountExternalId/clientExternalId in its items.
    # ExportAllAccounts uses the same filter and may include nested client data.
    for endpoint in ("instafin.SearchAllAccounts", "instafin.ExportAllAccounts"):
        data = api_post(session, endpoint, body)
        items = data.get("items")
        if not isinstance(items, list):
            raise RuntimeError(f"{endpoint} returned no 'items' array; check API response format.")
        matches = [
            item for item in items
            if isinstance(item, dict)
            and _account_external_id(item).casefold() == account_id.casefold()
        ]
        if not matches:
            continue
        clients = {_client_external_id(x) for x in matches} - {""}
        if len(clients) == 1 and all(_client_external_id(x) for x in matches):
            return clients.pop(), account_id
        raise RuntimeError(
            f"{endpoint} found account {account_id} but did not supply "
            "one unique external Client ID. Internal clientId cannot be used "
            "as the document endpoint's clientID."
        )

    raise RuntimeError(
        f"No exact match for {account_id} in SearchAllAccounts/ExportAllAccounts. "
        "Verify the account exists in the TRAINING API and that filter.accounts "
        "returns records for your API credentials."
    )



def format_upload_time(timestamp):
    """Keep the original uploadedAt and add a readable 12-hour timestamp.

    Example: 2024-12-20T12:27:00.930+08:00 -> 20-Dec-2024 12:27 pm
    The timezone/offset from the API is preserved (no conversion).
    """
    if not timestamp:
        return ""
    try:
        date = datetime.fromisoformat(str(timestamp).strip().replace("Z", "+00:00"))
        hour = date.hour % 12 or 12
        period = "am" if date.hour < 12 else "pm"
        return f"{date:%d-%b-%Y} {hour}:{date.minute:02d} {period}"
    except (ValueError, TypeError):
        return ""


def get_documents(session, client_id, account_id=""):
    """Read client-level documents, plus account-level docs when account_id is provided."""
    filters = [{"clientID": client_id}]
    if account_id:
        filters.append({"clientID": client_id, "accountID": account_id})

    rows, seen = [], set()
    for filt in filters:
        response = api_post(session, "documentmanager.RequestDocumentRows", {"filter": filt})
        groups = response.get("result")
        if not isinstance(groups, list):
            raise RuntimeError("Document response has no 'result' array.")
        for group in groups:
            if not isinstance(group, dict):
                continue
            for doc in group.get("documents") or []:
                if not isinstance(doc, dict):
                    continue
                row_client = str(group.get("clientID") or client_id)
                row_account = str(doc.get("accountID") or group.get("accountID") or "")
                if row_client.casefold() != client_id.casefold():
                    continue
                if account_id and row_account and row_account.casefold() != account_id.casefold():
                    continue
                uploader = doc.get("uploadedByUser")
                uploader_name = doc.get("uploadedByUserName") or ""
                if isinstance(uploader, dict):
                    uploader_name = uploader_name or uploader.get("fullName") or uploader.get("name") or ""
                    uploader = uploader.get("userID") or uploader.get("ID") or ""
                row = {
                    "clientID": str(group.get("clientID") or client_id),
                    # Client-level files have accountID=null; keep those cells blank.
                    "accountID": str(doc.get("accountID") or group.get("accountID") or ""),
                    "ID": doc.get("ID") or "",
                    "isActive": doc.get("isActive"),
                    "fileID": doc.get("fileID") or "",
                    "fileName": doc.get("fileName") or "",
                    "uploadedAt": doc.get("uploadedAt") or "",
                    "UploadTime": format_upload_time(doc.get("uploadedAt")),
                    "uploadedByUser": uploader if uploader is not None else "",
                    "uploadedByUserName": uploader_name,
                }
                key = (row["clientID"], row["accountID"], row["ID"], row["fileID"])
                if not (row["ID"] or row["fileID"]) or key not in seen:
                    seen.add(key)
                    rows.append(row)
    return rows


