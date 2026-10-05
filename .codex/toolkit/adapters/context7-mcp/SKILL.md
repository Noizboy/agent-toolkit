---
name: context7-mcp
description: Retrieve current version-specific documentation with Context7 when implementing or configuring libraries and APIs.
---

# Context7 documentation

Use the connected Context7 MCP: resolve-library-id with the library name and task, select the authoritative version match, then query-docs with that library ID and the exact question. Reuse a known library ID when appropriate. Cite the source/version and distinguish source facts from inference.

Check actual callable tools, not just config files. The toolkit configures the HTTP endpoint and reads CONTEXT7_API_KEY from the process environment; it never stores the key. If unavailable, fetch official primary documentation and report the fallback. Do not send secrets or confidential code in documentation queries.
