# Your first translation

RV Translation Studio translates a captured screen and places the result over the original scene. Translation starts when you release **F1**. It does not continuously watch the screen.

## Set up a workspace

1. Open **Connection** and select a translation provider. **Argos Local** works without an account once the bundled models are present. For ChatGPT, sign in through the browser and select a model returned by your account. For Gemini, choose API key mode and enter your key in the native masked dialog.
2. In **Studio**, choose the source and target languages. Start with an explicit source language when testing a new game.
3. Open **Settings → Capture** and choose the OCR engine and reading profile. The OCR profile must be able to read the source script.
4. Choose a display and capture area in Studio. Return to your game and release **F1**.
5. Press **F2**, or click the overlay when click-to-clear is enabled, before the scene changes.

| Shortcut | Action |
| --- | --- |
| F1, on release | Capture, recognize, translate, and show the overlay |
| F1 in Custom area mode | Open the crop selector; releasing the mouse starts translation |
| F2 | Clear the current overlay |
| Esc during selection | Cancel the crop selector |

## Choose a capture area

- **Full screen:** reads the selected display. Menus, HUD labels, and unrelated text may also be recognized.
- **Subtitle zone:** limits recognition to the lower part of the display. Adjust the subtitle percentage in Settings.
- **Custom area:** release F1, then drag around the dialogue. Select the region again for each capture.

Custom area usually gives the cleanest dialogue extraction and sends less unrelated text to cloud providers. Use windowed or borderless games when exclusive fullscreen interferes with capture or the overlay.

## OCR and language detection

**Windows native** uses installed Windows OCR languages. **RapidOCR** uses bundled ONNX models and does not need Windows language packs. **Windows via PowerShell** is a compatibility option.

RapidOCR offers eleven reading profiles: English; Chinese/Japanese/English; Korean/English; Latin/Vietnamese; Thai/English; Cyrillic/Russian; Arabic/Persian/Urdu; Devanagari/Hindi/Nepali; Greek; Tamil; and Telugu.

**Follow source** selects a matching profile for an explicit source language. With **Auto** source, it defaults to Chinese/Japanese/English. Select a reading profile manually for other scripts. Text language detection happens after OCR; it cannot recover characters the chosen OCR model did not recognize.

Auto detection is useful for mixed English/Japanese dialogue. Short labels and names can be ambiguous. Choose an explicit source when detection is unreliable. Version 2.9.3 source detects local translation languages per passage and preserves unresolved fullscreen passages rather than discarding the entire successful result.

## Make the overlay fit

- **Text scale:** 60–180% relative to the fitted text size; Reset returns to 100%.
- **Match source colors:** samples the original text color before removing the source glyphs.
- **Smart dialogue:** joins nearby OCR lines into passages so translation can keep their context.
- **Background blend:** fills source text areas from surrounding captured pixels. Complex textures, motion, and overlapping UI can still leave artifacts.
- **Stay in game:** hides the workspace during capture and avoids switching focus to the dashboard.

The overlay contains captured pixels. It does not track later animation or camera movement. Clear it and capture again after the scene changes.

## Library and settings

**Library** keeps recent translations locally, with search, selection, copy, JSON export, and clear/undo. **Connection** includes a text workbench for checking translation independently of OCR. Documentation screenshots use illustrative dialogue entered explicitly, not a measured translation result.

Settings cover capture delay and size limit, passage limit, OCR profile, provider/model, request timeout, cache, blend radius and mask padding, text appearance, click-to-clear, and interface motion. **Performance Lab** shows capture, OCR, preparation, translation, and blend timings for the most recent capture. Use it to identify the slow stage before changing engines.

## Troubleshooting

| Symptom | Try |
| --- | --- |
| F1 does nothing | Confirm a provider/model is ready; close another instance; check whether another app owns F1; match the game's privilege level when necessary. |
| OCR misses a script | Select a matching RapidOCR reading profile, or install the corresponding Windows OCR language. Increase capture size if small text is downscaled too far. |
| Translation is slow | Inspect Performance Lab. Reduce the capture area; enable cache; try Argos Fast for local latency or a faster model available to your cloud account. |
| Argos omits part of a sentence | Use shorter dialogue selections or compare with a cloud provider. Fast/Balanced/Quality change decoding effort and do not guarantee complete translation. |
| Local incomplete-text message | Retry a smaller region or an explicit source. The 2.9.3 source has partial fullscreen recovery; the earlier 2.9.2 binary may still reject the full result. |
| ChatGPT login succeeds but inference fails | Reload account models and check model access, workspace restrictions, and account quotas. Login alone does not guarantee inference access. |
| Gemini personal-account CLI is unsupported | Use Gemini API key mode. Legacy CLI organization access depends on the account's entitlement. |
| Overlay blocks a new scene | Press F2, then capture again. |

For an issue report, include the source version, provider/model, OCR profile, capture mode, sanitized error, and Performance Lab timings. Remove keys, tokens, account details, and private screen content.
