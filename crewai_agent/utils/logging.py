import re
import sys
import time
from ..config import agent_runs, _thread_local

# 更全面的 ANSI 转义码正则表达式
ANSI_ESCAPE = re.compile(r'''
    \x1B(?:[@-Z\\-_]|\[[0-9:;<=>?]*[A-MLP-Zhyccvuqx])
    | \x1B\[[0-9;]*[mGKF]
    | \x1B\(B
    | \x1B\[[0-9;]*[a-zA-Z]
''', re.VERBOSE)

class ThreadSpecificStdout:
    """
    一个专门的 stdout 包装类，用于捕获不同线程（即不同 Agent 运行实例）的输出。
    它会识别 CrewAI 的装饰框格式，并将其解析为结构化的日志存入 agent_runs。
    """
    def __init__(self, original_stream):
        self.original_stream = original_stream
        self.buffers = {}  # 存储每个 run_id 的缓冲区

    def write(self, data):
        # 始终将内容输出到原始控制台，保证终端能看到
        self.original_stream.write(data)
        
        # 获取当前线程绑定的 run_id
        run_id = getattr(_thread_local, 'run_id', None)
        
        # 如果当前线程没有 run_id (可能是 CrewAI 开启了子线程)，
        # 且当前只有一个正在运行的任务，则尝试归属于该任务。
        if not run_id:
            active_runs = [rid for rid, info in agent_runs.items() if info.get("status") in ["running", "waiting"]]
            if len(active_runs) == 1:
                run_id = active_runs[0]

        if not run_id or run_id not in agent_runs:
            return

        if run_id not in self.buffers:
            self.buffers[run_id] = ""
            
        self.buffers[run_id] += data
        
        # CrewAI 的日志块通常以 '╰' (下框边) 结束。
        if '╰' in data:
            self._process_buffer(run_id)

    def _process_buffer(self, run_id):
        content = self.buffers[run_id]
        if not content.strip():
            return

        # 1. 清理 ANSI 转义码
        clean_content = ANSI_ESCAPE.sub('', content)
        
        # 2. 寻找最后一个完整的框
        # 我们寻找 ╭ 到 ╰ 之间的内容
        box_pattern = re.compile(r'╭(.*?)╰[─\s]+╯', re.DOTALL)
        matches = list(box_pattern.finditer(clean_content))
        
        if not matches:
            # 如果没有找到完整的框，可能只是普通的 print
            if '\n' in clean_content and not any(c in clean_content for c in '╭╰│'):
                self._record_log(run_id, "系统提示", clean_content.strip())
                self.buffers[run_id] = ""
            return

        # 处理所有找到的框
        for match in matches:
            full_box = match.group(0)
            inner_content = match.group(1)
            
            # 提取标题
            title = "Agent 运行日志"
            title_line = full_box.split('\n')[0]
            title_match = re.search(r'[─\s]+(.*?)[─\s]+╮', title_line)
            if title_match:
                extracted_title = title_match.group(1).strip()
                if extracted_title:
                    title = re.sub(r'[^\w\s\u4e00-\u9fa5]', '', extracted_title).strip()

            # 提取主体内容
            lines = inner_content.split('\n')
            body_lines = []
            for line in lines:
                # 移除行首和行尾的 │ 符号以及空白
                stripped_line = line.strip().strip('│').strip()
                # 过滤掉包含过多边框字符的行
                if len(re.findall(r'[─╭╮╰╯]', stripped_line)) > 3:
                    continue
                # 过滤掉 CrewAI 的动态进度行
                if '🚀' in stripped_line or '📋' in stripped_line:
                    continue
                if stripped_line:
                    body_lines.append(stripped_line)
            
            final_body = "\n".join(body_lines)
            if final_body:
                self._record_log(run_id, title, final_body)

        # 清除已处理的部分
        last_match_end = matches[-1].end()
        self.buffers[run_id] = clean_content[last_match_end:]

    def _record_log(self, run_id, title, content):
        """记录日志到 agent_runs"""
        if "logs" not in agent_runs[run_id]:
            agent_runs[run_id]["logs"] = []
            
        # 避免重复记录完全相同的内容
        if agent_runs[run_id]["logs"]:
            if agent_runs[run_id]["logs"][-1]["content"] == content:
                return

        agent_runs[run_id]["logs"].append({
            "title": title,
            "content": content,
            "timestamp": time.time()
        })

    def flush(self):
        self.original_stream.flush()

    def isatty(self):
        return self.original_stream.isatty()

def setup_logging():
    """初始化日志重定向"""
    sys.stdout = ThreadSpecificStdout(sys.stdout)
    sys.stderr = ThreadSpecificStdout(sys.stderr)
