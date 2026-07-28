"""Unit tests for AI adapters (ai_parser and speech_to_text)."""

import json
from unittest.mock import patch, MagicMock, mock_open

from expense_manager.ai.ai_parser import parse_expense, _validate_expense_json, _build_prompt
from expense_manager.ai.speech_to_text import transcribe
from expense_manager.ai.exceptions import ExpenseParsingError, SpeechTranscriptionError
from expense_manager.constants.ai import ExpenseParsingConfig, SpeechToTextConfig


# ------------------------------------------------------------------
# ai_parser.parse_expense
# ------------------------------------------------------------------


class TestParseExpenseMockMode:

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=True)
    def test_mock_returns_fallback_category(self, _mock):
        result = parse_expense("spent 200 on lunch", ["Food", "Transport"])
        self.assertEqual(result["amount"], 200.0)
        self.assertEqual(result["category"], "Food")
        self.assertIn("spent 200 on lunch", result["description"])

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=True)
    def test_mock_with_empty_categories(self, _mock):
        result = parse_expense("something", [])
        self.assertEqual(result["category"], ExpenseParsingConfig.FALLBACK_CATEGORY)

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=True)
    def test_mock_always_returns_today(self, _mock):
        from frappe.utils import today
        result = parse_expense("test", ["Food"])
        self.assertEqual(str(result["expense_date"]), today())


class TestParseExpenseRealMode:

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=False)
    @patch("expense_manager.ai.ai_parser.get_openai_api_key", return_value="test-key")
    @patch("expense_manager.ai.ai_parser.get_openai_model", return_value="gpt-4o-mini")
    def test_successful_parse(self, _mock_model, _mock_key, _mock_api):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "amount": 150.0,
            "category": "Food",
            "description": "Lunch at cafe",
            "date": "2026-07-15",
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("expense_manager.ai.ai_parser.OpenAI", return_value=mock_client):
            result = parse_expense("I spent 150 on lunch", ["Food", "Transport"])
            self.assertEqual(result["amount"], 150.0)
            self.assertEqual(result["category"], "Food")
            self.assertEqual(result["description"], "Lunch at cafe")

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=False)
    @patch("expense_manager.ai.ai_parser.get_openai_api_key", return_value="test-key")
    @patch("expense_manager.ai.ai_parser.get_openai_model", return_value="gpt-4o-mini")
    def test_empty_response_raises(self, _mock_model, _mock_key, _mock_api):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("expense_manager.ai.ai_parser.OpenAI", return_value=mock_client):
            with self.assertRaises(ExpenseParsingError):
                parse_expense("test", ["Food"])

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=False)
    @patch("expense_manager.ai.ai_parser.get_openai_api_key", return_value="test-key")
    @patch("expense_manager.ai.ai_parser.get_openai_model", return_value="gpt-4o-mini")
    def test_invalid_json_raises(self, _mock_model, _mock_key, _mock_api):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not json at all"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("expense_manager.ai.ai_parser.OpenAI", return_value=mock_client):
            with self.assertRaises(ExpenseParsingError):
                parse_expense("test", ["Food"])

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=False)
    @patch("expense_manager.ai.ai_parser.get_openai_api_key", return_value="test-key")
    @patch("expense_manager.ai.ai_parser.get_openai_model", return_value="gpt-4o-mini")
    def test_non_dict_json_raises(self, _mock_model, _mock_key, _mock_api):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([1, 2, 3])

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("expense_manager.ai.ai_parser.OpenAI", return_value=mock_client):
            with self.assertRaises(ExpenseParsingError):
                parse_expense("test", ["Food"])

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=False)
    @patch("expense_manager.ai.ai_parser.get_openai_api_key", return_value="test-key")
    @patch("expense_manager.ai.ai_parser.get_openai_model", return_value="gpt-4o-mini")
    def test_missing_keys_raises(self, _mock_model, _mock_key, _mock_api):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "amount": 100.0,
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("expense_manager.ai.ai_parser.OpenAI", return_value=mock_client):
            with self.assertRaises(ExpenseParsingError):
                parse_expense("test", ["Food"])

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=False)
    @patch("expense_manager.ai.ai_parser.get_openai_api_key", return_value="test-key")
    @patch("expense_manager.ai.ai_parser.get_openai_model", return_value="gpt-4o-mini")
    def test_zero_amount_raises(self, _mock_model, _mock_key, _mock_api):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "amount": 0,
            "category": "Food",
            "description": "test",
            "date": "2026-07-15",
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("expense_manager.ai.ai_parser.OpenAI", return_value=mock_client):
            with self.assertRaises(ExpenseParsingError):
                parse_expense("test", ["Food"])

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=False)
    @patch("expense_manager.ai.ai_parser.get_openai_api_key", return_value="test-key")
    @patch("expense_manager.ai.ai_parser.get_openai_model", return_value="gpt-4o-mini")
    def test_unknown_category_becomes_fallback(self, _mock_model, _mock_key, _mock_api):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "amount": 100.0,
            "category": "UnknownCategory",
            "description": "test",
            "date": "2026-07-15",
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("expense_manager.ai.ai_parser.OpenAI", return_value=mock_client):
            result = parse_expense("test", ["Food", "Transport"])
            self.assertEqual(result["category"], ExpenseParsingConfig.FALLBACK_CATEGORY)


# ------------------------------------------------------------------
# ai_parser._validate_expense_json
# ------------------------------------------------------------------


class TestValidateExpenseJson:

    def test_empty_string_raises(self):
        with self.assertRaises(ExpenseParsingError):
            _validate_expense_json("", ["Food"])

    def test_none_raises(self):
        with self.assertRaises(ExpenseParsingError):
            _validate_expense_json(None, ["Food"])

    def test_invalid_json_string_raises(self):
        with self.assertRaises(ExpenseParsingError):
            _validate_expense_json("not json", ["Food"])

    def test_non_dict_json_raises(self):
        with self.assertRaises(ExpenseParsingError):
            _validate_expense_json(json.dumps([1, 2]), ["Food"])

    def test_missing_keys_raises(self):
        raw = json.dumps({"amount": 100})
        with self.assertRaises(ExpenseParsingError):
            _validate_expense_json(raw, ["Food"])

    def test_negative_amount_raises(self):
        raw = json.dumps({
            "amount": -50,
            "category": "Food",
            "description": "test",
            "date": "2026-07-15",
        })
        with self.assertRaises(ExpenseParsingError):
            _validate_expense_json(raw, ["Food"])

    def test_valid_response(self):
        raw = json.dumps({
            "amount": 200.0,
            "category": "Food",
            "description": "Lunch",
            "date": "2026-07-15",
        })
        result = _validate_expense_json(raw, ["Food", "Transport"])
        self.assertEqual(result["amount"], 200.0)
        self.assertEqual(result["category"], "Food")

    def test_null_date_uses_today(self):
        from frappe.utils import today
        raw = json.dumps({
            "amount": 100.0,
            "category": "Food",
            "description": "test",
            "date": None,
        })
        result = _validate_expense_json(raw, ["Food"])
        self.assertEqual(str(result["expense_date"]), today())


# ------------------------------------------------------------------
# ai_parser._build_prompt
# ------------------------------------------------------------------


class TestBuildPrompt:

    def test_contains_categories(self):
        messages = _build_prompt("spent 100", ["Food", "Transport"])
        system_content = messages[0]["content"]
        self.assertIn("Food", system_content)
        self.assertIn("Transport", system_content)

    def test_user_message_is_text(self):
        messages = _build_prompt("spent 100", ["Food"])
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], "spent 100")

    def test_empty_categories_uses_fallback(self):
        messages = _build_prompt("test", [])
        system_content = messages[0]["content"]
        self.assertIn(ExpenseParsingConfig.FALLBACK_CATEGORY, system_content)


# ------------------------------------------------------------------
# speech_to_text.transcribe
# ------------------------------------------------------------------


class TestTranscribeMockMode:

    @patch("expense_manager.ai.speech_to_text.get_use_mock_ai_apis", return_value=True)
    def test_mock_returns_sample_text(self, _mock):
        result = transcribe("/tmp/test.oga")
        self.assertEqual(result, "I spent 200 on Zomato")


class TestTranscribeRealMode:

    @patch("expense_manager.ai.speech_to_text.get_use_mock_ai_apis", return_value=False)
    @patch("expense_manager.ai.speech_to_text.get_sarvam_api_key", return_value="test-key")
    def test_successful_transcription(self, _mock_key, _mock_api):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"transcript": "I spent 200 on lunch"}

        with patch("expense_manager.ai.speech_to_text.requests.post", return_value=mock_response):
            with patch("builtins.open", mock_open(read_data=b"audio-data")):
                result = transcribe("/tmp/test.oga")
                self.assertEqual(result, "I spent 200 on lunch")

    @patch("expense_manager.ai.speech_to_text.get_use_mock_ai_apis", return_value=False)
    @patch("expense_manager.ai.speech_to_text.get_sarvam_api_key", return_value="test-key")
    def test_empty_transcript_raises(self, _mock_key, _mock_api):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"transcript": ""}

        with patch("expense_manager.ai.speech_to_text.requests.post", return_value=mock_response):
            with patch("builtins.open", mock_open(read_data=b"audio-data")):
                with self.assertRaises(SpeechTranscriptionError):
                    transcribe("/tmp/test.oga")

    @patch("expense_manager.ai.speech_to_text.get_use_mock_ai_apis", return_value=False)
    @patch("expense_manager.ai.speech_to_text.get_sarvam_api_key", return_value="test-key")
    def test_whitespace_transcript_raises(self, _mock_key, _mock_api):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"transcript": "   "}

        with patch("expense_manager.ai.speech_to_text.requests.post", return_value=mock_response):
            with patch("builtins.open", mock_open(read_data=b"audio-data")):
                with self.assertRaises(SpeechTranscriptionError):
                    transcribe("/tmp/test.oga")

    @patch("expense_manager.ai.speech_to_text.get_use_mock_ai_apis", return_value=False)
    @patch("expense_manager.ai.speech_to_text.get_sarvam_api_key", return_value="test-key")
    def test_client_error_raises(self, _mock_key, _mock_api):
        mock_response = MagicMock()
        mock_response.status_code = 400

        with patch("expense_manager.ai.speech_to_text.requests.post", return_value=mock_response):
            with patch("builtins.open", mock_open(read_data=b"audio-data")):
                with self.assertRaises(SpeechTranscriptionError):
                    transcribe("/tmp/test.oga")

    @patch("expense_manager.ai.speech_to_text.get_use_mock_ai_apis", return_value=False)
    @patch("expense_manager.ai.speech_to_text.get_sarvam_api_key", return_value="test-key")
    @patch("expense_manager.ai.speech_to_text.time.sleep")
    def test_retries_on_network_error(self, _mock_sleep, _mock_key, _mock_api):
        import requests as req_lib

        mock_post = MagicMock(side_effect=req_lib.exceptions.ConnectionError("fail"))

        with patch("expense_manager.ai.speech_to_text.requests.post", mock_post):
            with patch("builtins.open", mock_open(read_data=b"audio-data")):
                with self.assertRaises(SpeechTranscriptionError):
                    transcribe("/tmp/test.oga")
                self.assertEqual(mock_post.call_count, SpeechToTextConfig.MAX_RETRIES + 1)

    @patch("expense_manager.ai.speech_to_text.get_use_mock_ai_apis", return_value=False)
    @patch("expense_manager.ai.speech_to_text.get_sarvam_api_key", return_value="test-key")
    def test_strips_whitespace_from_transcript(self, _mock_key, _mock_api):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"transcript": "  I spent 200  "}

        with patch("expense_manager.ai.speech_to_text.requests.post", return_value=mock_response):
            with patch("builtins.open", mock_open(read_data=b"audio-data")):
                result = transcribe("/tmp/test.oga")
                self.assertEqual(result, "I spent 200")

    @patch("expense_manager.ai.speech_to_text.get_use_mock_ai_apis", return_value=False)
    @patch("expense_manager.ai.speech_to_text.get_sarvam_api_key", return_value="test-key")
    def test_sends_language_hint(self, _mock_key, _mock_api):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"transcript": "hello"}

        mock_post = MagicMock(return_value=mock_response)

        with patch("expense_manager.ai.speech_to_text.requests.post", mock_post):
            with patch("builtins.open", mock_open(read_data=b"audio-data")):
                transcribe("/tmp/test.oga", language_hint="hi")
                call_kwargs = mock_post.call_args
                self.assertEqual(call_kwargs[1]["data"]["language_code"], "hi")
