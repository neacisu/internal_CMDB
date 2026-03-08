"""internalCMDB — SQLAlchemy models for all Wave-1 schemas.

Import order is important: schemas with no intra-package FK deps first,
then schemas that reference them, so that all Table objects are registered
on the shared MetaData before Alembic autogenerate introspects it.
"""

# 7. Agent control
from .agent_control import (  # noqa: F401
    ActionRequest,
    AgentEvidence,
    AgentRun,
    PromptTemplateRegistry,
)
from .base import Base

# 3. Discovery (referenced by registry, governance)
from .discovery import (  # noqa: F401
    CollectionRun,
    DiscoverySource,
    EvidenceArtifact,
    ObservedFact,
    ReconciliationResult,
)

# 2. Docs (referenced by governance, registry, retrieval, agent_control)
from .docs import Document, DocumentEntityBinding, DocumentVersion  # noqa: F401

# 4. Governance (referenced by agent_control)
from .governance import ApprovalRecord, ChangeLog, PolicyRecord  # noqa: F401

# 5. Registry
from .registry import (  # noqa: F401
    Cluster,
    ClusterMembership,
    DnsResolverState,
    GpuDevice,
    Host,
    HostHardwareSnapshot,
    HostRoleAssignment,
    IpAddressAssignment,
    NetworkInterface,
    NetworkSegment,
    OwnershipAssignment,
    RouteEntry,
    ServiceDependency,
    ServiceExposure,
    ServiceInstance,
    SharedService,
    StorageAsset,
)

# 6. Retrieval
from .retrieval import (  # noqa: F401
    ChunkEmbedding,
    DocumentChunk,
    EvidencePack,
    EvidencePackItem,
)

# 1. Taxonomy (referenced by everyone else)
from .taxonomy import TaxonomyDomain, TaxonomyTerm  # noqa: F401

# Export the shared MetaData so Alembic env.py can reference it.
metadata = Base.metadata
