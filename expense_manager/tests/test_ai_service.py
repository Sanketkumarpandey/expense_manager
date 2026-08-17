"""Unit tests for AI adapters (ai_parser and speech_to_text)."""

import json
from datetime import date, timedelta
from typing import ClassVar
from unittest import TestCase
from unittest.mock import MagicMock, mock_open, patch

from expense_manager.ai.ai_parser import _build_prompt, _validate_expense_json, parse_expense
from expense_manager.ai.exceptions import ExpenseParsingError, IncomeDetectedError, SpeechTranscriptionError
from expense_manager.ai.speech_to_text import transcribe
from expense_manager.constants.ai import ExpenseParsingConfig, SpeechToTextConfig
from expense_manager.services.ai_service import AIService
from expense_manager.services.exceptions import PocketMoneyExceededError

RECENT_DATE = (date.today() - timedelta(days=7)).isoformat()

# ------------------------------------------------------------------
# ai_parser.parse_expense
# ------------------------------------------------------------------


class TestParseExpenseMockMode(TestCase):
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


class TestParseExpenseRealMode(TestCase):
	@patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=False)
	@patch("expense_manager.ai.ai_parser.get_groq_api_key", return_value="test-key")
	@patch("expense_manager.ai.ai_parser.get_groq_model", return_value="llama-3.3-70b-versatile")
	def test_successful_parse(self, _mock_model, _mock_key, _mock_api):
		mock_response = MagicMock()
		mock_response.choices = [MagicMock()]
		mock_response.choices[0].message.content = json.dumps(
			{
				"amount": 150.0,
				"category": "Food",
				"description": "Lunch at cafe",
				"date": RECENT_DATE,
				"transaction_type": "expense",
			}
		)

		mock_client = MagicMock()
		mock_client.chat.completions.create.return_value = mock_response

		with patch("expense_manager.ai.ai_parser.Groq", return_value=mock_client):
			result = parse_expense("I spent 150 on lunch", ["Food", "Transport"])
			self.assertEqual(result["amount"], 150.0)
			self.assertEqual(result["category"], "Food")
			self.assertEqual(result["description"], "Lunch at cafe")

	@patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=False)
	@patch("expense_manager.ai.ai_parser.get_groq_api_key", return_value="test-key")
	@patch("expense_manager.ai.ai_parser.get_groq_model", return_value="llama-3.3-70b-versatile")
	def test_empty_response_raises(self, _mock_model, _mock_key, _mock_api):
		mock_response = MagicMock()
		mock_response.choices = [MagicMock()]
		mock_response.choices[0].message.content = None

		mock_client = MagicMock()
		mock_client.chat.completions.create.return_value = mock_response

		with patch("expense_manager.ai.ai_parser.Groq", return_value=mock_client):
			with self.assertRaises(ExpenseParsingError):
				parse_expense("test", ["Food"])

	@patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=False)
	@patch("expense_manager.ai.ai_parser.get_groq_api_key", return_value="test-key")
	@patch("expense_manager.ai.ai_parser.get_groq_model", return_value="llama-3.3-70b-versatile")
	def test_invalid_json_raises(self, _mock_model, _mock_key, _mock_api):
		mock_response = MagicMock()
		mock_response.choices = [MagicMock()]
		mock_response.choices[0].message.content = "not json at all"

		mock_client = MagicMock()
		mock_client.chat.completions.create.return_value = mock_response

		with patch("expense_manager.ai.ai_parser.Groq", return_value=mock_client):
			with self.assertRaises(ExpenseParsingError):
				parse_expense("test", ["Food"])

	@patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=False)
	@patch("expense_manager.ai.ai_parser.get_groq_api_key", return_value="test-key")
	@patch("expense_manager.ai.ai_parser.get_groq_model", return_value="llama-3.3-70b-versatile")
	def test_non_dict_json_raises(self, _mock_model, _mock_key, _mock_api):
		mock_response = MagicMock()
		mock_response.choices = [MagicMock()]
		mock_response.choices[0].message.content = json.dumps([1, 2, 3])

		mock_client = MagicMock()
		mock_client.chat.completions.create.return_value = mock_response

		with patch("expense_manager.ai.ai_parser.Groq", return_value=mock_client):
			with self.assertRaises(ExpenseParsingError):
				parse_expense("test", ["Food"])

	@patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=False)
	@patch("expense_manager.ai.ai_parser.get_groq_api_key", return_value="test-key")
	@patch("expense_manager.ai.ai_parser.get_groq_model", return_value="llama-3.3-70b-versatile")
	def test_missing_keys_raises(self, _mock_model, _mock_key, _mock_api):
		mock_response = MagicMock()
		mock_response.choices = [MagicMock()]
		mock_response.choices[0].message.content = json.dumps(
			{
				"amount": 100.0,
			}
		)

		mock_client = MagicMock()
		mock_client.chat.completions.create.return_value = mock_response

		with patch("expense_manager.ai.ai_parser.Groq", return_value=mock_client):
			with self.assertRaises(ExpenseParsingError):
				parse_expense("test", ["Food"])

	@patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=False)
	@patch("expense_manager.ai.ai_parser.get_groq_api_key", return_value="test-key")
	@patch("expense_manager.ai.ai_parser.get_groq_model", return_value="llama-3.3-70b-versatile")
	def test_zero_amount_raises(self, _mock_model, _mock_key, _mock_api):
		mock_response = MagicMock()
		mock_response.choices = [MagicMock()]
		mock_response.choices[0].message.content = json.dumps(
			{
				"amount": 0,
				"category": "Food",
				"description": "test",
				"date": RECENT_DATE,
				"transaction_type": "expense",
			}
		)

		mock_client = MagicMock()
		mock_client.chat.completions.create.return_value = mock_response

		with patch("expense_manager.ai.ai_parser.Groq", return_value=mock_client):
			with self.assertRaises(ExpenseParsingError):
				parse_expense("test", ["Food"])

	@patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=False)
	@patch("expense_manager.ai.ai_parser.get_groq_api_key", return_value="test-key")
	@patch("expense_manager.ai.ai_parser.get_groq_model", return_value="llama-3.3-70b-versatile")
	def test_unknown_category_becomes_fallback(self, _mock_model, _mock_key, _mock_api):
		mock_response = MagicMock()
		mock_response.choices = [MagicMock()]
		mock_response.choices[0].message.content = json.dumps(
			{
				"amount": 100.0,
				"category": "UnknownCategory",
				"description": "test",
				"date": RECENT_DATE,
				"transaction_type": "expense",
			}
		)

		mock_client = MagicMock()
		mock_client.chat.completions.create.return_value = mock_response

		with patch("expense_manager.ai.ai_parser.Groq", return_value=mock_client):
			result = parse_expense("test", ["Food", "Transport"])
			self.assertEqual(result["category"], ExpenseParsingConfig.FALLBACK_CATEGORY)


# ------------------------------------------------------------------
# ai_parser._validate_expense_json
# ------------------------------------------------------------------


class TestValidateExpenseJson(TestCase):
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
		raw = json.dumps(
			{
				"amount": -50,
				"category": "Food",
				"description": "test",
				"date": RECENT_DATE,
				"transaction_type": "expense",
			}
		)
		with self.assertRaises(ExpenseParsingError):
			_validate_expense_json(raw, ["Food"])

	def test_valid_response(self):
		raw = json.dumps(
			{
				"amount": 200.0,
				"category": "Food",
				"description": "Lunch",
				"date": RECENT_DATE,
				"transaction_type": "expense",
			}
		)
		result = _validate_expense_json(raw, ["Food", "Transport"])
		self.assertEqual(result["amount"], 200.0)
		self.assertEqual(result["category"], "Food")

	def test_null_date_uses_today(self):
		from frappe.utils import today

		raw = json.dumps(
			{
				"amount": 100.0,
				"category": "Food",
				"description": "test",
				"date": None,
				"transaction_type": "expense",
			}
		)
		result = _validate_expense_json(raw, ["Food"])
		self.assertEqual(str(result["expense_date"]), today())

	def test_case_insensitive_category_matches(self):
		raw = json.dumps(
			{
				"amount": 50.0,
				"category": "food",
				"description": "lunch",
				"date": RECENT_DATE,
				"transaction_type": "expense",
			}
		)
		result = _validate_expense_json(raw, ["Food", "Transport"])
		self.assertEqual(result["category"], "Food")

	def test_alias_category_resolves(self):
		raw = json.dumps(
			{
				"amount": 300.0,
				"category": "zomato",
				"description": "dinner",
				"date": RECENT_DATE,
				"transaction_type": "expense",
			}
		)
		result = _validate_expense_json(raw, ["Food", "Food Delivery", "Transport"])
		self.assertEqual(result["category"], "Food Delivery")


# ------------------------------------------------------------------
# ai_parser._build_prompt
# ------------------------------------------------------------------


class TestBuildPrompt(TestCase):
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
# ai_parser._resolve_category_name
# ------------------------------------------------------------------


class TestResolveCategoryName(TestCase):
	def test_exact_match(self):
		from expense_manager.ai.ai_parser import _resolve_category_name

		result = _resolve_category_name("Food", ["Food", "Transport"])
		self.assertEqual(result, "Food")

	def test_case_insensitive_match(self):
		from expense_manager.ai.ai_parser import _resolve_category_name

		result = _resolve_category_name("food", ["Food", "Transport"])
		self.assertEqual(result, "Food")

	def test_alias_maps_to_known_category(self):
		from expense_manager.ai.ai_parser import _resolve_category_name

		result = _resolve_category_name("zomato", ["Food Delivery", "Food", "Transport"])
		self.assertEqual(result, "Food Delivery")

	def test_alias_swiggy_maps_to_food_delivery(self):
		from expense_manager.ai.ai_parser import _resolve_category_name

		result = _resolve_category_name("swiggy", ["Food Delivery", "Food"])
		self.assertEqual(result, "Food Delivery")

	def test_alias_gym_maps_to_fitness(self):
		from expense_manager.ai.ai_parser import _resolve_category_name

		result = _resolve_category_name("gym", ["Fitness", "Healthcare"])
		self.assertEqual(result, "Fitness")

	def test_alias_uber_maps_to_transport(self):
		from expense_manager.ai.ai_parser import _resolve_category_name

		result = _resolve_category_name("uber", ["Transport", "Food"])
		self.assertEqual(result, "Transport")

	def test_unknown_falls_back(self):
		from expense_manager.ai.ai_parser import _resolve_category_name

		result = _resolve_category_name("SomeRandomThing", ["Food", "Transport"])
		self.assertEqual(result, ExpenseParsingConfig.FALLBACK_CATEGORY)

	def test_empty_input_falls_back(self):
		from expense_manager.ai.ai_parser import _resolve_category_name

		result = _resolve_category_name("", ["Food"])
		self.assertEqual(result, ExpenseParsingConfig.FALLBACK_CATEGORY)

	def test_none_input_falls_back(self):
		from expense_manager.ai.ai_parser import _resolve_category_name

		result = _resolve_category_name(None, ["Food"])
		self.assertEqual(result, ExpenseParsingConfig.FALLBACK_CATEGORY)

	def test_uncategorized_passthrough(self):
		from expense_manager.ai.ai_parser import _resolve_category_name

		result = _resolve_category_name("Uncategorized", ["Food"])
		self.assertEqual(result, "Uncategorized")

	def test_closest_match_resolves(self):
		from expense_manager.ai.ai_parser import _resolve_category_name

		result = _resolve_category_name("Food & Dining", ["Food", "Transport"])
		self.assertEqual(result, "Food")

	def test_alias_target_closest_match_resolves(self):
		from expense_manager.ai.ai_parser import _resolve_category_name

		result = _resolve_category_name("zomato", ["Food", "Gym"])
		self.assertEqual(result, "Food")

	def test_far_away_label_still_falls_back(self):
		from expense_manager.ai.ai_parser import _resolve_category_name

		result = _resolve_category_name("QuantumFinance", ["Food", "Transport"])
		self.assertEqual(result, ExpenseParsingConfig.FALLBACK_CATEGORY)


# ------------------------------------------------------------------
# speech_to_text.transcribe
# ------------------------------------------------------------------


class TestTranscribeMockMode(TestCase):
	@patch("expense_manager.ai.speech_to_text.get_use_mock_ai_apis", return_value=True)
	def test_mock_returns_sample_text(self, _mock):
		result = transcribe("/tmp/test.oga")
		self.assertEqual(result, "I spent 200 on Zomato")


class TestTranscribeRealMode(TestCase):
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


# ------------------------------------------------------------------
# AIService income guardrails (keyword pre-filter)
# ------------------------------------------------------------------


class TestAIServiceIncomeGuardrails(TestCase):
	def test_keyword_refund_triggers(self):
		with patch("expense_manager.services.ai_service.CategoryService.list_categories", return_value=[]):
			with self.assertRaises(IncomeDetectedError):
				AIService.create_expense_from_text("user@x.com", "got a refund of 200 from Amazon")

	def test_keyword_credit_triggers(self):
		with patch("expense_manager.services.ai_service.CategoryService.list_categories", return_value=[]):
			with self.assertRaises(IncomeDetectedError):
				AIService.create_expense_from_text("user@x.com", "received 500 credit")

	def test_keyword_cashback_triggers(self):
		with patch("expense_manager.services.ai_service.CategoryService.list_categories", return_value=[]):
			with self.assertRaises(IncomeDetectedError):
				AIService.create_expense_from_text("user@x.com", "cashback of 30 rupees")

	def test_keyword_got_money_triggers(self):
		with patch("expense_manager.services.ai_service.CategoryService.list_categories", return_value=[]):
			with self.assertRaises(IncomeDetectedError):
				AIService.create_expense_from_text("user@x.com", "got money from dad")

	def test_normal_expense_passes_keyword_filter(self):
		with (
			patch("expense_manager.services.ai_service.CategoryService.list_categories", return_value=[]),
			patch("expense_manager.services.ai_service.CategoryService.create_default_categories"),
			patch("expense_manager.services.ai_service.CategoryService.category_exists", return_value=False),
			patch("expense_manager.services.ai_service.CategoryService.create_category") as mock_cat_create,
			patch("expense_manager.services.ai_service.ai_parser.parse_expense") as mock_parse,
		):
			mock_cat_create.return_value.name = "cat-uncategorized"
			mock_parse.return_value = {
				"amount": 200.0,
				"category": "Uncategorized",
				"description": "lunch 250",
				"expense_date": "2026-07-27",
				"transaction_type": "expense",
			}
			with patch("expense_manager.services.ai_service.ExpenseService.create_expense") as mock_create:
				mock_doc = MagicMock()
				mock_doc.name = "exp-test"
				mock_create.return_value = mock_doc
				result = AIService.create_expense_from_text("user@x.com", "lunch 250")
				self.assertEqual(result.name, "exp-test")

	def test_transaction_type_income_rejected(self):
		with (
			patch("expense_manager.services.ai_service.CategoryService.list_categories", return_value=[]),
			patch("expense_manager.services.ai_service.ai_parser.parse_expense") as mock_parse,
		):
			mock_parse.return_value = {
				"amount": 500.0,
				"category": "Uncategorized",
				"description": "salary credit",
				"expense_date": "2026-07-27",
				"transaction_type": "income",
			}
			with self.assertRaises(IncomeDetectedError):
				AIService.create_expense_from_text("user@x.com", "salary credited")


# ------------------------------------------------------------------
# AIService._resolve_category (canonical live-list resolution)
# ------------------------------------------------------------------


class TestAIServiceCategoryResolution(TestCase):
	KNOWN: ClassVar[list[dict]] = [
		{"name": "cat-food-001", "category_name": "Food"},
		{"name": "cat-gym-001", "category_name": "Gym"},
		{"name": "cat-med-001", "category_name": "Medical"},
	]

	def test_exact_match_returns_live_id(self):
		result = AIService._resolve_category("user@x.com", "Food", self.KNOWN)
		self.assertEqual(result, "cat-food-001")

	def test_case_insensitive_exact_match(self):
		result = AIService._resolve_category("user@x.com", "food", self.KNOWN)
		self.assertEqual(result, "cat-food-001")

	def test_brand_alias_resolves_to_closest_live_category(self):
		# Live list has no "Food Delivery"; "zomato" alias lands on "Food".
		result = AIService._resolve_category("user@x.com", "zomato", self.KNOWN)
		self.assertEqual(result, "cat-food-001")

	def test_gym_alias_maps_to_live_gym_name(self):
		# Live list calls it "Gym" while the alias table targets "Fitness".
		result = AIService._resolve_category("user@x.com", "gym", self.KNOWN)
		self.assertEqual(result, "cat-gym-001")

	def test_near_miss_llm_label_resolves_to_closest(self):
		result = AIService._resolve_category("user@x.com", "Food & Dining", self.KNOWN)
		self.assertEqual(result, "cat-food-001")

	def test_no_match_creates_fallback_category(self):
		with (
			patch("expense_manager.services.ai_service.CategoryService.category_exists", return_value=False),
			patch("expense_manager.services.ai_service.CategoryService.create_category") as mock_create,
		):
			mock_create.return_value.name = "cat-uncat-001"
			result = AIService._resolve_category("user@x.com", "QuantumFinance", self.KNOWN)
			self.assertEqual(result, "cat-uncat-001")
			mock_create.assert_called_once_with("user@x.com", ExpenseParsingConfig.FALLBACK_CATEGORY)


# ------------------------------------------------------------------
# Free-text / voice parity: default seeding + same resolution
# ------------------------------------------------------------------


class TestAIServiceCategorySeeding(TestCase):
	SEEDED: ClassVar[list[dict]] = [{"name": "cat-food-001", "category_name": "Food"}]

	def _parse_result(self):
		return {
			"amount": 200.0,
			"category": "Food",
			"description": "lunch",
			"expense_date": "2026-07-27",
			"transaction_type": "expense",
		}

	def test_text_creation_seeds_defaults_when_no_categories(self):
		with (
			patch(
				"expense_manager.services.ai_service.CategoryService.list_categories",
				side_effect=[[], self.SEEDED],
			),
			patch(
				"expense_manager.services.ai_service.CategoryService.create_default_categories"
			) as mock_seed,
			patch(
				"expense_manager.services.ai_service.ai_parser.parse_expense",
				return_value=self._parse_result(),
			) as mock_parse,
			patch("expense_manager.services.ai_service.ExpenseService.create_expense") as mock_create,
		):
			mock_doc = MagicMock()
			mock_doc.name = "exp-text-001"
			mock_create.return_value = mock_doc

			result = AIService.create_expense_from_text("user@x.com", "lunch 200")

			mock_seed.assert_called_once_with("user@x.com")
			self.assertEqual(mock_parse.call_args[0][1], ["Food"])
			_, kwargs = mock_create.call_args
			self.assertEqual(kwargs["category"], "cat-food-001")
			self.assertEqual(result.name, "exp-text-001")

	def test_voice_creation_seeds_defaults_when_no_categories(self):
		with (
			patch(
				"expense_manager.services.ai_service.CategoryService.list_categories",
				side_effect=[[], self.SEEDED],
			),
			patch(
				"expense_manager.services.ai_service.CategoryService.create_default_categories"
			) as mock_seed,
			patch("expense_manager.ai.speech_to_text.transcribe", return_value="I spent 200 on lunch"),
			patch(
				"expense_manager.services.ai_service.ai_parser.parse_expense",
				return_value=self._parse_result(),
			) as mock_parse,
			patch("expense_manager.services.ai_service.ExpenseService.create_expense") as mock_create,
		):
			mock_doc = MagicMock()
			mock_doc.name = "exp-voice-001"
			mock_create.return_value = mock_doc

			result = AIService.create_expense_from_audio("user@x.com", "/tmp/test.oga")

			mock_seed.assert_called_once_with("user@x.com")
			self.assertEqual(mock_parse.call_args[0][1], ["Food"])
			_, kwargs = mock_create.call_args
			self.assertEqual(kwargs["category"], "cat-food-001")
			self.assertEqual(result.name, "exp-voice-001")


class TestAIServiceLoadKnownCategories(TestCase):
	"""The AI vocabulary is derived from the acting identity's category pool:
	guardian → all guardian-owned categories; dependent → allowed_categories
	(with the empty-table = all fallback), so an excluded category can never
	appear in the parser vocabulary."""

	def test_guardian_loads_all_guardian_categories(self):
		with patch(
			"expense_manager.services.ai_service.CategoryService.list_categories",
			return_value=[{"name": "cat-food-001", "category_name": "Food"}],
		) as mock_list:
			result = AIService._load_known_categories("user@x.com")

		self.assertEqual([row["category_name"] for row in result], ["Food"])
		mock_list.assert_called_once_with("user@x.com", active_only=True)

	def test_dependent_loads_only_allowed_categories(self):
		with patch(
			"expense_manager.services.ai_service.DependentService.list_allowed_categories",
			return_value=[{"name": "cat-gym-001", "category_name": "Gym"}],
		) as mock_list:
			result = AIService._load_known_categories("user@x.com", dependent="dep-son-001")

		self.assertEqual([row["category_name"] for row in result], ["Gym"])
		mock_list.assert_called_once_with("user@x.com", "dep-son-001", active_only=True)

	def test_excluded_category_falls_back_to_uncategorized(self):
		"""A parsed label that is not in the dependent's allowed vocabulary
		resolves to the fallback category, never a silently wrong category."""
		known = [{"name": "cat-gym-001", "category_name": "Gym"}]
		with (
			patch("expense_manager.services.ai_service.CategoryService.category_exists", return_value=False),
			patch("expense_manager.services.ai_service.CategoryService.create_category") as mock_create,
		):
			mock_create.return_value.name = "cat-uncat-001"
			result = AIService._resolve_category("user@x.com", "Travel", known)

		self.assertEqual(result, "cat-uncat-001")
		mock_create.assert_called_once_with("user@x.com", ExpenseParsingConfig.FALLBACK_CATEGORY)


class TestAIServicePocketMoneyHardBlock(TestCase):
	"""AIService enforces the pocket-money hard block for dependents before
	creating the expense, in both the free-text and voice paths."""

	PARSED: ClassVar[dict] = {
		"amount": 200.0,
		"category": "Food",
		"description": "lunch",
		"expense_date": "2026-07-27",
		"transaction_type": "expense",
	}

	def test_text_path_enforces_block_for_dependent(self):
		with (
			patch.object(
				AIService,
				"_load_known_categories",
				return_value=[{"name": "cat-food-001", "category_name": "Food"}],
			),
			patch("expense_manager.services.ai_service.ai_parser.parse_expense", return_value=self.PARSED),
			patch.object(AIService, "_resolve_category", return_value="cat-food-001"),
			patch("expense_manager.services.ai_service.ExpenseService.create_expense") as mock_create,
			patch(
				"expense_manager.services.ai_service.PocketMoneyService.enforce_available_balance"
			) as mock_enforce,
		):
			AIService.create_expense_from_text("user@x.com", "spent 200 on lunch", dependent="dep-son-001")

		mock_enforce.assert_called_once_with("user@x.com", "dep-son-001", 200.0)
		mock_create.assert_called_once()

	def test_voice_path_enforces_block_for_dependent(self):
		with (
			patch("expense_manager.ai.speech_to_text.transcribe", return_value="spent 200 on lunch"),
			patch.object(
				AIService,
				"_load_known_categories",
				return_value=[{"name": "cat-food-001", "category_name": "Food"}],
			),
			patch("expense_manager.services.ai_service.ai_parser.parse_expense", return_value=self.PARSED),
			patch.object(AIService, "_resolve_category", return_value="cat-food-001"),
			patch("expense_manager.services.ai_service.ExpenseService.create_expense") as mock_create,
			patch(
				"expense_manager.services.ai_service.PocketMoneyService.enforce_available_balance"
			) as mock_enforce,
		):
			AIService.create_expense_from_audio("user@x.com", "/tmp/test.oga", dependent="dep-son-001")

		mock_enforce.assert_called_once_with("user@x.com", "dep-son-001", 200.0)
		mock_create.assert_called_once()

	def test_guardian_path_skips_block(self):
		with (
			patch.object(
				AIService,
				"_load_known_categories",
				return_value=[{"name": "cat-food-001", "category_name": "Food"}],
			),
			patch("expense_manager.services.ai_service.ai_parser.parse_expense", return_value=self.PARSED),
			patch.object(AIService, "_resolve_category", return_value="cat-food-001"),
			patch("expense_manager.services.ai_service.ExpenseService.create_expense") as mock_create,
			patch(
				"expense_manager.services.ai_service.PocketMoneyService.enforce_available_balance"
			) as mock_enforce,
		):
			AIService.create_expense_from_text("user@x.com", "spent 200 on lunch")

		mock_enforce.assert_not_called()
		mock_create.assert_called_once()

	def test_blocked_expense_skips_creation(self):
		with (
			patch.object(
				AIService,
				"_load_known_categories",
				return_value=[{"name": "cat-food-001", "category_name": "Food"}],
			),
			patch("expense_manager.services.ai_service.ai_parser.parse_expense", return_value=self.PARSED),
			patch.object(AIService, "_resolve_category", return_value="cat-food-001"),
			patch("expense_manager.services.ai_service.ExpenseService.create_expense") as mock_create,
			patch(
				"expense_manager.services.ai_service.PocketMoneyService.enforce_available_balance",
				side_effect=PocketMoneyExceededError("Not enough pocket money"),
			),
		):
			with self.assertRaises(PocketMoneyExceededError):
				AIService.create_expense_from_text(
					"user@x.com", "spent 200 on lunch", dependent="dep-son-001"
				)

		mock_create.assert_not_called()
