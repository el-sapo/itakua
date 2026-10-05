# Itakua

Itakua is a portable, agent-friendly framework for a personal knowledge base. It keeps
distilled knowledge in Markdown, raw evidence in append-only logs, large artifacts in
cloud storage, with normal operating rules in `itakua-map` and machine setup in
`itakua-setup`.

The project ships one plugin, [`itakua`](plugins/itakua), for both Claude and Codex.
Both hosts load the same two skills; only their discovery manifests differ.

## The model

Every brain stores its nodes under `spaces/`. Every node has four slots:

- `notes/` — distilled knowledge; agents may edit it only with owner approval.
- `log/` — dated raw evidence; append-only and never silently rewritten.
- `docs/` — optional durable artifacts; creation or editing requires owner approval.
- `inbox/` — captured, not yet filed; text is tracked, other files stay on the machine.
  Nothing there is a source, nothing processes it unattended, and nothing is removed
  without owner approval.

Any other folder inside a node is limbo: the owner's own space, which agents leave alone.

See the [one-page overview](docs/index.html) for the architecture.

## Install with Claude

```sh
claude plugin marketplace add el-sapo/itakua --scope user
claude plugin install itakua@itakua --scope user
```

Restart the session afterwards; Claude discovers skills at session start.

## Install with Codex

```sh
codex plugin marketplace add el-sapo/itakua
codex plugin add itakua@itakua
```

Start a new Codex task afterwards so it discovers `itakua-map` and `itakua-setup`.

## Validate a checkout

```sh
claude plugin validate .claude-plugin/marketplace.json --strict
claude plugin validate plugins/itakua --strict
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
python3 -m json.tool plugins/itakua/.codex-plugin/plugin.json >/dev/null
python3 -m unittest discover -s tests -v
```

## License

[MIT](LICENSE)
