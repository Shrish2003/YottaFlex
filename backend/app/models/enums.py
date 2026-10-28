from enum import StrEnum


class ShipmentStatus(StrEnum):
    PLANNED = "planned"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class ContainerStatus(StrEnum):
    PREPARED = "prepared"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    QUARANTINED = "quarantined"


class SensorType(StrEnum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"


class SensorStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAULTY = "faulty"


class ReadingQualityStatus(StrEnum):
    VALID = "valid"
    SUSPECT = "suspect"
    INVALID = "invalid"


class RouteStopStatus(StrEnum):
    PLANNED = "planned"
    ARRIVED = "arrived"
    DEPARTED = "departed"
    SKIPPED = "skipped"


class ExcursionSeverity(StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"


class ExcursionStatus(StrEnum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"


class CustodyEventType(StrEnum):
    HANDOVER = "handover"
    RECEIVED = "received"
    DISPATCHED = "dispatched"


class CorrectiveActionType(StrEnum):
    INSPECT = "inspect"
    QUARANTINE = "quarantine"
    RECALIBRATE = "recalibrate"
    REVIEW = "review"
    OTHER = "other"


class CorrectiveActionStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
