from .memory_service import OntologyMemoryService

get_memory_service = OntologyMemoryService.get_instance

__all__ = ["OntologyMemoryService", "get_memory_service"]
