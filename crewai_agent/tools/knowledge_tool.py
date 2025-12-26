import os
import json
import re
import pandas as pd
import logging
from typing import Optional, Type, Dict, Any
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

logger = logging.getLogger('crewai_agent')

try:
    from crewai_tools import CSVSearchTool
except ImportError:
    CSVSearchTool = None

from ..config import BASE_DIR, agent_runs, _thread_local, AgentStoppedException

def get_knowledge_base_description():
    """动态生成知识库工具的描述，包含当前所有 CSV 的元数据"""
    base_desc = """Search the knowledge base for error codes, troubleshooting steps, and asset information. 
    You should choose the appropriate source based on the query.
    Use precise=True when you have an exact ID, error code, or tag name.
    
    Current available sources:
    """
    
    data_dir = os.path.join(BASE_DIR, "data")
    metadata_path = os.path.join(data_dir, "metadata.json")
    
    metadata = {}
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except Exception as e:
            logger.error(f"Error loading metadata for description: {e}")

    # 扫描目录下的所有 CSV
    if os.path.exists(data_dir):
        csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
        for filename in csv_files:
            desc_info = metadata.get(filename, "No description provided.")
            if isinstance(desc_info, dict):
                desc = desc_info.get("description", "No description provided.")
                cols = desc_info.get("columns", "")
                if isinstance(cols, list):
                    cols = ", ".join(cols)
                base_desc += f"- {filename}: {desc} (Columns: {cols})\n"
            else:
                base_desc += f"- {filename}: {desc_info}\n"
    else:
        base_desc += "No CSV sources available yet.\n"
        
    return base_desc

class KnowledgeBaseInput(BaseModel):
    query: str = Field(..., description="The search term to look up in the knowledge base.")
    source: Optional[str] = Field(None, description="Optional: Specific CSV file to search in (e.g., 'assets.csv'). If not provided, searches all.")
    precise: bool = Field(False, description="Whether to use precise matching (exact string match) instead of fuzzy matching.")

class KnowledgeBaseTool(BaseTool):
    name: str = "knowledge_base"
    description: str = get_knowledge_base_description()
    args_schema: Type[BaseModel] = KnowledgeBaseInput
    _csv_search_tools: Dict[str, Any] = {} # 缓存 CSVSearchTool 实例

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 实例化时动态更新描述，确保获取最新的元数据
        self.description = get_knowledge_base_description()

    def _run(self, query: str, source: Optional[str] = None, precise: bool = False) -> str:
        # 检查是否已被手动停止
        run_id = getattr(_thread_local, 'run_id', None)
        if run_id and agent_runs.get(run_id, {}).get("status") == "stopped":
            raise AgentStoppedException("Agent execution stopped by user")

        try:
            data_dir = os.path.join(BASE_DIR, "data")
            if not os.path.exists(data_dir):
                return "Error: data directory not found."
            
            all_results = []
            if source:
                csv_files = [source] if source.endswith('.csv') else [f"{source}.csv"]
            else:
                csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
            
            if not csv_files:
                return f"No CSV files found matching '{source}'."

            for filename in csv_files:
                csv_path = os.path.join(data_dir, filename)
                if not os.path.exists(csv_path):
                    continue
                
                if precise:
                    # 【模式 1】精确匹配
                    try:
                        df = pd.read_csv(csv_path)
                        search_cols = [col for col in df.columns if not col.lower().endswith('_id')]
                        if not search_cols: search_cols = df.columns.tolist()
                        
                        mask = pd.Series([False] * len(df))
                        for col in search_cols:
                            mask |= df[col].astype(str).str.lower() == str(query).lower()
                        
                        result = df[mask]
                        if not result.empty:
                            result_copy = result.copy()
                            result_copy['source_file'] = filename
                            all_results.append(result_copy.to_string(index=False))
                    except Exception as e:
                        logger.error(f"Error in precise search for {filename}: {e}")
                
                else:
                    # 【模式 2】模糊匹配
                    success_semantic = False
                    if CSVSearchTool:
                        try:
                            if csv_path not in self._csv_search_tools:
                                self._csv_search_tools[csv_path] = CSVSearchTool(csv=csv_path)
                            
                            rag_result = self._csv_search_tools[csv_path]._run(search_query=query)
                            if rag_result and "Relevant Content" in rag_result:
                                all_results.append(f"--- Results from {filename} (Semantic Search) ---\n{rag_result}")
                                success_semantic = True
                        except Exception as e:
                            logger.error(f"Semantic search failed for {filename}, falling back to keyword: {e}")

                    if not success_semantic:
                        try:
                            df = pd.read_csv(csv_path)
                            search_cols = [col for col in df.columns if not col.lower().endswith('_id')]
                            if not search_cols: search_cols = df.columns.tolist()
                            
                            mask = pd.Series([False] * len(df))
                            query_words = str(query).lower().split()
                            for col in search_cols:
                                col_data = df[col].astype(str).str.lower()
                                for word in query_words:
                                    if len(word) > 1:
                                        mask |= col_data.str.contains(re.escape(word), na=False)
                            
                            result = df[mask]
                            if not result.empty:
                                result_copy = result.copy()
                                result_copy['source_file'] = filename
                                all_results.append(result_copy.to_string(index=False))
                        except Exception as e:
                            logger.error(f"Error in keyword search for {filename}: {e}")
            
            if not all_results:
                match_type = "precise" if precise else "fuzzy"
                return f"No {match_type} matches found in {source or 'knowledge base'} for '{query}'."
            
            if all(isinstance(r, str) for r in all_results):
                return "\n\n".join(all_results)
            else:
                final_output = ""
                for r in all_results:
                    final_output += str(r) + "\n\n"
                return final_output.strip()

        except Exception as e:
            error_msg = f"Error searching knowledge base: {str(e)}"
            logger.error(f"> 工具执行错误: {error_msg}")
            return error_msg
