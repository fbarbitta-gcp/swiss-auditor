# Lessons Learned: Working with Large Files & Agents in ADK

## 1. Large File Processing with Gemini
When working with large files (like PDFs) in the Google Agent Development Kit (ADK):
- **Pass Bytes directly**: Instead of extracting text manually which might lose structure or encoding, read the file as bytes and pass it as a `types.Part` with `mime_type`.
- **Inline Blob**: Use `types.Part(inline_data=types.Blob(mime_type="application/pdf", data=file_bytes))` for direct transmission.

## 2. Managing Output Token Limits
For large documents where the extracted structured data (JSON) might be extensive:
- **Increase Max Output Tokens**: The default token limit might be too low. Explicitly set `max_output_tokens` in `generate_content_config`.
  ```python
  generate_content_config=types.GenerateContentConfig(
      max_output_tokens=65536  # Increased to 64k for large billing extractions
  )
  ```
- **Validation Errors**: If the JSON is truncated, you will receive `json_invalid` errors from Pydantic validation because the JSON string ended prematurely.

## 3. Disabling "Thinking" in Gemini 2.5
Gemini 2.5 Flash has a "Thinking" feature enabled by default which consumes tokens and adds latency. To disable it using ADK:
- **Use BuiltInPlanner**: The `thinking_config` must be passed via the `planner` argument, not directly in `GenerateContentConfig`.
- **Configuration**:
  ```python
  from google.adk.planners import BuiltInPlanner
  from google.genai import types

  agent = LlmAgent(
      ...,
      planner=BuiltInPlanner(
          thinking_config=types.ThinkingConfig(
              include_thoughts=False,
              thinking_budget=0
          )
      )
  )
  ```

## 4. Handling Page Limits
Gemini/Vertex AI has a limit on the number of pages (e.g., 1000 pages) per request.
- **Split Large PDFs**: For files exceeding the limit, use a library like `pypdf` to split the document into smaller chunks.
- **Chunk Size**: We found **200 pages** to be a reliable chunk size to avoid `503 Service Unavailable` errors and reduce context processing load.
- **Multiple Parts**: Pass each chunk as a separate `types.Part` to the agent.

## 5. Isolated Session Pipeline (Context Isolation)
For multi-step complex workflows (e.g., Extraction -> Verification -> Audit), keeping a single session state often leads to context bloat and 503 errors.
- **Pattern**: Create a FRESH `InMemorySessionService` for each agent/step.
- **State Injection**: Explicitly pass the necessary results from the previous step into the new session's `state` or as `text` in the user prompt.
  - *Option A (Prompt)*: Convert the JSON result to a string and add it to `types.Content` (Best for visibility).
  - *Option B (State)*: Use `create_session(state={...})` (Best for purely programmatic data, but LLM might not see it unless instructed).
- **Result**: Drastically improved stability and reduced latency by "forgetting" the heavy PDF context of Step 1 when performing Step 2 (unless explicitly needed).

## 6. Batch Processing & Logging
- **Logging vs Print**: In batch processing, use `logging` with timestamps to track progress across many files. `print` is insufficient for debugging long-running batch jobs.
- **Dynamic Context**: Injecting the JSON output of Step 1 as *Text Context* into Step 2's prompt is often more reliable than relying solely on "state" presence, especially when sessions are isolated.
