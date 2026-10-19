from unittest.mock import Mock, patch

from django.test import TestCase


class ChatViewTests(TestCase):
    @patch("gemini_assistant.views.os.getenv", return_value="test-api-key")
    @patch("gemini_assistant.views.time.sleep")
    @patch("gemini_assistant.views.requests.post")
    def test_retries_temporary_gemini_overload(
        self,
        post,
        sleep,
        getenv
    ):
        overloaded = Mock(ok=False, status_code=503, text="temporarily busy")
        success = Mock(
            ok=True,
            status_code=200,
            json=Mock(
                return_value={
                    "candidates": [
                        {"content": {"parts": [{"text": "Here is an answer."}]}}
                    ]
                }
            )
        )
        post.side_effect = [overloaded, success]

        response = self.client.post(
            "/api/chat/",
            data='{"prompt": "Explain gravity"}',
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"answer": "Here is an answer."})
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(1)

    @patch("gemini_assistant.views.os.getenv", return_value="test-api-key")
    @patch("gemini_assistant.views.time.sleep")
    @patch("gemini_assistant.views.requests.post")
    def test_returns_clear_error_after_repeated_gemini_overload(
        self,
        post,
        sleep,
        getenv
    ):
        post.return_value = Mock(
            ok=False,
            status_code=503,
            text="upstream overload details"
        )

        response = self.client.post(
            "/api/chat/",
            data='{"prompt": "Explain gravity"}',
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "error": (
                    "Gemini is temporarily busy. "
                    "Please try again in a moment."
                )
            }
        )
        self.assertEqual(post.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])
