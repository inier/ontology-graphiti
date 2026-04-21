"""异步任务定义"""

from odap.celery_app import celery_app
import time
import json
import pandas as pd
import io


@celery_app.task
def process_ingest_task(task_id, ingest_type, data, scenario_id=None):
    """处理数据摄入任务"""
    try:
        # 模拟处理时间
        time.sleep(5)
        
        result = {
            'task_id': task_id,
            'ingest_type': ingest_type,
            'status': 'completed',
            'processed_count': 1,
            'scenario_id': scenario_id
        }
        
        if ingest_type == 'text':
            # 处理文本数据
            result['content_length'] = len(data.get('text', ''))
        elif ingest_type == 'news':
            # 处理新闻数据
            result['url'] = data.get('url', '')
        elif ingest_type == 'random':
            # 处理随机数据
            result['generated_count'] = data.get('count', 10)
        elif ingest_type == 'manual':
            # 处理手动录入数据
            result['data_type'] = data.get('type', 'entity')
        elif ingest_type == 'file':
            # 处理文件数据
            result['filename'] = data.get('filename', '')
            result['file_size'] = data.get('file_size', 0)
        
        return result
    except Exception as e:
        return {
            'task_id': task_id,
            'status': 'failed',
            'error': str(e)
        }


@celery_app.task
def generate_graph_task(task_id, scenario_id, config=None):
    """生成图谱任务"""
    try:
        # 模拟处理时间
        time.sleep(10)
        
        # 模拟生成结果
        result = {
            'task_id': task_id,
            'scenario_id': scenario_id,
            'status': 'completed',
            'entities_generated': 100,
            'relations_generated': 150,
            'config': config or {}
        }
        
        return result
    except Exception as e:
        return {
            'task_id': task_id,
            'status': 'failed',
            'error': str(e)
        }


@celery_app.task
def process_file_upload_task(task_id, filename, file_content, file_extension, scenario_id=None):
    """处理文件上传任务"""
    try:
        # 模拟处理时间
        time.sleep(3)
        
        result = {
            'task_id': task_id,
            'filename': filename,
            'file_size': len(file_content),
            'file_extension': file_extension,
            'scenario_id': scenario_id,
            'status': 'completed'
        }
        
        # 根据文件类型进行处理
        if file_extension == '.json':
            # 解析JSON
            data = json.loads(file_content.decode('utf-8'))
            result['json_keys'] = list(data.keys()) if isinstance(data, dict) else len(data)
        elif file_extension == '.csv':
            # 解析CSV
            csv_data = io.StringIO(file_content.decode('utf-8'))
            df = pd.read_csv(csv_data)
            result['csv_rows'] = len(df)
            result['csv_columns'] = list(df.columns)
        elif file_extension == '.txt':
            # 处理文本
            lines = file_content.decode('utf-8').split('\n')
            result['text_lines'] = len(lines)
        
        return result
    except Exception as e:
        return {
            'task_id': task_id,
            'status': 'failed',
            'error': str(e)
        }