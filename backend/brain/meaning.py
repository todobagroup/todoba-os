from dataclasses import dataclass

from backend.brain.memory.models.experience import Experience


@dataclass
class MeaningResult:
    is_meaningful: bool
    reason: str


class MeaningAnalyzer:
    """
    Meaning Analyzer decides whether an experience has meaning.
    """

    def analyze(self, experience: Experience) -> MeaningResult:
        if not experience.content.strip():
            return MeaningResult(
                is_meaningful=False,
                reason="Experience has no content.",
            )

        return MeaningResult(
            is_meaningful=True,
            reason="Experience contains meaningful content.",
        )