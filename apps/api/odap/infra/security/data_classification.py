from enum import Enum


class DataClassification(str, Enum):
    TS = "TS"
    S = "S"
    C = "C"
    U = "U"


CLASSIFICATION_LABELS = {
    DataClassification.TS: "Top Secret",
    DataClassification.S: "Secret",
    DataClassification.C: "Confidential",
    DataClassification.U: "Unclassified",
}

CLASSIFICATION_HIERARCHY = {
    DataClassification.TS: 4,
    DataClassification.S: 3,
    DataClassification.C: 2,
    DataClassification.U: 1,
}


def can_access(user_clearance: DataClassification, data_classification: DataClassification) -> bool:
    return CLASSIFICATION_HIERARCHY.get(user_clearance, 0) >= CLASSIFICATION_HIERARCHY.get(data_classification, 0)
