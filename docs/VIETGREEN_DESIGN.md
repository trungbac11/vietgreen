# VietGreen identity and overview

The design keeps the original forest-green workspace and builds a research instrument around it: a reported change, a scope-aware explorer, then evidence and coverage. Source metric names remain in their original Vietnamese; the English interface presents the name as a separate label rather than composing an English sentence around it. Coverage counts are descriptive, never sustainability scores.

## Three original vector directions

- [A — Converging signal](brand-concepts/concept-a.svg): a geometric V with two converging planes and a point of observation. The silhouette remains clear at small sizes; the point suggests a measured datum. **Selected** for its strong V and minimal internal detail.
- [B — Connected nodes](brand-concepts/concept-b.svg): a V-shaped network with three endpoints. It signals connectivity well but is closer to a conventional network icon and the thin line is less robust at 24 px.
- [C — Data strata](brand-concepts/concept-c.svg): a V intersected by horizontal data lines. It suggests analytical layers but becomes visually busy at favicon scale.

The selected mark is provided as a compact icon, standalone symbol, light symbol, and horizontal light/dark wordmarks in `app/static/brand/`. The light and dark wordmarks use a system font in the SVG; rendered wordmark typography can vary slightly with the operating system. The sidebar icons use Lucide geometry under the ISC license, vendored locally to avoid a runtime network dependency.

## Data and interaction

The featured change and spotlight use `/api/insights`, restricted to unique, exact, consecutive-year actual observations with matching recorded metric, entity, boundary and unit. The overview explorer retrieves `/api/company-metrics` and `/api/series`, separates measurement types and scopes, lets the user select a period, and exposes recorded report references. Points with duplicate or qualified values are omitted; missing years do not get connected. A recorded scope match does not independently establish methodological comparability. Reports are references, not necessarily linked PDFs.

The catalog contains only product-to-source relationships, not a claim-to-source mapping. Product evidence counts show availability, not verification. No cross-company performance ranking or product footprint is inferred.

## Practical limits

The rendered desktop/mobile review and before/after screenshots still require a browser-capable environment. The current environment has no Chromium or puppeteer-core. The legacy application has a number of pre-existing Hallmark spacing and contrast warnings that require a broader cross-page accessibility review.
