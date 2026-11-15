# VietGreen UI/UX audit and implementation notes

## Findings and priorities

1. **Insight discovery:** The original overview opened with a promotional panel and four coverage counts, requiring users to find trends themselves. The overview now starts with calculated, source-referenced changes and links to the matching company metric and scope.
2. **Interpretation:** Counts of observations and metrics describe reporting coverage, not performance. This distinction is now stated beside company discovery and preserved in company coverage.
3. **Evidence:** Company observations include report names, page numbers and scope; the source PDFs are not included in the demo. Product sources are associated with products, not individual claims. Claim records now explicitly say this and link to available product sources rather than implying independent verification.
4. **Analytical context:** The existing chart already separates entity, boundary, unit and measurement type, excludes ambiguous observations, and preserves values. The chart now breaks its line at missing years. Findings use only unique, exact, consecutive-year actuals with the same recorded series fields and a positive baseline.
5. **Visual hierarchy and accessibility:** The existing green workspace and navigation remain. An editorial findings list, restrained surfaces, readable hierarchy, keyboard focus treatment and responsive layouts improve the overview. Further browser-based contrast and assistive-technology testing is needed.

## Data and calculation limitations

The insight endpoint calculates `(current − previous) / previous × 100` from database records. Each result retains observation IDs, metric, entity, boundary, unit, measurement type, periods, report references, methodology and limitations. Matching recorded scope does not establish that underlying methodologies or boundaries are scientifically comparable, nor does a decrease automatically mean better environmental performance. Records may be extracted without independent review.

Product source links are only product-level associations; certification scope and company data must not be attributed to a product without specific evidence. Company report filenames and page numbers are references, not direct PDF links. The system does not rank companies, assess claims as true or false, or calculate a product footprint.

## Remaining work

- Add explicit claim-to-source relationships and document URLs/pages to the data model before claiming evidence supports a particular claim.
- Add reporting methodology and organizational-boundary change metadata, and use it to validate comparisons.
- Add a dedicated multi-company explorer with compatible-series checks and URL-backed period filters; the current explorer uses existing company metric and scope controls.
- Add related-product comparison and fuller evidence coverage/gap analysis once comparable attributes and claim-level links are available.
- Review rendered desktop and mobile screens, keyboard navigation, contrast and screen-reader output; capture screenshots in an environment with a browser and a permitted local server.
