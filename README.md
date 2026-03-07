<div align="center">

<img src=".github/assets/tx_lsp.png" alt="tx-lsp — Generic Language Server for textX DSLs" width="600"/>

# tx-lsp

**Instant IDE support for any textX-based DSL.**\
Diagnostics · Completions · Hover · Go-to-Definition · References · Symbols

[![PyPI](https://img.shields.io/pypi/v/tx-lsp?color=blue)](https://pypi.org/project/tx-lsp/)
![Python](https://img.shields.io/pypi/pyversions/tx-lsp)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![CI](https://github.com/robotics-4-all/tx-lsp/actions/workflows/ci.yml/badge.svg)](https://github.com/robotics-4-all/tx-lsp/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/robotics-4-all/tx-lsp/branch/master/graph/badge.svg)](https://codecov.io/gh/robotics-4-all/tx-lsp)

[Install](#installation) · [Quick Start](#quick-start) · [REST API](#rest-api) · [Editor Setup](#editor-integration) · [Contribute](#development)

</div>

---

## Why tx-lsp?

Building a DSL with [textX](https://textx.github.io/textX/) is fast. Getting editor support for it shouldn't be slow.

**tx-lsp** is a generic [Language Server Protocol](https://microsoft.github.io/language-server-protocol/) implementation that works with *any* textX grammar — **zero configuration required**. Install your textX language, start the server, and your editor lights up with diagnostics, completions, hover info, navigation, and more.

No custom LSP code. No per-language setup. Just `pip install` and go.

### Key Highlights

- **Zero-config** — auto-discovers installed textX languages via Python entry points
- **Editor-agnostic** — works with VS Code, Neovim, Emacs, Sublime Text, or any LSP client
- **Full LSP coverage** — diagnostics, completion, hover, go-to-definition, find references, document symbols
- **Optional REST API** — expose any textX DSL as an HTTP service, [Rosetta](https://github.com/robotics-4-all/rosetta)-compatible
- **Lightweight** — built on [pygls](https://github.com/openlawlibrary/pygls) and [lsprotocol](https://github.com/microsoft/lsprotocol), minimal footprint

---

## Installation

> **Requires Python 3.10+**

```bash
pip install tx-lsp
```

With REST API support:

```bash
pip install "tx-lsp[api]"
```

---

## Quick Start

### Start the LSP Server

```bash
# stdio — default, for editor integration
tx-lsp

# TCP — useful for debugging
tx-lsp --tcp --port 2087

# WebSocket
tx-lsp --ws --port 2087
```

### Map Custom File Extensions

When your DSL uses a file extension different from what's registered:

```bash
tx-lsp --extra-pattern '*.auto=smauto' --extra-pattern '*.rob=robodsl'
```

### Start the REST API

```bash
tx-lsp --api --api-port 8080

# With authentication
tx-lsp --api --api-port 8080 --api-key YOUR_SECRET
```

That's it. The server discovers all textX languages installed in your environment and serves them immediately.

---

## LSP Features

| Feature | Description |
|---------|-------------|
| **Diagnostics** | Real-time parse and semantic error reporting as you type |
| **Completion** | Grammar keywords and cross-reference suggestions |
| **Hover** | Rule type, attributes, and metadata on mouse-over |
| **Go-to-Definition** | Jump to where any symbol is defined, across files |
| **Find References** | Locate every usage of a symbol in the workspace |
| **Document Symbols** | Structured outline for navigation and breadcrumbs |

---

## REST API

The optional REST API exposes the same language intelligence over HTTP, implementing the [Rosetta Backend API Contract](https://github.com/robotics-4-all/rosetta#-backend-api-contract). Interactive docs are available at `/docs` when the server is running.

### Public Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe |
| `GET` | `/info` | DSL metadata — name, version, file extensions |
| `GET` | `/capabilities` | Supported operations |
| `GET` | `/keywords` | Grammar keyword list |

### Authenticated Endpoints

> Requires `X-API-Key` header when `--api-key` is set.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/validate` | Validate model source, return diagnostics |
| `POST` | `/validate/file` | Validate via file upload |
| `POST` | `/generate` | Run code generation for a target |
| `POST` | `/generate/file` | Generate via file upload |
| `POST` | `/complete` | Completion suggestions at a position |
| `POST` | `/hover` | Hover information at a position |

### Usage Examples

```bash
# Validate a model
curl -X POST http://localhost:8080/validate \
  -H "Content-Type: application/json" \
  -d '{"source": "entity Sensor { temperature: float }"}'

# Upload and validate a file
curl -X POST http://localhost:8080/validate/file \
  -F "file=@model.auto"

# Run code generation
curl -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{"source": "...", "target": "python"}'

# Get completions
curl -X POST http://localhost:8080/complete \
  -H "Content-Type: application/json" \
  -d '{"source": "entity ", "position": {"line": 0, "character": 7}}'
```

---

## Editor Integration

tx-lsp speaks standard LSP over **stdio** (default), **TCP**, or **WebSocket**. It works with any LSP-compatible editor out of the box.

| Editor | Integration |
|--------|-------------|
| **VS Code** | `settings.json` custom server config or dedicated extension |
| **Neovim** | [`nvim-lspconfig`](https://github.com/neovim/nvim-lspconfig) custom server definition |
| **Emacs** | [`eglot`](https://github.com/joaotavora/eglot) or [`lsp-mode`](https://github.com/emacs-lsp/lsp-mode) |
| **Sublime Text** | [LSP package](https://github.com/sublimelsp/LSP) |

> **No per-language configuration needed.** The server auto-discovers every textX language installed in the Python environment.

---

## How It Works

```
┌──────────────────────────────────────────────────┐
│                    tx-lsp                        │
│                                                  │
│  ┌────────────────┐      ┌────────────────────┐  │
│  │   Language     │      │   Model            │  │
│  │   Registry     │─────▶│   Manager          │  │
│  │                │      │   (parse & cache)   │  │
│  └───────┬────────┘      └─────────┬──────────┘  │
│          │                         │              │
│    Auto-discover             Parse/cache          │
│    via entry_points          per document          │
│                                    │              │
│  ┌─────────────────────────────────┴────────────┐ │
│  │              LSP Features                    │ │
│  │                                              │ │
│  │  diagnostics · completion · hover            │ │
│  │  definition  · references · symbols          │ │
│  └──────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

1. **LanguageRegistry** discovers all textX languages installed as Python entry points
2. **ModelManager** parses documents with the matching metamodel and caches results
3. **Features** are stateless functions that query the cached model state

---

## Development

```bash
# Clone and install with dev dependencies
git clone https://github.com/robotics-4-all/tx-lsp.git
cd tx-lsp
pip install -e ".[api,dev]"

# Run tests
pytest

# Lint and format
ruff check tx_lsp/
ruff format tx_lsp/

# Build distribution
python -m build
```

---

## Contributing

Contributions are welcome. Please open an issue first to discuss what you'd like to change.

---

## License

[MIT](LICENSE) © 2024 [klpanagi](https://github.com/klpanagi)
