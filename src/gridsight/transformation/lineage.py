"""Shared row-level lineage for canonical transformed datasets."""

from dataclasses import dataclass

import pandas as pd

from gridsight.ingestion.snapshot_registry import ExportDefinition

SOURCE_EXPORT_ID_COLUMN = "source_export_id"
SOURCE_CATEGORY_COLUMN = "source_category"
SOURCE_GEOGRAPHY_COLUMN = "source_geography"
SOURCE_RESOLUTION_COLUMN = "source_resolution"
SOURCE_PERIOD_START_COLUMN = "source_period_start"
SOURCE_PERIOD_END_COLUMN = "source_period_end"
SOURCE_ORIGINAL_FILENAME_COLUMN = "source_original_filename"
SOURCE_FILENAME_COLUMN = "source_filename"
SOURCE_SHA256_COLUMN = "source_sha256"
LINEAGE_COLUMNS = (
    SOURCE_EXPORT_ID_COLUMN,
    SOURCE_CATEGORY_COLUMN,
    SOURCE_GEOGRAPHY_COLUMN,
    SOURCE_RESOLUTION_COLUMN,
    SOURCE_PERIOD_START_COLUMN,
    SOURCE_PERIOD_END_COLUMN,
    SOURCE_ORIGINAL_FILENAME_COLUMN,
    SOURCE_FILENAME_COLUMN,
    SOURCE_SHA256_COLUMN,
)


@dataclass(frozen=True)
class SourceLineage:
    """Row-level source lineage copied from an approved manifest record."""

    export_id: str
    source_category: str
    source_geography: str
    source_resolution: str
    period_start: str
    period_end: str
    original_filename: str
    local_filename: str
    sha256: str

    @classmethod
    def from_record(
        cls,
        definition: ExportDefinition,
        record: dict[str, str],
    ) -> "SourceLineage":
        """Create transformation lineage from matching config and manifest."""
        matching_fields = (
            "export_id",
            "source_category",
            "source_geography",
            "source_resolution",
            "period_start",
            "period_end",
            "local_filename",
        )
        for field in matching_fields:
            if record[field] != getattr(definition, field):
                raise ValueError(
                    f"Manifest {field} mismatch for {definition.export_id}"
                )

        return cls(
            export_id=record["export_id"],
            source_category=record["source_category"],
            source_geography=record["source_geography"],
            source_resolution=record["source_resolution"],
            period_start=record["period_start"],
            period_end=record["period_end"],
            original_filename=record["original_filename"],
            local_filename=record["local_filename"],
            sha256=record["sha256"],
        )

    def validate_for(
        self,
        source_category: str,
        source_geography: str,
    ) -> None:
        """Require the expected category, geography, hourly grain, and hash."""
        if self.source_category != source_category:
            raise ValueError(
                f"Transformation requires {source_category} source category"
            )
        if self.source_geography != source_geography:
            raise ValueError(
                f"Transformation requires {source_geography} geography"
            )
        if self.source_resolution != "hour":
            raise ValueError("Transformation requires hourly resolution")
        if len(self.sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.sha256
        ):
            raise ValueError("Transformation lineage requires lowercase SHA-256")


def attach_source_lineage(
    frame: pd.DataFrame,
    lineage: SourceLineage,
) -> None:
    """Attach constant lineage columns to a transformed frame in place."""
    frame[SOURCE_EXPORT_ID_COLUMN] = lineage.export_id
    frame[SOURCE_CATEGORY_COLUMN] = lineage.source_category
    frame[SOURCE_GEOGRAPHY_COLUMN] = lineage.source_geography
    frame[SOURCE_RESOLUTION_COLUMN] = lineage.source_resolution
    frame[SOURCE_PERIOD_START_COLUMN] = lineage.period_start
    frame[SOURCE_PERIOD_END_COLUMN] = lineage.period_end
    frame[SOURCE_ORIGINAL_FILENAME_COLUMN] = lineage.original_filename
    frame[SOURCE_FILENAME_COLUMN] = lineage.local_filename
    frame[SOURCE_SHA256_COLUMN] = lineage.sha256
