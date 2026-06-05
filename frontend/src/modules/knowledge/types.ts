export interface KnowledgeBase {
  kb_id: string;
  name: string;
  description: string;
  knowledge_count: number;
  category_count: number;
  updated_at: string;
  created_at: string;
  created_by: string;
  status: 'active' | 'building' | 'error';
}

export interface KnowledgeCategory {
  category_id: string;
  kb_id: string;
  name: string;
  parent_id?: string;
  children?: KnowledgeCategory[];
  document_count: number;
  updated_at: string;
}

export interface KnowledgeDocument {
  doc_id: string;
  kb_id: string;
  category_id?: string;
  title: string;
  content_type: 'file' | 'online_doc' | 'text' | 'web_crawl';
  file_type?: string;
  file_size?: number;
  file_url?: string;
  content?: string;
  keywords: string[];
  summary?: string;
  status: 'pending' | 'processing' | 'indexed' | 'error';
  graph_built: boolean;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeBaseFormData {
  name: string;
  description: string;
}

export interface DocumentUploadData {
  kb_id: string;
  category_id?: string;
  content_type: 'file' | 'online_doc' | 'text' | 'web_crawl';
  title: string;
  content?: string;
  file?: File;
  web_url?: string;
}

export interface GraphBuildRequest {
  doc_id: string;
  extraction_method?: 'regex' | 'llm' | 'auto';
  entity_types?: string[];
  extraction_config: {
    extract_entities: boolean;
    extract_relations: boolean;
    entity_types: string[];
    relation_types: string[];
  };
}

export interface RAGQueryRequest {
  kb_id: string;
  query: string;
  top_k?: number;
  filters?: Record<string, string[]>;
}

export interface RAGQueryResult {
  answer: string;
  sources: {
    doc_id: string;
    title: string;
    content: string;
    score: number;
  }[];
  related_entities: {
    entity_id: string;
    name: string;
    type: string;
  }[];
}
