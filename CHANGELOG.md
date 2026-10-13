# Source release notes

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

The desktop redesign added a locally bundled daisyUI dashboard, responsive capture controls, searchable translation history, provider connection tools, advanced settings, performance timings, selectable OCR engines, source-color sampling, glyph-aware background blending, and text scaling. ChatGPT browser sign-in and Gemini API key support are separate provider integrations.
