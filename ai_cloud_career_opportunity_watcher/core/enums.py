from enum import Enum


class SourceType(str, Enum):
    JOB = "job"
    NEWS = "news"
    CHANGE = "change"


class OpportunityStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DeliveryStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
