import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock

from google.genai import errors, types

from backend.check_gemini import run_checks


class DiagnosticTests(unittest.TestCase):
    def client(self):
        client = Mock()
        client.models.list.return_value = [types.Model(
            name="models/test-flash", supported_actions=["generateContent"]
        )]
        return client

    def test_unknown_model_does_not_generate(self):
        client = self.client()
        with redirect_stdout(io.StringIO()) as output:
            code = run_checks(client, "unknown-model")
        self.assertEqual(code, 1)
        self.assertIn("목록에 설정한 모델이 없습니다", output.getvalue())
        client.models.generate_content.assert_not_called()

    def test_basic_success_and_tool_failure_are_distinguished(self):
        client = self.client()
        client.models.generate_content.side_effect = [
            types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
                role="model", parts=[types.Part.from_text(text="Hello")]
            ))]),
            errors.ServerError(504, {"error": {"message": "private-data"}}),
        ]
        with redirect_stdout(io.StringIO()) as output:
            code = run_checks(client, "test-flash")
        self.assertEqual(code, 1)
        self.assertIn("[2/3] 기본 요청 (도구 없이) 성공", output.getvalue())
        self.assertIn("[3/3] 도구 명세 포함 요청 실패 (HTTP 504)", output.getvalue())
        self.assertNotIn("private-data", output.getvalue())
        first, second = client.models.generate_content.call_args_list
        self.assertIsNone(first.kwargs["config"].tools)
        self.assertTrue(second.kwargs["config"].tools)
