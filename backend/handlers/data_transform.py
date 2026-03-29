"""Data transformation node handlers.

Covers: Set, Filter, Sort, Limit, Split Out, Aggregate, Remove Duplicates,
Rename Keys, Summarize, Item Lists, Compare Datasets, Convert to File,
Extract from File, DateTime, HTML, XML, Crypto, Markdown, Execute Command.
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
# Set (Edit Fields)
# ---------------------------------------------------------------------------


@register(
    "n8n-nodes-base.set",
    "n8n-nodes-base.editFields",
)
class SetNodeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        code_lines = [f"# Set node: {node.name!r}"]

        # v3+ JSON mode
        if params.get("mode") == "raw":
            json_output = ctx.resolve_expr(str(params.get("jsonOutput", "{}")))
            code_lines += [
                f"{var}_fields = {json_output}",
                f"{var}_output = [{{**item, 'json': {{**item.get('json', {{}}), **({var}_fields if isinstance({var}_fields, dict) else {{}})}}}} for item in {prev_var}]",
            ]
            return IRNode(
                node_id=node.id,
                node_name=node.name,
                kind=IRNodeKind.STATEMENT,
                python_var=var,
                code_lines=code_lines,
            )

        # Manual mode: assigned fields
        assignments = params.get("assignments", {})
        assignment_list = []
        if isinstance(assignments, dict):
            assignment_list = assignments.get("assignments", [])
        elif isinstance(assignments, list):
            assignment_list = assignments

        # Also check v1-style values
        values = params.get("values", {})
        if isinstance(values, dict):
            for vtype, vlist in values.items():
                if isinstance(vlist, list):
                    for item in vlist:
                        if isinstance(item, dict):
                            assignment_list.append(item)

        if assignment_list:
            field_lines = []
            for asgn in assignment_list:
                if not isinstance(asgn, dict):
                    continue
                field_name = str(asgn.get("name") or asgn.get("key", ""))
                field_val = ctx.resolve_expr(str(asgn.get("value", "")))
                if field_name:
                    field_lines.append(f'            "{field_name}": {field_val},')

            if field_lines:
                code_lines += [
                    f"{var}_output = [",
                    f"    {{",
                    f"        **item,",
                    f"        'json': {{",
                    f"            **item.get('json', {{}}),",
                ]
                code_lines.extend(field_lines)
                code_lines += [
                    f"        }}",
                    f"    }}",
                    f"    for item in {prev_var}",
                    f"]",
                ]
            else:
                code_lines.append(f"{var}_output = {prev_var}")
        else:
            # Include/exclude mode
            include = str(params.get("include", "all")).lower()
            if include == "all":
                code_lines.append(f"{var}_output = {prev_var}")
            elif include == "none":
                code_lines.append(
                    f"{var}_output = [{{'json': {{}}}} for _ in {prev_var}]"
                )
            else:
                code_lines.append(f"{var}_output = {prev_var}")

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=code_lines,
            comment=f"Set / Edit Fields",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.set", "n8n-nodes-base.editFields"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.filter")
class FilterNodeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        from backend.handlers.flow_control import _conditions_to_python

        conditions = params.get("conditions", params.get("condition", {}))
        cond_expr = _conditions_to_python(conditions, ctx)

        code_lines = [
            f"import re",
            f"# Filter: keep items where condition is True",
            f"def {var}_condition(item):",
            f"    _json = item.get('json', {{}})",
            f"    return bool({cond_expr})",
            f"{var}_output = [item for item in {prev_var} if {var}_condition(item)]",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import re"],
            code_lines=code_lines,
            comment=f"Filter items by condition",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.filter"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Sort
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.sort")
class SortNodeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        sort_fields = params.get("sortFieldsUi", {})
        if isinstance(sort_fields, dict):
            sort_list = sort_fields.get("sortField", [])
        else:
            sort_list = []

        code_lines = [f"# Sort node: {node.name!r}"]

        if sort_list and isinstance(sort_list, list):
            for sf in reversed(sort_list):
                if not isinstance(sf, dict):
                    continue
                field_name = sf.get("fieldName", "")
                order = str(sf.get("order", "ASC")).upper()
                reverse = "True" if order == "DESC" else "False"
                code_lines.append(
                    f"{prev_var} = sorted({prev_var}, key=lambda item: item.get('json', {{}}).get('{field_name}'), reverse={reverse})"
                )
            code_lines.append(f"{var}_output = {prev_var}")
        else:
            code_lines.append(f"{var}_output = {prev_var}")

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=code_lines,
            comment="Sort items",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.sort"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Limit
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.limit")
class LimitNodeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        max_items = params.get("maxItems", 1)
        keep = str(params.get("keep", "first")).lower()

        if keep == "last":
            slice_expr = f"[-{max_items}:]"
        else:
            slice_expr = f"[:{max_items}]"

        code_lines = [
            f"{var}_output = {prev_var}{slice_expr}  # Limit to {max_items} items ({keep})",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=code_lines,
            comment=f"Limit to {max_items} items",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.limit"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Split Out
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.splitOut")
class SplitOutHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        field_name = str(params.get("fieldToSplitOut", ""))
        dest_field = str(params.get("destinationFieldName", field_name))

        code_lines = [
            f"# Split Out: expand {field_name!r} array into individual items",
            f"{var}_output = []",
            f"for _item in {prev_var}:",
            f"    _val = _item.get('json', {{}}).get('{field_name}', [])",
            f"    if isinstance(_val, list):",
            f"        for _v in _val:",
            f"            {var}_output.append({{'json': {{**_item.get('json', {{}}), '{dest_field}': _v}}}})",
            f"    else:",
            f"        {var}_output.append({{**_item, 'json': {{**_item.get('json', {{}}), '{dest_field}': _val}}}})",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=code_lines,
            comment=f"Split Out: {field_name!r}",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.splitOut"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.aggregate")
class AggregateHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        agg_op = str(params.get("aggregate", "aggregateAllItemData")).lower()

        if "allitemdata" in agg_op:
            dest_field = str(params.get("destinationFieldName", "data"))
            code_lines = [
                f"# Aggregate: combine all items into a single item",
                f"{var}_all = [item.get('json', {{}}) for item in {prev_var}]",
                f"{var}_output = [{{'json': {{'{dest_field}': {var}_all}}}}]",
            ]
        else:
            fields_spec = params.get("fieldsToAggregate", {})
            fields_list = (
                fields_spec.get("fieldToAggregate", [])
                if isinstance(fields_spec, dict)
                else []
            )
            code_lines = [f"# Aggregate fields"]
            if fields_list:
                aggregated = []
                for f in fields_list:
                    if not isinstance(f, dict):
                        continue
                    fname = str(f.get("fieldToAggregate", ""))
                    new_name = str(f.get("renameField", fname) or fname)
                    aggregated.append((fname, new_name))

                code_lines.append(f"{var}_combined = {{")
                for orig, renamed in aggregated:
                    code_lines.append(
                        f"    '{renamed}': [item.get('json', {{}}).get('{orig}') for item in {prev_var}],"
                    )
                code_lines.append(f"}}")
                code_lines.append(f"{var}_output = [{{'json': {var}_combined}}]")
            else:
                code_lines.append(f"{var}_output = {prev_var}")

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=code_lines,
            comment="Aggregate items",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.aggregate"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Remove Duplicates
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.removeDuplicates")
class RemoveDuplicatesHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        compare = params.get("compare", "allFields")
        dedup_fields = []
        if compare == "selectedFields":
            fields_spec = params.get("fieldsToCompare", {})
            dedup_fields = [
                str(f.get("fieldName", ""))
                for f in fields_spec.get("fields", [])
                if isinstance(f, dict)
            ]

        if dedup_fields:
            key_expr = (
                "("
                + ", ".join(
                    f'item.get("json", {{}}).get("{fn}")' for fn in dedup_fields
                )
                + ")"
            )
            code_lines = [
                f"# Remove Duplicates by: {', '.join(dedup_fields)}",
                f"{var}_seen = set()",
                f"{var}_output = []",
                f"for item in {prev_var}:",
                f"    _key = {key_expr}",
                f"    if _key not in {var}_seen:",
                f"        {var}_seen.add(_key)",
                f"        {var}_output.append(item)",
            ]
        else:
            code_lines = [
                f"# Remove Duplicates (all fields)",
                f"import json as _json_mod",
                f"{var}_seen = set()",
                f"{var}_output = []",
                f"for item in {prev_var}:",
                f"    _key = _json_mod.dumps(item.get('json', {{}}), sort_keys=True)",
                f"    if _key not in {var}_seen:",
                f"        {var}_seen.add(_key)",
                f"        {var}_output.append(item)",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=code_lines,
            comment="Remove Duplicates",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.removeDuplicates"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Rename Keys
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.renameKeys")
class RenameKeysHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        keys_spec = params.get("keys", {})
        rename_list = keys_spec.get("key", []) if isinstance(keys_spec, dict) else []

        if rename_list:
            rename_map = {}
            for item in rename_list:
                if isinstance(item, dict):
                    old_name = str(item.get("currentKey", ""))
                    new_name = str(item.get("newKey", ""))
                    if old_name:
                        rename_map[old_name] = new_name

            map_literal = (
                "{" + ", ".join(f'"{k}": "{v}"' for k, v in rename_map.items()) + "}"
            )
            code_lines = [
                f"# Rename Keys",
                f"{var}_rename_map = {map_literal}",
                f"{var}_output = []",
                f"for _item in {prev_var}:",
                f"    _new_json = {{",
                f"        {var}_rename_map.get(k, k): v",
                f"        for k, v in _item.get('json', {{}}).items()",
                f"    }}",
                f"    {var}_output.append({{'json': _new_json}})",
            ]
        else:
            code_lines = [
                f"{var}_output = {prev_var}  # Rename Keys: no mappings configured"
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=code_lines,
            comment="Rename Keys",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.renameKeys"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Summarize
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.summarize")
class SummarizeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        fields_spec = params.get("fieldsToSummarize", {})
        summarize_list = (
            fields_spec.get("values", []) if isinstance(fields_spec, dict) else []
        )

        group_by = params.get("fieldsToGroupBy", {})
        group_list = group_by.get("values", []) if isinstance(group_by, dict) else []
        group_fields = [
            str(g.get("name", "")) for g in group_list if isinstance(g, dict)
        ]

        code_lines = [f"# Summarize node"]

        if summarize_list:
            agg_ops = []
            for s in summarize_list:
                if not isinstance(s, dict):
                    continue
                field = str(s.get("field", ""))
                agg = str(s.get("aggregation", "count")).lower()
                rename = str(s.get("outputField", f"{agg}_{field}"))
                agg_ops.append((field, agg, rename))

            code_lines += [
                f"from collections import defaultdict",
                f"{var}_groups = defaultdict(list)",
                f"for _item in {prev_var}:",
                f"    _json = _item.get('json', {{}})",
                f"    _key = tuple(_json.get(f, None) for f in {group_fields!r})",
                f"    {var}_groups[_key].append(_json)",
                f"{var}_output = []",
                f"for _key, _group in {var}_groups.items():",
                f"    _result = {{f: v for f, v in zip({group_fields!r}, _key)}}",
            ]
            for field, agg, rename in agg_ops:
                if agg == "sum":
                    code_lines.append(
                        f"    _result['{rename}'] = sum(g.get('{field}', 0) for g in _group)"
                    )
                elif agg == "count":
                    code_lines.append(f"    _result['{rename}'] = len(_group)")
                elif agg == "countunique":
                    code_lines.append(
                        f"    _result['{rename}'] = len(set(g.get('{field}') for g in _group))"
                    )
                elif agg == "min":
                    code_lines.append(
                        f"    _result['{rename}'] = min((g.get('{field}', 0) for g in _group), default=None)"
                    )
                elif agg == "max":
                    code_lines.append(
                        f"    _result['{rename}'] = max((g.get('{field}', 0) for g in _group), default=None)"
                    )
                elif agg == "average":
                    code_lines.append(
                        f"    _vals = [g.get('{field}', 0) for g in _group]"
                    )
                    code_lines.append(
                        f"    _result['{rename}'] = sum(_vals) / len(_vals) if _vals else 0"
                    )
                else:
                    code_lines.append(
                        f"    _result['{rename}'] = len(_group)  # unsupported agg: {agg}"
                    )
            code_lines.append(f"    {var}_output.append({{'json': _result}})")
        else:
            code_lines.append(f"{var}_output = {prev_var}")

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=code_lines,
            comment="Summarize",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.summarize"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# DateTime
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.dateTime")
class DateTimeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        action = str(params.get("action", "format")).lower()

        if action == "format":
            value_expr = ctx.resolve_expr(str(params.get("value", "")))
            format_str = str(params.get("toFormat", "%Y-%m-%d %H:%M:%S"))
            output_field = str(params.get("outputFieldName", "formattedDate"))

            code_lines = [
                f"from datetime import datetime as _dt",
                f"# DateTime format",
                f"{var}_output = []",
                f"for _item in {prev_var}:",
                f"    try:",
                f"        _raw = {value_expr}",
                f"        if isinstance(_raw, str):",
                f"            _parsed = _dt.fromisoformat(_raw.replace('Z', '+00:00'))",
                f"        elif isinstance(_raw, (int, float)):",
                f"            _parsed = _dt.fromtimestamp(_raw / 1000 if _raw > 1e10 else _raw)",
                f"        else:",
                f"            _parsed = _dt.now()",
                f"        _formatted = _parsed.strftime('{format_str}')",
                f"    except Exception:",
                f"        _formatted = str(_raw) if '_raw' in dir() else ''",
                f"    {var}_output.append({{**_item, 'json': {{**_item.get('json', {{}}), '{output_field}': _formatted}}}})",
            ]
        else:
            code_lines = [
                f"# DateTime node (action={action!r}) — pass-through",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["from datetime import datetime"],
            code_lines=code_lines,
            comment=f"DateTime ({action})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.dateTime"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# HTML Node (parse HTML / extract data)
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.html")
class HtmlNodeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        operation = str(params.get("operation", "generateHtml")).lower()

        if operation == "extracthtmlcontent":
            source_key = str(params.get("sourceKey", "html"))
            dest_key = str(params.get("destinationKey", "parsed"))
            code_lines = [
                f"from bs4 import BeautifulSoup",
                f"{var}_output = []",
                f"for _item in {prev_var}:",
                f"    _html = _item.get('json', {{}}).get('{source_key}', '')",
                f"    _soup = BeautifulSoup(_html, 'html.parser')",
                f"    _text = _soup.get_text(separator=' ', strip=True)",
                f"    {var}_output.append({{**_item, 'json': {{**_item.get('json', {{}}), '{dest_key}': _text}}}})",
            ]
            pip_packages = ["beautifulsoup4"]
        elif operation == "generatehtml":
            html_template = ctx.resolve_expr(str(params.get("html", "")))
            code_lines = [
                f"{var}_output = [{{'json': {{'html': {html_template}}}}}]",
            ]
            pip_packages = []
        else:
            code_lines = [
                f"# HTML node (operation={operation!r}) — pass-through",
                f"{var}_output = {prev_var}",
            ]
            pip_packages = []

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=(
                ["from bs4 import BeautifulSoup"]
                if "beautifulsoup4" in pip_packages
                else []
            ),
            pip_packages=pip_packages,
            code_lines=code_lines,
            comment=f"HTML ({operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.html"]

    def required_packages(self) -> list[str]:
        return ["beautifulsoup4"]


# ---------------------------------------------------------------------------
# XML Node
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.xml")
class XmlNodeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        mode = str(params.get("mode", "xmlToJson")).lower()
        field_name = str(params.get("dataPropertyName", "data"))

        if mode in ("xmltojson", "xml_to_json"):
            code_lines = [
                f"import xmltodict",
                f"{var}_output = []",
                f"for _item in {prev_var}:",
                f"    _xml = _item.get('json', {{}}).get('{field_name}', '')",
                f"    try:",
                f"        _parsed = xmltodict.parse(_xml)",
                f"    except Exception:",
                f"        _parsed = {{'error': 'XML parse failed'}}",
                f"    {var}_output.append({{'json': _parsed}})",
            ]
        else:
            code_lines = [
                f"import xmltodict",
                f"{var}_output = []",
                f"for _item in {prev_var}:",
                f"    _data = _item.get('json', {{}})",
                f"    _xml = xmltodict.unparse({{'root': _data}})",
                f"    {var}_output.append({{'json': {{'{field_name}': _xml}}}})",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import xmltodict"],
            pip_packages=["xmltodict"],
            code_lines=code_lines,
            comment=f"XML ({mode})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.xml"]

    def required_packages(self) -> list[str]:
        return ["xmltodict"]


# ---------------------------------------------------------------------------
# Crypto
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.crypto")
class CryptoHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        action = str(params.get("action", "hash")).lower()
        field_name = str(params.get("dataPropertyName", "data"))
        hash_type = str(params.get("type", "MD5")).lower()
        output_field = str(params.get("destinationKey", "result"))
        encoding = str(params.get("encoding", "hex")).lower()

        if action == "hash":
            code_lines = [
                f"import hashlib",
                f"{var}_output = []",
                f"for _item in {prev_var}:",
                f"    _data = str(_item.get('json', {{}}).get('{field_name}', '')).encode()",
                f"    _h = hashlib.{hash_type}(_data)",
                f"    _result = _h.{'hexdigest' if encoding == 'hex' else 'digest'}()",
                f"    {var}_output.append({{**_item, 'json': {{**_item.get('json', {{}}), '{output_field}': _result}}}})",
            ]
        elif action == "hmac":
            secret_key = ctx.resolve_expr(str(params.get("secret", "")))
            code_lines = [
                f"import hmac",
                f"import hashlib",
                f"{var}_output = []",
                f"for _item in {prev_var}:",
                f"    _data = str(_item.get('json', {{}}).get('{field_name}', '')).encode()",
                f"    _h = hmac.new({secret_key}.encode(), _data, hashlib.{hash_type})",
                f"    {var}_output.append({{**_item, 'json': {{**_item.get('json', {{}}), '{output_field}': _h.hexdigest()}}}})",
            ]
        else:
            code_lines = [
                f"# Crypto node (action={action!r}) — pass-through",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import hashlib"],
            code_lines=code_lines,
            comment=f"Crypto ({action}, {hash_type})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.crypto"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.markdown")
class MarkdownHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        mode = str(params.get("mode", "markdownToHtml")).lower()
        field = str(params.get("dataPropertyName", "data"))
        dest = str(
            params.get("destinationKey", "html" if "tohtml" in mode else "markdown")
        )

        if "tohtml" in mode.replace("_", ""):
            code_lines = [
                f"import markdown",
                f"{var}_output = []",
                f"for _item in {prev_var}:",
                f"    _md = _item.get('json', {{}}).get('{field}', '')",
                f"    _html = markdown.markdown(str(_md))",
                f"    {var}_output.append({{**_item, 'json': {{**_item.get('json', {{}}), '{dest}': _html}}}})",
            ]
            pip_packages = ["markdown"]
        elif "tomarkdown" in mode.replace("_", ""):
            code_lines = [
                f"import html2text",
                f"{var}_output = []",
                f"for _item in {prev_var}:",
                f"    _html = _item.get('json', {{}}).get('{field}', '')",
                f"    _md = html2text.html2text(str(_html))",
                f"    {var}_output.append({{**_item, 'json': {{**_item.get('json', {{}}), '{dest}': _md}}}})",
            ]
            pip_packages = ["html2text"]
        else:
            code_lines = [f"{var}_output = {prev_var}"]
            pip_packages = []

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            pip_packages=pip_packages,
            code_lines=code_lines,
            comment=f"Markdown ({mode})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.markdown"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Execute Command
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.executeCommand")
class ExecuteCommandHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        ctx.register_node_var(node.name, var)
        params = node.parameters

        command = ctx.resolve_expr(str(params.get("command", "")))
        code_lines = [
            f"import subprocess",
            f"import shlex",
            f"# Execute Command: {params.get('command', '')}",
            f"_cmd_str = {command}",
            f"_result = subprocess.run(shlex.split(str(_cmd_str)), capture_output=True, text=True)",
            f"{var}_output = [{{",
            f"    'json': {{",
            f"        'exitCode': _result.returncode,",
            f"        'stdout': _result.stdout,",
            f"        'stderr': _result.stderr,",
            f"    }}",
            f"}}]",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import subprocess", "import shlex"],
            code_lines=code_lines,
            comment="Execute Command",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.executeCommand"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Compare Datasets
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.compareDatasets")
class CompareDatasetsHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        field1 = str(
            params.get("mergeByFields", {}).get("values", [{}])[0].get("field1", "id")
            if isinstance(params.get("mergeByFields", {}), dict)
            else "id"
        )
        field2 = str(
            params.get("mergeByFields", {}).get("values", [{}])[0].get("field2", "id")
            if isinstance(params.get("mergeByFields", {}), dict)
            else "id"
        )

        code_lines = [
            f"# Compare Datasets",
            f"# TODO: supply two input datasets as {var}_input1, {var}_input2",
            f"{var}_input1 = {prev_var}",
            f"{var}_input2 = []  # second input",
            f"{var}_keys1 = {{item.get('json', {{}}).get('{field1}'): item for item in {var}_input1}}",
            f"{var}_keys2 = {{item.get('json', {{}}).get('{field2}'): item for item in {var}_input2}}",
            f"{var}_only_in1 = [v for k, v in {var}_keys1.items() if k not in {var}_keys2]",
            f"{var}_only_in2 = [v for k, v in {var}_keys2.items() if k not in {var}_keys1]",
            f"{var}_in_both = [v for k, v in {var}_keys1.items() if k in {var}_keys2]",
            f"{var}_output = {var}_only_in1 + {var}_only_in2 + {var}_in_both",
        ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=code_lines,
            comment="Compare Datasets",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.compareDatasets"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Convert to File / Extract from File
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.convertToFile")
class ConvertToFileHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        operation = str(params.get("operation", "csv")).lower()
        file_name = ctx.resolve_expr(str(params.get("fileName", "output.csv")))

        if operation == "csv":
            code_lines = [
                f"import csv",
                f"import io",
                f"{var}_buf = io.StringIO()",
                f"if {prev_var}:",
                f"    _writer = csv.DictWriter({var}_buf, fieldnames=list({prev_var}[0].get('json', {{}}).keys()))",
                f"    _writer.writeheader()",
                f"    for _item in {prev_var}:",
                f"        _writer.writerow(_item.get('json', {{}}))",
                f"{var}_csv_content = {var}_buf.getvalue()",
                f"{var}_output = [{{'json': {{'fileName': {file_name}, 'data': {var}_csv_content}}}}]",
            ]
        elif operation == "json":
            code_lines = [
                f"import json as _json_mod",
                f"{var}_json_content = _json_mod.dumps([item.get('json', {{}}) for item in {prev_var}], indent=2)",
                f"{var}_output = [{{'json': {{'fileName': {file_name}, 'data': {var}_json_content}}}}]",
            ]
        else:
            code_lines = [
                f"# Convert to File ({operation}): pass-through",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=code_lines,
            comment=f"Convert to File ({operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.convertToFile"]

    def required_packages(self) -> list[str]:
        return []


@register("n8n-nodes-base.extractFromFile")
class ExtractFromFileHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        operation = str(params.get("operation", "csv")).lower()
        field = str(params.get("dataPropertyName", "data"))

        if operation == "csv":
            code_lines = [
                f"import csv",
                f"import io",
                f"{var}_output = []",
                f"for _item in {prev_var}:",
                f"    _data = _item.get('json', {{}}).get('{field}', '')",
                f"    _reader = csv.DictReader(io.StringIO(str(_data)))",
                f"    for _row in _reader:",
                f"        {var}_output.append({{'json': dict(_row)}})",
            ]
        elif operation == "json":
            code_lines = [
                f"import json as _json_mod",
                f"{var}_output = []",
                f"for _item in {prev_var}:",
                f"    _data = _item.get('json', {{}}).get('{field}', '[]')",
                f"    _parsed = _json_mod.loads(str(_data)) if isinstance(_data, str) else _data",
                f"    if isinstance(_parsed, list):",
                f"        {var}_output.extend([{{'json': r}} for r in _parsed])",
                f"    else:",
                f"        {var}_output.append({{'json': _parsed}})",
            ]
        else:
            code_lines = [
                f"# Extract from File ({operation}): pass-through",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id,
            node_name=node.name,
            kind=IRNodeKind.STATEMENT,
            python_var=var,
            code_lines=code_lines,
            comment=f"Extract from File ({operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.extractFromFile"]

    def required_packages(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Item Lists
# ---------------------------------------------------------------------------


@register("n8n-nodes-base.itemLists")
class ItemListsHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        operation = str(params.get("operation", "splitOutItems")).lower()

        if "split" in operation:
            from backend.handlers.data_transform import SplitOutHandler

            return SplitOutHandler().generate(node, ctx)
        elif "remove" in operation:
            from backend.handlers.data_transform import RemoveDuplicatesHandler

            return RemoveDuplicatesHandler().generate(node, ctx)
        else:
            code_lines = [
                f"# Item Lists ({operation}): pass-through",
                f"{var}_output = {prev_var}",
            ]
            return IRNode(
                node_id=node.id,
                node_name=node.name,
                kind=IRNodeKind.STATEMENT,
                python_var=var,
                code_lines=code_lines,
                comment=f"Item Lists ({operation})",
            )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.itemLists"]

    def required_packages(self) -> list[str]:
        return []
