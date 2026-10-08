# Itakua

Itakua is a portable, agent-friendly framework for a personal knowledge base. It keeps
distilled knowledge in Markdown, raw evidence in append-only logs, and large artifacts
in cloud storage. A brain is a folder of plain files: it needs no sync, and takes any.

The project ships one plugin, [`itakua`](plugins/itakua), for both Claude and Codex, with
three skills: `itakua-map` for normal operation, `itakua-setup` to stand a brain up on a
machine, and `itakua-sync` for whatever carries it between machines. Both hosts load the
same skills; only their discovery manifests differ.

## The model

Every brain stores its nodes under `spaces/`. Every node has four slots:

- `notes/` — distilled knowledge; agents may edit it only with owner approval.
- `log/` — dated raw evidence; append-only and never silently rewritten.
- `docs/` — optional durable artifacts in cloud storage; creation or editing requires
  owner approval. No sync ever carries the `docs/drive` link.
- `inbox/` — captured, not yet filed. Nothing there is a source, nothing processes it
  unattended, and nothing is removed without owner approval.

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

Start a new Codex task afterwards so it discovers the skills.

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
