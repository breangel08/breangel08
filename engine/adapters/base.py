from abc import ABC, abstractmethod


class ProductionAdapter(ABC):
    name: str
    version = "1.0.0"
    capabilities: dict
    constraints: list[str]

    def contract(self):
        return {"name": self.name, "version": self.version, "capabilities": self.capabilities, "constraints": self.constraints, "operations": ["initialize", "build", "validate", "package", "preview", "prepare_deployment"], "retry_limit": 3}

    def initialize(self, output):
        output.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def build(self, project, spec, output):
        pass

    @abstractmethod
    def validate(self, output):
        pass

    def prepare_deployment(self, project):
        return {"state": "PREPARED", "published": False, "requires_final_approval": True, "irreversible_operations": "Never automatic; separate credentialed deployment integration required"}
