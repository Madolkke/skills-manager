from copy import deepcopy

import pytest

from skillhub.models.rules.workflows.expression import evaluate_expression, validate_binding_expression, validate_expression
from skillhub.models.rules.workflows.expression.registry import builtin_function_documents
from tests.api_command_test_case import ApiCommandTestCase

ADMIN = {"X-SkillHub-Admin-Key": "test-admin-key"}
PATH = "/api/admin/expression-functions"


def function_payload(name="probe"):
    """故意使用非字典排序参数，检查 JSONB 往返后的调用顺序。"""
    return {"name": name, "description": "验收声明", "body": "raise RuntimeError('must not execute')", "language": "python",
            "parameterSchema": {"type": "object", "properties": {"zvalue": {"type": "string"}, "amount": {"type": "integer"}},
                                "required": ["zvalue", "amount"], "additionalProperties": False},
            "returnSchema": {"type": "object", "properties": {"answer": {"type": "integer"}}, "required": ["answer"], "additionalProperties": False}}


class ExpressionFunctionCatalogTest(ApiCommandTestCase):
    def test_crud_contract_order_validation_and_deletion(self):
        """接口从保存到禁用删除均使用同一声明目录，body 不在公开契约中。"""
        assert self.client.get(PATH).status_code == 403
        response = self.client.post(PATH, headers=ADMIN, json=function_payload())
        assert response.status_code == 200, response.text
        item = response.json()
        assert list(item["parameterSchema"]["properties"]) == ["zvalue", "amount"]
        assert self.client.get(f"{PATH}/{item['id']}", headers=ADMIN).json() == item
        assert self.client.post(PATH, headers=ADMIN, json=function_payload()).status_code == 409
        functions = self.store.expression_function_contract()
        assert functions["probe"]["parameters"] == ["zvalue", "amount"]
        assert "body" not in functions["probe"]
        assert validate_expression("probe('x', 2).answer", {}, functions)["inferredType"]["kind"] == "integer"
        assert validate_binding_expression("probe('x', 2).answer", {}, {"type": "integer"}, functions)["assignable"]
        for source, code in [("probe(2, 'x')", "FUNCTION_ARGUMENT_TYPE_MISMATCH"), ("probe('x')", "FUNCTION_REQUIRED_ARGUMENT"),
                             ("probe('x', 2, 3)", "FUNCTION_TOO_MANY_ARGUMENTS"), ("probe('x', 2, amount=3)", "FUNCTION_DUPLICATE_ARGUMENT"),
                             ("probe('x', 2, unknown=3)", "FUNCTION_UNKNOWN_KEYWORD")]:
            assert code in {row["code"] for row in validate_expression(source, {}, functions)["diagnostics"]}
        with pytest.raises(ValueError, match="暂不支持运行"):
            evaluate_expression("probe('x', 2)", inputs={}, outputs={}, functions=functions)
        payload = {**function_payload(), "enabled": False}
        assert self.client.put(f"{PATH}/{item['id']}", headers=ADMIN, json=payload).status_code == 200
        assert self.store.expression_function_contract() == {}
        assert validate_expression("len('x')", {}, {})["diagnostics"][0]["code"] == "UNREGISTERED_CALL"
        assert self.client.delete(f"{PATH}/{item['id']}", headers=ADMIN).status_code == 200
        assert self.client.get(f"{PATH}/{item['id']}", headers=ADMIN).status_code == 404

    def test_invalid_schemas_and_builtin_compatibility(self):
        """拒绝非法声明，内置泛型和历史合法调用保持兼容。"""
        for change in [{"name": "_private"}, {"name": "class"}, {"body": " "}, {"parameterSchema": {"type": "string"}},
                       {"returnSchema": {"type": "array"}}, {"parameterSchema": {"type": "object", "properties": {}, "additionalProperties": "yes"}}]:
            assert self.client.post(PATH, headers=ADMIN, json={**function_payload(), **change}).status_code == 400
        nested = deepcopy(function_payload())
        nested["parameterSchema"]["properties"]["zvalue"] = {"type": "object", "properties": {"not-an-identifier": {"type": "string"}}}
        assert self.client.post(PATH, headers=ADMIN, json=nested).status_code == 200
        for document in builtin_function_documents():
            assert self.client.post(PATH, headers=ADMIN, json=document).status_code == 200
        functions = self.store.expression_function_contract()
        for source in ["min(1, 2)", "sum([1, 2])", "str()", "round(1.25, 1)", "len('abc')", "sorted([1, 2])"]:
            assert validate_expression(source, {}, functions)["diagnostics"] == []
        assert validate_expression("min([1, 2])", {}, functions)["inferredType"]["kind"] == "integer"
