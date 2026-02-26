# 🔤 tx-lsp

**Generic Language Server Protocol implementation for [textX](https://textx.github.io/textX/)-based DSLs.**

![Python](https://img.shields.io/badge/python-%3E%3D3.9-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Version](https://img.shields.io/badge/version-0.1.0-orange)

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [REST API Reference](#-rest-api-reference)
- [Editor Integration](#-editor-integration)
- [How It Works](#-how-it-works)
- [Development](#-development)
- [License](#-license)

---

## 🔎 Overview

**tx-lsp** is a generic LSP server that works with *any* textX-based DSL out of the box. It auto-discovers installed textX languages via Python entry points and provides full editor support — diagnostics, completions, hover, go-to-definition, and more. Built on [pygls](https://github.com/openlawlibrary/pygls) and [lsprotocol](https://github.com/microsoft/lsprotocol).

Optionally, the same language infrastructure can be exposed as a **REST API** that complies with the [Rosetta](https://github.com/robotics-4-all/rosetta) Backend API Contract — making any textX DSL instantly available as a backend service for the Rosetta DSL gateway.

---

## ✨ Features

### LSP Capabilities

- 🔴 **Diagnostics** — real-time parse and semantic error reporting
- 💡 **Completion** — grammar keywords and cross-reference suggestions
- 💬 **Hover** — rule type, attributes, and metadata display
- 🔗 **Go-to-Definition** — jump to where a symbol is defined (cross-file support)
- 🔍 **Find References** — locate all usages of a symbol
- 🗂️ **Document Symbols** — structured outline of the model

### REST API (optional)

- 📐 **Rosetta-compatible** — implements the [Backend API Contract](https://github.com/robotics-4-all/rosetta#-backend-api-contract) out of the box
- 📋 Validate models and retrieve diagnostics over HTTP
- 📤 File upload support for validation and code generation
- ⚡ Run textX code generators and collect artifacts
- 🗝️ Grammar keyword listing endpoint
- 🔑 Optional API key authentication

---

## 📦 Installation

> Requires **Python ≥ 3.9**

```bash
# Core LSP server
pip install tx-lsp

# With REST API support
pip install "tx-lsp[api]"
```

---

## 🚀 Quick Start

### LSP Server

```bash
# stdio (default — for editor clients)
tx-lsp

# TCP (useful for debugging)
tx-lsp --tcp --port 2087

# WebSocket
tx-lsp --ws --port 2087

# Custom log level
tx-lsp --log-level DEBUG
```

### Custom File Extensions

Map file extensions to textX languages when the DSL uses a different extension than what's registered:

```bash
tx-lsp --extra-pattern '*.auto=smauto'
```

Multiple patterns can be provided:

```bash
tx-lsp --extra-pattern '*.auto=smauto' --extra-pattern '*.rob=robodsl'
```

### REST API Server

```bash
# Start the API
tx-lsp --api --api-port 8080

# With API key authentication
tx-lsp --api --api-port 8080 --api-key YOUR_SECRET_KEY
```

When an API key is configured, include it in the `X-API-Key` header. Public endpoints (`/health`, `/info`, `/capabilities`, `/keywords`) do not require authentication.

```bash
curl -H "X-API-Key: YOUR_SECRET_KEY" http://localhost:8080/validate \
  -H "Content-Type: application/json" \
  -d '{"source": "..."}'
```

---

## 📡 REST API Reference

The API implements the [Rosetta Backend API Contract](https://github.com/robotics-4-all/rosetta#-backend-api-contract). Endpoints are at root level (no prefix). Interactive docs available at `/docs` when the server is running.

### Public Endpoints (no auth)

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Liveness check |
| `GET`  | `/info` | DSL metadata (name, version, file extensions) |
| `GET`  | `/capabilities` | Supported operations |
| `GET`  | `/keywords` | Grammar keyword list for the DSL |

### Operation Endpoints (auth required if API key configured)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/validate` | Validate model source, return diagnostics |
| `POST` | `/generate` | Run code generation (target in body) |
| `POST` | `/complete` | Completion suggestions at a position |
| `POST` | `/hover` | Hover information at a position |
| `POST` | `/validate/file` | Validate via file upload |
| `POST` | `/generate/file` | Generate via file upload |

### Examples

**Validate a model:**

```bash
curl -X POST http://localhost:8080/validate \
  -H "Content-Type: application/json" \
  -d '{"source": "item sensor { 42 }"}'
```

**Validate via file upload:**

```bash
curl -X POST http://localhost:8080/validate/file \
  -F "file=@model.auto"
```

**Run code generation:**

```bash
curl -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{"source": "...", "target": "python"}'
```

**Get completions at a position:**

```bash
curl -X POST http://localhost:8080/complete \
  -H "Content-Type: application/json" \
  -d '{"source": "item ", "position": {"line": 0, "character": 5}}'
```

**List grammar keywords:**

```bash
curl http://localhost:8080/keywords
```

**Check capabilities:**

```bash
curl http://localhost:8080/capabilities
```

---

## 🖥️ Editor Integration

tx-lsp works with any LSP-compatible editor. The default transport is **stdio**, which is what most editors expect.

| Editor | Setup |
|--------|-------|
| **VS Code** | Configure via `settings.json` or a dedicated extension |
| **Neovim** | Use `nvim-lspconfig` with a custom server config |
| **Emacs** | Configure via `lsp-mode` or `eglot` |
| **Sublime Text** | Use the LSP package |

The server auto-discovers all installed textX languages — no per-language configuration needed.

---

## ⚙️ How It Works

```
┌─────────────────────────────────────────┐
│              tx-lsp                     │
│                                         │
│  ┌──────────────┐   ┌──────────────┐   │
│  │ Language     │   │ Model        │   │
│  │ Registry     │──▶│ Manager      │   │
│  │              │   │ (parse/cache)│   │
│  └──────┬───────┘   └──────┬───────┘   │
│         │                  │            │
│    discover()         parse/cache       │
│    via entry_points   per document      │
│                            │            │
│  ┌─────────────────────────┴──────────┐ │
│  │           Features                 │ │
│  │  diagnostics │ completion │ hover  │ │
│  │  definition  │ references │symbols │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

1. **LanguageRegistry** discovers all textX languages installed via Python entry points
2. **ModelManager** parses documents using the appropriate metamodel and caches results
3. **Features** are stateless functions that query the cached model state

---

## 🛠️ Development

```bash
# Editable install
pip install -e .
pip install -e ".[api]"    # with REST API deps

# Run tests
pytest

# Lint & format
ruff check tx_lsp/
ruff format tx_lsp/
```

---

## 📄 License

[MIT](LICENSE)
