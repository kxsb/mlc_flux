# RUNTIME001 — Contract shadow runtime

Status: shadow / non-production analytical source.

## Purpose

RUNTIME001 materializes the normalized contracts already validated by
MLCFlux:

- TRANSACTIONS001
- PARTNERS002

into the SQLite database of the installed standalone instance.

This runtime does not replace the legacy transaction pipeline yet.

## Data path

    normalized PostgreSQL transactions_*
                |
                v
          TRANSACTIONS001
                |
                v
     contract001_transactions


    administrative source adapter
                |
                v
            PARTNERS002
                |
                v
       contract002_partners

## Isolation

RUNTIME001 does not write to:

- the Lokavaluto PostgreSQL source;
- ComChain native tables;
- Cyclos;
- transactions;
- transaction_semantics;
- INPUT001 tables;
- dashboard caches.

The PostgreSQL readers remain read-only.

## Snapshot semantics

The current normalized transaction PostgreSQL reader returns the complete
configured relation.

RUNTIME001 therefore stores a complete local snapshot and replaces the
previous shadow snapshot atomically.

The same rule applies to PARTNERS002 when its provider is enabled.

A failed write transaction leaves the preceding SQLite snapshot intact.

## Configuration

Runtime secrets and installation-specific relation names belong outside the
Git checkout, in the deployed environment file.

Required for transactions:

- MLCFLUX_CONTRACT_PG_DSN
- MLCFLUX_TRANSACTIONS_RELATION

Optional:

- MLCFLUX_TRANSACTIONS_SCHEMA, public by default
- MLCFLUX_PARTNERS_PROVIDER
- MLCFLUX_PARTNERS_PG_DSN

MLCFLUX_PARTNERS_PROVIDER=disabled keeps PARTNERS002 disabled.

odoo_postgres currently selects the existing Odoo -> PARTNERS002 adapter.

## Deliberate non-goals

RUNTIME001 does not:

- project normalized transactions through Financial Core;
- reinterpret type or fn_abi;
- infer partner identity from missing values;
- classify transactions as payment/conversion/reconversion;
- feed production analytics;
- modify the current scheduled synchronization.

The purpose of this stage is only to establish a small, inspectable local
runtime for the normalized contracts.


## Snapshot provenance

Every materialized contract records:

- its contract version;
- its availability status;
- a source instance identifier;
- a non-secret source reference;
- its refresh timestamp;
- its row count.

The source instance identifier is mandatory.

This prevents a test source or another installation from being silently
mistaken for the currently installed MLC.

When PARTNERS002 is disabled, its previous local snapshot is cleared and
its runtime state is recorded as disabled. Stale administrative data must
not remain silently available.


## Neutral transaction context

The local SQLite runtime exposes the read-only view
`contract_transaction_context_v1`.

The view joins TRANSACTIONS001 with PARTNERS002 for both transaction
endpoints.

It is a local read model, not a third input contract.

It does not infer:

- professional or individual status;
- payment semantics;
- conversion or reconversion semantics;
- account ownership;
- monetary stock;
- account balance.

`amount_minor` deliberately remains expressed in the integer unit supplied
by TRANSACTIONS001. Unit conversion belongs to explicit installation
metadata and must not be guessed by the read model.

Missing partner profiles remain NULL. They are not interpreted as external.
The explicit external flags from TRANSACTIONS001 remain authoritative for
that property.

## Partner data minimization

The local PARTNERS002 snapshot persists only partner profiles referenced by
the current TRANSACTIONS001 snapshot.

Additional administrative partner records exposed by the provider are not
materialized in the local analytical database.

A missing partner profile remains a valid unresolved profile and is not
interpreted as an external endpoint.


## Shared-account ownership

A financial event is stored exactly once in
`contract001_transactions`, keyed by transaction hash.

Administrative ownership is materialized separately in
`contract001_transaction_partners` with the key:

    hash + side + partner_id

One financial endpoint may therefore be associated with multiple partner
profiles without duplicating the financial event.

`contract_transaction_context_v1` remains event-grained and can safely be
used for transaction counts.

`contract_transaction_partner_context_v1` is association-grained and is
intended for partner filtering and profile lookup. Monetary aggregation over
that association view must not be performed without returning to the event
grain.
