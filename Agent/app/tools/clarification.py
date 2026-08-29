from langchain_core.tools import tool

CLARIFICATION_TOOL_NAME = "request_clarification"


@tool(CLARIFICATION_TOOL_NAME)
def request_clarification(field: str, question: str, options: list[str]) -> str:
    """Ask the user to pick a value for a field from a small, bounded set of options,
    to be shown as buttons instead of typed as free text.

    Use this only when the field has a natural small set of choices (e.g. a due-date
    shortcut like "today"/"tomorrow"/"next week", or an existing category). For
    open-ended or free-text fields, ask a normal question instead of using this tool.

    field: the name of the field being clarified (e.g. "due_date", "category").
    question: a short question to show the user.
    options: 2-5 short option labels the user can choose from.
    """
    raise NotImplementedError("request_clarification is intercepted by the graph before execution")
