import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.data.knowledge_base.storage.sqlite_kb_storage import SQLiteKnowledgeBaseStorage


@pytest.fixture
def storage(tmp_path):
    db_path = str(tmp_path / "test_kb.db")
    return SQLiteKnowledgeBaseStorage(db_path=db_path)


def test_create_knowledge_base(storage):
    result = storage.create_knowledge_base({'name': 'Test KB', 'description': 'A test knowledge base'})
    assert result is not None
    assert result['name'] == 'Test KB'
    assert result['description'] == 'A test knowledge base'
    assert result['kb_id'].startswith('kb_')
    assert result['status'] == 'active'
    assert result['knowledge_count'] == 0
    assert result['category_count'] == 0


def test_get_knowledge_base(storage):
    created = storage.create_knowledge_base({'name': 'Test KB'})
    result = storage.get_knowledge_base(created['kb_id'])
    assert result is not None
    assert result['kb_id'] == created['kb_id']
    assert result['name'] == 'Test KB'


def test_get_knowledge_base_not_found(storage):
    result = storage.get_knowledge_base('kb_nonexistent')
    assert result is None


def test_update_knowledge_base(storage):
    created = storage.create_knowledge_base({'name': 'Old Name', 'description': 'Old desc'})
    updated = storage.update_knowledge_base(created['kb_id'], {'name': 'New Name', 'description': 'New desc'})
    assert updated is not None
    assert updated['name'] == 'New Name'
    assert updated['description'] == 'New desc'
    assert updated['kb_id'] == created['kb_id']


def test_update_knowledge_base_not_found(storage):
    result = storage.update_knowledge_base('kb_nonexistent', {'name': 'New Name'})
    assert result is None


def test_delete_knowledge_base(storage):
    created = storage.create_knowledge_base({'name': 'To Delete'})
    result = storage.delete_knowledge_base(created['kb_id'])
    assert result is True
    assert storage.get_knowledge_base(created['kb_id']) is None


def test_delete_knowledge_base_not_found(storage):
    result = storage.delete_knowledge_base('kb_nonexistent')
    assert result is False


def test_list_knowledge_bases(storage):
    storage.create_knowledge_base({'name': 'KB1'})
    storage.create_knowledge_base({'name': 'KB2'})
    result = storage.list_knowledge_bases()
    assert len(result) == 2
    names = [kb['name'] for kb in result]
    assert 'KB1' in names
    assert 'KB2' in names


def test_create_category(storage):
    kb = storage.create_knowledge_base({'name': 'Test KB'})
    result = storage.create_category(kb['kb_id'], {'name': 'Category 1'})
    assert result is not None
    assert result['name'] == 'Category 1'
    assert result['kb_id'] == kb['kb_id']
    assert result['category_id'].startswith('cat_')
    assert result['document_count'] == 0


def test_list_categories(storage):
    kb = storage.create_knowledge_base({'name': 'Test KB'})
    storage.create_category(kb['kb_id'], {'name': 'Cat A'})
    storage.create_category(kb['kb_id'], {'name': 'Cat B'})
    result = storage.list_categories(kb['kb_id'])
    assert len(result) == 2
    names = [c['name'] for c in result]
    assert 'Cat A' in names
    assert 'Cat B' in names


def test_delete_category(storage):
    kb = storage.create_knowledge_base({'name': 'Test KB'})
    cat = storage.create_category(kb['kb_id'], {'name': 'To Delete'})
    result = storage.delete_category(kb['kb_id'], cat['category_id'])
    assert result is True
    remaining = storage.list_categories(kb['kb_id'])
    assert len(remaining) == 0


def test_create_document(storage):
    kb = storage.create_knowledge_base({'name': 'Test KB'})
    result = storage.create_document(kb['kb_id'], {
        'title': 'Test Doc',
        'content': 'Some content',
        'content_type': 'text',
    })
    assert result is not None
    assert result['title'] == 'Test Doc'
    assert result['content'] == 'Some content'
    assert result['doc_id'].startswith('doc_')
    assert result['status'] == 'pending'
    assert result['graph_built'] is False


def test_get_document(storage):
    kb = storage.create_knowledge_base({'name': 'Test KB'})
    doc = storage.create_document(kb['kb_id'], {'title': 'Test Doc'})
    result = storage.get_document(kb['kb_id'], doc['doc_id'])
    assert result is not None
    assert result['doc_id'] == doc['doc_id']
    assert result['title'] == 'Test Doc'


def test_list_documents(storage):
    kb = storage.create_knowledge_base({'name': 'Test KB'})
    storage.create_document(kb['kb_id'], {'title': 'Doc 1'})
    storage.create_document(kb['kb_id'], {'title': 'Doc 2'})
    result = storage.list_documents(kb['kb_id'])
    assert len(result) == 2
    titles = [d['title'] for d in result]
    assert 'Doc 1' in titles
    assert 'Doc 2' in titles


def test_list_documents_by_category(storage):
    kb = storage.create_knowledge_base({'name': 'Test KB'})
    cat = storage.create_category(kb['kb_id'], {'name': 'Cat A'})
    storage.create_document(kb['kb_id'], {'title': 'Doc in Cat', 'category_id': cat['category_id']})
    storage.create_document(kb['kb_id'], {'title': 'Doc no Cat'})
    result = storage.list_documents(kb['kb_id'], category_id=cat['category_id'])
    assert len(result) == 1
    assert result[0]['title'] == 'Doc in Cat'
    assert result[0]['category_id'] == cat['category_id']


def test_delete_document(storage):
    kb = storage.create_knowledge_base({'name': 'Test KB'})
    doc = storage.create_document(kb['kb_id'], {'title': 'To Delete'})
    result = storage.delete_document(kb['kb_id'], doc['doc_id'])
    assert result is True
    assert storage.get_document(kb['kb_id'], doc['doc_id']) is None


class TestUpdateDocumentGraphStatus:
    def test_update_graph_status_success(self, storage):
        kb = storage.create_knowledge_base({'name': 'Test KB'})
        doc = storage.create_document(kb['kb_id'], {'title': 'Doc', 'content': 'text'})
        result = storage.update_document_graph_status(doc['doc_id'], True, 5)
        assert result is True
        updated = storage.find_document_by_id(doc['doc_id'])
        assert updated['graph_built'] is True

    def test_update_graph_status_not_found(self, storage):
        result = storage.update_document_graph_status('doc_nonexistent', True, 0)
        assert result is False

    def test_update_graph_status_set_false(self, storage):
        kb = storage.create_knowledge_base({'name': 'Test KB'})
        doc = storage.create_document(kb['kb_id'], {'title': 'Doc', 'content': 'text'})
        storage.update_document_graph_status(doc['doc_id'], True, 3)
        storage.update_document_graph_status(doc['doc_id'], False, 0)
        updated = storage.find_document_by_id(doc['doc_id'])
        assert updated['graph_built'] is False


class TestFindDocumentById:
    def test_find_existing(self, storage):
        kb = storage.create_knowledge_base({'name': 'Test KB'})
        doc = storage.create_document(kb['kb_id'], {'title': 'FindMe', 'content': 'hello'})
        found = storage.find_document_by_id(doc['doc_id'])
        assert found is not None
        assert found['title'] == 'FindMe'

    def test_find_not_existing(self, storage):
        found = storage.find_document_by_id('doc_nonexistent')
        assert found is None


class TestKnowledgeBaseService:
    @pytest.fixture
    def service(self, tmp_path):
        from odap.biz.data.knowledge_base.services.knowledge_base_service import KnowledgeBaseService
        db_path = str(tmp_path / "test_kb_svc.db")
        storage = SQLiteKnowledgeBaseStorage(db_path=db_path)
        return KnowledgeBaseService(storage=storage)

    def test_get_knowledge_base_error(self, service):
        result = service.get_knowledge_base('kb_nonexistent')
        assert result['status'] == 'error'

    def test_update_knowledge_base_error(self, service):
        result = service.update_knowledge_base('kb_nonexistent', {'name': 'X'})
        assert result['status'] == 'error'

    def test_delete_knowledge_base_error(self, service):
        result = service.delete_knowledge_base('kb_nonexistent')
        assert result['status'] == 'error'

    def test_delete_category_error(self, service):
        result = service.delete_category('kb_nonexistent', 'cat_nonexistent')
        assert result['status'] == 'error'

    def test_get_document_error(self, service):
        result = service.get_document('kb_nonexistent', 'doc_nonexistent')
        assert result['status'] == 'error'

    def test_delete_document_error(self, service):
        result = service.delete_document('kb_nonexistent', 'doc_nonexistent')
        assert result['status'] == 'error'

    def test_get_graph_build_status_not_found(self, service):
        result = service.get_graph_build_status('task_nonexistent')
        assert result['status'] == 'error'

    @pytest.mark.asyncio
    async def test_build_graph_doc_not_found(self, service):
        result = await service.build_graph('doc_nonexistent')
        assert result['status'] == 'error'

    @pytest.mark.asyncio
    async def test_build_graph_empty_content(self, service):
        kb = service.create_knowledge_base({'name': 'KB'})
        doc = service.create_document(kb['kb_id'], {'title': 'Empty', 'content': ''})
        result = await service.build_graph(doc['doc_id'], extraction_method='regex')
        assert result['status'] == 'error'

    @pytest.mark.asyncio
    async def test_build_graph_regex(self, service):
        kb = service.create_knowledge_base({'name': 'KB'})
        doc = service.create_document(kb['kb_id'], {
            'title': 'Military Doc',
            'content': '东部舰队在南海执行任务，红旗导弹部队已部署完毕',
        })
        result = await service.build_graph(doc['doc_id'], extraction_method='regex')
        assert result['status'] == 'completed'
        assert result['method'] == 'regex'
        assert result['entities_extracted'] > 0
        task_id = result['task_id']
        status = service.get_graph_build_status(task_id)
        assert status['status'] == 'completed'

    @pytest.mark.asyncio
    async def test_rag_query_kb_not_found(self, service):
        result = await service.rag_query('kb_nonexistent', 'test')
        assert result['status'] == 'error'

    @pytest.mark.asyncio
    async def test_rag_query_no_results(self, service):
        kb = service.create_knowledge_base({'name': 'KB'})
        result = await service.rag_query(kb['kb_id'], 'nonexistent query xyz')
        assert result['answer'] == '未找到与查询相关的文档'

    @pytest.mark.asyncio
    async def test_rag_query_with_results(self, service):
        kb = service.create_knowledge_base({'name': 'KB'})
        service.create_document(kb['kb_id'], {'title': 'Python Guide', 'content': 'Python is a programming language'})
        result = await service.rag_query(kb['kb_id'], 'python')
        assert len(result['sources']) > 0

    @pytest.mark.asyncio
    async def test_crawl_web_kb_not_found(self, service):
        result = await service.crawl_web('kb_nonexistent', ['http://example.com'])
        assert result['status'] == 'error'

    def test_extract_with_regex(self, service):
        content = '东部舰队在南海执行任务，红旗导弹部队已部署完毕'
        result = service._extract_with_regex(content)
        assert 'entities' in result
        assert len(result['entities']) > 0

    def test_extract_with_regex_custom_types(self, service):
        content = '第一装甲师在北方演习'
        result = service._extract_with_regex(content, entity_types=['师'])
        assert len(result['entities']) > 0
