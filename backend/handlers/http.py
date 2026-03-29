"""HTTP Request node handler."""

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


@register(
    "n8n-nodes-base.httpRequest",
    "n8n-nodes-base.httpRequestV4",
)
class HttpRequestHandler:
    """Handles n8n HTTP Request nodes for all HTTP methods and auth types."""

    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        ctx.register_node_var(node.name, var)
        params = node.parameters

        method = str(params.get("method", "GET")).upper()
        url_raw = params.get("url", "")
        url_expr = ctx.resolve_expr(str(url_raw)) if url_raw else '""'

        # Auth configuration
        auth_type = str(params.get("authentication", "none")).lower()

        # Headers
        headers_spec = params.get("headerParameters", {})
        header_params = []
        if isinstance(headers_spec, dict):
            for param in headers_spec.get("parameters", []):
                if isinstance(param, dict):
                    name_val = param.get("name", "")
                    value_val = ctx.resolve_expr(str(param.get("value", "")))
                    header_params.append((name_val, value_val))

        # Query params
        query_spec = params.get("queryParameters", {})
        query_params_list = []
        if isinstance(query_spec, dict):
            for param in query_spec.get("parameters", []):
                if isinstance(param, dict):
                    name_val = param.get("name", "")
                    value_val = ctx.resolve_expr(str(param.get("value", "")))
                    query_params_list.append((name_val, value_val))

        # Request body
        body_type = str(
            params.get("contentType", params.get("bodyContentType", ""))
        ).lower()
        json_body = params.get("jsonBody", params.get("body", ""))
        body_params_spec = params.get("bodyParameters", {})
        form_params_list = []
        if isinstance(body_params_spec, dict):
            for param in body_params_spec.get("parameters", []):
                if isinstance(param, dict):
                    name_val = param.get("name", "")
                    value_val = ctx.resolve_expr(str(param.get("value", "")))
                    form_params_list.append((name_val, value_val))

        # Response format
        response_format = str(params.get("responseFormat", "json")).lower()
        timeout = params.get("timeout", 10000)
        try:
            timeout_secs = int(timeout) / 1000
        except (TypeError, ValueError):
            timeout_secs = 10.0

        # Redirect
        allow_redirect = not bool(
            params.get("redirect", {}).get("redirect", {}).get("followRedirects", True)
            is False
        )

        code_lines = [f"# HTTP {method}: {var}"]

        # Build headers dict
        if header_params:
            hdr_items = ", ".join(f'"{n}": {v}' for n, v in header_params)
            code_lines.append(f"{var}_headers = {{{hdr_items}}}")
        else:
            code_lines.append(f"{var}_headers = {{}}")

        # Add auth headers
        if auth_type in ("basicauth", "basic"):
            code_lines += [
                f"import os",
                f'{var}_auth = (os.environ.get("HTTP_BASIC_USER", ""), os.environ.get("HTTP_BASIC_PASS", ""))',
            ]
        elif auth_type in (
            "headerauth",
            "genericcredentialtype",
            "predefinedcredentialtype",
        ):
            code_lines += [
                f"import os",
                f'{var}_headers["Authorization"] = os.environ.get("HTTP_AUTH_TOKEN", "")',
                f"{var}_auth = None",
            ]
        else:
            code_lines.append(f"{var}_auth = None")

        # Build query params
        if query_params_list:
            q_items = ", ".join(f'"{n}": {v}' for n, v in query_params_list)
            code_lines.append(f"{var}_params = {{{q_items}}}")
        else:
            code_lines.append(f"{var}_params = {{}}")

        # Build body
        if method in ("POST", "PUT", "PATCH"):
            if body_type in ("json", "") and json_body:
                body_expr = ctx.resolve_expr(str(json_body))
                code_lines.append(f"{var}_json = {body_expr}")
                code_lines.append(f"{var}_data = None")
            elif form_params_list:
                f_items = ", ".join(f'"{n}": {v}' for n, v in form_params_list)
                code_lines.append(f"{var}_data = {{{f_items}}}")
                code_lines.append(f"{var}_json = None")
            else:
                code_lines.append(f"{var}_json = None")
                code_lines.append(f"{var}_data = None")
        else:
            code_lines.append(f"{var}_json = None")
            code_lines.append(f"{var}_data = None")

        # Make the request
        code_lines += [
            f"{var}_response = requests.request(",
            f'    method="{method}",',
            f"    url={url_expr},",
            f"    headers={var}_headers,",
            f"    params={var}_params,",
            f"    json={var}_json,",
            f"    data={var}_data,",
            f"    auth={var}_auth,",
            f"    timeout={timeout_secs},",
            f"    allow_redirects={allow_redirect!r},",
            f")",
            f"{var}_response.raise_for_status()",
        ]

        # Parse response
        if response_format == "json":
            code_lines += [
                f"try:",
                f"    {var}_resp_data = {var}_response.json()",
                f"except Exception:",
                f"    {var}_resp_data = {{'text': {var}_response.text}}",
            ]
        elif response_format == "text":
            code_lines.append(f"{var}_resp_data = {{'text': {var}_response.text}}")
        else:
            code_lines.append(
                f"{var}_resp_data = {{'content': {var}_response.content, 'text': {var}_response.text}}"
            )

        code_lines += [
            f"if isinstance({var}_resp_data, list):",
            f"    {var}_output = [{{'json': item}} for item in {var}_resp_data]",
            f"else:",
            f"    {var}_output = [{{'json': {var}_resp_data}}]",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import requests", "import os"],
            pip_packages=["requests"],
            code_lines=code_lines,
            comment=f"HTTP Request: {method} {url_raw or '(url from expression)'}",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.httpRequest"]

    def required_packages(self) -> list[str]:
        return ["requests"]
