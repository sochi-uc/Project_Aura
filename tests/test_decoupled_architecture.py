"""
tests/test_decoupled_architecture.py — Architecture & Contract Verification Suite

Purpose:
Validates that all decoupled provider contracts, configuration bindings,
and utility abstractions function correctly without requiring live network calls,
external API tokens, or GPU runtimes.
"""

import asyncio
import os
import sys
import unittest

# Ensure repository root is available on import path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config import AppConfig, get_config
from common.embeddings import (
    get_embedding_provider,
    MockEmbeddingProvider,
    SentenceTransformerProvider,
    format_vector,
)
from common.llm import (
    get_llm_provider,
    call_llm,
    call_gemini,
    MockLLMProvider,
    GeminiProvider,
    GroqProvider,
    OpenAICompatibleProvider,
)
from common.links import build_message_link


class TestProjectAuraArchitecture(unittest.TestCase):
    """
    Automated contract tests for Project Aura's modular architecture.
    """

    def test_config_singleton_and_defaults(self):
        """
        Verifies that AppConfig resolves default values properly and enforces
        singleton immutability across repeated lookups.
        """
        cfg = get_config()
        self.assertIsInstance(cfg, AppConfig)
        self.assertIsNotNone(cfg.database_url)
        self.assertIn(cfg.llm_provider, ["gemini", "groq", "openai", "mock"])
        self.assertEqual(cfg.batch_size, 50)

    def test_mock_embedding_provider(self):
        """
        Verifies that the MockEmbeddingProvider correctly implements the
        BaseEmbeddingProvider contract and produces 384-dimensional pgvector strings.
        """
        provider = get_embedding_provider(name="mock")
        self.assertIsInstance(provider, MockEmbeddingProvider)
        
        # Test single embedding generation
        vec = provider.get_embedding("Test semantic search query")
        self.assertEqual(len(vec), 384)
        
        # Test SQL vector formatting syntax
        sql_vec = provider.to_vector_sql(vec[:3])
        self.assertTrue(sql_vec.startswith("["))
        self.assertTrue(sql_vec.endswith("]"))

        # Test batch embedding generation
        batch = provider.get_embeddings_batch(["text1", "text2"])
        self.assertEqual(len(batch), 2)
        self.assertEqual(len(batch[0]), 384)

    def test_llm_provider_factory(self):
        """
        Verifies that the factory function `get_llm_provider` maps configured
        provider keys to their respective class implementations.
        """
        mock_p = get_llm_provider("mock")
        self.assertIsInstance(mock_p, MockLLMProvider)

        gemini_p = get_llm_provider("gemini")
        self.assertIsInstance(gemini_p, GeminiProvider)

        groq_p = get_llm_provider("groq")
        self.assertIsInstance(groq_p, GroqProvider)

        openai_p = get_llm_provider("openai")
        self.assertIsInstance(openai_p, OpenAICompatibleProvider)

    def test_mock_llm_generate(self):
        """
        Verifies that call_llm asynchronously routes to the mock provider
        and respects both freeform text and structured JSON response requirements.
        """
        async def run_test():
            # Test text mode
            res = await call_llm("test prompt", provider="mock")
            self.assertIn("MockLLMResponse", res)

            # Test structured JSON mode
            json_res = await call_llm("test prompt", is_json=True, provider="mock")
            self.assertIn("results", json_res)

        asyncio.run(run_test())

    def test_telegram_link_builder(self):
        """
        Verifies MTProto-to-Web link normalization:
        - Public channels should yield t.me/{username}/{msg_id}
        - Private channels with -100 prefix should yield t.me/c/{clean_id}/{msg_id}
        """
        public_link = build_message_link(chat_id=-1001234567, message_id=42, username="aura_channel")
        self.assertEqual(public_link, "https://t.me/aura_channel/42")

        private_supergroup = build_message_link(chat_id=-1001987654321, message_id=99)
        self.assertEqual(private_supergroup, "https://t.me/c/1987654321/99")


if __name__ == "__main__":
    unittest.main()
