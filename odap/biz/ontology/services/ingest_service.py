"""数据摄入服务"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from ..ingestion import NewsIngester, ManualInputHandler, RandomEventGenerator, FreeNewsIngester, WebScraper, OntologyDocument
from ..storage import SQLiteIngestStorage
from .build_service import get_builder_service


class IngestService:
    """数据摄入服务"""

    def __init__(self, llm_client=None):
        self.storage = SQLiteIngestStorage()
        self.news_ingester = NewsIngester(llm_client=llm_client)
        self.manual_input_handler = ManualInputHandler(llm_client=llm_client)
        self.random_event_generator = RandomEventGenerator(llm_client=llm_client)
        self.web_scraper = WebScraper()
        self.free_news_ingester = FreeNewsIngester(scraper=self.web_scraper, llm_client=llm_client)
        self.builder_service = get_builder_service()

    async def ingest_from_url(self, url: str, event_context: str = "", scenario_id: str = None) -> str:
        """
        从URL摄入数据（免费方案，无需API Key）
        
        Args:
            url (str): 要抓取的网页URL
            event_context (str, optional): 事件上下文，用于指导实体/关系提取
            scenario_id (str, optional): 场景ID，用于组织和管理摄入数据
        
        Returns:
            str: 摄入记录ID
        
        Raises:
            Exception: 当URL抓取或处理失败时
        
        Process:
            1. 创建摄入记录，设置状态为processing
            2. 清理URL（去除首尾空格）
            3. 使用FreeNewsIngester抓取网页内容
            4. 提取实体、关系和事件
            5. 保存原始网页内容到摄入记录
            6. 保存生成的本体文档
            7. 触发本体构建过程
            8. 更新摄入记录状态为completed
            9. 处理任何异常并更新状态为failed
        """
        # 创建摄入记录
        ingest_id = str(uuid.uuid4())
        # 清理 URL（去除首尾空格）
        url = url.strip()
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

            # 收集文档ID
            document_ids = [doc.doc_id for doc in documents]

            # 保存原始网页内容（无论抓取是否成功都设置）
            scrape_result = None
            if hasattr(self.free_news_ingester, 'scraper'):
                # 抓取网页内容
                scrape_result = self.free_news_ingester.scraper.scrape(url)
                if scrape_result.get('status') == 'success':
                    ingest_record['original_content'] = scrape_result.get('text', '')
                else:
                    # 抓取失败时，也设置原始内容为抓取结果摘要
                    ingest_record['original_content'] = f"网页抓取失败: {scrape_result.get('error', '未知错误')}"
            else:
                # 没有 scraper 时使用文档内容作为原始内容
                if documents:
                    ingest_record['original_content'] = documents[0].meta.description if documents[0].meta.description else str(documents[0].to_dict())[:1000]

            # 统一返回结构（无论抓取是否成功都设置）
            source_data = []
            if scrape_result and scrape_result.get('status') == 'success':
                source_data.append({
                    'url': scrape_result.get('url', ''),
                    'title': scrape_result.get('title', ''),
                    'text': scrape_result.get('text', ''),
                    'description': scrape_result.get('description', ''),
                    'publish_date': scrape_result.get('publish_date', '')
                })
            elif documents:
                # 使用生成的文档信息
                for doc in documents:
                    source_data.append({
                        'url': url,
                        'title': doc.meta.title or '网页内容',
                        'text': doc.meta.description or '',
                        'description': doc.meta.description or '',
                        'publish_date': doc.source.collected_at or ''
                    })
            else:
                source_data.append({
                    'url': url,
                    'title': '网页内容',
                    'text': '',
                    'description': '',
                    'publish_date': ''
                })

            ingest_record['extracted_data'] = {
                'source_data': source_data,
                'document_ids': document_ids,
                'document_count': len(documents)
            }

            # 保存文档
            for doc in documents:
                self.storage.save_ontology_document(doc)
                # 触发本体构建
                try:
                    build_result = await self.builder_service.build_ontology(
                        document=doc,
                        scenario_id=scenario_id or "default",
                        workspace_id="default",
                        create_new_version=True
                    )
                    # 记录构建结果
                    if 'build_id' in build_result:
                        if 'builds' not in ingest_record:
                            ingest_record['builds'] = []
                        ingest_record['builds'].append({
                            'build_id': build_result['build_id'],
                            'document_id': doc.doc_id,
                            'status': build_result.get('status'),
                            'version_info': build_result.get('version_info')
                        })
                except Exception as build_error:
                    print(f"本体构建失败: {build_error}")

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
    
    async def ingest_from_news(self, query: str, event_context: str = "", max_sources: int = 5, scenario_id: str = None) -> str:
        """
        从新闻摄入数据
        
        Args:
            query (str): 新闻搜索查询关键词
            event_context (str, optional): 事件上下文，用于指导实体/关系提取
            max_sources (int, optional): 最大新闻源数量，默认为5
            scenario_id (str, optional): 场景ID，用于组织和管理摄入数据
        
        Returns:
            str: 摄入记录ID
        
        Raises:
            Exception: 当新闻搜索或处理失败时
        
        Process:
            1. 创建摄入记录，设置状态为processing
            2. 使用NewsIngester搜索相关新闻
            3. 提取实体、关系和事件
            4. 保存原始新闻内容到摄入记录
            5. 保存生成的本体文档
            6. 触发本体构建过程
            7. 更新摄入记录状态为completed
            8. 处理任何异常并更新状态为failed
        """
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
            
            # 收集文档ID
            document_ids = [doc.doc_id for doc in documents]
            
            # 保存原始新闻数据和内容（无论搜索是否成功都设置）
            search_results = None
            if hasattr(self.news_ingester, '_search'):
                # 获取原始搜索结果
                search_results = await self.news_ingester._search(query, max_sources)
                if search_results:
                    # 合并原始内容
                    combined_text = self.news_ingester._combine_sources(search_results)
                    ingest_record['original_content'] = combined_text
                else:
                    # 搜索失败时，设置原始内容为搜索结果摘要
                    ingest_record['original_content'] = f"新闻搜索失败，使用模拟数据。查询词: {query}"
            
            # 统一返回结构（无论搜索是否成功都设置）
            source_data = []
            if search_results and len(search_results) > 0:
                for result in search_results:
                    source_data.append({
                        'url': result.get('url', ''),
                        'title': result.get('title', ''),
                        'text': result.get('content', result.get('snippet', '')),
                        'description': result.get('snippet', ''),
                        'publish_date': result.get('date', '')
                    })
            elif documents:
                # 使用生成的文档信息
                for doc in documents:
                    source_data.append({
                        'url': doc.source.url or '',
                        'title': doc.meta.title or '新闻内容',
                        'text': doc.meta.description or '',
                        'description': doc.meta.description or '',
                        'publish_date': doc.source.collected_at or ''
                    })
            else:
                source_data.append({
                    'url': '',
                    'title': '新闻内容',
                    'text': '',
                    'description': '',
                    'publish_date': ''
                })
            
            # 设置提取数据
            if documents and len(documents) > 0 and hasattr(documents[0], 'entities'):
                ingest_record['extracted_data'] = {
                    'source_data': source_data,
                    'document_ids': document_ids,
                    'document_count': len(documents),
                    'entities_count': sum(len(doc.entities) for doc in documents),
                    'relations_count': sum(len(doc.relations) for doc in documents),
                    'events_count': sum(len(doc.events) for doc in documents)
                }
            else:
                ingest_record['extracted_data'] = {
                    'source_data': source_data,
                    'document_ids': document_ids,
                    'document_count': len(documents)
                }
            
            # 保存文档
            for doc in documents:
                self.storage.save_ontology_document(doc)
                # 触发本体构建
                try:
                    build_result = await self.builder_service.build_ontology(
                        document=doc,
                        scenario_id=scenario_id or "default",
                        workspace_id="default",
                        create_new_version=True
                    )
                    # 记录构建结果
                    if 'build_id' in build_result:
                        if 'builds' not in ingest_record:
                            ingest_record['builds'] = []
                        ingest_record['builds'].append({
                            'build_id': build_result['build_id'],
                            'document_id': doc.doc_id,
                            'status': build_result.get('status'),
                            'version_info': build_result.get('version_info')
                        })
                except Exception as build_error:
                    print(f"本体构建失败: {build_error}")

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
    
    async def ingest_from_manual(self, form_data: Any, scenario_id: str = None) -> str:
        """
        从手动输入摄入数据
        
        Args:
            form_data (Any): 手动输入的数据，可以是字典、字符串或其他类型
            scenario_id (str, optional): 场景ID，用于组织和管理摄入数据
        
        Returns:
            str: 摄入记录ID
        
        Raises:
            Exception: 当处理手动输入失败时
        
        Process:
            1. 创建摄入记录，设置状态为processing
            2. 自动检测并转换form_data类型：
               - 字典：直接使用
               - 字符串：转换为 {"text": str}
               - 其他类型：转换为 {"data": str}
            3. 使用ManualInputHandler处理输入数据
            4. 提取实体、关系和事件
            5. 保存原始输入内容到摄入记录
            6. 保存生成的本体文档
            7. 触发本体构建过程
            8. 更新摄入记录状态为completed
            9. 处理任何异常并更新状态为failed
        """
        # 创建摄入记录
        ingest_id = str(uuid.uuid4())
        
        # 检查 form_data 类型并进行转换
        form_data_keys = []
        original_content = ""
        if isinstance(form_data, dict):
            form_data_keys = list(form_data.keys())
            original_content = str(form_data)
        elif isinstance(form_data, str):
            form_data = {"text": form_data}
            form_data_keys = ["text"]
            original_content = form_data["text"]
        else:
            form_data = {"data": str(form_data)}
            form_data_keys = ["data"]
            original_content = form_data["data"]
        
        ingest_record = {
            'id': ingest_id,
            'source': 'manual',
            'source_details': {'form_data_keys': form_data_keys},
            'original_content': original_content,
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
            # 触发本体构建
            try:
                build_result = await self.builder_service.build_ontology(
                    document=doc,
                    scenario_id=scenario_id or "default",
                    workspace_id="default",
                    create_new_version=True
                )
                # 记录构建结果
                if 'build_id' in build_result:
                    if 'builds' not in ingest_record:
                        ingest_record['builds'] = []
                    ingest_record['builds'].append({
                        'build_id': build_result['build_id'],
                        'document_id': doc.doc_id,
                        'status': build_result.get('status'),
                        'version_info': build_result.get('version_info')
                    })
                # 记录提取数据
                # 统一返回结构
                source_data = [{
                    'url': '',
                    'title': doc.meta.title or '手动输入',
                    'text': original_content,
                    'description': doc.meta.description or '',
                    'publish_date': doc.source.collected_at or ''
                }]
                ingest_record['extracted_data'] = {
                    'source_data': source_data,
                    'document_ids': [doc.doc_id],
                    'document_count': 1,
                    'entities_count': len(doc.entities),
                    'relations_count': len(doc.relations),
                    'events_count': len(doc.events)
                }
            except Exception as build_error:
                print(f"本体构建失败: {build_error}")

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
        """
        从 JSON 摄入数据
        
        Args:
            raw_json (str): JSON格式的原始数据
            scenario_id (str, optional): 场景ID，用于组织和管理摄入数据
        
        Returns:
            str: 摄入记录ID
        
        Raises:
            Exception: 当JSON解析或处理失败时
        
        Process:
            1. 创建摄入记录，设置状态为processing
            2. 使用ManualInputHandler处理JSON输入
            3. 提取实体、关系和事件
            4. 保存原始JSON内容到摄入记录
            5. 保存生成的本体文档
            6. 触发本体构建过程
            7. 更新摄入记录状态为completed
            8. 处理任何异常并更新状态为failed
        """
        # 创建摄入记录
        ingest_id = str(uuid.uuid4())
        ingest_record = {
            'id': ingest_id,
            'source': 'json',
            'source_details': {'json_length': len(raw_json)},
            'original_content': raw_json,
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
            # 触发本体构建
            try:
                build_result = await self.builder_service.build_ontology(
                    document=doc,
                    scenario_id=scenario_id or "default",
                    workspace_id="default",
                    create_new_version=True
                )
                # 记录构建结果
                if 'build_id' in build_result:
                    if 'builds' not in ingest_record:
                        ingest_record['builds'] = []
                    ingest_record['builds'].append({
                        'build_id': build_result['build_id'],
                        'document_id': doc.doc_id,
                        'status': build_result.get('status'),
                        'version_info': build_result.get('version_info')
                    })
                # 记录提取数据
                # 统一返回结构
                source_data = [{
                    'url': '',
                    'title': doc.meta.title or 'JSON输入',
                    'text': raw_json,
                    'description': doc.meta.description or '',
                    'publish_date': doc.source.collected_at or ''
                }]
                ingest_record['extracted_data'] = {
                    'source_data': source_data,
                    'document_ids': [doc.doc_id],
                    'document_count': 1,
                    'entities_count': len(doc.entities),
                    'relations_count': len(doc.relations),
                    'events_count': len(doc.events)
                }
            except Exception as build_error:
                print(f"本体构建失败: {build_error}")

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
        """
        从自然语言摄入数据
        
        Args:
            text (str): 自然语言文本
            scenario_id (str, optional): 场景ID，用于组织和管理摄入数据
        
        Returns:
            str: 摄入记录ID
        
        Raises:
            Exception: 当处理自然语言输入失败时
        
        Process:
            1. 创建摄入记录，设置状态为processing
            2. 使用ManualInputHandler处理自然语言输入
            3. 提取实体、关系和事件
            4. 保存原始文本内容到摄入记录
            5. 保存生成的本体文档
            6. 触发本体构建过程
            7. 更新摄入记录状态为completed
            8. 处理任何异常并更新状态为failed
        """
        # 创建摄入记录
        ingest_id = str(uuid.uuid4())
        ingest_record = {
            'id': ingest_id,
            'source': 'natural_language',
            'source_details': {'text_length': len(text)},
            'original_content': text,
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
            # 触发本体构建
            try:
                build_result = await self.builder_service.build_ontology(
                    document=doc,
                    scenario_id=scenario_id or "default",
                    workspace_id="default",
                    create_new_version=True
                )
                # 记录构建结果
                if 'build_id' in build_result:
                    if 'builds' not in ingest_record:
                        ingest_record['builds'] = []
                    ingest_record['builds'].append({
                        'build_id': build_result['build_id'],
                        'document_id': doc.doc_id,
                        'status': build_result.get('status'),
                        'version_info': build_result.get('version_info')
                    })
                # 记录提取数据
                # 统一返回结构
                source_data = [{
                    'url': '',
                    'title': doc.meta.title or '自然语言输入',
                    'text': text,
                    'description': doc.meta.description or '',
                    'publish_date': doc.source.collected_at or ''
                }]
                ingest_record['extracted_data'] = {
                    'source_data': source_data,
                    'document_ids': [doc.doc_id],
                    'document_count': 1,
                    'entities_count': len(doc.entities),
                    'relations_count': len(doc.relations),
                    'events_count': len(doc.events)
                }
            except Exception as build_error:
                print(f"本体构建失败: {build_error}")

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
        """
        生成随机事件
        
        Args:
            parties (List[str]): 参与方列表
            scenario_context (dict, optional): 场景上下文，用于指导事件生成
            count (int, optional): 生成的事件数量，默认为1
            scenario_id (str, optional): 场景ID，用于组织和管理摄入数据
        
        Returns:
            str: 摄入记录ID
        
        Raises:
            Exception: 当生成随机事件失败时
        
        Process:
            1. 创建摄入记录，设置状态为processing
            2. 使用RandomEventGenerator生成随机事件
            3. 提取实体、关系和事件
            4. 保存生成的本体文档
            5. 触发本体构建过程
            6. 汇总统计信息
            7. 更新摄入记录状态为completed
            8. 处理任何异常并更新状态为failed
        """
        # 创建摄入记录
        ingest_id = str(uuid.uuid4())
        ingest_record = {
            'id': ingest_id,
            'source': 'random',
            'source_details': {'parties': parties, 'count': count},
            'original_content': f"随机生成 {count} 个事件，参与方: {parties}",
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
            document_ids = []
            total_entities = 0
            total_relations = 0
            total_events = 0
            
            for doc in documents:
                document_ids.append(doc.doc_id)
                total_entities += len(doc.entities)
                total_relations += len(doc.relations)
                total_events += len(doc.events)
                
                self.storage.save_ontology_document(doc)
                # 触发本体构建
                try:
                    build_result = await self.builder_service.build_ontology(
                        document=doc,
                        scenario_id=scenario_id or "default",
                        workspace_id="default",
                        create_new_version=True
                    )
                    # 记录构建结果
                    if 'build_id' in build_result:
                        if 'builds' not in ingest_record:
                            ingest_record['builds'] = []
                        ingest_record['builds'].append({
                            'build_id': build_result['build_id'],
                            'document_id': doc.doc_id,
                            'status': build_result.get('status'),
                            'version_info': build_result.get('version_info')
                        })
                except Exception as build_error:
                    print(f"本体构建失败: {build_error}")

            # 记录提取数据
            # 统一返回结构
            source_data = [{
                'url': '',
                'title': f"随机事件生成",
                'text': f"随机生成 {count} 个事件，参与方: {parties}",
                'description': f"生成了 {count} 个随机事件，包含 {total_entities} 个实体，{total_relations} 个关系，{total_events} 个事件",
                'publish_date': datetime.now().isoformat()
            }]
            ingest_record['extracted_data'] = {
                'source_data': source_data,
                'document_ids': document_ids,
                'document_count': len(documents),
                'total_entities': total_entities,
                'total_relations': total_relations,
                'total_events': total_events
            }

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