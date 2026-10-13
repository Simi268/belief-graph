from dataclasses import dataclass, field
from uuid import uuid4

from .sdk import BeliefGraphSDK


@dataclass
class RunSession:
    """An isolated execution context for Belief-Graph."""

    sdk: BeliefGraphSDK = field(default_factory=BeliefGraphSDK)
    run_id: str = field(default_factory=lambda: str(uuid4()))

    @property
    def runtime(self):
        return self.sdk.runtime

    @property
    def graph(self):
        return self.sdk.graph

    def langgraph_adapter(self):
        """Create a LangGraph adapter bound to this run's SDK."""
        from .langgraph_adapter import LangGraphAdapter

        return LangGraphAdapter(belief_graph=self.sdk)

    def __getattr__(self, name):
        """Delegate SDK methods to this session's isolated SDK."""
        return getattr(self.sdk, name)