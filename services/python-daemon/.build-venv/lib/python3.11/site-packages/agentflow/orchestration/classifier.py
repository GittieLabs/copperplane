"""
Complexity classifier for multi-step request detection.

Determines whether a user message requires a multi-step orchestration plan
(COMPLEX) or can be handled by a single workflow (SIMPLE).

Uses a two-stage approach:
1. Fast bypass: messages under _FAST_BYPASS_LIMIT words with no multi-step
   language markers return SIMPLE immediately (no LLM call).
2. LLM fallback: a direct Haiku call classifies ambiguous messages.

Defaults to SIMPLE on any failure to ensure graceful degradation.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("agentflow.orchestration")

_FAST_BYPASS_LIMIT = 20
_MULTI_STEP_MARKERS = (
    "and then",
    "after that",
    "followed by",
    "then write",
    "then create",
    "then send",
    "then research",
)


class ComplexityClassifier:
    """Classifies a message as SIMPLE or COMPLEX via fast pre-check + LLM call.

    Args:
        api_key: Anthropic API key for the Haiku classification call.
        model:   Model to use for classification. Defaults to claude-3-5-haiku-20241022.

    Example:
        classifier = ComplexityClassifier(api_key=os.getenv("ANTHROPIC_API_KEY"))
        result = await classifier.classify("Research AI agents and then write a LinkedIn post")
        # result == "COMPLEX"
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-haiku-20241022",
    ) -> None:
        self._api_key = api_key
        self._model = model

    async def classify(self, message: str) -> str:
        """Return 'SIMPLE' or 'COMPLEX'. Defaults to 'SIMPLE' on any failure.

        Args:
            message: The user message to classify.

        Returns:
            'COMPLEX' if the message requires multiple distinct workflow steps,
            'SIMPLE' otherwise.
        """
        # Fast path: short messages with no multi-step markers skip the LLM call
        if len(message.split()) < _FAST_BYPASS_LIMIT and not any(
            m in message.lower() for m in _MULTI_STEP_MARKERS
        ):
            return "SIMPLE"

        try:
            import anthropic as _anthropic

            client = _anthropic.AsyncAnthropic(api_key=self._api_key)
            resp = await client.messages.create(
                model=self._model,
                max_tokens=10,
                temperature=0.0,
                system=(
                    "Classify the user request as SIMPLE (single task, one workflow) or "
                    "COMPLEX (multiple distinct tasks each requiring their own workflow). "
                    "Reply with exactly one word: SIMPLE or COMPLEX."
                ),
                messages=[{"role": "user", "content": message}],
            )
            text = resp.content[0].text if resp.content else ""
            return "COMPLEX" if "COMPLEX" in text.upper() else "SIMPLE"

        except ImportError:
            logger.warning("anthropic package not installed; ComplexityClassifier defaulting to SIMPLE")
            return "SIMPLE"
        except Exception:
            logger.warning("ComplexityClassifier failed, defaulting to SIMPLE", exc_info=True)
            return "SIMPLE"
