from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ExtractionAdapterInterface(ABC):
    @abstractmethod
    def extract_from_text(self, text: str, template_config: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def extract_incremental(self, ka_path: str, text: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def merge_results(self, data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        pass


class DocumentParserInterface(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> str:
        pass

    @abstractmethod
    def chunk_text(self, text: str, max_tokens: int = 4000) -> List[str]:
        pass


class TemplateGeneratorInterface(ABC):
    @abstractmethod
    def generate_from_ontology(self, ontology_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def select_preset(self, domain_hint: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def generate_with_web_search(self, text: str) -> Optional[Dict[str, Any]]:
        pass


class ProvenanceTrackerInterface(ABC):
    @abstractmethod
    def record_extraction(self, entity_id: str, source_doc_id: str, chunk_id: str, fragment_id: str, method: str, template_version: str) -> None:
        pass

    @abstractmethod
    def get_provenance(self, entity_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_entities_by_source(self, source_doc_id: str) -> List[Dict[str, Any]]:
        pass
