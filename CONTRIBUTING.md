# Contributing to BianLunTing

Thank you for helping improve BianLunTing. Contributions should preserve the framework's central principle: policy-review conclusions must remain evidence-grounded, traceable, and open to authorized human review.

## Ways to Contribute

- report reproducible bugs;
- improve documentation and examples;
- add tests or evaluation fixtures;
- propose policy-pack examples using public or simulated materials;
- add collectors for new structured data-source types;
- improve privacy, traceability, and review safeguards.

## Development Setup

Follow [docs/development.md](docs/development.md) for environment configuration, startup commands, test layers, and extension points.

Before opening a pull request, run the checks relevant to your change:

```powershell
.\scripts\validate-packs.ps1
.\scripts\test-backend.ps1 -Mode unit
.\scripts\test-backend.ps1 -Mode api
.\scripts\test-frontend.ps1 -Mode all
```

Some scripts require a local database or LLM credentials. State clearly in the pull request which checks were run and which could not be run locally.

## Policy and Data Contributions

- Do not submit personal identifiers, credentials, or non-public business data.
- Prefer public policy texts, simulated examples, and desensitized fixtures.
- Keep policy logic in `policy_packs/` and schema mappings in `data_source_packs/`.
- Add tests for new rules, collectors, or runtime behavior.
- Document the source and intended scope of each policy example.

## Pull Requests

Keep each pull request focused. Describe the problem, implementation approach, validation performed, and any policy, privacy, or compatibility considerations.

By contributing, you agree that your contribution will be licensed under the Apache License 2.0.
