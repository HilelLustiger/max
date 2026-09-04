from app.tools.clarification import request_clarification
from app.tools.habits import HABIT_TOOLS
from app.tools.news import NEWS_TOOLS
from app.tools.tasks import TASK_TOOLS

ALL_TOOLS = [*TASK_TOOLS, *HABIT_TOOLS, *NEWS_TOOLS, request_clarification]
