import json
import os
import pandas as pd
import logging
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
from ..config import RizhiyiOAuthConfig

logger = logging.getLogger('oauth')

def generate_csv_description(df, filename):
    """
    根据 CSV 内容自动生成描述
    优先尝试使用 LLM (Moonshot/OpenAI)，如果没有配置则使用启发式模板
    """
    columns = df.columns.tolist()
    sample_data = df.head(3).to_dict(orient='records')
    
    # 获取环境变量
    api_key = os.getenv('OPENAI_API_KEY')
    base_url = os.getenv('OPENAI_BASE_URL', 'https://api.moonshot.cn/v1')
    model_name = os.getenv('MOONSHOT_MODEL', 'moonshot-v1-8k')

    if api_key:
        try:
            llm = ChatOpenAI(
                model_name=model_name,
                temperature=0,
                openai_api_base=base_url,
                openai_api_key=api_key
            )
            prompt = f"""
            你是一个知识库管理员。请分析以下 CSV 文件的列名和样本数据，然后生成一段简短的中文描述（不超过 50 字，以“该文件包含...”开头），说明该文件的用途。

            文件名: {filename}
            列名: {', '.join(columns)}
            样本数据: {json.dumps(sample_data, ensure_ascii=False)}
            
            描述:
            """
            response = llm.invoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            logger.error(f"LLM description generation failed: {e}")

    # 启发式兜底方案
    desc = f"该文件包含{', '.join(columns[:5])}"
    if len(columns) > 5:
        desc += " 等信息"
    else:
        desc += " 信息"
    
    # 尝试识别一些常见场景
    cols_str = " ".join(columns).lower()
    if any(k in cols_str for k in ['error', 'code', 'status']):
        desc = f"该文件主要包含系统错误码、状态信息及其含义，涉及 {', '.join(columns[:3])} 等字段。"
    elif any(k in cols_str for k in ['ip', 'host', 'asset', 'server']):
        desc = f"该文件主要包含服务器资产、IP 地址及相关负责人信息，涉及 {', '.join(columns[:3])} 等字段。"
    elif any(k in cols_str for k in ['user', 'name', 'email', 'phone']):
        desc = f"该文件主要包含用户信息、联系方式及权限细节，涉及 {', '.join(columns[:3])} 等字段。"
        
    return desc

def csv_manager(request):
    """CSV 文件管理页面"""
    user_info = request.session.get('user_info')
    if not user_info:
        return redirect('index')

    data_dir = settings.BASE_DIR / 'data'
    metadata_path = data_dir / 'metadata.json'
    
    if not data_dir.exists():
        data_dir.mkdir(parents=True)

    # 加载现有元数据
    metadata = {}
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'upload':
            uploaded_file = request.FILES.get('csv_file')
            description = request.POST.get('description', '')
            columns = request.POST.get('columns', '').strip()
            
            if uploaded_file and uploaded_file.name.endswith('.csv'):
                file_path = data_dir / uploaded_file.name
                
                # 先写入临时文件进行校验，或者直接写入
                with open(file_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)
                
                # 校验 CSV 合法性
                try:
                    # 尝试读取前几行来验证格式
                    df_check = pd.read_csv(file_path, nrows=5)
                    
                    # 如果用户没写列名，自动从读取的结果中提取
                    if not columns:
                        columns = ", ".join(df_check.columns.tolist())
                        logger.debug(f"Auto-extracted columns: {columns}")
                    
                    # 如果用户没写描述，自动生成描述
                    if not description:
                        description = generate_csv_description(df_check, uploaded_file.name)
                        logger.debug(f"Auto-generated description: {description}")
                    
                    # 更新元数据
                    metadata[uploaded_file.name] = {
                        'description': description,
                        'columns': columns
                    }
                    with open(metadata_path, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=4, ensure_ascii=False)
                        
                except Exception as e:
                    # 如果不合法，删除已写入的文件并报错
                    if file_path.exists():
                        os.remove(file_path)
                    logger.error(f"Invalid CSV file {uploaded_file.name}: {e}")
                    request.session['upload_error'] = f"无效的 CSV 文件: {str(e)}"
                
                return redirect('csv_manager')
        
        elif action == 'delete':
            filename = request.POST.get('filename')
            if filename:
                file_path = data_dir / filename
                if file_path.exists() and file_path.is_file() and filename.endswith('.csv'):
                    os.remove(file_path)
                    # 删除元数据
                    if filename in metadata:
                        del metadata[filename]
                        with open(metadata_path, 'w', encoding='utf-8') as f:
                            json.dump(metadata, f, indent=4, ensure_ascii=False)
                return redirect('csv_manager')
        
        elif action == 'update_metadata':
            filename = request.POST.get('filename')
            description = request.POST.get('description')
            columns = request.POST.get('columns')
            if filename:
                if filename not in metadata:
                    metadata[filename] = {'description': '', 'columns': ''}
                
                if isinstance(metadata[filename], str):
                    # 兼容旧格式
                    metadata[filename] = {'description': metadata[filename], 'columns': ''}

                if description is not None:
                    metadata[filename]['description'] = description
                if columns is not None:
                    metadata[filename]['columns'] = columns

                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=4, ensure_ascii=False)
                return JsonResponse({'status': 'success'})

    # 获取可能的上传错误
    upload_error = request.session.pop('upload_error', None)

    # 预览功能
    preview_data = None
    preview_filename = request.GET.get('preview')
    if preview_filename:
        logger.debug(f"Previewing file: {preview_filename}")
        file_path = data_dir / preview_filename
        if file_path.exists() and file_path.is_file() and preview_filename.endswith('.csv'):
            try:
                df = pd.read_csv(file_path, nrows=10)
                preview_data = {
                    'filename': preview_filename,
                    'columns': df.columns.tolist(),
                    'rows': df.values.tolist()
                }
            except Exception as e:
                logger.error(f"Error previewing CSV: {e}")
                preview_data = {'error': str(e)}

    # 获取所有 CSV 文件
    csv_files = []
    for file in data_dir.glob('*.csv'):
        meta = metadata.get(file.name, {})
        if isinstance(meta, str):
            # 兼容旧格式
            meta = {'description': meta, 'columns': ''}
        
        columns_val = meta.get('columns', '')
        if isinstance(columns_val, list):
            columns_val = ", ".join(columns_val)
        
        csv_files.append({
            'name': file.name,
            'size': f"{file.stat().st_size / 1024:.2f} KB",
            'modified': file.stat().st_mtime,
            'description': meta.get('description', ''),
            'columns': columns_val
        })
    
    # 按修改时间排序
    csv_files.sort(key=lambda x: x['modified'], reverse=True)

    context = {
        'csv_files': csv_files,
        'app_name': RizhiyiOAuthConfig.APP_NAME,
        'preview_data': preview_data,
        'upload_error': upload_error,
    }
    return render(request, 'oauth/csv_manager.html', context)
