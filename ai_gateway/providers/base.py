from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    def generate(self, model_id, messages, **options):
        raise NotImplementedError

    @abstractmethod
    def stream(self, model_id, messages, **options):
        raise NotImplementedError

    @abstractmethod
    def list_models(self):
        raise NotImplementedError
