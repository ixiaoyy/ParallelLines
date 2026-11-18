"""固定消费者的纯配置/中间像回归；不导入应用、不连接 Docker 或任何数据库。"""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'entertainment_sso.py'


def functions(*names, **scope):
    """仅编译选定纯函数，避免加载 Linux 运维入口或触发服务操作。"""
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    selected = [item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name in names]
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), 'exec'), scope)
    return scope


class InterruptedWriteContractTests(unittest.TestCase):
    def test_all_prefix_overwrites_before_and_after_truncate_are_recognized(self):
        matches = functions('intermediate_content_matches')['intermediate_content_matches']
        for source, target in ((b'aaaaaaaa', b'BBBBB'), (b'aaa', b'BBBBBBBB'),
                               (b'abcdef', b'abXYef'), (b'abcdef', b'abcdef')):
            for prefix in range(len(target) + 1):
                with self.subTest(source=source, target=target, prefix=prefix):
                    self.assertTrue(matches(target[:prefix] + source[prefix:], source, target))
            self.assertTrue(matches(target, source, target))

    def test_unrelated_drift_and_unknown_lengths_are_rejected(self):
        matches = functions('intermediate_content_matches')['intermediate_content_matches']
        self.assertFalse(matches(b'BBaBaaaa', b'aaaaaaaa', b'BBBBB'))
        self.assertFalse(matches(b'BBBB', b'aaaaaaaa', b'BBBBB'))
        self.assertFalse(matches(b'BBBBx', b'aaa', b'BBBBBBBB'))


class NativeLoginFlowContractTests(unittest.TestCase):
    def verify(self, flows):
        def check(value, code):
            if not value:
                raise ValueError(code)
        scope = functions('verify_sso_flows', native=SimpleNamespace(check=check),
                          login_flows=lambda: {'flows': flows})
        scope['verify_sso_flows']()

    def sso(self, provider='oidc-parallellines'):
        return {'type': 'm.login.sso', 'identity_providers': [{'id': provider}]}

    def test_synapse_native_application_service_flow_is_preserved(self):
        self.verify([self.sso(), {'type': 'm.login.token'}, {'type': 'm.login.application_service'}])

    def test_password_login_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'password_flow_still_enabled'):
            self.verify([self.sso(), {'type': 'm.login.password'}, {'type': 'm.login.application_service'}])

    def test_missing_or_different_provider_is_rejected(self):
        for flows in ([{'type': 'm.login.token'}], [self.sso('oidc-other')]):
            with self.subTest(flows=flows), self.assertRaisesRegex(ValueError, 'provider_missing_or_changed'):
                self.verify(flows)


if __name__ == '__main__':
    unittest.main()
