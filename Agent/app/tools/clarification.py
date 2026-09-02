from langchain_core.tools import tool
from pydantic import BaseModel

CLARIFICATION_TOOL_NAME = "request_clarification"


class ClarificationOption(BaseModel):
    label: str
    value: str


@tool(CLARIFICATION_TOOL_NAME)
def request_clarification(
    tool: str,
    known_args: dict[str, str],
    field: str,
    question: str,
    options: list[ClarificationOption],
) -> str:
    """Ask the user to pick a value for a field from a small, bounded set of options,
    to be shown as buttons instead of typed as free text - and complete the tool call
    you were making, once they pick one.

    Use this only when the field has a natural small set of choices (e.g. a due-date
    shortcut like "today"/"tomorrow"/"next week", or an existing category). For
    open-ended or free-text fields, ask a normal question instead of using this tool.

    tool: the name of the tool you were about to call (e.g. "create_task").
    known_args: the arguments for that tool you've already determined (e.g. {"title": "Buy milk"}).
    field: the still-missing argument name (e.g. "due_date").
    question: a short question to show the user.
    options: 2-5 {label, value} pairs. label is shown on the button (in Hebrew); value is the
      exact literal value to pass as `field` if this option is chosen - resolve it yourself
      (e.g. a relative date like "today" into an ISO 8601 date, using today's date from the
      system prompt). Use value="" for an option that means "leave this field unset".
    """
    raise NotImplementedError("request_clarification is intercepted by the graph before execution")
