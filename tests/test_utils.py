import unittest

from src.utils.async_utils import bump_llm_calls, run_async, truncate


class TruncateTests(unittest.TestCase):
    def test_short_text_is_unchanged(self):
        self.assertEqual(truncate("hello", 10), "hello")

    def test_long_text_is_clipped_to_the_limit(self):
        self.assertEqual(truncate("abcdefghij", 4), "abcd")

    def test_exact_length_is_unchanged(self):
        self.assertEqual(truncate("abcd", 4), "abcd")

    def test_zero_limit_gives_empty_string(self):
        self.assertEqual(truncate("abc", 0), "")

    def test_non_strings_are_converted_first(self):
        self.assertEqual(truncate(12345, 3), "123")
        self.assertEqual(truncate(None, 10), "None")
        self.assertEqual(truncate({"a": 1}, 100), "{'a': 1}")

    def test_result_is_always_a_string(self):
        self.assertIsInstance(truncate([1, 2, 3], 50), str)


class BumpLlmCallsTests(unittest.TestCase):
    def test_increments_existing_count(self):
        self.assertEqual(bump_llm_calls({"llm_calls": 3}), 4)

    def test_missing_key_starts_from_zero(self):
        self.assertEqual(bump_llm_calls({}), 1)

    def test_custom_increment(self):
        self.assertEqual(bump_llm_calls({"llm_calls": 2}, count=3), 5)

    def test_does_not_mutate_the_state(self):
        state = {"llm_calls": 1}
        bump_llm_calls(state)
        self.assertEqual(state, {"llm_calls": 1})


class RunAsyncTests(unittest.TestCase):
    def test_returns_the_coroutine_result(self):
        async def work():
            return 5

        self.assertEqual(run_async(work()), 5)

    def test_propagates_exceptions(self):
        async def boom():
            raise ValueError("nope")

        with self.assertRaises(ValueError):
            run_async(boom())


if __name__ == "__main__":
    unittest.main()
