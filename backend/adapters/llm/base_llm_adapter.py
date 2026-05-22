# abstract interface for llm adapters
# basically just forces everyone to implement handle() so the orcehstrator
# doesnt care if its claude or gpt or whatever

from abc import ABC, abstractmethod


class BaseLLMAdapter(ABC):

    @abstractmethod
    def handle(self, query: str, system_prompt=None, context: dict = None) -> dict:
        # subclasses gotta override this
        # query = the raw text from the user
        # context = optional extra stuff like calendar events or whatever
        # should return a dict with task_type, description, plan_steps, response_message
        pass
