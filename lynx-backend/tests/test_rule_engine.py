import pytest

from app.services.rule_engine import (
    eval_rule,
    deep_get,
    DEFAULT_RULES,
    RULE_OPERATORS,
)


class TestDeepGet:
    def test_deep_get_simple(self):
        data = {"a": 1, "b": {"c": 2}}
        assert deep_get(data, "a") == 1
        assert deep_get(data, "b.c") == 2

    def test_deep_get_missing(self):
        data = {"a": 1}
        assert deep_get(data, "b") is None
        assert deep_get(data, "a.b.c") is None

    def test_deep_get_empty_dict(self):
        assert deep_get({}, "anything") is None

    def test_deep_get_nested_none(self):
        data = {"a": {"b": None}}
        assert deep_get(data, "a.b") is None

    def test_deep_get_nested_deep(self):
        data = {"a": {"b": {"c": {"d": 42}}}}
        assert deep_get(data, "a.b.c.d") == 42


class TestRuleOperators:
    @pytest.mark.parametrize("op,value,params,expected", [
        ("exists", "hello", {}, True),
        ("exists", None, {}, False),
        ("not_exists", None, {}, True),
        ("not_exists", "hello", {}, False),
        ("eq", 5, {"value": 5}, True),
        ("eq", 5, {"value": 6}, False),
        ("neq", 5, {"value": 6}, True),
        ("neq", 5, {"value": 5}, False),
        ("in", "a", {"values": ["a", "b"]}, True),
        ("in", "c", {"values": ["a", "b"]}, False),
        ("not_in", "c", {"values": ["a", "b"]}, True),
        ("not_in", "a", {"values": ["a", "b"]}, False),
        ("gt", 10, {"value": 5}, True),
        ("gt", 5, {"value": 10}, False),
        ("gte", 5, {"value": 5}, True),
        ("gte", 4, {"value": 5}, False),
        ("lt", 3, {"value": 5}, True),
        ("lt", 6, {"value": 5}, False),
        ("lte", 5, {"value": 5}, True),
        ("lte", 6, {"value": 5}, False),
    ])
    def test_operator(self, op, value, params, expected):
        assert RULE_OPERATORS[op](value, params) == expected

    def test_regex_match(self):
        result = RULE_OPERATORS["regex"]("hello123", {"pattern": r"hello\d+"})
        assert result is not False
        result2 = RULE_OPERATORS["regex"]("helloABC", {"pattern": r"hello\d+"})
        assert result2 is None or result2 is False

    def test_between(self):
        assert RULE_OPERATORS["between"](5, {"min": 1, "max": 10}) is True
        assert RULE_OPERATORS["between"](0, {"min": 1, "max": 10}) is False
        assert RULE_OPERATORS["between"](10, {"min": 1, "max": 10}) is True


class TestEvalRule:
    def test_rule_not_applicable_wrong_class(self):
        rule = {
            "applies_to": {"ifc_classes": ["IfcPipeSegment"], "where": []},
            "check": {"field": "name", "op": "exists"},
        }
        element = {"ifc_class": "IfcWall", "name": "Wall-1"}
        passed, msg = eval_rule(rule, element)
        assert passed is None
        assert msg is None

    def test_rule_applies_and_passes(self):
        rule = {
            "applies_to": {"ifc_classes": ["IfcPipeSegment"], "where": []},
            "check": {"field": "name", "op": "exists"},
        }
        element = {"ifc_class": "IfcPipeSegment", "name": "Pipe-1"}
        passed, msg = eval_rule(rule, element)
        assert passed is True

    def test_rule_applies_and_fails(self):
        rule = {
            "applies_to": {"ifc_classes": ["IfcPipeSegment"], "where": []},
            "check": {"field": "name", "op": "exists"},
        }
        element = {"ifc_class": "IfcPipeSegment", "name": None}
        passed, msg = eval_rule(rule, element)
        assert passed is False
        assert msg is not None

    def test_rule_with_where_condition(self):
        rule = {
            "applies_to": {
                "ifc_classes": ["IfcPipeSegment"],
                "where": [{"field": "system_name", "op": "eq", "value": "B1"}],
            },
            "check": {"field": "canonical.diameter_mm", "op": "exists"},
        }
        el_match = {"ifc_class": "IfcPipeSegment", "system_name": "B1", "canonical": {"diameter_mm": 50}}
        el_no_match = {"ifc_class": "IfcPipeSegment", "system_name": "K1", "canonical": {"diameter_mm": 50}}
        passed_match, _ = eval_rule(rule, el_match)
        passed_no, _ = eval_rule(rule, el_no_match)
        assert passed_match is True
        assert passed_no is None

    def test_rule_with_unknown_operator(self):
        rule = {
            "applies_to": {"ifc_classes": ["IfcPipeSegment"], "where": []},
            "check": {"field": "name", "op": "unknown_op", "value": "x"},
        }
        element = {"ifc_class": "IfcPipeSegment", "name": "x"}
        passed, msg = eval_rule(rule, element)
        assert passed is None
        assert msg is None

    def test_rule_empty_applies_to(self):
        rule = {
            "applies_to": {"ifc_classes": [], "where": []},
            "check": {"field": "name", "op": "exists"},
        }
        element = {"ifc_class": "IfcPipeSegment", "name": "x"}
        passed, msg = eval_rule(rule, element)
        assert passed is None

    def test_rule_missing_check_field(self):
        rule = {
            "applies_to": {"ifc_classes": ["IfcPipeSegment"], "where": []},
            "check": {"field": "nonexistent.field", "op": "exists"},
        }
        element = {"ifc_class": "IfcPipeSegment", "name": "x"}
        passed, msg = eval_rule(rule, element)
        assert passed is False


class TestDefaultRules:
    def test_default_rules_have_required_keys(self):
        assert len(DEFAULT_RULES) > 0
        for rule in DEFAULT_RULES:
            assert "rule_key" in rule
            assert "applies_to" in rule
            assert "check" in rule
            assert "severity" in rule
            assert "message_template" in rule
            assert "ifc_classes" in rule["applies_to"]

    def test_default_rules_unique_keys(self):
        keys = [r["rule_key"] for r in DEFAULT_RULES]
        assert len(keys) == len(set(keys)), f"Duplicate rule keys: {keys}"

    def test_default_rules_valid_severity(self):
        valid = {"error", "warning", "info"}
        for rule in DEFAULT_RULES:
            assert rule["severity"] in valid, f"Bad severity for {rule['rule_key']}"

    def test_default_rules_valid_operators(self):
        for rule in DEFAULT_RULES:
            op = rule["check"]["op"]
            assert op in RULE_OPERATORS, f"Bad operator '{op}' for {rule['rule_key']}"

    def test_diameter_rule_checks_size(self):
        for rule in DEFAULT_RULES:
            if rule["rule_key"] == "viv.pipe.diameter.exists":
                element_pass = {
                    "ifc_class": "IfcPipeSegment",
                    "canonical": {"size_filled": True},
                }
                element_fail = {
                    "ifc_class": "IfcPipeSegment",
                    "canonical": {"size_filled": False},
                }
                passed_pass, _ = eval_rule(rule, element_pass)
                passed_fail, _ = eval_rule(rule, element_fail)
                assert passed_pass is True
                assert passed_fail is False
                return
        pytest.fail("viv.pipe.diameter.exists rule not found")

    def test_default_rules_all_evaluable_for_segment(self):
        """PipeSegment rules should evaluate (pass or skip) for a complete element."""
        perfect_element = {
            "ifc_class": "IfcPipeSegment",
            "name": "Perfect-Pipe-1",
            "object_type": "Pipe",
            "predefined_type": "SEGMENT",
            "type_name": "Steel Pipe",
            "storey_name": "Floor 1",
            "system_name": "B1",
            "canonical": {
                "diameter_mm": 50,
                "size_filled": True,
                "material_name": "Steel",
            },
            "params": {
                "ADSK_Номер секции": "1",
                "BRU_ЧастьСистемы": "Supply",
                "BRU_Система": "B1",
                "ADSK_Этаж": "Floor 1",
                "CUBE_Сокращение для системы": "B1",
                "BRU_Вид": "Pipe",
                "Размер": "50",
                "ADSK_Размер": "50",
                "Толщина стенки": "4",
                "ADSK_Толщина стенки": "4",
                "Длина": "3000",
                "Стадия возведения": "Main",
                "Толщина изоляции": "50",
            },
        }
        for rule in DEFAULT_RULES:
            if "IfcPipeSegment" in rule["applies_to"].get("ifc_classes", []):
                passed, msg = eval_rule(rule, perfect_element)
                if passed is False:
                    pytest.fail(f"Rule {rule['rule_key']} failed for complete element: {msg}")
