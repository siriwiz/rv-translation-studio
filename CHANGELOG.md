# Release notes

## 2.10.0 — RV identity and focused providers

- Introduces generated RV logos in white-on-black and black-on-white rounded-square variants, plus a Windows icon with multiple display sizes.
- Replaces the initial house illustration with a generated monochrome mountain valley, stone viaduct, and railway station.
- Removes Gemini authentication, API/CLI translation, controls, runtime payloads, preparation scripts, and provider-specific tests. ChatGPT and Argos Local remain available.
- Recovers retired provider selections to ChatGPT on startup and preserves the remaining account and local translation workflows.
- Adds Windows file/product version metadata and updates documentation, screenshots, and build instructions.
- Source validation: 60 regression tests and desktop UI acceptance, including local translation and responsive layout checks.


## 2.9.3 — Source preview

- Local source detection operates per passage, including mixed Japanese/English content.
- Fullscreen local translation can retain unresolved original passages while showing successful translations, with bounded recovery for empty responses.
- English dialogue uses the same Playpen Sans Thai family as Thai dialogue.
- This source checkpoint passed 70 regression tests. A generated executable is not a verified GitHub release.

## 2.9.2 — Benchmark baseline

- Argos sentence-boundary preparation and local-language detection support offline multilingual translation.
- Bundled offline routes cover English, Thai, Simplified Chinese, Japanese, Korean, French, German, Spanish, Vietnamese, and Russian.
- RapidOCR and Argos/OpenAI performance comparison was recorded on 13 October 2026; see the benchmark report for completeness limitations.

## Earlier development

The desktop redesign added a locally bundled daisyUI dashboard, responsive capture controls, searchable translation history, provider connection tools, advanced settings, performance timings, selectable OCR engines, source-color sampling, glyph-aware background blending, and text scaling. ChatGPT browser sign-in remains the cloud provider integration.
