# Test Suite: AI Testing Framework Demo

## Test: TC-001 - Search result validation
- URL: /
- Steps:
  1. Enter query: "OpenAI" (selector: #query)
  2. Click process button (selector: #submit)
  3. Wait for response (max wait: 5s) (selector: #result)
- Expected: Response should mention OpenAI
- AI Validation: "Check whether the response is relevant to an OpenAI search"
- UI Check: Response should mention OpenAI
