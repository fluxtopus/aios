# Python Packages (PyPI)

This repo publishes Python packages to PyPI so agents can install them directly with `uv`.

## Published Packages

Current package names and latest released versions:

| Package | Version | Import |
|---|---|---|
| `fluxos-agent` | `2.0.0` | `flux_agent` |
| `fluxos-stripe` | `1.0.1` | `fluxos_stripe` |
| `inkpass-sdk` | `0.1.2` | `inkpass_sdk` |
| `mimic-sdk` | `0.1.1` | `mimic` |

## Install With uv

Add to a project:

```bash
uv add fluxos-agent fluxos-stripe inkpass-sdk mimic-sdk
```

Pin exact versions:

```bash
uv add "fluxos-agent==2.0.0" "fluxos-stripe==1.0.1" "inkpass-sdk==0.1.2" "mimic-sdk==0.1.1"
```

For ad-hoc agent runs (without editing project dependencies):

```bash
uv venv .venv
source .venv/bin/activate
uv pip install fluxos-agent fluxos-stripe inkpass-sdk mimic-sdk
```

## Quick Smoke Test

```bash
python -c "import flux_agent, fluxos_stripe, inkpass_sdk, mimic; print('ok')"
```

## Minimal Usage

```python
# fluxos-agent
from flux_agent import Agent, AgentOptions

# fluxos-stripe
from fluxos_stripe import StripeClient, StripeConfig

# inkpass-sdk
from inkpass_sdk import InkPassClient, InkPassConfig

# mimic-sdk
from mimic import MimicClient
```

## Release Source

- Release/publish process: `docs/release-playbook.md`
- Publish workflow: `.github/workflows/publish-release.yml`
