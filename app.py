import base64
import hmac
import io
import json
import os

import requests
import xlsxwriter

from instafin import HEADERS, find_client_from_account, get_documents


def excel(rows):
    output = io.BytesIO()
    options = {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False}
    with xlsxwriter.Workbook(output, options) as book:
        sheet = book.add_worksheet("Documents")
        header = book.add_format({"bold": True, "bg_color": "#17365D", "font_color": "white"})
        sheet.write_row(0, 0, HEADERS, header)
        for i, row in enumerate(rows, 1):
            sheet.write_row(i, 0, [row[k] for k in HEADERS])
        sheet.freeze_panes(1, 2)
        sheet.autofilter(0, 0, len(rows), len(HEADERS) - 1)
        for i, width in enumerate([18, 18, 39, 12, 39, 38, 34, 26, 28, 28]):
            sheet.set_column(i, i, width)
    return base64.b64encode(output.getvalue()).decode()


def app(env, start_response):
    origin = os.environ.get("PAGES_ORIGIN", "").rstrip("/")
    headers = [("Content-Type", "application/json"), ("Cache-Control", "no-store"), ("Vary", "Origin")]

    def reply(status, value):
        start_response(status, headers)
        return [json.dumps(value).encode()]

    if env["PATH_INFO"] != "/lookup":
        return reply("404 Not Found", {"error": "Unknown endpoint."})
    if not origin or env.get("HTTP_ORIGIN") != origin:
        return reply("403 Forbidden", {"error": "Pages origin is not configured for this service."})
    headers.extend([("Access-Control-Allow-Origin", origin),
                    ("Access-Control-Allow-Headers", "Authorization, Content-Type"),
                    ("Access-Control-Allow-Methods", "POST, OPTIONS")])
    if env["REQUEST_METHOD"] == "OPTIONS":
        return reply("200 OK", {})
    if env["REQUEST_METHOD"] != "POST":
        return reply("405 Method Not Allowed", {"error": "POST required."})
    token = os.environ.get("APP_ACCESS_KEY", "")
    auth = env.get("HTTP_AUTHORIZATION", "")
    if not token or not hmac.compare_digest(auth.encode(), ("Bearer " + token).encode()):
        return reply("401 Unauthorized", {"error": "Check the report access key."})
    try:
        size = int(env.get("CONTENT_LENGTH") or 0)
        if not 0 < size <= 4096:
            raise ValueError()
        data = json.loads(env["wsgi.input"].read(size))
        client, account = [data.get(k, "").strip() for k in ("clientID", "accountID")]
        if not (client or account) or max(len(client), len(account)) > 128:
            raise ValueError()
    except (ValueError, AttributeError, TypeError):
        return reply("400 Bad Request", {"error": "Enter a valid external client ID or account ID."})
    try:
        with requests.Session() as session:
            session.auth = (os.environ["INSTAFIN_USERNAME"], os.environ["INSTAFIN_PASSWORD"])
            if account:
                owner, account = find_client_from_account(session, account)
                if client and client.casefold() != owner.casefold():
                    return reply("400 Bad Request", {"error": "The account belongs to a different client."})
                client = owner
            rows = get_documents(session, client, account)
        return reply("200 OK", {"rows": rows, "client": client, "workbook": excel(rows)})
    except KeyError:
        return reply("500 Internal Server Error", {"error": "Check the API service configuration."})
    except RuntimeError as error:
        return reply("422 Unprocessable Entity", {"error": str(error)})
    except (requests.RequestException, ValueError):
        return reply("502 Bad Gateway", {"error": "Instafin was unreachable or returned unreadable data."})
