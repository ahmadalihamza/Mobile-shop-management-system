# Offline mobile catalogue

Bundled dataset **2026.09.29.1** contains **19,667 normalized reference names across 122 brands**. The application installs `resources/mobile_catalogue.json` into an independent local SQLite database on first use. No runtime download or API request occurs.

## Sources

| Source | Retained model names | Licence / treatment |
|---|---:|---|
| [ilyasozkurt/mobilephone-brands-and-models](https://github.com/ilyasozkurt/mobilephone-brands-and-models) | 10,250 | GPL-3.0; historical 2021 dataset reused from the supplied prototype |
| [bsthen/device-models](https://github.com/bsthen/device-models) | 9,372 | Apache-2.0; device-name/code mapping downloaded 29 September 2026 |
| [Apple model identification](https://support.apple.com/en-us/108044) | 45 | Supplied factual model names; no manufacturer text or images copied |

Source attribution is also recorded per model. The supplied prototype's direct Google extract had no bundled redistribution licence and was replaced by the Apache-licensed mapping. Historical GPL text and Apache-2.0 text are in `resources/licences/`. Mobile Desk and its bundled aggregate are distributed with source under GPL-3.0-or-later. Brand/model names remain their owners' marks.

`tools/build_catalogue.py` strips redundant brand prefixes, normalizes identities, combines aliases, generates deterministic model IDs and filters obvious tablets/watches/TVs by name. Inputs are preserved locally under `reference/`; rebuild inputs are needed only to regenerate the dataset, not to build/run the app. The ready-to-import JSON is shipped with the source.

This is a broad name reference, not a verified specification database. Some regional names/device codes can represent the same physical phone and some non-phone references may survive filtering. RAM/storage variants are not fabricated; the bundled data does not claim exhaustive variant coverage. Current models missing from these sources can be added manually as shop products. No completeness claim is made.

Normalized models checksum: `e758d1f37efef8c5502fa2212ddc2eccf52df34d0017594aa30f8fa153c409f4`.

Downloaded Apache source file SHA-256: `d0a826f153f5d5950c4ec2d8d026c24b8909fd4768cae27135dd4b6fed373743`.

## Search and separation

FTS5 indexes normalized brand, model, series and aliases with token-prefix matching. A compact-name fallback tolerates missing spaces. `15 pro` locates iPhone 15 Pro/Pro Max; `a55` prioritizes Samsung Galaxy A55 5G. Search is case-insensitive and handles harmless punctuation. Shop transactions search shop products first; the worldwide reference list appears when adding a new product.

`products.catalogue_model_id` is nullable. Manual products work without it. A catalogue update cannot open or rewrite the business database. Purchases/sales keep their own product descriptions, price/quantity/rate/cost and party snapshots. Even a removed/unavailable catalogue does not erase shop history.

## Versioned JSON update

Settings → Mobile Catalogue → Import Catalogue Update accepts this format:

```json
{
  "format": "mobile-desk-catalogue",
  "schema_version": 1,
  "version": "2026.10.01.1",
  "source": "Describe the verified source and snapshot",
  "licence": "State its redistribution licence",
  "models": [
    {
      "id": "stable-model-identity",
      "brand": "Samsung",
      "model": "Galaxy A55 5G",
      "aliases": ["A55"],
      "series": "Galaxy A",
      "device_type": "Phone",
      "release_year": 2024,
      "variants": []
    }
  ],
  "sha256": "replace-with-models-checksum"
}
```

The example ID is illustrative. When updating an existing model, use its actual installed stable ID from the bundled JSON; never create a different ID for the same normalized brand/model. Only include verified variants, as `{ "ram": "8GB", "storage": "256GB" }` objects. Optional fields may be omitted; model-level `source` may override the package source.

Calculate checksum with `mobile_desk.catalogue.models_checksum(models)`, which hashes UTF-8 JSON with `sort_keys=True`, `ensure_ascii=False`, `separators=(',', ':')`. Version has 2–5 numeric parts and must be strictly newer. The importer limits package size/count, validates fields and duplicate IDs/names, upserts models/aliases/variants, rebuilds affected search entries, and records the version in one transaction. A conflict anywhere rolls the whole import back. Models absent from a package remain installed, allowing additive updates. Checksums detect corruption; packages are not cryptographically signed, so use a trusted administrator source.
