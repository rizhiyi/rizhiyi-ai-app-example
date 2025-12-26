import os
import threading
from langchain_openai import ChatOpenAI

# Base directory of the project
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# MCP server path
LOG_TOOLS_SERVER_PATH = os.getenv("LOG_TOOLS_SERVER_PATH")

# Global state for agent runs and Human-in-the-loop
agent_runs = {}
_thread_local = threading.local()

class AgentStoppedException(Exception):
    """Exception raised when the agent run is manually stopped."""
    pass

# Configure Kimi (Moonshot) LLM using LangChain
kimi_llm = ChatOpenAI(
    model=os.getenv("MOONSHOT_MODEL", "moonshot-v1-8k"),
)
