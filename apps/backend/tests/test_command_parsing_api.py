"""真实数据库、HTTP 契约与只读保证。"""
from unittest.mock import patch

from sqlalchemy import func, select

from skillhub.models.errors import CommandParseError
from skillhub.models.schema.tables import metadata
from tests.api_command_test_case import ApiCommandTestCase

TEMPLATE = '<group name="interfaces*">\nInterface {{ name }} is {{ state }}\n</group>'
SCHEMA = {"type": "object", "properties": {"interfaces": {"type": "array", "items": {
    "type": "object", "properties": {"name": {"type": "string"}, "state": {"type": "string"}},
    "required": ["name", "state"], "additionalProperties": False}}}, "required": ["interfaces"], "additionalProperties": False}


class CommandParsingApiTest(ApiCommandTestCase):
    def create_command(self, key="interfaces", expression="show interfaces <interface>", **fields):
        """通过现有后台协议准备命令。"""
        response = self.client.post('/api/admin/system-commands', headers={"X-SkillHub-Admin-Key": "test-admin-key"},
                                    json={"key": key, "name": key, "expression": expression, "ttp": TEMPLATE, "outputSchema": SCHEMA, **fields})
        assert response.status_code == 200, response.text
        return response.json()

    def parse(self, **fields):
        """不携带后台密钥或 MCP Cookie 调用解析接口。"""
        return self.client.post('/api/command-library/parse', json={"input": "show interfaces eth0", "echo": "Interface eth0 is up\n", **fields})

    def counts(self):
        """核对所有业务表行数，覆盖审计、版本及访问事实。"""
        with self.engine.connect() as connection:
            return {table.name: connection.scalar(select(func.count()).select_from(table)) for table in metadata.sorted_tables}

    def test_contract_and_read_only(self):
        created = self.create_command()
        before = self.counts()
        response = self.parse(input="  show interfaces eth0  ")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['command']['id'] == created['id']
        assert body['result'] == {"interfaces": [{"name": "eth0", "state": "up"}]}
        assert body['validation'] == {"valid": True, "warnings": []}
        assert 'ttp' not in body['command'] and 'echo' not in body
        assert self.counts() == before
        self.create_command('bad-schema', 'show schema', outputSchema={"type": "object", "properties": {"required": {"type": "integer"}}, "required": ["required"]})
        warned = self.parse(input="show schema").json()
        assert warned['result'] == body['result']
        assert warned['validation']['valid'] is False
        assert any(w['code'] == 'SCHEMA_REQUIRED' for w in warned['validation']['warnings'])
        empty = self.parse(echo='').json()
        assert empty['result'] == {}
        assert any(w['code'] == 'TTP_EMPTY_RESULT' for w in empty['validation']['warnings'])

    def test_selection_and_no_fallback(self):
        self.create_command()
        exact = self.create_command('exact', 'show interfaces eth0')
        assert self.parse().json()['command']['id'] == exact['id']
        self.create_command('disabled', 'show interfaces eth0 [detail]', enabled=False)
        assert self.parse().json()['command']['id'] == exact['id']
        self.client.delete('/api/admin/system-commands/' + exact['id'], headers={"X-SkillHub-Admin-Key": "test-admin-key"})
        self.create_command('same', 'show <kind> eth0')
        response = self.parse()
        assert response.status_code == 409
        assert response.json()['code'] == 'COMMAND_AMBIGUOUS'
        assert len(response.json()['candidates']) == 2
        self.create_command('invalid', 'show broken', ttp='{{ x | unknown }}')
        self.create_command('fallback', 'show <name>')
        response = self.parse(input='show broken')
        assert response.status_code == 400 and response.json()['code'] == 'TTP_TEMPLATE_INVALID'

    def test_missing_partial_name_and_template(self):
        self.create_command()
        for command in ['show interfaces', 'interfaces', 'sh interfaces eth0', 'other']:
            response = self.parse(input=command)
            assert response.status_code == 404, response.text
            assert response.json()['code'] == 'COMMAND_NOT_FOUND'
        self.create_command('missing', 'show missing', ttp='')
        assert self.parse(input='show missing').json()['code'] == 'TTP_TEMPLATE_MISSING'

    def test_inputs_size_and_openapi(self):
        for fields in [{"input": " "}, {"input": 1}, {"input": "show\ninterfaces"}, {"echo": None}, {"extra": True}, {"input": "x" * 4001}]:
            response = self.parse(**fields)
            assert response.status_code == 422
            assert response.json()['code'] == 'INVALID_REQUEST'
        response = self.parse(echo='中' * 349526)
        assert response.status_code == 413 and response.json()['code'] == 'ECHO_TOO_LARGE'
        self.create_command()
        with patch('skillhub.services.command_parsing.run_parser', side_effect=CommandParseError('TTP_PARSE_TIMEOUT', '解析超时。', 504)):
            response = self.parse()
        assert response.status_code == 504 and response.json()['code'] == 'TTP_PARSE_TIMEOUT'
        contract = self.client.get('/openapi.json').json()
        endpoint = contract['paths']['/api/command-library/parse']['post']
        assert set(endpoint['responses']) >= {'200', '400', '404', '409', '413', '422', '504'}
        schema = contract['components']['schemas']['CommandParsePayload']
        assert schema['required'] == ['input', 'echo'] and schema['additionalProperties'] is False
