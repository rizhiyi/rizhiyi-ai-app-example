import os
import builtins
import logging
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

import openlit
openlit.init()

from crewai import Agent, Task, Crew, Process
from crewai.mcp import MCPServerStdio

# Import local modules
from .config import agent_runs, _thread_local, kimi_llm, AgentStoppedException, LOG_TOOLS_SERVER_PATH
from .utils.logging import setup_logging
from .tools.human_tool import HumanInputManager, AskHumanTool
from .tools.knowledge_tool import KnowledgeBaseTool

logger = logging.getLogger('crewai_agent')

# Initialize logging redirection
setup_logging()

def run_crew(query: str, history: list = None, allow_human_input: bool = True, run_id: str = None, base_url: str = None, api_key: str = None, username: str = None):
    # Set run_id for log capturing
    if run_id:
        _thread_local.run_id = run_id
        if "logs" not in agent_runs[run_id]:
            agent_runs[run_id]["logs"] = []

    # Prepare context from history
    context_str = ""
    if history:
        context_str = "以下是之前的对话历史，请参考这些信息来回答用户的新问题：\n"
        for msg in history:
            role_name = "用户" if msg.get('role') == 'user' else "助手"
            context_str += f"{role_name}: {msg.get('content')}\n"
        context_str += "\n当前新问题："

    # Set up tools for this run
    knowledge_tool = KnowledgeBaseTool()
    tools = [knowledge_tool]
    
    if allow_human_input:
        ask_tool = AskHumanTool()
        if run_id:
            ask_tool.run_id = run_id
        tools.append(ask_tool)
        
        # We also keep the monkeypatching as a fallback for internal CrewAI calls
        if run_id:
            original_input = builtins.input
            def web_input(prompt=""):
                return HumanInputManager.ask(run_id, prompt)
            builtins.input = web_input

    # 构造 username:api-key 格式
    formatted_api_key = f"{username}:{api_key}" if username and api_key else (api_key or "")

    # Create a local agent instance for this run to avoid global state conflicts
    local_log_assistant = Agent(
        role='Log Analysis Assistant',
        goal='Help users search logs in Rizhiyi and troubleshoot issues using the knowledge base.',
        backstory="""You are a helpful and cautious log analysis assistant. 
        You have access to a knowledge base (error codes, assets, solutions) and Rizhiyi log search.
        IMPORTANT: If a user's query is vague, or if you need more details to perform a log search, use the 'ask_human' tool to clarify.
        When searching logs, provide clear and concise analysis of the results.""",
        tools=tools,
        mcps=[
            MCPServerStdio(
                command="node",
                args=[LOG_TOOLS_SERVER_PATH] if LOG_TOOLS_SERVER_PATH else [],
                env={
                    "LOGEASE_BASE_URL": base_url or "",
                    "LOGEASE_API_KEY": formatted_api_key,
                    "LOGEASE_TLS_REJECT_UNAUTHORIZED": os.getenv("LOGEASE_TLS_REJECT_UNAUTHORIZED", "false"),
                    **os.environ
                },
                cache_tools_list=True,
            )
        ],
        verbose=True,
        allow_delegation=False,
        memory=True,
        llm=kimi_llm
    )
        
    try:
        # Task 1: Information Gathering and Problem Solving
        info_task = Task(
            description=f'{context_str}Answer the user query: "{query}". \n'
                        'Steps:\n'
                        '1. Search and analyze logs in Rizhiyi.\n'
                        '2. Search the knowledge base for error codes or assets if needed.\n'
                        '3. CRITICAL: If you need any clarification, use the "ask_human" tool to ask for details.',
            expected_output='A detailed response based on the log analysis and knowledge base information. If ask_human was used, incorporate the user\'s feedback.',
            agent=local_log_assistant
        )

        crew = Crew(
            agents=[local_log_assistant],
            tasks=[info_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        
        if run_id:
            agent_runs[run_id]["status"] = "completed"
            agent_runs[run_id]["result"] = str(result)
            
        return str(result)
    except AgentStoppedException:
        logger.info(f"Agent run {run_id} stopped by user.")
        if run_id:
            agent_runs[run_id]["status"] = "stopped"
            agent_runs[run_id]["result"] = "Task stopped by user."
    except Exception as e:
        if run_id:
            agent_runs[run_id]["status"] = "error"
            agent_runs[run_id]["result"] = str(e)
        raise e
    finally:
        if run_id and allow_human_input:
            # Restore original input
            builtins.input = original_input
