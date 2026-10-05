---
name: spec-kit
description: Use GitHub Spec Kit templates to define requirements, acceptance criteria and implementation plans for substantial or ambiguous features.
---

# Spec Kit adapter

This is a local Codex adapter for https://github.com/github/spec-kit. Find spec-kit source_path in .agent-toolkit/tools.lock.json; read the locked README.md and relevant templates under that checkout. Do not import upstream contributor-only skills as the product workflow.

For substantial work, define the problem, users, acceptance criteria, scope, data/privacy concerns and exceptional states. Resolve architectural constraints into a plan and bounded tasks tied to acceptance criteria. Preserve the project's existing specification format and scale documentation to the actual request; tiny fixes do not require a specification tree.

Downloading templates does not install Specify CLI or initialize a project. If the user requests CLI setup, inspect current official usage and platform prerequisites first. Initialization must preserve AGENTS.md, existing specs, repository history and unrelated files. Do not execute upstream setup scripts during toolkit bootstrap.
