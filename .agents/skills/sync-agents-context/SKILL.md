---
name: sync-agents-context
description: Maintain the repository AGENTS.md document index when project Markdown specifications are added, changed, moved, superseded, or deleted. Add only compact task-specific references; never copy documentation into AGENTS.md or index every Markdown file.
---

# Sync AGENTS.md Context References

Keep the repository's root `AGENTS.md` useful and small by maintaining a compact index of authoritative, task-specific Markdown documents.

This skill updates references only. It does not summarize entire documents, rewrite project instructions, or add every Markdown file it finds.

## Goal

After this skill runs, a coding agent should be able to:

1. Read `AGENTS.md` first.
2. Identify the one or two project documents relevant to its current task.
3. Open those documents for detailed context.

`AGENTS.md` must remain a routing document, not a duplicate knowledge base.

## Target file

1. Prefer the repository-root `AGENTS.md`.
2. If `AGENTS.md` does not exist but a root `agent.md` or `agents.md` exists, update that existing file instead of creating a duplicate.
3. Do not rename an existing instruction file unless the user explicitly requests it.
4. If no root instruction file exists, create `AGENTS.md` with only a short heading, a rule telling agents to read task-specific documents, and the managed reference section defined below.

## Discovery workflow

1. Find the repository root.
2. Inspect the current instruction file and its existing document references.
3. Identify Markdown files that were added, modified, moved, superseded, or deleted.
   - In a Git repository, check tracked files and the current diff first.
   - On the first run, or when the current index is unreliable, scan all repository Markdown files.
4. Ignore generated, dependency, cache, build, vendored, and hidden tool-output directories.
5. Read only enough of each candidate to determine its purpose and authority: title, introduction, scope, source-of-truth statements, and major headings. Read more only when classification is unclear.
6. Compare candidates with the current reference index.
7. Edit the managed section only when a material reference change is needed.
8. Verify that every indexed path exists and every description accurately identifies when the file should be read.

## Include a document only when

A Markdown file deserves an `AGENTS.md` reference when all of the following are true:

- It provides implementation context, architecture rules, domain rules, workflow rules, data contracts, API contracts, security boundaries, testing rules, or another durable source of truth.
- It affects how an agent should implement or review a meaningful class of tasks.
- Its purpose is not already fully represented by another indexed document.
- An agent can decide when to read it from a short description.

Typical documents worth indexing:

- database or migration specifications
- ontology metadata specifications
- architecture and runtime contracts
- UI implementation specifications
- action, permission, audit, or security specifications
- MCP or AI-agent integration specifications
- deployment or testing runbooks that materially constrain implementation

## Do not include

Do not add references merely because a file is Markdown.

Exclude:

- brainstorming notes and temporary design exploration
- meeting notes, transcripts, status updates, and progress logs
- task plans that are no longer authoritative
- generated reports and copied external documentation
- changelogs, contribution templates, pull-request templates, and issue templates
- duplicated, obsolete, archived, or superseded documents
- tiny notes that do not change implementation behavior
- files whose only purpose is already obvious from normal repository structure
- this skill's own `SKILL.md`

A `README.md` should be indexed only when it contains unique implementation rules that are not referenced elsewhere.

## Managed section

Maintain exactly one managed section in the root instruction file:

```markdown
## Project document index

Read only the document relevant to the current task. These files contain detailed implementation context; this file contains only routing guidance.

<!-- BEGIN MANAGED: PROJECT-DOC-REFERENCES -->
- `relative/path/to/file.md` — Read for database schema, constraints, migration rules, and seed-data compatibility.
<!-- END MANAGED: PROJECT-DOC-REFERENCES -->
```

If the markers do not exist:

- Reuse an existing project-document or context-file section when practical.
- Replace its detailed per-file explanations with the compact managed index only when doing so does not remove unique global instructions.
- Otherwise, insert the managed section near the existing source-of-truth or project-context guidance.

Never modify text outside the managed markers unless a missing section must be created.

## Reference format

Use exactly one bullet per document:

```markdown
- `path/from/repository/root.md` — Read for <specific task or layer covered by this document>.
```

Rules:

- Use the exact repository-relative path and filename casing.
- Keep each entry to one line.
- Keep the description between 8 and 24 words.
- Describe when to read the document, not everything inside it.
- Do not copy headings, object lists, table lists, endpoint lists, counts, examples, or implementation details from the source document.
- Do not repeat project background in each entry.
- Do not assign the same responsibility to multiple documents unless their boundaries are clearly different.
- Group entries under short category labels only when there are at least three references in that category.

Good:

```markdown
- `docs/database-context.md` — Read for PostgreSQL tables, relationships, constraints, indexes, migrations, and seed-data rules.
```

Too detailed:

```markdown
- `docs/database-context.md` — Defines all supplier, part, warehouse, inventory, order, shipment, purchase-order, risk-event, mitigation-plan, execution, and audit tables.
```

Too vague:

```markdown
- `docs/database-context.md` — Read for more information.
```

## Size controls

Keep the managed index lightweight:

- Maximum 24 document references.
- Maximum 3,500 characters between the managed markers.
- Prefer one authoritative document per implementation area.
- When multiple small documents cover one area, reference a stable index document instead of every child document when such an index exists.
- When the limit would be exceeded, do not silently add more entries. Consolidate duplicate references, remove obsolete entries, or recommend creating a task-specific nested `AGENTS.md` closer to that subsystem.

Do not reduce useful global instructions merely to make room for more references.

## Update rules

Apply the smallest valid change.

- Add a reference for a new authoritative document.
- Update a reference when its path or responsibility materially changes.
- Remove a reference when the file is deleted, superseded, archived, or no longer affects implementation.
- Replace an old reference when a new document explicitly supersedes it.
- Keep the existing order unless a new entry belongs beside a closely related document.
- Prefer ordering by implementation flow: project foundation, data, ontology/runtime, backend/actions, UI, AI/MCP, testing/deployment.
- Make no edit when the current index is already accurate.

## Conflict handling

When two documents appear authoritative for the same layer:

1. Look for explicit source-of-truth or superseded statements.
2. Prefer the more specific and current document.
3. Keep both only when their responsibilities are distinct and the descriptions make that boundary clear.
4. Do not invent precedence. Report the ambiguity when it cannot be resolved from the repository.

## Validation checklist

Before finishing, confirm:

- The target instruction file is the repository-root instruction file.
- All referenced files exist.
- No important indexed file was deleted or moved.
- Every included file meets the inclusion criteria.
- No temporary or duplicate document was added.
- Each entry is one concise routing sentence.
- The managed section stays within both size limits.
- Manual content outside the markers is unchanged.
- No file was modified when no material update was required.

## Completion response

Report only:

- whether the instruction file changed
- references added, updated, removed, or left unchanged
- any unresolved documentation conflict

Do not repeat the indexed documents' content in the response.
