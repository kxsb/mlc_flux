# Financial Core v0.1

Status: initial neutral storage contract for FINCORE001.

## Purpose

Financial Core stores source-backed financial facts without assuming that every
financial event is a binary transfer. It replaces INPUT001 as the target model
for future neutral adapters, while INPUT001 remains untouched during migration.

The three layers are distinct:

1. `FinancialEvent`: what happened in the source.
2. `AccountEffect`: a signed monetary effect attested by, or safely derived from,
   that event.
3. Analytical projections: later interpretations consumed by MLCFlux indicators.

Financial Core does not define analytical activity categories.

## Stable dataset and atomic publication

`dataset_id` identifies one stable financial namespace. `publication_id`
identifies one validated materialization of that dataset.

A publication replaces the current materialized facts in one database
transaction. If publication fails, the preceding materialization remains valid.
Publication metadata is retained even though v0.1 keeps only the current facts,
which bounds SQLite growth during the migration phase.

The following dataset identity fields may not silently change:

- `contract_version`;
- `source_system`;
- `source_instance_id`.

A changed namespace requires a new `dataset_id`.

## Required core relations

- `financial_core_datasets`
- `financial_core_publications`
- `financial_core_accounts`
- `financial_core_events`
- `financial_core_account_effects`

Optional factual relations already represented in v0.1:

- actors;
- identity links;
- balance observations;
- monetary observations;
- account replacements;
- explicit publication capabilities.

## Event/effect invariant

An event may have zero, one, two, or many effects.

Examples:

- a scheduled but unexecuted payment can be retained as one event with zero
  realized effects;
- a realized binary transfer can be one event with two derived effects;
- a Kohinos-style change can be one event with four or more effects.

Financial Core MUST NOT require the sum of event effects to equal zero and MUST
NOT invent a counterparty in order to balance an event.

## Money representation

Every stored monetary effect or observation has:

- an exact integer `amount_minor`;
- `unit_code`;
- non-negative `unit_exponent`;
- `monetary_dimension`.

`amount_minor` rejects floats, including numerically integral floats. This keeps
the contract independent of SQLite's permissive numeric affinity.

Different monetary dimensions are not summed merely because they share an
exponent or an announced parity.

## Time representation

`time_precision` is explicit:

- `instant`: requires a timezone-aware datetime;
- `date`: requires a civil `YYYY-MM-DD` value and does not fabricate a time;
- `unknown`: stores neither an instant nor a calendar date.

Business timezone may be preserved separately when meaningful.

## Finality

`execution_state` in v0.1 can be:

- `realized`
- `pending`
- `scheduled`
- `cancelled`
- `failed`
- `reversed`
- `unknown`

Native status remains independently preserved. Adapters are responsible for
mapping source evidence to the common execution state without deleting the
native evidence.

Only later projections decide which states contribute to realized movements.

## Identity links

Accounts and actors are separate. A valid account needs no actor.

Identity links preserve their state (`resolved`, `candidate`, `rejected`, or
`unknown`). Multiple candidate actors for one account are valid and must not be
collapsed arbitrarily.

## Provenance

Core rows provide explicit native references and optional provenance references,
hashes, and structured native attributes. A later adapter must keep enough
source evidence to explain and recompute a publication without relying on UI
labels.

## Explicit capabilities

Publication capabilities use `available`, `partial`, `unavailable`, or
`unknown`. Availability is independent of row count: a capability may be
available and legitimately contain zero observations.

This is intended to feed a later pipeline/status API and, eventually, UI levels
of data enrichment.

## Non-goals of v0.1

FINCORE001 does not yet:

- migrate Cyclos or ComChain providers;
- replace the INPUT001 shadow runtime;
- expose Financial Core to the dashboard;
- define payment/activity/LM3 semantic projections;
- remove any legacy table or route.
