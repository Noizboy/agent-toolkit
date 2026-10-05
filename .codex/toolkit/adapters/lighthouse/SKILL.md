---
name: lighthouse
description: Measure performance, accessibility and web best practices with Lighthouse for an authorized running web interface.
---

# Lighthouse adapter

This local adapter routes web auditing to https://github.com/GoogleChrome/lighthouse. Read the locked upstream README.md and project audit scripts. Prefer a reproducible production/preview build with a known URL and browser configuration.

Use an already available Lighthouse runtime or the project's existing audit command. Source download does not install Chrome or Lighthouse. Report missing prerequisites instead of invented scores. Record URL, build, device/throttling settings, time and report path. Use repeated measurements only when variation materially affects a decision.

Treat automated accessibility scores as partial evidence; also inspect keyboard navigation, focus, labels, contrast and important interactions. Native/embedded/non-web systems use platform-appropriate checks. Never launch an audit against an unrelated target or install an application dependency merely to prepare this skill.
