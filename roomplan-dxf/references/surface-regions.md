# Surface Region legend and limits

SR means **Surface Region**, not “slope region”. Supplied regions retain existing `SR <room>.<index>` identifiers. Reconstructed zones use `SR reconstructed:<zoneKey>` and never impersonate a supplied face index. Registry entries record `origin`, `sourceRefs`, source face areas, and available geometry/height. Horizontal supplied faces remain intact.

CLI `--surface-region-groups <sidecar.json>` reads an explicit, source-SHA256-scoped override:

```json
{"sourceSHA256":"<exact input SHA256>","groups":[{"id":"K1","confirmation":"user-confirmed","members":["SR example.1","SR example.2"]}]}
```

A mismatched hash, unknown face, duplicate member, or cross-room/story group fails.
Without the flag the converter AUTO-DISCOVERS a sidecar beside the scan using only fixed names, most specific first:

1. `<scanDir>/<scanBase>.surface-region-groups.json`
2. `<projectDir>/surface-region-groups.json`
3. `<scanDir>/surface-region-groups.json` (for a scan at `data/scan.json`)

The same `sourceSHA256` gate applies. An explicit `--surface-region-groups` always wins over a discovered file. When two files exist the most specific one is used and `roomplan.surface-region-groups-sidecar-ambiguous` records the others. A discovered sidecar that cannot be read, is not a JSON object, or names a DIFFERENT source SHA256 is NOT applied: it is reported as `roomplan.surface-region-groups-sidecar-ignored` and conversion finishes with no groups, because a directory may legitimately hold a confirmation for another capture. An explicit path stays a hard error in that situation. Provenance is recorded as `surfaceRegions.groupsSource` (`mode` = `explicit` | `auto-discovered` | `none`, `path`, `relative`, `sourceSHA256`, `confirmedGroupCount`) in the report JSON and the Markdown line `Potvrda grupa:`; the sidecar warnings above travel with the other plan warnings into the `.roomplan.json` manifest. Nothing is inferred from a missing sidecar: no sidecar means no confirmed grouping, not a claim that the faces are not one slope.
 Without confirmation there is no confirmed grouping. A group retains all component faces; its area is a reference sum, never an additional quantity. Grouping does not flatten planes or delete horizontal caps, and it does not change any face's area. It records grouping metadata and computes the source-normal bend angle for two-face groups.

On the SHEET a confirmed group is drawn as ONE piece:

- the per-face SR labels are withdrawn and replaced by ONE group label — `SR 2.1-2.2  h 0.84-2.70` when the member ids form a series, otherwise the explicit `+` join — placed inside the stitched union of the member faces;
- ONE fall arrow is kept for the whole slope (the arrow of the largest member face); the other per-face fall arrows are withdrawn;
- the internal seam line is **not** drawn, and neither is the coincident perimeter line that both faces share — the group is outlined as one continuous union, not two adjacent polygons. The shared edge survives as data in `ceilingDiagnostics.surfaceRegionDraw[].seamWithdrawn` (`drawnOnSheet: false`), and the member faces stay in the registry with their areas unchanged. The `S<n>_CEILING_SEAM` layer remains defined in the layer table for compatibility but receives no entity. Manifest ceiling diagnostics, CLI report, Markdown references, CSV reference-only rows and USDZ root customData share one registry. CSV references leave quantity columns empty to avoid double counting. Standalone buildReport without the CLI does not construct this annotation registry.

The explicit source surface sum is retained only as a diagnostic (`surfaceAreaSumM2`): the reported ceiling quantity is the **plan-union envelope** (each square metre once, stacked duplicates add 0 m2), which is still **not a verified physical total**. Overlapping hypotheses remain unresolved; no minimum/maximum envelope is selected. User confirmation of one slope does not verify every other supplied face. Heights using supplied floor-level are not measured clear heights.

Room/storey titles contain name and area only, separated by ASCII spaces. Each reconstructed flat zone gets a regional height annotation; each split slope part gets its height. Layout sheet bounds include conservative text envelopes and unresolved annotations are moved to a reserved strip on their own story. Unresolved associations remain unresolved, without fabricated leaders. Font substitution and physical survey accuracy remain outside these guarantees.

Registry area sums are reference-only source-surface sums, never extra report
ceiling quantities. The report uses a plan-union envelope where supported;
when a footprint is unusable it explicitly falls back to a surface sum with
`usedFallback` and a warning. Group confirmation is a user assertion scoped
to the source hash, not independent physical verification.
