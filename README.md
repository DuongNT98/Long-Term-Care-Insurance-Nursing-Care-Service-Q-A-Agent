# HCR-C2-054 — Long-Term Care Insurance & Nursing Care Service Q&A Agent

> **Category**: Cat 2 (multiple processing steps combined to complete one specific use case)
> **Industry**: Healthcare

## Overview

This agent answers questions about Japan's Long-Term Care Insurance (介護保険) system for family
caregivers, care workers, and municipality staff. Given a natural-language question — in Japanese
or English — about service eligibility by certified care level, out-of-pocket cost rules, covered
service types, or application procedures, it returns a plain-language answer grounded in the
relevant law and public guidance, together with a source reference. Because care costs and
provider availability vary by municipality, the agent appends a note directing the caller to
confirm local specifics whenever a municipality code isn't supplied. Every answer also carries a
non-suppressible notice that the response is general program information, not an individualized
care determination or medical advice, and that care-plan-specific decisions belong with the
caller's care manager. Free-text care-level phrasing that doesn't match one of the standard
categories can optionally be normalized by a real LLM call (Azure OpenAI); a missing/unconfigured
key or an LLM-call failure degrades to keeping the caller's original wording rather than failing
the request. It deliberately does not process patient medical records, does not make an
individualized eligibility determination, and does not replace the certified care-need assessment
process.

This is an agent template built with the **AGENTIC STAR** development platform and the
**AgentCore Framework**. It is intended to be taken as a starting point: fork it, adapt it to
your own data and policies, and run it inside your own AGENTIC STAR deployment.

## Requirements

**This template does not run standalone.** It requires:

| Requirement | Notes |
|---|---|
| **AGENTIC STAR platform** | The agent connects to the platform at start-up. Without it, start-up fails immediately (see *Behaviour without the platform* below). Deployment guides and API documentation: [AGENTIC STAR Developers](https://developers.fd.agenticstar.tm.softbank.jp/) |
| **AgentCore Framework** (`agenticstar-agentcore`) | Installed from PyPI as a dependency. |
| Python | >=3.11 |

```bash
pip install -e .
```

### Behaviour without the platform

The framework is designed to run **only** on AGENTIC STAR. There is no fallback or degraded
mode. If the platform is unreachable or the SDK version does not match, the agent raises
`PlatformRequired` during graph compile / start-up preflight rather than starting in a partially
working state. This is intentional — a half-running agent is worse than one that refuses to start.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Tests run without a platform connection. Running the agent itself does not.

## Project Structure

```
src/          agent implementation (nodes, services, schemas)
tests/        unit, integration and boundary tests
config/       agent configuration
docs/         design and operational documentation
```

See `docs/` for the design spec and test specification.

## Customising

1. Adjust `config/` for your own environment and policies.
2. Replace the knowledge sources and sample data with your own.
3. Review the node implementations under `src/nodes/` for domain-specific logic.
4. Re-run the test suite.

## License

MIT — see [LICENSE](LICENSE).

## Status of this repository

This template is published **as is**, by its individual author, under the MIT license. It carries
**no warranty and no support commitment**, and no organisation stands behind its behaviour or
fitness for any purpose. Issues and pull requests may or may not receive a response; that is at
the sole discretion of the repository owner.
