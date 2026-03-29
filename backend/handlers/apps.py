"""App integration node handlers.

Covers: Slack, Telegram, Discord, Gmail, Notion, Airtable, Google Sheets,
GitHub, Jira, HubSpot, Stripe, Supabase, Twilio, SendGrid.

All use requests + environment variable credentials.
"""

from __future__ import annotations

import re

from backend.core.ir import IRNode, IRNodeKind
from backend.handlers.base import GenerationContext
from backend.handlers.registry import register
from backend.models.workflow import N8nNode


def _safe_var(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower())
    s = re.sub(r"_+", "_", s).strip("_") or "node"
    return f"n_{s}" if s[0].isdigit() else s


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.slack")
class SlackHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        resource = str(params.get("resource", "message")).lower()
        operation = str(params.get("operation", "post")).lower()

        if resource == "message" and operation in ("post", "send"):
            channel = ctx.resolve_expr(str(params.get("channel", "")))
            text = ctx.resolve_expr(str(params.get("text", "")))
            code_lines = [
                f"import requests, os",
                f"_slack_token = os.environ.get('SLACK_BOT_TOKEN', '')",
                f"_slack_resp = requests.post(",
                f'    "https://slack.com/api/chat.postMessage",',
                f"    json={{",
                f"        'channel': {channel},",
                f"        'text': {text},",
                f"    }},",
                f"    headers={{'Authorization': f'Bearer {{_slack_token}}'}},",
                f")",
                f"{var}_output = [{{'json': _slack_resp.json()}}]",
            ]
        else:
            code_lines = [
                f"# Slack ({resource}/{operation}): TODO implement",
                f"import requests, os",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import requests", "import os"],
            pip_packages=["requests"],
            code_lines=code_lines,
            comment=f"Slack ({resource}/{operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.slack"]

    def required_packages(self) -> list[str]:
        return ["requests"]


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.telegram")
class TelegramHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        resource = str(params.get("resource", "message")).lower()
        operation = str(params.get("operation", "sendMessage")).lower()

        chat_id = ctx.resolve_expr(str(params.get("chatId", "")))
        text = ctx.resolve_expr(str(params.get("text", "")))

        code_lines = [
            f"import requests, os",
            f"_tg_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')",
            f"_tg_resp = requests.post(",
            f'    f"https://api.telegram.org/bot{{_tg_token}}/sendMessage",',
            f"    json={{",
            f"        'chat_id': {chat_id},",
            f"        'text': {text},",
            f"    }},",
            f")",
            f"{var}_output = [{{'json': _tg_resp.json()}}]",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import requests", "import os"],
            pip_packages=["requests"],
            code_lines=code_lines,
            comment=f"Telegram ({resource}/{operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.telegram"]

    def required_packages(self) -> list[str]:
        return ["requests"]


# ---------------------------------------------------------------------------
# Discord
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.discord")
class DiscordHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        operation = str(params.get("operation", "sendMessage")).lower()

        if operation == "sendmessage":
            webhook_url = ctx.resolve_expr(
                str(params.get("webhookUri", params.get("webhookUrl", "")))
            )
            text = ctx.resolve_expr(str(params.get("text", params.get("content", ""))))
            code_lines = [
                f"import requests",
                f"_disc_resp = requests.post(",
                f"    {webhook_url},",
                f"    json={{'content': {text}}},",
                f")",
                f"{var}_output = [{{'json': {{'success': _disc_resp.status_code < 300}}}}]",
            ]
        else:
            code_lines = [
                f"# Discord ({operation}): TODO implement",
                f"import requests",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import requests"],
            pip_packages=["requests"],
            code_lines=code_lines,
            comment=f"Discord ({operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.discord"]

    def required_packages(self) -> list[str]:
        return ["requests"]


# ---------------------------------------------------------------------------
# Gmail
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.gmail")
class GmailHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        operation = str(params.get("operation", "send")).lower()

        if operation in ("send", "sendemail"):
            to_addr = ctx.resolve_expr(
                str(params.get("toList", params.get("sendTo", "")))
            )
            subject = ctx.resolve_expr(str(params.get("subject", "")))
            body = ctx.resolve_expr(
                str(params.get("message", params.get("emailType", "")))
            )
            code_lines = [
                f"import smtplib",
                f"import os",
                f"from email.mime.text import MIMEText",
                f"_gmail_user = os.environ.get('GMAIL_ADDRESS', '')",
                f"_gmail_pass = os.environ.get('GMAIL_APP_PASSWORD', '')",
                f"_msg = MIMEText({body})",
                f"_msg['Subject'] = {subject}",
                f"_msg['From'] = _gmail_user",
                f"_msg['To'] = {to_addr}",
                f"with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:",
                f"    smtp.login(_gmail_user, _gmail_pass)",
                f"    smtp.send_message(_msg)",
                f"{var}_output = [{{'json': {{'success': True}}}}]",
            ]
        else:
            code_lines = [
                f"# Gmail ({operation}): TODO implement",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import smtplib", "import os"],
            code_lines=code_lines,
            comment=f"Gmail ({operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.gmail"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Notion
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.notion", "n8n-nodes-base.notionV2")
class NotionHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        resource = str(params.get("resource", "page")).lower()
        operation = str(params.get("operation", "get")).lower()

        code_lines = [
            f"import requests, os",
            f"_notion_key = os.environ.get('NOTION_API_KEY', '')",
            f"_notion_headers = {{'Authorization': f'Bearer {{_notion_key}}', 'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'}}",
        ]

        if resource == "page" and operation == "get":
            page_id = ctx.resolve_expr(str(params.get("pageId", "")))
            code_lines += [
                f'_notion_resp = requests.get(f\'https://api.notion.com/v1/pages/{{str({page_id}).replace("-", ""[0:])}}\', headers=_notion_headers)',
                f"{var}_output = [{{'json': _notion_resp.json()}}]",
            ]
        elif resource == "database" and operation in ("getall", "query"):
            db_id = ctx.resolve_expr(str(params.get("databaseId", "")))
            code_lines += [
                f"_notion_resp = requests.post(f'https://api.notion.com/v1/databases/{{str({db_id})}}' + '/query', headers=_notion_headers, json={{}})",
                f"_notion_data = _notion_resp.json()",
                f"{var}_output = [{{'json': item}} for item in _notion_data.get('results', [])]",
            ]
        elif resource == "page" and operation == "create":
            db_id = ctx.resolve_expr(str(params.get("databaseId", "")))
            code_lines += [
                f"# Create Notion page",
                f"_notion_payload = {{'parent': {{'database_id': {db_id}}}, 'properties': {{}}}}",
                f"# TODO: populate properties from {prev_var}[0]['json']",
                f"_notion_resp = requests.post('https://api.notion.com/v1/pages', headers=_notion_headers, json=_notion_payload)",
                f"{var}_output = [{{'json': _notion_resp.json()}}]",
            ]
        else:
            code_lines += [
                f"# Notion ({resource}/{operation}): TODO implement",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import requests", "import os"],
            pip_packages=["requests"],
            code_lines=code_lines,
            comment=f"Notion ({resource}/{operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.notion"]

    def required_packages(self) -> list[str]:
        return ["requests"]


# ---------------------------------------------------------------------------
# Airtable
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.airtable")
class AirtableHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        operation = str(params.get("operation", "list")).lower()
        table_id = ctx.resolve_expr(str(params.get("table", params.get("tableId", ""))))
        base_id = ctx.resolve_expr(str(params.get("base", params.get("baseId", ""))))

        code_lines = [
            f"import requests, os",
            f"_at_key = os.environ.get('AIRTABLE_API_KEY', '')",
            f"_at_headers = {{'Authorization': f'Bearer {{_at_key}}'}}",
            f"_at_base = {base_id}",
            f"_at_table = {table_id}",
        ]

        if operation == "list":
            code_lines += [
                f"_at_resp = requests.get(f'https://api.airtable.com/v0/{{_at_base}}/{{_at_table}}', headers=_at_headers)",
                f"{var}_output = [{{'json': {{**r.get('fields', {{}}), 'id': r['id']}}}} for r in _at_resp.json().get('records', [])]",
            ]
        elif operation == "create":
            code_lines += [
                f"_at_records = [{{'fields': item.get('json', {{}})}} for item in {prev_var}]",
                f"_at_resp = requests.post(f'https://api.airtable.com/v0/{{_at_base}}/{{_at_table}}', headers={{**_at_headers, 'Content-Type': 'application/json'}}, json={{'records': _at_records}})",
                f"{var}_output = [{{'json': {{**r.get('fields', {{}}), 'id': r['id']}}}} for r in _at_resp.json().get('records', [])]",
            ]
        elif operation in ("update", "upsert"):
            code_lines += [
                f"_at_results = []",
                f"for _item in {prev_var}:",
                f"    _rec_id = _item.get('json', {{}}).get('id', '')",
                f"    _fields = {{k: v for k, v in _item.get('json', {{}}).items() if k != 'id'}}",
                f"    if _rec_id:",
                f"        _at_resp = requests.patch(f'https://api.airtable.com/v0/{{_at_base}}/{{_at_table}}/{{_rec_id}}', headers={{**_at_headers, 'Content-Type': 'application/json'}}, json={{'fields': _fields}})",
                f"        _at_results.append({{'json': _at_resp.json()}})",
                f"{var}_output = _at_results or {prev_var}",
            ]
        elif operation == "delete":
            code_lines += [
                f"_at_results = []",
                f"for _item in {prev_var}:",
                f"    _rec_id = _item.get('json', {{}}).get('id', '')",
                f"    if _rec_id:",
                f"        requests.delete(f'https://api.airtable.com/v0/{{_at_base}}/{{_at_table}}/{{_rec_id}}', headers=_at_headers)",
                f"        _at_results.append({{'json': {{'deleted': True, 'id': _rec_id}}}})",
                f"{var}_output = _at_results or {prev_var}",
            ]
        else:
            code_lines += [
                f"# Airtable ({operation}): pass-through",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import requests", "import os"],
            pip_packages=["requests"],
            code_lines=code_lines,
            comment=f"Airtable ({operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.airtable"]

    def required_packages(self) -> list[str]:
        return ["requests"]


# ---------------------------------------------------------------------------
# Google Sheets
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.googleSheets")
class GoogleSheetsHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        operation = str(params.get("operation", "read")).lower()
        sheet_id = ctx.resolve_expr(
            str(params.get("documentId", params.get("spreadsheetId", "")))
        )
        range_val = ctx.resolve_expr(str(params.get("range", "Sheet1!A:Z")))

        code_lines = [
            f"# Google Sheets — uses google-api-python-client",
            f"import os",
            f"from googleapiclient.discovery import build",
            f"from google.oauth2 import service_account",
            f"_gs_creds_path = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON', '')",
            f"_gs_creds = service_account.Credentials.from_service_account_file(",
            f"    _gs_creds_path,",
            f"    scopes=['https://www.googleapis.com/auth/spreadsheets'],",
            f")",
            f"_gs_service = build('sheets', 'v4', credentials=_gs_creds)",
            f"_gs_sheets = _gs_service.spreadsheets()",
        ]

        if operation in ("read", "getall", "readsheet"):
            code_lines += [
                f"_gs_result = _gs_sheets.values().get(spreadsheetId={sheet_id}, range={range_val}).execute()",
                f"_gs_values = _gs_result.get('values', [])",
                f"_gs_headers = _gs_values[0] if _gs_values else []",
                f"{var}_output = [{{'json': dict(zip(_gs_headers, row))}} for row in _gs_values[1:]]",
            ]
        elif operation in ("append", "appendorUpdate"):
            code_lines += [
                f"_gs_rows = [list(item.get('json', {{}}).values()) for item in {prev_var}]",
                f"_gs_sheets.values().append(",
                f"    spreadsheetId={sheet_id},",
                f"    range={range_val},",
                f"    valueInputOption='USER_ENTERED',",
                f"    body={{'values': _gs_rows}},",
                f").execute()",
                f"{var}_output = {prev_var}",
            ]
        else:
            code_lines += [
                f"# Google Sheets ({operation}): TODO implement",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            pip_packages=["google-api-python-client", "google-auth"],
            code_lines=code_lines,
            comment=f"Google Sheets ({operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.googleSheets"]

    def required_packages(self) -> list[str]:
        return ["google-api-python-client", "google-auth"]


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.github")
class GitHubHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        resource = str(params.get("resource", "issue")).lower()
        operation = str(params.get("operation", "get")).lower()
        owner = ctx.resolve_expr(str(params.get("owner", "")))
        repo = ctx.resolve_expr(str(params.get("repository", params.get("repo", ""))))

        code_lines = [
            f"import requests, os",
            f"_gh_token = os.environ.get('GITHUB_TOKEN', '')",
            f"_gh_headers = {{'Authorization': f'token {{_gh_token}}', 'Accept': 'application/vnd.github.v3+json'}}",
        ]

        if resource == "issue" and operation == "get":
            issue_num = ctx.resolve_expr(str(params.get("issueNumber", "")))
            code_lines += [
                f"_gh_resp = requests.get(f'https://api.github.com/repos/{{{owner}}}/{{{repo}}}/issues/{{{issue_num}}}', headers=_gh_headers)",
                f"{var}_output = [{{'json': _gh_resp.json()}}]",
            ]
        elif resource == "issue" and operation in ("create", "post"):
            title = ctx.resolve_expr(str(params.get("title", "")))
            body = ctx.resolve_expr(str(params.get("body", "")))
            code_lines += [
                f"_gh_resp = requests.post(f'https://api.github.com/repos/{{{owner}}}/{{{repo}}}/issues', headers={{**_gh_headers, 'Content-Type': 'application/json'}}, json={{'title': {title}, 'body': {body}}})",
                f"{var}_output = [{{'json': _gh_resp.json()}}]",
            ]
        else:
            code_lines += [
                f"# GitHub ({resource}/{operation}): TODO implement",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import requests", "import os"],
            pip_packages=["requests"],
            code_lines=code_lines,
            comment=f"GitHub ({resource}/{operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.github"]

    def required_packages(self) -> list[str]:
        return ["requests"]


# ---------------------------------------------------------------------------
# Stripe
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.stripe")
class StripeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        resource = str(params.get("resource", "charge")).lower()
        operation = str(params.get("operation", "get")).lower()

        code_lines = [
            f"import stripe, os",
            f"stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')",
        ]

        if resource == "customer" and operation in ("get", "retrieve"):
            cid = ctx.resolve_expr(str(params.get("customerId", "")))
            code_lines += [
                f"_stripe_cust = stripe.Customer.retrieve({cid})",
                f"{var}_output = [{{'json': dict(_stripe_cust)}}]",
            ]
        elif resource == "customer" and operation == "create":
            email = ctx.resolve_expr(str(params.get("email", "")))
            code_lines += [
                f"_stripe_cust = stripe.Customer.create(email={email})",
                f"{var}_output = [{{'json': dict(_stripe_cust)}}]",
            ]
        else:
            code_lines += [
                f"# Stripe ({resource}/{operation}): TODO implement",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import stripe", "import os"],
            pip_packages=["stripe"],
            code_lines=code_lines,
            comment=f"Stripe ({resource}/{operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.stripe"]

    def required_packages(self) -> list[str]:
        return ["stripe"]


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.supabase")
class SupabaseHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        operation = str(params.get("operation", "select")).lower()
        table = str(params.get("tableId", ""))

        code_lines = [
            f"from supabase import create_client, Client",
            f"import os",
            f"_sb_url = os.environ.get('SUPABASE_URL', '')",
            f"_sb_key = os.environ.get('SUPABASE_ANON_KEY', '')",
            f"_sb: Client = create_client(_sb_url, _sb_key)",
        ]

        if operation == "select":
            columns = str(params.get("fields", "*"))
            code_lines += [
                f"_sb_data = _sb.table('{table}').select('{columns}').execute()",
                f"{var}_output = [{{'json': row}} for row in _sb_data.data]",
            ]
        elif operation in ("insert", "upsert"):
            code_lines += [
                f"_sb_records = [item.get('json', {{}}) for item in {prev_var}]",
                f"_sb_data = _sb.table('{table}').insert(_sb_records).execute()",
                f"{var}_output = [{{'json': row}} for row in _sb_data.data]",
            ]
        elif operation == "update":
            code_lines += [
                f"# Supabase update: TODO implement filter",
                f"{var}_output = {prev_var}",
            ]
        elif operation == "delete":
            code_lines += [
                f"# Supabase delete: TODO implement filter",
                f"{var}_output = {prev_var}",
            ]
        else:
            code_lines += [f"{var}_output = {prev_var}"]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            pip_packages=["supabase"],
            code_lines=code_lines,
            comment=f"Supabase ({operation}) on {table!r}",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.supabase"]

    def required_packages(self) -> list[str]:
        return ["supabase"]


# ---------------------------------------------------------------------------
# HubSpot
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.hubspot")
class HubSpotHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        resource = str(params.get("resource", "contact")).lower()
        operation = str(params.get("operation", "get")).lower()

        code_lines = [
            f"import requests, os",
            f"_hs_key = os.environ.get('HUBSPOT_API_KEY', '')",
            f"_hs_headers = {{'Authorization': f'Bearer {{_hs_key}}'}}",
        ]

        if resource == "contact" and operation in ("get", "getall"):
            code_lines += [
                f"_hs_resp = requests.get('https://api.hubapi.com/crm/v3/objects/contacts', headers=_hs_headers)",
                f"{var}_output = [{{'json': c}} for c in _hs_resp.json().get('results', [])]",
            ]
        else:
            code_lines += [
                f"# HubSpot ({resource}/{operation}): TODO implement",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import requests", "import os"],
            pip_packages=["requests"],
            code_lines=code_lines,
            comment=f"HubSpot ({resource}/{operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.hubspot"]

    def required_packages(self) -> list[str]:
        return ["requests"]


# ---------------------------------------------------------------------------
# Jira
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.jira")
class JiraHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        resource = str(params.get("resource", "issue")).lower()
        operation = str(params.get("operation", "get")).lower()

        code_lines = [
            f"import requests, os",
            f"_jira_url = os.environ.get('JIRA_BASE_URL', '')",
            f"_jira_user = os.environ.get('JIRA_EMAIL', '')",
            f"_jira_token = os.environ.get('JIRA_API_TOKEN', '')",
            f"_jira_auth = (_jira_user, _jira_token)",
        ]

        if resource == "issue" and operation == "get":
            issue_key = ctx.resolve_expr(str(params.get("issueKey", "")))
            code_lines += [
                f"_jira_resp = requests.get(f'{{_jira_url}}/rest/api/3/issue/{{{issue_key}}}', auth=_jira_auth)",
                f"{var}_output = [{{'json': _jira_resp.json()}}]",
            ]
        elif resource == "issue" and operation == "create":
            project = ctx.resolve_expr(str(params.get("project", "")))
            summary = ctx.resolve_expr(str(params.get("summary", "")))
            issue_type = str(params.get("issueType", "Task"))
            code_lines += [
                f"_jira_payload = {{",
                f"    'fields': {{",
                f"        'project': {{'key': {project}}},",
                f"        'summary': {summary},",
                f"        'issuetype': {{'name': '{issue_type}'}},",
                f"    }}",
                f"}}",
                f"_jira_resp = requests.post(f'{{_jira_url}}/rest/api/3/issue', auth=_jira_auth, json=_jira_payload)",
                f"{var}_output = [{{'json': _jira_resp.json()}}]",
            ]
        else:
            code_lines += [
                f"# Jira ({resource}/{operation}): TODO implement",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import requests", "import os"],
            pip_packages=["requests"],
            code_lines=code_lines,
            comment=f"Jira ({resource}/{operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.jira"]

    def required_packages(self) -> list[str]:
        return ["requests"]


# ---------------------------------------------------------------------------
# Sticky Note (annotation only — generates no executable code)
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.stickyNote", "n8n-nodes-base.stickynote")
class StickyNoteHandler:
    """Sticky notes are visual annotations; they emit only a comment."""

    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        import re as _re

        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        content = str(node.parameters.get("content", "")).replace("\n", " ")
        content_short = content[:80] + ("..." if len(content) > 80 else "")
        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=[
                f"# Sticky Note: {node.name!r} — {content_short!r}",
                f"{var}_output = {prev_var}",
            ],
            comment="Sticky note (annotation)",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.stickyNote"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Send Email (SMTP)
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.emailSend", "n8n-nodes-base.send_email")
class EmailSendHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        to_email = ctx.resolve_expr(str(params.get("toEmail", params.get("to", ""))))
        subject = ctx.resolve_expr(str(params.get("subject", "")))
        body = ctx.resolve_expr(str(params.get("message", params.get("text", ""))))
        from_email = ctx.resolve_expr(
            str(params.get("fromEmail", params.get("from", "")))
        )

        code_lines = [
            f"import smtplib, os",
            f"from email.mime.text import MIMEText",
            f"from email.mime.multipart import MIMEMultipart",
            f"_smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')",
            f"_smtp_port = int(os.environ.get('SMTP_PORT', '587'))",
            f"_smtp_user = os.environ.get('SMTP_USER', '')",
            f"_smtp_pass = os.environ.get('SMTP_PASSWORD', '')",
            f"_email_msg = MIMEMultipart()",
            f"_email_msg['From'] = {from_email} or _smtp_user",
            f"_email_msg['To'] = {to_email}",
            f"_email_msg['Subject'] = {subject}",
            f"_email_msg.attach(MIMEText({body}, 'plain'))",
            f"try:",
            f"    with smtplib.SMTP(_smtp_host, _smtp_port) as _smtp:",
            f"        _smtp.starttls()",
            f"        _smtp.login(_smtp_user, _smtp_pass)",
            f"        _smtp.send_message(_email_msg)",
            f"    {var}_output = [{{"
            + "'json': {'success': True, 'to': "
            + f"{to_email}"
            + ", 'subject': "
            + f"{subject}"
            + "}"
            + "}]",
            f"except Exception as _e:",
            f"    {var}_output = [{{"
            + "'json': {'success': False, 'error': str(_e)}"
            + "}]",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import smtplib", "import os"],
            pip_packages=[],
            code_lines=code_lines,
            comment="Send Email (SMTP)",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.emailSend"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# RSS Feed Read
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.rssFeedRead", "n8n-nodes-base.rss")
class RssFeedHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        url = ctx.resolve_expr(str(params.get("url", "")))
        limit = int(params.get("limit", 100))

        code_lines = [
            f"import feedparser",
            f"_rss_feed = feedparser.parse({url})",
            f"{var}_output = [",
            f"    {{'json': {{'title': e.get('title', ''), 'link': e.get('link', ''), 'summary': e.get('summary', ''), 'published': e.get('published', '')}}}}",
            f"    for e in _rss_feed.entries[:{limit}]",
            f"]",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=[],
            pip_packages=["feedparser"],
            code_lines=code_lines,
            comment="RSS Feed Read",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.rssFeedRead"]

    def required_packages(self) -> list[str]:
        return ["feedparser"]


# ---------------------------------------------------------------------------
# Typeform
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.typeform")
class TypeformHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        form_id = ctx.resolve_expr(str(params.get("formId", "")))
        code_lines = [
            f"import requests, os",
            f"_tf_token = os.environ.get('TYPEFORM_API_KEY', '')",
            f"_tf_resp = requests.get(",
            f"    f'https://api.typeform.com/forms/{{form_id}}/responses',",
            f"    headers={{'Authorization': f'Bearer {{_tf_token}}'}}",
            f").json()",
            f"{var}_output = [{{'json': item}} for item in _tf_resp.get('items', [])]",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import requests", "import os"],
            pip_packages=["requests"],
            code_lines=code_lines,
            comment="Typeform",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.typeform"]

    def required_packages(self) -> list[str]:
        return ["requests"]


# ---------------------------------------------------------------------------
# Pipedrive
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.pipedrive")
class PipedriveHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        resource = str(params.get("resource", "deal")).lower()
        operation = str(params.get("operation", "getAll")).lower()

        code_lines = [
            f"import requests, os",
            f"_pd_token = os.environ.get('PIPEDRIVE_API_TOKEN', '')",
            f"_pd_base = 'https://api.pipedrive.com/v1'",
        ]

        if resource == "deal" and "getall" in operation:
            code_lines += [
                f"_pd_resp = requests.get(f'{{_pd_base}}/deals', params={{'api_token': _pd_token}}).json()",
                f"{var}_output = [{{'json': d}} for d in _pd_resp.get('data', []) or []]",
            ]
        elif resource == "person" and "getall" in operation:
            code_lines += [
                f"_pd_resp = requests.get(f'{{_pd_base}}/persons', params={{'api_token': _pd_token}}).json()",
                f"{var}_output = [{{'json': p}} for p in _pd_resp.get('data', []) or []]",
            ]
        else:
            code_lines += [
                f"# Pipedrive {resource}/{operation}: TODO implement",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import requests", "import os"],
            pip_packages=["requests"],
            code_lines=code_lines,
            comment=f"Pipedrive ({resource}/{operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.pipedrive"]

    def required_packages(self) -> list[str]:
        return ["requests"]


# ---------------------------------------------------------------------------
# Zendesk
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.zendesk")
class ZendeskHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        resource = str(params.get("resource", "ticket")).lower()
        operation = str(params.get("operation", "getAll")).lower()

        code_lines = [
            f"import requests, os",
            f"_zd_subdomain = os.environ.get('ZENDESK_SUBDOMAIN', '')",
            f"_zd_email = os.environ.get('ZENDESK_EMAIL', '')",
            f"_zd_token = os.environ.get('ZENDESK_API_TOKEN', '')",
            f"_zd_auth = (_zd_email + '/token', _zd_token)",
            f"_zd_base = f'https://{{_zd_subdomain}}.zendesk.com/api/v2'",
        ]

        if resource == "ticket" and "getall" in operation:
            code_lines += [
                f"_zd_resp = requests.get(f'{{_zd_base}}/tickets.json', auth=_zd_auth).json()",
                f"{var}_output = [{{'json': t}} for t in _zd_resp.get('tickets', [])]",
            ]
        else:
            code_lines += [
                f"# Zendesk {resource}/{operation}: TODO implement",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import requests", "import os"],
            pip_packages=["requests"],
            code_lines=code_lines,
            comment=f"Zendesk ({resource}/{operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.zendesk"]

    def required_packages(self) -> list[str]:
        return ["requests"]


# ---------------------------------------------------------------------------
# Twitter / X
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.twitter", "n8n-nodes-base.x")
class TwitterHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        resource = str(params.get("resource", "tweet")).lower()
        operation = str(params.get("operation", "create")).lower()

        code_lines = [
            f"import requests, os",
            f"_tw_bearer = os.environ.get('TWITTER_BEARER_TOKEN', '')",
            f"_tw_headers = {{'Authorization': f'Bearer {{_tw_bearer}}'}}",
        ]

        if resource == "tweet" and operation == "create":
            text = ctx.resolve_expr(str(params.get("text", "")))
            code_lines += [
                f"_tw_resp = requests.post(",
                f"    'https://api.twitter.com/2/tweets',",
                f"    headers={{**_tw_headers, 'Content-Type': 'application/json'}},",
                f"    json={{'text': {text}}}",
                f").json()",
                f"{var}_output = [{{'json': _tw_resp.get('data', _tw_resp)}}]",
            ]
        elif resource == "tweet" and "search" in operation:
            query = ctx.resolve_expr(str(params.get("searchTerm", "")))
            code_lines += [
                f"_tw_resp = requests.get(",
                f"    'https://api.twitter.com/2/tweets/search/recent',",
                f"    headers=_tw_headers,",
                f"    params={{'query': {query}, 'max_results': 10}}",
                f").json()",
                f"{var}_output = [{{'json': t}} for t in _tw_resp.get('data', [])]",
            ]
        else:
            code_lines += [f"{var}_output = {prev_var}"]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import requests", "import os"],
            pip_packages=["requests"],
            code_lines=code_lines,
            comment=f"Twitter ({resource}/{operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.twitter"]

    def required_packages(self) -> list[str]:
        return ["requests"]
