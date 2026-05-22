import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.knowledge_base.storage.sqlite_kb_storage import SQLiteKnowledgeBaseStorage


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
