"""异步任务定义"""

from odap.celery_app import celery_app
import time
import json
import pandas as pd
import io
from typing import Dict, Any


@celery_app.task
def process_ingest_task(task_id, ingest_type, data, scenario_id=None):
    """处理数据摄入任务"""
    try:
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
            
            # 保存到场景
            if scenario_id:
                _save_to_scenario(scenario_id, 'text', data)
                
        elif ingest_type == 'news':
            # 处理新闻数据
            result['url'] = data.get('url', '')
            
            if data.get('url') and scenario_id:
                from odap.utils.web_scraper import WebScraper
                scraper = WebScraper()
                news_data = scraper.scrape_news(data.get('url'))
                
                if news_data:
                    result['title'] = news_data.get('title', '')
                    result['content_length'] = len(news_data.get('content', ''))
                    
                    # 保存到场景
                    _save_to_scenario(scenario_id, 'news', news_data)
                    result['processed_count'] = 1
        
        elif ingest_type == 'random':
            # 处理随机数据
            result['generated_count'] = data.get('count', 10)
            
            if scenario_id:
                from odap.utils.data_generator import DataGenerator
                gen = DataGenerator()
                sample_data = gen.generate_sample_data(data.get('count', 10))
                _save_to_scenario(scenario_id, 'random', sample_data)
                result['processed_count'] = len(sample_data.get('entities', []))
                
        elif ingest_type == 'manual':
            # 处理手动录入数据
            result['data_type'] = data.get('type', 'entity')
            
            if scenario_id:
                _save_to_scenario(scenario_id, 'manual', data)
        
        elif ingest_type == 'file':
            # 处理文件数据
            result['filename'] = data.get('filename', '')
            result['file_size'] = data.get('file_size', 0)
        
        return result
    except Exception as e:
        import traceback
        return {
            'task_id': task_id,
            'status': 'failed',
            'error': str(e),
            'traceback': traceback.format_exc()
        }


def _save_to_scenario(scenario_id: str, doc_type: str, data: Dict[str, Any]):
    """保存数据到场景"""
    try:
        from odap.biz.workspace.storage import Storage
        storage = Storage()
        
        doc = {
            'doc_type': doc_type,
            'data': data,
            'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        storage.add_scenario_document(scenario_id, doc)
    except Exception as e:
        print(f"Error saving to scenario: {e}")


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