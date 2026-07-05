"""Shared SQLAlchemy FK targets and server defaults for model definitions."""

FK_TAXONOMY_TERM = "taxonomy.taxonomy_term.taxonomy_term_id"
FK_HOST = "registry.host.host_id"
FK_COLLECTION_RUN = "discovery.collection_run.collection_run_id"
FK_DOCUMENT = "docs.document.document_id"
FK_NETWORK_SEGMENT = "registry.network_segment.network_segment_id"
FK_SERVICE_INSTANCE = "registry.service_instance.service_instance_id"
SERVER_DEFAULT_NOW = "now()"
