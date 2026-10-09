# Data Card

Status: source and licence selected; acquisition-specific provenance, schema, quality findings, exclusions, and limitations remain incomplete.

The selected source is UCI Online Retail II, a public dataset re-skinned as Boreal Marche for a pedagogical scenario. It must never be described as proprietary client data.

## Verified source information

- Publisher: UCI Machine Learning Repository
- Creator: Daqing Chen
- DOI: `10.24432/C5CG6D`
- Official page: `https://archive.ics.uci.edu/dataset/502/online+retail+ii`
- Period: 1 December 2009 through 9 December 2011
- Published size: 1,067,371 transaction rows; downloadable workbook approximately 43.5 MB
- Licence: Creative Commons Attribution 4.0 International (CC BY 4.0)
- Citation: Chen, D. (2012). *Online Retail II* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D.
- Retrieved: 3 September 2026
- Downloaded archive: 45,622,418 bytes
- Verified archive SHA-256: `572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb`
- Extracted workbook SHA-256: `bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980`
- Verified workbook sheets: `Year 2009-2010` and `Year 2010-2011`
- Bronze Parquet rows: 1,067,371 across 9 canonical columns
- Initial missingness: 243,007 customer identifiers and 4,382 descriptions

The data represents a UK-based non-store retailer, not a Quebec grocer. Geographic, temporal, product-mix, currency, and customer-population differences limit direct business generalization. Missing values and cancellations are known to be present and require explicit treatment.

## Silver cleaning summary

The bronze layer contains 1,067,371 rows. Ordered, non-overlapping rejection reasons exclude 276,411 rows and retain 790,960 rows (74.10%) in the silver transaction table.

Primary rejection reasons:

- 12,133 exact duplicates
- 242,870 rows missing a customer identifier
- 18,688 cancellation lines not already excluded
- 71 non-positive price lines not already excluded
- 2,649 service or non-product lines not already excluded

Missing-description and non-positive-quantity conditions had zero additional exclusions because those rows were already assigned to earlier missing-customer or cancellation rules. The report retains both raw-condition and newly-excluded counts so overlap remains visible.

Valid extreme purchases are retained. Values above the 99.9th percentile are flagged for quantity, unit price, and line total; 1,932 retained rows trigger at least one flag. Any transformation or cap used by a model must be learned from training data only.

The complete rule table and artifact checksums are in `reports/data/CLEANING_REPORT.md`.

## Required completion areas

- [x] Source and stable retrieval location
- [x] Licence and redistribution constraints
- [x] Retrieval date and SHA-256 checksum
- [x] Original and bronze row counts
- [x] Explicit bronze schema
- [x] Cleaning and exclusion rules with non-overlapping audit counts
- Re-skinning mapping and explicit statement of geographic/domain limitations
- Intended and out-of-scope uses
- [~] Known biases, missingness, and representativeness limits documented initially; modelling-population effects remain to be quantified
- Data retention and deletion approach
