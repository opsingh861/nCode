"""Tests for the expression engine (backend/core/expression_engine.py)."""

import pytest
from backend.core.expression_engine import VariableContext, translate_expression


@pytest.fixture()
def ctx() -> VariableContext:
    vc = VariableContext()
    vc.register("HTTP Request", "http_request")
    vc.register("Set Fields", "set_fields")
    return vc


# ---------------------------------------------------------------------------
# VariableContext tests
# ---------------------------------------------------------------------------


class TestVariableContext:
    def test_register_and_resolve(self):
        vc = VariableContext()
        vc.register("My Node", "my_node")
        assert vc.resolve("My Node") == "my_node_output"

    def test_resolve_unknown_returns_fallback(self):
        vc = VariableContext()
        result = vc.resolve("Unknown Node")
        assert "_output" in result

    def test_current_var_initial(self):
        vc = VariableContext()
        # When no nodes registered, returns a sensible placeholder
        result = vc.current_var()
        assert isinstance(result, str) and len(result) > 0

    def test_current_var_after_register(self):
        vc = VariableContext()
        vc.register("N", "var_stem")
        assert vc.current_var() == "var_stem_output"


# ---------------------------------------------------------------------------
# translate_expression: plain strings
# ---------------------------------------------------------------------------


class TestTranslatePlainStrings:
    def test_plain_string_returns_repr(self, ctx):
        result = translate_expression("hello world", ctx)
        assert result == "'hello world'"

    def test_integer_like_plain(self, ctx):
        result = translate_expression("42", ctx)
        assert result == "'42'"

    def test_empty_string(self, ctx):
        result = translate_expression("", ctx)
        assert result == "''"


# ---------------------------------------------------------------------------
# translate_expression: pure expression templates
# ---------------------------------------------------------------------------


class TestPureExpressions:
    def test_json_field(self, ctx):
        result = translate_expression("={{ $json.name }}", ctx)
        assert "name" in result
        assert "json" in result.lower() or "_item" in result

    def test_input_all(self, ctx):
        result = translate_expression("={{ $input.all() }}", ctx)
        assert "_output" in result or "http_request" in result

    def test_input_first(self, ctx):
        result = translate_expression("={{ $input.first() }}", ctx)
        assert "[0]" in result or "first" in result

    def test_env_variable(self, ctx):
        result = translate_expression("={{ $env.MY_VAR }}", ctx)
        assert "MY_VAR" in result
        assert "os" in result or "environ" in result

    def test_node_reference_json(self, ctx):
        result = translate_expression("={{ $('HTTP Request').item.json.url }}", ctx)
        assert "http_request" in result
        assert "url" in result

    def test_now_returns_datetime(self, ctx):
        result = translate_expression("={{ $now }}", ctx)
        assert "datetime" in result.lower() or "now" in result.lower()

    def test_boolean_operators(self, ctx):
        result = translate_expression("={{ $json.a === $json.b }}", ctx)
        assert "==" in result
        assert "===" not in result

    def test_and_operator(self, ctx):
        result = translate_expression("={{ $json.a && $json.b }}", ctx)
        assert " and " in result
        assert "&&" not in result

    def test_or_operator(self, ctx):
        result = translate_expression("={{ $json.a || $json.b }}", ctx)
        assert " or " in result
        assert "||" not in result

    def test_null_becomes_none(self, ctx):
        result = translate_expression("={{ null }}", ctx)
        assert "None" in result

    def test_true_becomes_True(self, ctx):
        result = translate_expression("={{ true }}", ctx)
        assert "True" in result

    def test_false_becomes_False(self, ctx):
        result = translate_expression("={{ false }}", ctx)
        assert "False" in result


# ---------------------------------------------------------------------------
# translate_expression: mixed f-string templates
# ---------------------------------------------------------------------------


class TestMixedTemplates:
    def test_mixed_string_with_expression(self, ctx):
        result = translate_expression("Hello, {{ $json.name }}!", ctx)
        assert result.startswith("f'") or result.startswith('f"')
        assert "Hello" in result
        assert "name" in result or "json" in result

    def test_two_expressions_in_template(self, ctx):
        result = translate_expression("{{ $json.first }} {{ $json.last }}", ctx)
        assert "first" in result or "json" in result


# ---------------------------------------------------------------------------
# translate_expression: JS method translations
# ---------------------------------------------------------------------------


class TestJsMethods:
    def test_to_lower_case(self, ctx):
        result = translate_expression("={{ $json.name.toLowerCase() }}", ctx)
        assert ".lower()" in result

    def test_to_upper_case(self, ctx):
        result = translate_expression("={{ $json.name.toUpperCase() }}", ctx)
        assert ".upper()" in result

    def test_trim(self, ctx):
        result = translate_expression("={{ $json.name.trim() }}", ctx)
        assert ".strip()" in result

    def test_includes(self, ctx):
        result = translate_expression("={{ $json.name.includes('x') }}", ctx)
        assert " in " in result

    def test_length_property(self, ctx):
        result = translate_expression("={{ $json.items.length }}", ctx)
        assert "len(" in result

    def test_json_stringify(self, ctx):
        result = translate_expression("={{ JSON.stringify($json.data) }}", ctx)
        assert "json.dumps" in result

    def test_json_parse(self, ctx):
        result = translate_expression("={{ JSON.parse($json.raw) }}", ctx)
        assert "json.loads" in result


# ---------------------------------------------------------------------------
# translate_expression: ternary operator
# ---------------------------------------------------------------------------


class TestTernary:
    def test_simple_ternary(self, ctx):
        result = translate_expression("={{ $json.x > 0 ? 'pos' : 'neg' }}", ctx)
        assert " if " in result
        assert " else " in result

    def test_ternary_preserves_values(self, ctx):
        result = translate_expression("={{ $json.x ? 'yes' : 'no' }}", ctx)
        assert "'yes'" in result or "yes" in result
        assert "'no'" in result or "no" in result


# ---------------------------------------------------------------------------
# Phase 2: Arrow function translations
# ---------------------------------------------------------------------------

from backend.core.expression_engine import _arrow_body_translate, _parse_arrow_fn


class TestParseArrowFn:
    def test_simple_arrow(self):
        result = _parse_arrow_fn("x => x.id")
        assert result is not None
        params, body = result
        assert params == ["x"]
        assert body == "x.id"

    def test_parens_arrow(self):
        result = _parse_arrow_fn("(item) => item.name")
        assert result is not None
        params, body = result
        assert params == ["item"]
        assert body == "item.name"

    def test_two_params(self):
        result = _parse_arrow_fn("(acc, cur) => acc + cur.value")
        assert result is not None
        params, body = result
        assert params == ["acc", "cur"]
        assert body == "acc + cur.value"

    def test_not_arrow(self):
        assert _parse_arrow_fn("someFunction") is None
        assert _parse_arrow_fn("myVar") is None

    def test_no_parens_multi_word_body(self):
        result = _parse_arrow_fn("x => x.active === true")
        assert result is not None
        params, body = result
        assert params == ["x"]
        assert "active" in body


class TestArrowBodyTranslate:
    def test_dot_access(self):
        result = _arrow_body_translate("item.id", ["item"])
        assert result == 'item["id"]'

    def test_nested_dot_access(self):
        result = _arrow_body_translate("item.address.city", ["item"])
        assert result == 'item["address"]["city"]'

    def test_method_not_converted(self):
        # .lower() is a method call — should NOT be turned into subscript
        result = _arrow_body_translate("item.name.lower()", ["item"])
        assert '["name"]' in result
        assert ".lower()" in result

    def test_operator_translation(self):
        result = _arrow_body_translate("item.active === true", ["item"])
        assert "==" in result
        assert "===" not in result
        assert "True" in result


class TestMapWithArrow:
    def test_map_simple_field(self, ctx):
        result = translate_expression("={{ $json.items.map(item => item.id) }}", ctx)
        assert "for item in" in result
        assert '["id"]' in result
        # Should be a list comprehension, not a lambda wrapper
        assert "lambda" not in result or "lambda item" not in result

    def test_map_no_arrow(self, ctx):
        result = translate_expression("={{ $json.items.map(myFn) }}", ctx)
        assert "for _item in" in result

    def test_map_nested_field(self, ctx):
        result = translate_expression(
            "={{ $json.users.map(u => u.profile.email) }}", ctx
        )
        assert "for u in" in result
        assert '["profile"]' in result
        assert '["email"]' in result


class TestFilterWithArrow:
    def test_filter_simple_condition(self, ctx):
        result = translate_expression("={{ $json.items.filter(x => x.active) }}", ctx)
        assert "for x in" in result
        assert "if" in result
        assert '["active"]' in result

    def test_filter_comparison(self, ctx):
        result = translate_expression(
            "={{ $json.items.filter(item => item.score > 5) }}", ctx
        )
        assert "for item in" in result
        assert '["score"]' in result
        assert ">" in result


class TestFindWithArrow:
    def test_find_returns_next(self, ctx):
        result = translate_expression("={{ $json.users.find(u => u.id === 1) }}", ctx)
        assert "next(" in result
        assert "None" in result
        assert '["id"]' in result

    def test_find_index(self, ctx):
        result = translate_expression(
            "={{ $json.list.findIndex(x => x.name === 'foo') }}", ctx
        )
        assert "next(" in result
        assert "enumerate(" in result
        assert "-1" in result


class TestSomeEveryWithArrow:
    def test_some(self, ctx):
        result = translate_expression("={{ $json.items.some(x => x.active) }}", ctx)
        assert "any(" in result
        assert "for x in" in result

    def test_every(self, ctx):
        result = translate_expression("={{ $json.items.every(x => x.valid) }}", ctx)
        assert "all(" in result
        assert "for x in" in result


class TestReduceWithArrow:
    def test_reduce_with_init(self, ctx):
        result = translate_expression(
            "={{ $json.items.reduce((acc, cur) => acc + cur.value, 0) }}", ctx
        )
        assert "functools.reduce(" in result
        assert "lambda acc, cur:" in result

    def test_reduce_no_init(self, ctx):
        result = translate_expression("={{ $json.nums.reduce((a, b) => a + b) }}", ctx)
        assert "functools.reduce(" in result


class TestSortWithArrow:
    def test_sort_no_args(self, ctx):
        result = translate_expression("={{ $json.items.sort() }}", ctx)
        assert "sorted(" in result

    def test_sort_key_fn(self, ctx):
        result = translate_expression("={{ $json.items.sort(x => x.name) }}", ctx)
        assert "sorted(" in result
        assert "key=" in result

    def test_sort_comparator(self, ctx):
        result = translate_expression(
            "={{ $json.items.sort((a, b) => a.score - b.score) }}", ctx
        )
        assert "sorted(" in result
        assert "cmp_to_key" in result


# ---------------------------------------------------------------------------
# Phase 2: Expanded string methods
# ---------------------------------------------------------------------------


class TestStringMethodsExpanded:
    def test_join(self, ctx):
        result = translate_expression("={{ $json.parts.join(', ') }}", ctx)
        assert ".join(" in result

    def test_split(self, ctx):
        result = translate_expression("={{ $json.csv.split(',') }}", ctx)
        assert ".split(" in result

    def test_replace(self, ctx):
        result = translate_expression("={{ $json.text.replace('foo', 'bar') }}", ctx)
        assert ".replace(" in result

    def test_replace_all(self, ctx):
        result = translate_expression("={{ $json.text.replaceAll(' ', '_') }}", ctx)
        assert ".replace(" in result

    def test_pad_start(self, ctx):
        result = translate_expression("={{ $json.num.padStart(5, '0') }}", ctx)
        assert ".rjust(" in result

    def test_pad_end(self, ctx):
        result = translate_expression("={{ $json.num.padEnd(5) }}", ctx)
        assert ".ljust(" in result

    def test_repeat(self, ctx):
        result = translate_expression("={{ $json.str.repeat(3) }}", ctx)
        assert " * 3" in result or "* 3" in result

    def test_char_at(self, ctx):
        result = translate_expression("={{ $json.str.charAt(0) }}", ctx)
        assert "[0]" in result

    def test_substring(self, ctx):
        result = translate_expression("={{ $json.str.substring(0, 5) }}", ctx)
        assert "[0:5]" in result

    def test_trim_start(self, ctx):
        result = translate_expression("={{ $json.str.trimStart() }}", ctx)
        assert ".lstrip()" in result

    def test_trim_end(self, ctx):
        result = translate_expression("={{ $json.str.trimEnd() }}", ctx)
        assert ".rstrip()" in result


# ---------------------------------------------------------------------------
# Phase 2: Expanded array methods
# ---------------------------------------------------------------------------


class TestArrayMethodsExpanded:
    def test_flat(self, ctx):
        result = translate_expression("={{ $json.matrix.flat() }}", ctx)
        assert "for _sub in" in result
        assert "for _x in _sub" in result

    def test_flat_map(self, ctx):
        result = translate_expression("={{ $json.items.flatMap(x => x.tags) }}", ctx)
        assert "for _y in" in result

    def test_reverse(self, ctx):
        result = translate_expression("={{ $json.items.reverse() }}", ctx)
        assert "reversed(" in result

    def test_pop(self, ctx):
        result = translate_expression("={{ $json.items.pop() }}", ctx)
        assert "[-1]" in result

    def test_shift(self, ctx):
        result = translate_expression("={{ $json.items.shift() }}", ctx)
        assert "[0]" in result


# ---------------------------------------------------------------------------
# Phase 2: Math methods
# ---------------------------------------------------------------------------


class TestMathMethods:
    def test_floor(self, ctx):
        result = translate_expression("={{ Math.floor($json.x) }}", ctx)
        assert "math.floor(" in result

    def test_ceil(self, ctx):
        result = translate_expression("={{ Math.ceil($json.x) }}", ctx)
        assert "math.ceil(" in result

    def test_round(self, ctx):
        result = translate_expression("={{ Math.round($json.x) }}", ctx)
        assert "round(" in result

    def test_random(self, ctx):
        result = translate_expression("={{ Math.random() }}", ctx)
        assert "random.random()" in result

    def test_abs(self, ctx):
        result = translate_expression("={{ Math.abs($json.x) }}", ctx)
        assert "abs(" in result

    def test_pow(self, ctx):
        result = translate_expression("={{ Math.pow($json.x, 2) }}", ctx)
        assert "**" in result

    def test_sqrt(self, ctx):
        result = translate_expression("={{ Math.sqrt($json.x) }}", ctx)
        assert "math.sqrt(" in result

    def test_pi(self, ctx):
        result = translate_expression("={{ Math.PI }}", ctx)
        assert "math.pi" in result

    def test_max(self, ctx):
        result = translate_expression("={{ Math.max(1, 2, 3) }}", ctx)
        assert "max(" in result

    def test_min(self, ctx):
        result = translate_expression("={{ Math.min(1, 2, 3) }}", ctx)
        assert "min(" in result


# ---------------------------------------------------------------------------
# Phase 2: Type converters
# ---------------------------------------------------------------------------


class TestTypeConverters:
    def test_string_fn(self, ctx):
        result = translate_expression("={{ String($json.num) }}", ctx)
        assert "str(" in result

    def test_number_fn(self, ctx):
        result = translate_expression("={{ Number($json.str) }}", ctx)
        assert "float(" in result

    def test_boolean_fn(self, ctx):
        result = translate_expression("={{ Boolean($json.val) }}", ctx)
        assert "bool(" in result

    def test_date_now(self, ctx):
        result = translate_expression("={{ Date.now() }}", ctx)
        assert "timestamp" in result or "datetime" in result

    def test_new_date_no_args(self, ctx):
        result = translate_expression("={{ new Date() }}", ctx)
        assert "datetime" in result.lower()


# ---------------------------------------------------------------------------
# Phase 2: $fromAI improved handling
# ---------------------------------------------------------------------------


class TestFromAI:
    def test_from_ai_has_key(self, ctx):
        result = translate_expression(
            "={{ $fromAI('user_query', 'The user question', 'string', '') }}", ctx
        )
        assert "user_query" in result
        assert "TODO" in result

    def test_from_ai_placeholder(self, ctx):
        result = translate_expression(
            "={{ $fromAI('count', 'Number', 'number', 0) }}", ctx
        )
        assert "count" in result
