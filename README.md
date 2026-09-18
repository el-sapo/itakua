# Itakua

Itakua is a portable, agent-friendly framework for a personal knowledge base. It keeps
distilled knowledge in Markdown, raw evidence in append-only logs, large artifacts in
cloud storage, and operating rules in the `itakua-map` skill.

The project ships one plugin, [`itakua`](plugins/itakua), for both Claude and Codex.
Both hosts load the same skill and scripts; only their discovery manifests differ.

## The model

Every brain stores its nodes under `spaces/`. Every node has four slots:

- `notes/` — distilled knowledge; agents may edit it only with owner approval.
- `log/` — dated raw evidence; append-only and never silently rewritten.
- `docs/` — optional durable artifacts; creation or editing requires owner approval.
- `_tmp/` — manual staging; never processed automatically and never deleted without
  owner approval.

See the [one-page overview](docs/index.html) for the architecture.

## Install with Claude

```sh
claude plugin marketplace add <path-to-itakua>
claude plugin install itakua@itakua
```

Restart the session afterwards; Claude discovers skills at session start.

## Install with Codex

```sh
codex plugin marketplace add <path-to-itakua>
codex plugin add itakua@itakua
```

Start a new Codex task afterwards so it discovers `itakua-map`.

## Validate a checkout

```sh
claude plugin validate .claude-plugin/marketplace.json --strict
claude plugin validate plugins/itakua --strict
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
python3 -m json.tool plugins/itakua/.codex-plugin/plugin.json >/dev/null
```

## License

[MIT](LICENSE)
