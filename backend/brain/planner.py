from backend.brain.models.experience import Experience
from backend.brain.models.task import Task


class Planner:
    def plan(self, experience: Experience) -> Task | None:
        if self._is_trading_plan(experience):
            return self._create_trading_task(experience)

        return None

    def _is_trading_plan(self, experience: Experience) -> bool:
        content = experience.content.upper()

        return (
            ("BUY" in content or "SELL" in content)
            and "SL" in content
            and "TP" in content
        )

    def _create_trading_task(self, experience: Experience) -> Task:
        return Task(
            title="Review Trading Plan",
            description=experience.content,
            department="Trading Operation",
            role="Trading Receptionist",
        )


planner = Planner()