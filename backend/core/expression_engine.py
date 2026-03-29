"""Expression translation engine for n8n → Python.

Three-stage translation pipeline:
1. Template extraction — strip {{ }} wrappers; handle mixed static+dynamic strings.
2. n8n variable resolution — $json, $input, $('Node'), $env, $now, etc.
3. JS→Python translation — operators, method chains, arrow functions, ternaries.

Key design decisions:
- A ``VariableContext`` maps n8n node names to Python variable stems so that
  ``$('HTTP Request').item.json.status`` resolves to the correct variable.
- Arrow functions (``x => expr``) are detected and rewritten as list/generator
  comprehensions rather than being wrapped in callable lambdas.
- JS operators, methods, and ternaries are translated deterministically.
- Untranslatable patterns emit a ``# TODO: manual translation`` comment rather
  than raising an exception, so the pipeline always produces runnable code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Variable context
# ---------------------------------------------------------------------------

@dataclass
class VariableContext:
    """Maps n8n node display names to their Python output variable stems.

    Example:
        ctx = VariableContext()
        ctx.register("HTTP Request", "http_request")
        # $('HTTP Request').item.json.url → http_request_output[0]["json"]["url"]
    """

    _map: dict[str, str] = field(default_factory=dict)

    def register(self, node_name: str, python_var: str) -> None:
        self._map[node_name] = python_var

    def resolve(self, node_name: str) -> str:
        """Return the output variable name for a given n8n node display name."""
        stem = self._map.get(node_name)
        if stem is None:
            # Derive a safe stem from the display name as fallback.
            stem = _sanitize_var(node_name)
        return f"{stem}_output"

    def current_var(self) -> str:
        """Return the most recently registered output variable name."""
        if not self._map:
            return "[]"
        last_stem = list(self._map.values())[-1]
        return f"{last_stem}_output"


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _sanitize_var(name: str) -> str:
    """Convert a display name to a safe Python variable stem."""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower())
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        return "node"
    if s[0].isdigit():
        s = f"n_{s}"
    return s


def _build_subscript(base: str, keys: list[str]) -> str:
    """Build a Python subscript expression from a base and key list."""
    result = base
    for key in keys:
        result = f'{result}["{key}"]'
    return result


# ---------------------------------------------------------------------------
# Core expression translator
# ---------------------------------------------------------------------------

# Pattern to detect a pure n8n template expression (the whole value is {{ expr }} or ={{ expr }})
_FULL_TEMPLATE_RE = re.compile(r"^\s*=?\s*\{\{\s*(.+?)\s*\}\}\s*$", re.DOTALL)
# Pattern to find {{ expr }} fragments within a larger string
_FRAGMENT_RE = re.compile(r"\{\{\s*(.+?)\s*\}\}", re.DOTALL)
# JS template literal: `text ${expr} more`
_JS_TEMPLATE_LITERAL_RE = re.compile(r"`([^`]*)`")
# Ternary detector (simplified)
_TERNARY_RE = re.compile(r"(.+?)\s*\?\s*(.+?)\s*:\s*(.+)", re.DOTALL)
# $('Node Name').accessor...
_DOLLAR_FUNC_RE = re.compile(
    r"""\$\(\s*['"]((?:[^'"\\]|\\.)+)['"]\s*\)"""
    r"""\.(?P<accessor>item|first\(\)|last\(\)|all\(\))"""
    r"""(?:\.json(?P<path>[a-zA-Z0-9_."\[\]]*?))?(?=\s*[^a-zA-Z0-9_.\["']|$)"""
)
# $input.item / $input.first() / $input.last() / $input.all()
_INPUT_RE = re.compile(
    r"""\$input\.(?P<accessor>item|first\(\)|last\(\)|all\(\))"""
    r"""(?:\.json(?P<path>[a-zA-Z0-9_."\[\]]*?))?(?=\s*[^a-zA-Z0-9_.\["']|$)"""
)
# $json.path or $json["key"]...
# The path group stops before known JS method/property names to avoid
# consuming `$json.name.toLowerCase()` as path `name.toLowerCase`.
_JS_STOP_WORDS = (
    "trim|toLowerCase|toUpperCase|startsWith|endsWith|includes|indexOf|"
    "slice|split|join|concat|push|pop|shift|unshift|map|filter|reduce|"
    "some|every|find|findIndex|flat|flatMap|sort|reverse|forEach|toString|"
    "valueOf|hasOwnProperty|length"
)
_JSON_DOT_RE = re.compile(
    r"\$json\.(?P<path>[a-zA-Z_]\w*"
    r"(?:\.(?!(?:" + _JS_STOP_WORDS + r")\b)[a-zA-Z_]\w*)*)"
)
# Handle $json.path.length → len(path_expr) — processed before _JSON_DOT_RE
_JSON_LENGTH_RE = re.compile(
    r"\$json\.(?P<path>[a-zA-Z_]\w*"
    r"(?:\.(?!(?:" + _JS_STOP_WORDS + r")\b)[a-zA-Z_]\w*)*)"
    r"\.length(?!\w)"
)
_JSON_BRACKET_RE = re.compile(r"""\$json(?P<brackets>(?:\["[^"]*"\])+)""")
# $node["Name"].json.path (legacy syntax)
_NODE_BRACKET_RE = re.compile(
    r"""\$node\["(?P<node>[^"]+)"\]\.json\.(?P<path>[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)"""
)
# $env.VAR
_ENV_RE = re.compile(r"\$env\.(?P<var>[a-zA-Z_]\w*)")
# $vars.name
_VARS_RE = re.compile(r"\$vars\.(?P<var>[a-zA-Z_]\w*)")
# $now / $today
_NOW_RE = re.compile(r"\$now\b")
_TODAY_RE = re.compile(r"\$today\b")
# $prevNode
_PREV_NODE_RE = re.compile(r"\$prevNode\b")
# $parameter
_PARAMETER_RE = re.compile(r"\$parameter\b")
# $jmespath(obj, expr)
_JMESPATH_RE = re.compile(r"\$jmespath\s*\(")
# $fromAI(key, desc, type, default)
_FROM_AI_RE = re.compile(r"\$fromAI\s*\(")
# .includes("val") pattern
_INCLUDES_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.includes\(\s*(?P<arg>[^)]+)\s*\)"""
)
# .length (not followed by word char)
_LENGTH_RE = re.compile(r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.length(?!\w)""")
# .toString()
_TOSTRING_RE = re.compile(r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.toString\(\)""")
# .parseInt / .parseFloat at call-like positions
_PARSEINT_RE = re.compile(r"parseInt\(\s*(?P<arg>[^)]+)\s*\)")
_PARSEFLOAT_RE = re.compile(r"parseFloat\(\s*(?P<arg>[^)]+)\s*\)")
# typeof expr
_TYPEOF_RE = re.compile(r"\btypeof\s+(?P<expr>[A-Za-z_]\w*)")
# Object.keys(x), Object.values(x)
_OBJECT_KEYS_RE = re.compile(r"\bObject\.keys\s*\((?P<arg>[^)]+)\)")
_OBJECT_VALUES_RE = re.compile(r"\bObject\.values\s*\((?P<arg>[^)]+)\)")
# Math.max / Math.min
_MATH_MAX_RE = re.compile(r"\bMath\.max\s*\((?P<args>[^)]+)\)")
_MATH_MIN_RE = re.compile(r"\bMath\.min\s*\((?P<args>[^)]+)\)")
# JSON.parse / JSON.stringify
_JSON_PARSE_RE = re.compile(r"\bJSON\.parse\s*\((?P<arg>[^)]+)\)")
_JSON_STRINGIFY_RE = re.compile(r"\bJSON\.stringify\s*\((?P<arg>[^)]+)\)")
# Array.isArray
_ISARRAY_RE = re.compile(r"\bArray\.isArray\s*\((?P<arg>[^)]+)\)")
# .indexOf(x)
_INDEXOF_RE = re.compile(r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.indexOf\((?P<arg>[^)]+)\)""")
# .slice(a, b)
_SLICE_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.slice\((?P<args>[^)]+)\)"""
)
# .concat(other)
_CONCAT_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.concat\((?P<arg>[^)]+)\)"""
)
# .push(x) — translates to .append(x), returns the expression (side-effect)
_PUSH_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.push\((?P<arg>[^)]+)\)"""
)
# .map(fn) / .filter(fn) / and more array higher-order methods
_MAP_RE = re.compile(r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.map\((?P<fn>(?:[^()]|\([^)]*\))*)\)""")
_FILTER_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.filter\((?P<fn>(?:[^()]|\([^)]*\))*)\)"""
)
_FIND_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.find\((?P<fn>(?:[^()]|\([^)]*\))*)\)"""
)
_FIND_INDEX_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.findIndex\((?P<fn>(?:[^()]|\([^)]*\))*)\)"""
)
_SOME_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.some\((?P<fn>(?:[^()]|\([^)]*\))*)\)"""
)
_EVERY_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.every\((?P<fn>(?:[^()]|\([^)]*\))*)\)"""
)
_REDUCE_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.reduce\((?P<fn>(?:[^()]|\([^)]*\))*?)(?:,\s*(?P<init>[^)]+))?\)"""
)
_SORT_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.sort\((?P<fn>(?:[^()]|\([^)]*\))*)\)"""
)
_SORT_NO_ARGS_RE = re.compile(r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.sort\(\s*\)""")
_REVERSE_RE = re.compile(r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.reverse\(\s*\)""")
_FLAT_RE = re.compile(r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.flat\(\s*\)""")
_FLAT_MAP_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.flatMap\((?P<fn>(?:[^()]|\([^)]*\))*)\)"""
)
_POP_RE = re.compile(r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.pop\(\s*\)""")
_SHIFT_RE = re.compile(r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.shift\(\s*\)""")

# Additional string methods
_JOIN_RE = re.compile(r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.join\((?P<sep>[^)]+)\)""")
_SPLIT_RE = re.compile(r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.split\((?P<sep>[^)]*)\)""")
_REPLACE_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.replace\((?P<a>[^,]+),\s*(?P<b>[^)]+)\)"""
)
_REPLACE_ALL_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.replaceAll\((?P<a>[^,]+),\s*(?P<b>[^)]+)\)"""
)
_PAD_START_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.padStart\((?P<n>[^,)]+)(?:,\s*(?P<c>[^)]+))?\)"""
)
_PAD_END_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.padEnd\((?P<n>[^,)]+)(?:,\s*(?P<c>[^)]+))?\)"""
)
_REPEAT_RE = re.compile(r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.repeat\((?P<n>[^)]+)\)""")
_CHAR_AT_RE = re.compile(r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.charAt\((?P<i>[^)]+)\)""")
_SUBSTR_RE = re.compile(r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.substr\((?P<args>[^)]+)\)""")
_SUBSTRING_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.substring\((?P<args>[^)]+)\)"""
)
_MATCH_RE = re.compile(
    r"""(?P<obj>[A-Za-z_][\w.\["'\]]*?)\.match\((?P<pattern>[^)]+)\)"""
)
_TEST_RE = re.compile(
    r"""(?P<pattern>[A-Za-z_][\w.\["'\]]*?)\.test\((?P<obj>[^)]+)\)"""
)

# Math methods and constants
_MATH_FLOOR_RE = re.compile(r"\bMath\.floor\s*\((?P<arg>[^)]+)\)")
_MATH_CEIL_RE = re.compile(r"\bMath\.ceil\s*\((?P<arg>[^)]+)\)")
_MATH_ROUND_RE = re.compile(r"\bMath\.round\s*\((?P<arg>[^)]+)\)")
_MATH_RANDOM_RE = re.compile(r"\bMath\.random\s*\(\s*\)")
_MATH_ABS_RE = re.compile(r"\bMath\.abs\s*\((?P<arg>[^)]+)\)")
_MATH_POW_RE = re.compile(r"\bMath\.pow\s*\((?P<a>[^,]+),\s*(?P<b>[^)]+)\)")
_MATH_SQRT_RE = re.compile(r"\bMath\.sqrt\s*\((?P<arg>[^)]+)\)")
_MATH_LOG_RE = re.compile(r"\bMath\.log\s*\((?P<arg>[^)]+)\)")
_MATH_PI_RE = re.compile(r"\bMath\.PI\b")
_MATH_E_RE = re.compile(r"\bMath\.E\b")

# Type converter globals
_STRING_FN_RE = re.compile(r"\bString\s*\((?P<arg>[^)]+)\)")
_NUMBER_FN_RE = re.compile(r"\bNumber\s*\((?P<arg>[^)]+)\)")
_BOOLEAN_FN_RE = re.compile(r"\bBoolean\s*\((?P<arg>[^)]+)\)")
_DATE_NOW_RE = re.compile(r"\bDate\.now\s*\(\s*\)")
_NEW_DATE_ARGS_RE = re.compile(r"\bnew\s+Date\s*\((?P<arg>[^)]+)\)")
_NEW_DATE_RE = re.compile(r"\bnew\s+Date\s*\(\s*\)")

# $fromAI with args
_FROM_AI_FULL_RE = re.compile(r"\$fromAI\s*\(([^)]*)\)")


def _translate_path(path: str) -> list[str]:
    """Convert a dotted path string to a list of dict-access keys."""
    return [p for p in path.split(".") if p]


# ---------------------------------------------------------------------------
# Arrow function helpers
# ---------------------------------------------------------------------------

_ARROW_FN_WITH_PARENS_RE = re.compile(r"^\(([^)]*)\)\s*=>\s*(.+)$", re.DOTALL)
_ARROW_FN_SIMPLE_RE = re.compile(r"^([a-zA-Z_]\w*)\s*=>\s*(.+)$", re.DOTALL)


def _parse_arrow_fn(fn_str: str) -> tuple[list[str], str] | None:
    """Parse ``x => expr`` or ``(x, y) => expr`` into (params, body).

    Returns ``None`` if *fn_str* is not an arrow function.
    """
    s = fn_str.strip()
    # (params) => body
    m = _ARROW_FN_WITH_PARENS_RE.match(s)
    if m:
        params = [p.strip() for p in m.group(1).split(",") if p.strip()]
        return params, m.group(2).strip()
    # param => body (no parens)
    m = _ARROW_FN_SIMPLE_RE.match(s)
    if m:
        return [m.group(1)], m.group(2).strip()
    return None


def _arrow_body_translate(body: str, params: list[str]) -> str:
    """Translate an arrow-function body for use in comprehensions.

    1. Apply JS-to-Python operator replacements (null→None, &&→and, etc.).
    2. Convert ``param.field.nested`` (dot-access, not method calls) to
       ``param["field"]["nested"]`` for each parameter name.

    The dot-access pattern stops before any identifier that is immediately
    followed by ``(`` so that method calls like ``.lower()`` are left alone.
    """
    result = _apply_js_operators(body)
    for param in params:
        # Match param.field.nested... where each segment is NOT followed by (
        pattern = re.compile(
            rf"\b{re.escape(param)}((?:\.[a-zA-Z_]\w*(?!\s*\())+)"
        )
        def _repl(m: re.Match, _p: str = param) -> str:
            parts = m.group(1).split(".")[1:]  # skip leading empty str
            r = _p
            for part in parts:
                r += f'["{part}"]'
            return r
        result = pattern.sub(_repl, result)
    return result


def _resolve_accessor(node_var: str, accessor: str, path: str | None) -> str:
    """Build Python expression for $('Node').accessor.json.path style access."""
    if accessor == "all()":
        base = node_var  # list of items
        if path:
            keys = _translate_path(path.lstrip("."))
            key_accesses = "".join('["%s"]' % k for k in keys)
            return f'[item["json"]{key_accesses} for item in {base}]'
        return base
    elif accessor in ("item", "first()"):
        idx = "[0]"
        base = f"{node_var}{idx}"
    elif accessor == "last()":
        base = f"{node_var}[-1]"
    else:
        base = f"{node_var}[0]"

    if path:
        keys = ["json"] + _translate_path(path.lstrip("."))
        return _build_subscript(base, keys)
    return f'{base}["json"]'


def _apply_js_operators(expr: str) -> str:
    """Translate JS operators and keywords to Python equivalents."""
    # Order matters: longer patterns first.
    replacements = [
        (r"===", "=="),
        (r"!==", "!="),
        (r"\&\&", "and"),
        (r"\|\|", "or"),
        (r"(?<![=!<>])!(?!=)(?!\s*=)", "not "),
        (r"\bnull\b", "None"),
        (r"\bundefined\b", "None"),
        (r"\btrue\b", "True"),
        (r"\bfalse\b", "False"),
    ]
    result = expr
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result)
    return result


def _apply_js_methods(expr: str) -> str:
    """Translate common JS string/array/math methods to Python equivalents.

    Method translations are applied in a specific order to avoid regex
    conflicts. Arrow-function-aware helpers are used for higher-order methods.
    """
    result = expr

    # ── String methods ────────────────────────────────────────────────────
    result = result.replace(".trim()", ".strip()")
    result = result.replace(".trimStart()", ".lstrip()")
    result = result.replace(".trimEnd()", ".rstrip()")
    result = result.replace(".toLowerCase()", ".lower()")
    result = result.replace(".toUpperCase()", ".upper()")
    result = result.replace(".startsWith(", ".startswith(")
    result = result.replace(".endsWith(", ".endswith(")

    result = _INCLUDES_RE.sub(lambda m: f'({m.group("arg")} in {m.group("obj")})', result)
    result = _TOSTRING_RE.sub(lambda m: f'str({m.group("obj")})', result)
    result = _INDEXOF_RE.sub(lambda m: f'{m.group("obj")}.find({m.group("arg")})', result)
    result = _CONCAT_RE.sub(lambda m: f'({m.group("obj")} + {m.group("arg")})', result)
    result = _JOIN_RE.sub(lambda m: f'{m.group("sep")}.join({m.group("obj")})', result)
    result = _SPLIT_RE.sub(lambda m: f'{m.group("obj")}.split({m.group("sep")})', result)
    # replaceAll before replace to avoid partial matching
    result = _REPLACE_ALL_RE.sub(
        lambda m: f'{m.group("obj")}.replace({m.group("a")}, {m.group("b")})', result
    )
    result = _REPLACE_RE.sub(
        lambda m: f'{m.group("obj")}.replace({m.group("a")}, {m.group("b")})', result
    )
    def _pad_start_repl(m: re.Match) -> str:
        obj, n = m.group("obj"), m.group("n")
        c = m.group("c") or '"0"'
        return f"{obj}.rjust({n}, {c})"
    result = _PAD_START_RE.sub(_pad_start_repl, result)
    def _pad_end_repl(m: re.Match) -> str:
        obj, n = m.group("obj"), m.group("n")
        c = m.group("c") or '" "'
        return f"{obj}.ljust({n}, {c})"
    result = _PAD_END_RE.sub(_pad_end_repl, result)
    result = _REPEAT_RE.sub(lambda m: f'({m.group("obj")} * {m.group("n")})', result)
    result = _CHAR_AT_RE.sub(lambda m: f'{m.group("obj")}[{m.group("i")}]', result)
    def _substr_repl(m: re.Match) -> str:
        args = [a.strip() for a in m.group("args").split(",")]
        if len(args) == 1:
            return f"{m.group('obj')}[{args[0]}:]"
        return f"{m.group('obj')}[{args[0]}:{args[1]}]"
    result = _SUBSTRING_RE.sub(_substr_repl, result)
    result = _SUBSTR_RE.sub(_substr_repl, result)
    result = _MATCH_RE.sub(
        lambda m: f're.search({m.group("pattern")}, {m.group("obj")})', result
    )
    result = _TEST_RE.sub(
        lambda m: f'bool(re.search({m.group("pattern")}, {m.group("obj")}))', result
    )

    # ── Array higher-order methods (arrow-function aware) ─────────────────
    def _hof_map(m: re.Match) -> str:
        obj, fn = m.group("obj"), m.group("fn").strip()
        arrow = _parse_arrow_fn(fn)
        if arrow:
            params, body = arrow
            param = params[0] if params else "_item"
            tbody = _arrow_body_translate(body, params)
            return f"[{tbody} for {param} in {obj}]"
        return f"[({fn})(_item) for _item in {obj}]"

    def _hof_filter(m: re.Match) -> str:
        obj, fn = m.group("obj"), m.group("fn").strip()
        arrow = _parse_arrow_fn(fn)
        if arrow:
            params, body = arrow
            param = params[0] if params else "_item"
            tbody = _arrow_body_translate(body, params)
            return f"[{param} for {param} in {obj} if {tbody}]"
        return f"[_item for _item in {obj} if ({fn})(_item)]"

    def _hof_find(m: re.Match) -> str:
        obj, fn = m.group("obj"), m.group("fn").strip()
        arrow = _parse_arrow_fn(fn)
        if arrow:
            params, body = arrow
            param = params[0] if params else "_item"
            tbody = _arrow_body_translate(body, params)
            return f'next(({param} for {param} in {obj} if {tbody}), None)'
        return f"next((_item for _item in {obj} if ({fn})(_item)), None)"

    def _hof_find_index(m: re.Match) -> str:
        obj, fn = m.group("obj"), m.group("fn").strip()
        arrow = _parse_arrow_fn(fn)
        if arrow:
            params, body = arrow
            param = params[0] if params else "_item"
            tbody = _arrow_body_translate(body, params)
            return f'next((_i for _i, {param} in enumerate({obj}) if {tbody}), -1)'
        return f"next((_i for _i, _item in enumerate({obj}) if ({fn})(_item)), -1)"

    def _hof_some(m: re.Match) -> str:
        obj, fn = m.group("obj"), m.group("fn").strip()
        arrow = _parse_arrow_fn(fn)
        if arrow:
            params, body = arrow
            param = params[0] if params else "_item"
            tbody = _arrow_body_translate(body, params)
            return f"any({tbody} for {param} in {obj})"
        return f"any(({fn})(_item) for _item in {obj})"

    def _hof_every(m: re.Match) -> str:
        obj, fn = m.group("obj"), m.group("fn").strip()
        arrow = _parse_arrow_fn(fn)
        if arrow:
            params, body = arrow
            param = params[0] if params else "_item"
            tbody = _arrow_body_translate(body, params)
            return f"all({tbody} for {param} in {obj})"
        return f"all(({fn})(_item) for _item in {obj})"

    def _hof_reduce(m: re.Match) -> str:
        obj, fn = m.group("obj"), m.group("fn").strip()
        init = (m.group("init") or "").strip()
        arrow = _parse_arrow_fn(fn)
        if arrow:
            params, body = arrow
            acc = params[0] if len(params) >= 1 else "_acc"
            cur = params[1] if len(params) >= 2 else "_cur"
            tbody = _arrow_body_translate(body, params)
            lam = f"lambda {acc}, {cur}: {tbody}"
        else:
            lam = fn
        if init:
            return f"functools.reduce({lam}, {obj}, {init})"
        return f"functools.reduce({lam}, {obj})"

    def _hof_sort(m: re.Match) -> str:
        obj, fn = m.group("obj"), m.group("fn").strip()
        arrow = _parse_arrow_fn(fn)
        if arrow:
            params, body = arrow
            tbody = _arrow_body_translate(body, params)
            if len(params) == 2:
                a, b = params
                return f"sorted({obj}, key=functools.cmp_to_key(lambda {a}, {b}: {tbody}))"
            param = params[0]
            return f"sorted({obj}, key=lambda {param}: {tbody})"
        return f"sorted({obj}, key={fn})"

    def _hof_flat_map(m: re.Match) -> str:
        obj, fn = m.group("obj"), m.group("fn").strip()
        arrow = _parse_arrow_fn(fn)
        if arrow:
            params, body = arrow
            param = params[0] if params else "_item"
            tbody = _arrow_body_translate(body, params)
            return f"[_y for {param} in {obj} for _y in {tbody}]"
        return f"[_y for _item in {obj} for _y in ({fn})(_item)]"

    # Apply all higher-order method translations (flatMap before map to avoid partial match)
    result = _FLAT_MAP_RE.sub(_hof_flat_map, result)
    result = _MAP_RE.sub(_hof_map, result)
    result = _FILTER_RE.sub(_hof_filter, result)
    result = _FIND_INDEX_RE.sub(_hof_find_index, result)
    result = _FIND_RE.sub(_hof_find, result)
    result = _SOME_RE.sub(_hof_some, result)
    result = _EVERY_RE.sub(_hof_every, result)
    result = _REDUCE_RE.sub(_hof_reduce, result)
    result = _SORT_NO_ARGS_RE.sub(lambda m: f"sorted({m.group('obj')})", result)
    result = _SORT_RE.sub(_hof_sort, result)

    # ── Simple array methods ──────────────────────────────────────────────
    result = _LENGTH_RE.sub(lambda m: f'len({m.group("obj")})', result)
    result = _FLAT_RE.sub(
        lambda m: f"[_x for _sub in {m.group('obj')} for _x in _sub]", result
    )
    result = _REVERSE_RE.sub(lambda m: f"list(reversed({m.group('obj')}))", result)
    result = _POP_RE.sub(lambda m: f"{m.group('obj')}[-1]", result)
    result = _SHIFT_RE.sub(lambda m: f"{m.group('obj')}[0]", result)
    result = _PUSH_RE.sub(
        lambda m: f'(lambda _l, _v: (_l.append(_v), _l)[1])({m.group("obj")}, {m.group("arg")})',
        result,
    )
    def _slice_repl(m: re.Match) -> str:
        args = [a.strip() for a in m.group("args").split(",")]
        if len(args) == 1:
            return f"{m.group('obj')}[{args[0]}:]"
        return f"{m.group('obj')}[{args[0]}:{args[1]}]"
    result = _SLICE_RE.sub(_slice_repl, result)

    # ── Math methods ──────────────────────────────────────────────────────
    result = _MATH_FLOOR_RE.sub(lambda m: f'math.floor({m.group("arg")})', result)
    result = _MATH_CEIL_RE.sub(lambda m: f'math.ceil({m.group("arg")})', result)
    result = _MATH_ROUND_RE.sub(lambda m: f'round({m.group("arg")})', result)
    result = _MATH_RANDOM_RE.sub("random.random()", result)
    result = _MATH_ABS_RE.sub(lambda m: f'abs({m.group("arg")})', result)
    result = _MATH_POW_RE.sub(lambda m: f'({m.group("a")} ** {m.group("b")})', result)
    result = _MATH_SQRT_RE.sub(lambda m: f'math.sqrt({m.group("arg")})', result)
    result = _MATH_LOG_RE.sub(lambda m: f'math.log({m.group("arg")})', result)
    result = _MATH_PI_RE.sub("math.pi", result)
    result = _MATH_E_RE.sub("math.e", result)
    result = _MATH_MAX_RE.sub(lambda m: f'max({m.group("args")})', result)
    result = _MATH_MIN_RE.sub(lambda m: f'min({m.group("args")})', result)

    # ── JSON / type utilities ─────────────────────────────────────────────
    result = _JSON_PARSE_RE.sub(lambda m: f'json.loads({m.group("arg")})', result)
    result = _JSON_STRINGIFY_RE.sub(lambda m: f'json.dumps({m.group("arg")})', result)
    result = _ISARRAY_RE.sub(lambda m: f'isinstance({m.group("arg")}, list)', result)
    result = _OBJECT_KEYS_RE.sub(lambda m: f'list({m.group("arg")}.keys())', result)
    result = _OBJECT_VALUES_RE.sub(lambda m: f'list({m.group("arg")}.values())', result)
    result = _PARSEINT_RE.sub(lambda m: f'int({m.group("arg")})', result)
    result = _PARSEFLOAT_RE.sub(lambda m: f'float({m.group("arg")})', result)
    result = _TYPEOF_RE.sub(lambda m: f'type({m.group("expr")}).__name__', result)

    # Global type converters
    result = _STRING_FN_RE.sub(lambda m: f'str({m.group("arg")})', result)
    result = _NUMBER_FN_RE.sub(lambda m: f'float({m.group("arg")})', result)
    result = _BOOLEAN_FN_RE.sub(lambda m: f'bool({m.group("arg")})', result)

    # Date helpers
    result = _DATE_NOW_RE.sub("int(datetime.now(timezone.utc).timestamp() * 1000)", result)
    result = _NEW_DATE_ARGS_RE.sub(
        lambda m: f'datetime.fromisoformat({m.group("arg")})', result
    )
    result = _NEW_DATE_RE.sub("datetime.now(timezone.utc)", result)

    return result


def _translate_ternary(expr: str) -> str:
    """Translate a single-level JS ternary ``cond ? a : b`` to Python ``a if cond else b``.

    Uses a balanced-brace aware scan rather than a naive regex split, so that
    nested ternaries and method calls inside the branches don't trip it up.
    """
    # Find the position of '?' that is not inside brackets/parens/quotes.
    depth = 0
    in_str: str | None = None
    q_pos = -1
    c_pos = -1
    i = 0
    while i < len(expr):
        ch = expr[i]
        if in_str:
            if ch == "\\" and i + 1 < len(expr):
                i += 2
                continue
            if ch == in_str:
                in_str = None
        elif ch in ('"', "'", "`"):
            in_str = ch
        elif ch in ("(", "[", "{"):
            depth += 1
        elif ch in (")", "]", "}"):
            depth -= 1
        elif ch == "?" and depth == 0:
            q_pos = i
        elif ch == ":" and depth == 0 and q_pos != -1:
            c_pos = i
            break
        i += 1

    if q_pos == -1 or c_pos == -1:
        return expr  # Not a ternary.

    cond = expr[:q_pos].strip()
    true_val = expr[q_pos + 1 : c_pos].strip()
    false_val = expr[c_pos + 1 :].strip()

    # Recursively handle nested ternaries in sub-expressions.
    true_val = _translate_ternary(true_val)
    false_val = _translate_ternary(false_val)
    cond = _translate_ternary(cond)

    return f"({true_val} if {cond} else {false_val})"


def _translate_js_template_literal(s: str, ctx: VariableContext) -> str:
    r"""Convert JS template literal ``\`Hello ${name}\``` to Python f-string."""

    def _repl(m: re.Match) -> str:
        inner = m.group(1)
        # Replace ${expr} with {translated_expr}
        def _inner_repl(im: re.Match) -> str:
            raw_expr = im.group(1).strip()
            translated = _translate_body(raw_expr, ctx)
            return "{" + translated + "}"

        converted = re.sub(r"\$\{([^}]+)\}", _inner_repl, inner)
        # Escape existing curly braces that are not from our substitution.
        # (They are already replaced above, so remaining { } are literals.)
        return f'f"{converted}"'

    return _JS_TEMPLATE_LITERAL_RE.sub(_repl, s)


def _resolve_path_expr(path_str: str) -> str:
    """Convert a raw dotted/bracketed path to Python subscript notation."""
    # Already bracket-style: e.g. ["key"]["other"]
    if path_str.startswith("["):
        return path_str
    parts = [p for p in path_str.split(".") if p]
    return "".join(f'["{p}"]' for p in parts)


def _translate_body(body: str, ctx: VariableContext) -> str:
    """Core expression translator: convert n8n/JS body to Python expression.

    Called after stripping {{ }} wrappers. Handles variable references,
    JS methods/operators, and ternary expressions.
    """
    result = body.strip()

    # --- Handle JS template literals (backtick strings) ---
    result = _translate_js_template_literal(result, ctx)

    # --- Translate $('NodeName').accessor references ---
    def _dollar_func_repl(m: re.Match) -> str:
        node_name = m.group(1)
        accessor = m.group("accessor")
        path = m.group("path") or ""
        node_var = ctx.resolve(node_name)
        return _resolve_accessor(node_var, accessor, path.lstrip(".") if path else None)

    result = _DOLLAR_FUNC_RE.sub(_dollar_func_repl, result)

    # --- Translate $input references ---
    def _input_repl(m: re.Match) -> str:
        accessor = m.group("accessor")
        path = m.group("path") or ""
        cur_var = ctx.current_var()
        return _resolve_accessor(cur_var, accessor, path.lstrip(".") if path else None)

    result = _INPUT_RE.sub(_input_repl, result)

    # --- Translate $node["Name"].json.path (legacy) ---
    def _node_bracket_repl(m: re.Match) -> str:
        node_name = m.group("node")
        path = m.group("path")
        node_var = ctx.resolve(node_name)
        keys = ["json"] + _translate_path(path)
        return _build_subscript(f"{node_var}[0]", keys)

    result = _NODE_BRACKET_RE.sub(_node_bracket_repl, result)

    # --- Translate $json.path.length → len(path_expr) ---
    def _json_length_repl(m: re.Match) -> str:
        path = m.group("path")
        cur_var = ctx.current_var()
        keys = ["json"] + _translate_path(path)
        return f'len({_build_subscript(f"{cur_var}[0]", keys)})'

    result = _JSON_LENGTH_RE.sub(_json_length_repl, result)

    # --- Translate $json.path ---
    def _json_dot_repl(m: re.Match) -> str:
        path = m.group("path")
        cur_var = ctx.current_var()
        keys = ["json"] + _translate_path(path)
        return _build_subscript(f"{cur_var}[0]", keys)

    result = _JSON_DOT_RE.sub(_json_dot_repl, result)

    # --- Translate bare $json (no path) → current_var[0]["json"] ---
    result = re.sub(r'\$json(?!\s*[\.\[])', lambda m: f'{ctx.current_var()}[0]["json"]', result)

    # --- Translate $json["key"]... ---
    def _json_bracket_repl(m: re.Match) -> str:
        brackets = m.group("brackets")
        cur_var = ctx.current_var()
        return f'{cur_var}[0]["json"]{brackets}'

    result = _JSON_BRACKET_RE.sub(_json_bracket_repl, result)

    # --- Translate $env.VAR ---
    result = _ENV_RE.sub(lambda m: f'os.environ.get("{m.group("var")}", "")', result)

    # --- Translate $vars.name ---
    result = _VARS_RE.sub(lambda m: f'os.environ.get("{m.group("var")}", "")', result)

    # --- Translate $now / $today ---
    result = _NOW_RE.sub("datetime.now(timezone.utc)", result)
    result = _TODAY_RE.sub("datetime.now(timezone.utc).date()", result)

    # --- Translate $prevNode ---
    result = _PREV_NODE_RE.sub('"_prev_node"', result)

    # --- Translate $parameter ---
    result = _PARAMETER_RE.sub('"_parameter"', result)

    # --- Translate $jmespath(...) ---
    if _JMESPATH_RE.search(result):
        result = _JMESPATH_RE.sub("jmespath.search(", result)

    # --- Translate $fromAI(key, desc, type, default) → typed placeholder ---
    def _from_ai_repl(m: re.Match) -> str:
        raw_args = m.group(1)
        # Extract first arg (key) to name the placeholder meaningfully
        parts = [a.strip().strip("'\"") for a in raw_args.split(",")]
        key = parts[0] if parts else "ai_value"
        return f'""  # TODO: $fromAI placeholder — key={key!r}'

    result = _FROM_AI_FULL_RE.sub(_from_ai_repl, result)
    # Catch remaining $fromAI without closing paren
    if _FROM_AI_RE.search(result):
        result = _FROM_AI_RE.sub('""  # $fromAI(', result)

    # --- Apply JS method translations ---
    result = _apply_js_methods(result)

    # --- Apply JS operator translations ---
    result = _apply_js_operators(result)

    # --- Translate ternary expressions ---
    result = _translate_ternary(result)

    return result


def translate_expression(value: str, ctx: VariableContext) -> str:
    """Translate a raw n8n parameter value (may or may not contain {{ }}).

    - If the value is a pure template (the entire string is ``{{ expr }}``),
      returns just the translated Python expression.
    - If the value contains embedded templates in a larger string,
      returns an f-string with each template fragment translated.
    - Otherwise, returns the original value as a Python string literal.
    """
    if not isinstance(value, str):
        return repr(value)

    # Pure template: {{ expr }}
    pure_match = _FULL_TEMPLATE_RE.match(value)
    if pure_match:
        body = pure_match.group(1)
        return _translate_body(body, ctx)

    # Check for any template fragments in a mixed string.
    fragments = _FRAGMENT_RE.findall(value)
    if not fragments:
        return repr(value)

    # Build an f-string with translated fragments.
    def _frag_repl(m: re.Match) -> str:
        body = m.group(1).strip()
        translated = _translate_body(body, ctx)
        return "{" + translated + "}"

    inner = _FRAGMENT_RE.sub(_frag_repl, value)
    # Escape existing braces that are not our placeholders.
    # The sub above already created { expr } placeholders; raw braces in value
    # need to be doubled — but since we replaced all template tags already, the
    # remaining literal braces come from the original value text only.
    # We do a best-effort escape of remaining literal { } outside our placeholders.
    return f'f"{inner}"'
