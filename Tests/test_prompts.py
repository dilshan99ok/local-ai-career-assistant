import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from Scripts import prompt_loader
from Scripts.ai_provider import OpenAIProvider


class FakeStream(list):
    def close(self):
        pass


class PromptLibraryTests(unittest.TestCase):
    def test_all_workflow_guidelines_are_readable(self):
        names = (
            "job-extraction-prompt", "job-extraction-system", "job-checklist",
            "cv-evidence-review", "cv-evidence-system", "json-output-system",
            "resume-suggestions", "resume-draft", "resume-screening-review",
            "resume-editor-system", "cover-letter", "cover-letter-system",
            "follow-up-email", "follow-up-system", "default-output-system",
        )
        self.assertEqual(prompt_loader.PROMPT_DIR.name, "Prompts")
        for name in names:
            with self.subTest(name=name):
                self.assertTrue(prompt_loader.load_prompt(name))

    def test_pasted_text_is_substituted_once_and_templates_are_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            prompt_dir = Path(directory)
            (prompt_dir / "example.md").write_text("Section {{SECTION_ID}}\n{{SECTION_TEXT}}", encoding="utf-8")
            with patch.object(prompt_loader, "PROMPT_DIR", prompt_dir):
                output = prompt_loader.render_prompt(
                    "example", SECTION_ID="s1", SECTION_TEXT="Literal {{SECTION_ID}} from job ad")
                self.assertEqual(output, "Section s1\nLiteral {{SECTION_ID}} from job ad")
                (prompt_dir / "example.md").write_text("Updated {{SECTION_ID}}: {{SECTION_TEXT}}", encoding="utf-8")
                self.assertEqual(
                    prompt_loader.render_prompt("example", SECTION_ID="s2", SECTION_TEXT="new text"),
                    "Updated s2: new text",
                )
                with self.assertRaises(ValueError):
                    prompt_loader.render_prompt("example", SECTION_ID="s1")
                with self.assertRaises(ValueError):
                    prompt_loader.load_prompt("../example")
                (prompt_dir / "example.md").write_text("Bad {{section_id}}", encoding="utf-8")
                with self.assertRaises(ValueError):
                    prompt_loader.render_prompt("example")

    def test_job_extraction_uses_versioned_template(self):
        description = "Graduate / Junior Infrastructure Engineer"
        prompt = prompt_loader.build_extraction_prompt(description)
        self.assertIn(description, prompt)
        self.assertNotIn("{{JOB_DESCRIPTION}}", prompt)

    def test_provider_sends_markdown_system_guidance(self):
        provider = OpenAIProvider.__new__(OpenAIProvider)
        provider.model = "test-model"
        provider.client = Mock()
        provider.client.responses.create.return_value = FakeStream([
            SimpleNamespace(type="response.output_text.delta", delta="editable text"),
            SimpleNamespace(type="response.completed"),
        ])
        self.assertEqual(provider.generate_text("task"), "editable text")
        self.assertEqual(
            provider.client.responses.create.call_args.kwargs["instructions"],
            prompt_loader.load_prompt("default-output-system"),
        )


if __name__ == "__main__":
    unittest.main()
