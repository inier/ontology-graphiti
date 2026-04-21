"""数据摄入服务"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from ..ingestion import NewsIngester, ManualInputHandler, RandomEventGenerator, FreeNewsIngester, WebScraper, OntologyDocument
from ..storage import SQLiteIngestStorage


class IngestService:
    """数据摄入服务"""

    def __init__(self, llm_client=None):
        self.storage = SQLiteIngestStorage()
        self.news_ingester = NewsIngester(llm_client=llm_client)
        self.manual_input_handler = ManualInputHandler(llm_client=llm_client)
        self.random_event_generator = RandomEventGenerator(llm_client=llm_client)
        self.web_scraper = WebScraper()
        self.free_news_ingester = FreeNewsIngester(scraper=self.web_scraper, llm_client=llm_client)

    async def ingest_from_url(self, url: str, event_context: str = "") -> str:
        """从URL摄入数据（免费方案，无需API Key）"""
        # 创建摄入记录
        ingest_id = str(uuid.uuid4())
        ingest_record = {
            'id': ingest_id,
            'source': 'url',
            'source_details': {'url': url, 'context': event_context},
            'record_count': 0,
            'status': 'processing',
            'start_time': datetime.now().isoformat(),
            'created_by': 'system'
        }
        self.storage.save_ingest_record(ingest_record)

        try:
            # 使用免费网页抓取
            documents = await self.free_news_ingester.ingest(url, event_context=event_context)

            # 保存文档
            for doc in documents:
                self.storage.save_ontology_document(doc)

            # 更新摄入记录
            ingest_record['status'] = 'completed'
            ingest_record['record_count'] = len(documents)
            ingest_record['processed_count'] = len(documents)
            ingest_record['end_time'] = datetime.now().isoformat()
            ingest_record['duration_seconds'] = (datetime.now() - datetime.fromisoformat(ingest_record['start_time'])).total_seconds()
        except Exception as e:
            # 处理错误
            ingest_record['status'] = 'failed'
            ingest_record['errors'] = [{'message': str(e)}]
            ingest_record['end_time'] = datetime.now().isoformat()
            ingest_record['duration_seconds'] = (datetime.now() - datetime.fromisoformat(ingest_record['start_time'])).total_seconds()

        self.storage.update_ingest_record(ingest_id, ingest_record)
        return ingest_id
    
    async def ingest_from_news(self, query: str, event_context: str = "", max_sources: int = 5) -> str:
        """从新闻摄入数据"""
        # 创建摄入记录
        ingest_id = str(uuid.uuid4())
        ingest_record = {
            'id': ingest_id,
            'source': 'news',
            'source_details': {'query': query, 'max_sources': max_sources},
            'record_count': 0,
            'status': 'processing',
            'start_time': datetime.now().isoformat(),
            'created_by': 'system'
        }
        self.storage.save_ingest_record(ingest_record)
        
        try:
            # 执行新闻摄入
            documents = await self.news_ingester.ingest(query, event_context, max_sources)
            
            # 保存文档
            for doc in documents:
                self.storage.save_ontology_document(doc)
            
            # 更新摄入记录
            ingest_record['status'] = 'completed'
            ingest_record['record_count'] = len(documents)
            ingest_record['processed_count'] = len(documents)
            ingest_record['end_time'] = datetime.now().isoformat()
            ingest_record['duration_seconds'] = (datetime.now() - datetime.fromisoformat(ingest_record['start_time'])).total_seconds()
        except Exception as e:
            # 处理错误
            ingest_record['status'] = 'failed'
            ingest_record['errors'] = [{'message': str(e)}]
            ingest_record['end_time'] = datetime.now().isoformat()
            ingest_record['duration_seconds'] = (datetime.now() - datetime.fromisoformat(ingest_record['start_time'])).total_seconds()
        
        self.storage.update_ingest_record(ingest_id, ingest_record)
        return ingest_id
    
    async def ingest_from_manual(self, form_data: dict, scenario_id: str = None) -> str:
        """从手动输入摄入数据"""
        # 创建摄入记录
        ingest_id = str(uuid.uuid4())
        ingest_record = {
            'id': ingest_id,
            'source': 'manual',
            'source_details': {'form_data_keys': list(form_data.keys())},
            'record_count': 1,
            'status': 'processing',
            'start_time': datetime.now().isoformat(),
            'created_by': form_data.get('author', 'system')
        }
        self.storage.save_ingest_record(ingest_record)
        
        try:
            # 处理手动输入
            doc = await self.manual_input_handler.from_form(form_data, scenario_id)
            
            # 保存文档
            self.storage.save_ontology_document(doc)
            
            # 更新摄入记录
            ingest_record['status'] = 'completed'
            ingest_record['processed_count'] = 1
            ingest_record['end_time'] = datetime.now().isoformat()
            ingest_record['duration_seconds'] = (datetime.now() - datetime.fromisoformat(ingest_record['start_time'])).total_seconds()
        except Exception as e:
            # 处理错误
            ingest_record['status'] = 'failed'
            ingest_record['errors'] = [{'message': str(e)}]
            ingest_record['end_time'] = datetime.now().isoformat()
            ingest_record['duration_seconds'] = (datetime.now() - datetime.fromisoformat(ingest_record['start_time'])).total_seconds()
        
        self.storage.update_ingest_record(ingest_id, ingest_record)
        return ingest_id
    
    async def ingest_from_json(self, raw_json: str, scenario_id: str = None) -> str:
        """从 JSON 摄入数据"""
        # 创建摄入记录
        ingest_id = str(uuid.uuid4())
        ingest_record = {
            'id': ingest_id,
            'source': 'json',
            'source_details': {'json_length': len(raw_json)},
            'record_count': 1,
            'status': 'processing',
            'start_time': datetime.now().isoformat(),
            'created_by': 'system'
        }
        self.storage.save_ingest_record(ingest_record)
        
        try:
            # 处理 JSON 输入
            doc = await self.manual_input_handler.from_json(raw_json, scenario_id)
            
            # 保存文档
            self.storage.save_ontology_document(doc)
            
            # 更新摄入记录
            ingest_record['status'] = 'completed'
            ingest_record['processed_count'] = 1
            ingest_record['end_time'] = datetime.now().isoformat()
            ingest_record['duration_seconds'] = (datetime.now() - datetime.fromisoformat(ingest_record['start_time'])).total_seconds()
        except Exception as e:
            # 处理错误
            ingest_record['status'] = 'failed'
            ingest_record['errors'] = [{'message': str(e)}]
            ingest_record['end_time'] = datetime.now().isoformat()
            ingest_record['duration_seconds'] = (datetime.now() - datetime.fromisoformat(ingest_record['start_time'])).total_seconds()
        
        self.storage.update_ingest_record(ingest_id, ingest_record)
        return ingest_id
    
    async def ingest_from_natural_language(self, text: str, scenario_id: str = None) -> str:
        """从自然语言摄入数据"""
        # 创建摄入记录
        ingest_id = str(uuid.uuid4())
        ingest_record = {
            'id': ingest_id,
            'source': 'natural_language',
            'source_details': {'text_length': len(text)},
            'record_count': 1,
            'status': 'processing',
            'start_time': datetime.now().isoformat(),
            'created_by': 'system'
        }
        self.storage.save_ingest_record(ingest_record)
        
        try:
            # 处理自然语言输入
            doc = await self.manual_input_handler.from_natural_language(text, scenario_id)
            
            # 保存文档
            self.storage.save_ontology_document(doc)
            
            # 更新摄入记录
            ingest_record['status'] = 'completed'
            ingest_record['processed_count'] = 1
            ingest_record['end_time'] = datetime.now().isoformat()
            ingest_record['duration_seconds'] = (datetime.now() - datetime.fromisoformat(ingest_record['start_time'])).total_seconds()
        except Exception as e:
            # 处理错误
            ingest_record['status'] = 'failed'
            ingest_record['errors'] = [{'message': str(e)}]
            ingest_record['end_time'] = datetime.now().isoformat()
            ingest_record['duration_seconds'] = (datetime.now() - datetime.fromisoformat(ingest_record['start_time'])).total_seconds()
        
        self.storage.update_ingest_record(ingest_id, ingest_record)
        return ingest_id
    
    async def generate_random_events(self, parties: List[str], scenario_context: dict = None, 
                                   count: int = 1, scenario_id: str = None) -> str:
        """生成随机事件"""
        # 创建摄入记录
        ingest_id = str(uuid.uuid4())
        ingest_record = {
            'id': ingest_id,
            'source': 'random',
            'source_details': {'parties': parties, 'count': count},
            'record_count': count,
            'status': 'processing',
            'start_time': datetime.now().isoformat(),
            'created_by': 'system'
        }
        self.storage.save_ingest_record(ingest_record)
        
        try:
            # 生成随机事件
            documents = await self.random_event_generator.generate(parties, scenario_context, count, scenario_id)
            
            # 保存文档
            for doc in documents:
                self.storage.save_ontology_document(doc)
            
            # 更新摄入记录
            ingest_record['status'] = 'completed'
            ingest_record['processed_count'] = len(documents)
            ingest_record['end_time'] = datetime.now().isoformat()
            ingest_record['duration_seconds'] = (datetime.now() - datetime.fromisoformat(ingest_record['start_time'])).total_seconds()
        except Exception as e:
            # 处理错误
            ingest_record['status'] = 'failed'
            ingest_record['errors'] = [{'message': str(e)}]
            ingest_record['end_time'] = datetime.now().isoformat()
            ingest_record['duration_seconds'] = (datetime.now() - datetime.fromisoformat(ingest_record['start_time'])).total_seconds()
        
        self.storage.update_ingest_record(ingest_id, ingest_record)
        return ingest_id
    
    def get_ingest_status(self, ingest_id: str) -> Dict[str, Any]:
        """获取摄入状态"""
        return self.storage.get_ingest_record(ingest_id)
    
    def get_ingest_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取摄入历史"""
        return self.storage.get_ingest_records(limit)
    
    def get_ontology_documents(self, scenario_id: Optional[str] = None, limit: int = 100) -> List[OntologyDocument]:
        """获取本体文档"""
        return self.storage.list_ontology_documents(scenario_id, limit)
    
    def get_ontology_document(self, doc_id: str) -> Optional[OntologyDocument]:
        """获取本体文档详情"""
        return self.storage.get_ontology_document(doc_id)