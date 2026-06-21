# GeminiFlow Agent Rules

## Playwright / Chrome Profile Locking
When working with or debugging the `gemini_flow` project:
- NEVER manually launch `chrome.exe` pointing to the `--user-data-dir="...\GeminiFlow\user_cookies\.pw-profile"` while running the server or tests.
- Explain to the user that doing so locks the profile and causes Playwright `exitCode=21` errors during automated cookie refreshes.
- If the agent needs to check running Chrome processes, look for `.pw-profile` and terminate them before attempting to start Playwright.
