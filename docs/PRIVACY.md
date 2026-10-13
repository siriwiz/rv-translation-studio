# Data and privacy

## What stays on the PC

Screen capture, OCR, paragraph preparation, source color sampling, and background blending run locally. Argos Local also translates locally. In a prepared desktop build, local translation does not require a network connection, account, API key, or runtime model download.

The application stores its data in `%LOCALAPPDATA%\RueValleyTranslator` by default. `RUEVALLEY_DATA_DIR` selects another directory, which is useful for isolated testing.

| Data | Storage |
| --- | --- |
| ChatGPT account tokens | Windows DPAPI-encrypted account storage |
| Translation history, cache, settings | Local JSON files; not encrypted |
| OCR input screenshots | Processed locally; temporary capture files are removed after use |

DPAPI protects stored credentials for the Windows account. It does not make a compromised or shared Windows session safe. History and cache may contain recognized text from the screen.

## What cloud translation receives

ChatGPT receives recognized text and translation instructions when selected. The translation requests do not upload the screenshot image. A full-screen capture can recognize private or unrelated text, so choose a smaller region when appropriate. Cloud processing follows the selected provider's applicable account and API terms.

Browser-based authentication opens the provider's sign-in flow. Provider access and quotas are checked separately from a successful sign-in.

## Repository hygiene

This source repository excludes `.env` files, credentials, app data, personal history, caches, test data, compiled executables, dependency installations, and large model payloads. Documentation captures use isolated demonstration data. Do not attach an entire app-data directory to an issue.

To remove retained text, clear Library history and the translation cache. Log out or remove saved credentials using the application's provider controls. JSON history exports are regular files; manage them separately.
