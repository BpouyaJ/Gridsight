# Clean-data contract

## Canonical hourly time contract

Every clean GridSight dataset will use a unique UTC interval as its canonical
time key while retaining Europe/Berlin reporting context and the exact SMARD
source labels.

### Input requirements

- `Start date` and `End date` use SMARD's English 12-hour timestamp text.
- Rows remain in source order.
- Each raw start/end label pair spans one wall-clock hour.
- The source resolution is hourly.

### Output columns

| Column | Type | Meaning |
|---|---|---|
| `source_start_text` | string | Unchanged raw SMARD start label. |
| `source_end_text` | string | Unchanged raw SMARD end label. |
| `interval_start_utc` | timezone-aware datetime | Unique canonical interval key in UTC. |
| `interval_end_utc` | timezone-aware datetime | Exactly one real hour after the UTC start. |
| `interval_start_local` | timezone-aware datetime | Start rendered in `Europe/Berlin`. |
| `interval_end_local` | timezone-aware datetime | Canonical UTC end rendered in `Europe/Berlin`. |
| `utc_offset_minutes` | integer | Local UTC offset: 60 for CET or 120 for CEST. |
| `is_dst` | boolean | Whether the local start is in daylight-saving time. |
| `local_fold` | integer | `1` for the second occurrence of a repeated autumn hour; otherwise `0`. |

### Normalization rules

1. Parse English month abbreviations deterministically without depending on the
   computer's locale.
2. Preserve both source timestamp strings before creating canonical columns.
3. Localize ordered start timestamps to `Europe/Berlin`; source order assigns
   the first and second offsets to repeated autumn hours.
4. Convert localized starts to UTC and require them to be unique, strictly
   increasing, and one hour apart.
5. Derive `interval_end_utc` as `interval_start_utc + 1 hour`, then convert that
   canonical end back to Europe/Berlin for reporting.
6. Reject malformed text, unexpected source ordering, genuine gaps, duplicate
   UTC starts, or non-hourly source label pairs.

### Why source end text is not localized independently

SMARD's spring row from `01:00` to `02:00` ends on a local label that does not
exist when the clock jumps to `03:00`. During the autumn fallback, both source
rows beginning at `02:00` show `03:00` as their end. Independently localizing
those labels would create invalid or two-hour intervals.

GridSight therefore preserves `source_end_text` as lineage evidence but derives
the canonical end from the disambiguated UTC start and declared hourly
resolution. No row is dropped or merged.

### Verification

Run the normalization against all six immutable snapshots without writing clean
data:

```powershell
python -m gridsight.transformation.check_timestamps
```

The command succeeds only if every snapshot becomes continuous, unique hourly
UTC intervals. Focused tests separately cover the spring gap, both autumn
`02:00` occurrences, and rejection of a genuine source gap.

Measure parsing, category-specific names, missing-value flags, and clean-output
storage are defined in later Phase 3 steps.
