from pydantic import BaseModel


class CapabilityModel(BaseModel):
    invoke: bool = False
    stream: bool = False
    checkpoint: bool = False
    resume: bool = False
    interrupt: bool = False
    human_in_loop: bool = False
    tool_events: bool = False
    model_events: bool = False
    token_usage: bool = False
    filesystem: bool = False
    subagents: bool = False

    def require(self, capability: str, framework: str) -> None:
        from dimoo_run.adapters.base.contract import CapabilityNotSupportedError

        if not bool(getattr(self, capability, False)):
            raise CapabilityNotSupportedError(capability=capability, framework=framework)
