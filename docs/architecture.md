# Architecture

FitProof is a single FastAPI process plus a React/Vite frontend. SQLite is enough for the local MVP and keeps every run inspectable.

## Investigation path

1. Validate one exact laptop model and the user's configuration.
2. Discover manufacturer documents with Google Search, or load explicit replay excerpts in replay mode.
3. Fetch only recognized manufacturer hosts, after redirect and address checks.
4. Extract typed facts with an AI provider or replay fixture.
5. Validate exact subject, supporting excerpt, value normalization and source quality.
6. Discover offers with Google Shopping Light when no exact SKU was supplied.
7. Resolve each recognizable manufacturer SKU with targeted manufacturer searches.
8. Audit missing fields and optionally run at most two targeted follow-up rounds.
9. Run independent Python checks and persist the report.

## State boundary

The LangGraph state includes the input, exact device, sources, searches, facts, offers, checks, missing fields, query count, follow-up count, events and errors. It is saved after real progress events. A restart marks an in-flight run as `interrupted`.

## Trust boundary

Search output and fetched pages are untrusted data. Page instructions are never executed. The model receives a bounded relevant excerpt and is instructed to return schema-conforming facts only. A fact is not `supported` unless its exact excerpt exists in an available manufacturer source and its normalized value is supported by that excerpt. Unknown is a valid result.

## Live and replay modes

Live mode requires all provider settings and fails closed when they are missing. Replay mode is explicit, loads three recorded manufacturer excerpts and human-reviewed fact fixtures, and displays that no live provider calls or current prices were used. It is a demo fallback, not a substitute for the live hackathon run.
