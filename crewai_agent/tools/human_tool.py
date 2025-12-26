import time
from crewai.tools import BaseTool
from ..config import agent_runs, _thread_local, AgentStoppedException

class HumanInputManager:
    """Manages human input requests from the agent to the web UI."""
    @staticmethod
    def ask(run_id: str, prompt: str) -> str:
        if run_id in agent_runs:
            agent_runs[run_id]["status"] = "waiting"
            agent_runs[run_id]["prompt"] = prompt
            agent_runs[run_id]["event"].clear()
            
            # Wait for the web UI to provide input with a timeout
            timeout = 300 # 5 minutes
            
            is_set = agent_runs[run_id]["event"].wait(timeout=timeout)
            
            # 检查是否因为停止而被唤醒
            if agent_runs[run_id].get("status") == "stopped":
                raise AgentStoppedException("Agent execution stopped by user during human input")

            if not is_set:
                agent_runs[run_id]["status"] = "error"
                agent_runs[run_id]["result"] = "Human input timeout"
                return "Error: Human input timeout"
                
            agent_runs[run_id]["status"] = "running"
            agent_runs[run_id]["prompt"] = None
            response = agent_runs[run_id]["response"]
            agent_runs[run_id]["response"] = None # Clear for next time
            
            # 记录人类反馈到日志，以便前端渲染
            if "logs" not in agent_runs[run_id]:
                agent_runs[run_id]["logs"] = []
            agent_runs[run_id]["logs"].append({
                "title": "人类反馈",
                "content": response,
                "timestamp": time.time()
            })
            
            return response
        return "Error: run_id not found"

class AskHumanTool(BaseTool):
    name: str = "ask_human"
    description: str = "Use this tool to ask the user a question, get clarification, or request missing information. Use this whenever you are unsure or want to interact with the human."
    run_id: str = None

    def _run(self, prompt: str) -> str:        
        # 优先从线程局部变量获取 run_id，防止工具实例属性丢失
        run_id = getattr(_thread_local, 'run_id', self.run_id)
        
        if not run_id:
            # Fallback to standard input if no run_id (e.g. CLI)
            output = input(prompt)
            return output
            
        output = HumanInputManager.ask(run_id, prompt)
        return output
