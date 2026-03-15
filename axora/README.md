# Axora — Modular AI Agent CLI

```
     █████╗ ██╗  ██╗ ██████╗ ██████╗  █████╗
    ██╔══██╗╚██╗██╔╝██╔═══██╗██╔══██╗██╔══██╗
    ███████║ ╚███╔╝ ██║   ██║██████╔╝███████║
    ██╔══██║ ██╔██╗ ██║   ██║██╔══██╗██╔══██║
    ██║  ██║██╔╝ ██╗╚██████╔╝██║  ██║██║  ██║
    ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
```

**Axora** is a fully modular, production-grade AI agent CLI that runs a local FastAPI server, integrates with any AI provider (OpenAI, Anthropic, Groq, Ollama, and more), connects to remote server endpoints, manages encrypted API keys, and provides a rich interactive terminal interface.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🚀 **Auto-install** | Single `bash install.sh` sets up everything |
| 🤖 **Multi-model** | OpenAI, Anthropic, Groq, Ollama, custom OpenAI-compatible APIs |
| 🔐 **Encrypted secrets** | API keys stored with Fernet encryption, never plain-text |
| 🌐 **Local server** | FastAPI backend on `localhost:8765` with REST API |
| 🔗 **Remote endpoints** | Connect and proxy to remote backend servers |
| 💬 **Interactive chat** | Streaming terminal chat with slash commands |
| 📋 **Config management** | YAML config with dot-notation set/get |
| 🪵 **Activity logging** | Rotating file logs + structured output |
| 🔄 **Daemon mode** | Run agent as background process with PID management |
| 🧪 **Test suite** | pytest unit + async API tests |

---

## 📦 Installation

### Linux / macOS (recommended)

```bash
git clone <repo-url> axora
cd axora
bash install.sh
source ~/.bashrc   # or source ~/.zshrc
```

### Windows

```bat
git clone <repo-url> axora
cd axora
install.bat
```

### Developer install

```bash
bash install.sh --dev
# or
make install-dev
```

---

## 🚀 Quick Start

```bash
# 1. Interactive setup wizard
axora init

# 2. Add your OpenAI key (if skipped in wizard)
axora config add-key

# 3. Start the local server
axora agent start

# 4. Chat!
axora chat
```

---

## 📁 Folder Structure

```
axora/
├── axora/                    # Python package
│   ├── __init__.py
│   ├── cli/                  # CLI entry points
│   │   ├── main.py           # Root click group
│   │   └── commands/
│   │       ├── agent.py      # start / stop / restart / logs
│   │       ├── chat.py       # Interactive chat session
│   │       ├── config.py     # set / get / add-key / add-endpoint
│   │       ├── models.py     # add / list / remove / test models
│   │       ├── server.py     # ping / call / list-endpoints
│   │       └── setup.py      # First-run wizard
│   ├── server/
│   │   ├── app.py            # FastAPI application
│   │   └── runner.py         # Uvicorn runner (daemon mode)
│   ├── config/
│   │   └── manager.py        # YAML config + Fernet encryption
│   └── utils/
│       ├── ai_client.py      # Unified AI model caller (stream + batch)
│       ├── banner.py         # ASCII art banner
│       ├── crypto.py         # Encryption helpers
│       ├── logger.py         # Rotating file logger
│       └── status.py         # Full system status display
├── tests/
│   └── test_axora.py         # pytest unit + async API tests
├── scripts/                  # Optional helper scripts
├── logs/                     # Log output directory
├── install.sh                # Linux/macOS auto-installer
├── install.bat               # Windows auto-installer
├── uninstall.sh              # Clean uninstall
├── pyproject.toml            # Package metadata & deps
├── requirements.txt          # Direct pip requirements
├── Makefile                  # Dev workflow shortcuts
└── .env.example              # Environment variable reference
```

---

## 🛠 Command Reference

### `axora init`
Interactive first-run setup wizard.

### `axora status`
Full system status: server health, models, endpoints.

### Agent Commands

```bash
axora agent start              # Start server (foreground)
axora agent start --daemon     # Start as background daemon
axora agent start --port 9000  # Override port
axora agent start --reload     # Enable auto-reload (dev)
axora agent stop               # Stop daemon
axora agent restart            # Stop + start
axora agent logs               # Tail log file
```

### Config Commands

```bash
axora config set server.port 8765
axora config set remote.url https://api.myserver.com
axora config set api.openai_key sk-xxx --secret
axora config get server.port
axora config show                    # All config (secrets masked)
axora config show --show-secrets     # Reveal secrets
axora config unset server.debug
axora config add-key                 # Interactive API key wizard
axora config add-endpoint            # Add remote server endpoint
axora config reset                   # Reset to defaults
```

### Model Commands

```bash
axora models add                     # Interactive model add
axora models list                    # List configured models
axora models remove gpt4             # Remove a model
axora models set-default gpt4        # Set default model
axora models test gpt4               # Test model with a prompt
axora models test gpt4 --prompt "Explain quantum computing"
```

### Server Commands

```bash
axora server local-status            # Check local server
axora server ping                    # Ping local server
axora server ping --url https://...  # Ping any URL
axora server list-endpoints          # List remote endpoints
axora server call production /v1/status   # Make API call to endpoint
axora server call production /v1/chat --method POST --data '{"msg":"hi"}'
```

### Chat Commands

```bash
axora chat                           # Start interactive session
axora chat --model gpt4              # Use specific model
axora chat --system "You are a pirate"
axora chat --no-stream               # Disable streaming
```

#### Chat Slash Commands (inside chat session)

| Command | Action |
|---|---|
| `/exit` or `/quit` | End session |
| `/clear` | Clear conversation history |
| `/history` | Show message history |
| `/save` | Save session to JSON file |
| `/model` | Show current model |
| `/model <alias>` | Switch model mid-session |
| `/help` | Show help |

---

## 🔌 REST API (Local Server)

Once running (`axora agent start`), the API is available at `http://127.0.0.1:8765`.

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check + uptime |
| `/v1/chat` | POST | Chat completion (streaming supported) |
| `/v1/models` | GET | List configured models |
| `/v1/config` | GET | Get configuration |
| `/v1/config` | POST | Set configuration value |
| `/v1/logs` | GET | Get recent log lines |
| `/v1/proxy/{name}` | POST | Proxy request to remote endpoint |

### Chat API Example

```bash
curl -X POST http://localhost:8765/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "model": "gpt4",
    "stream": false
  }'
```

---

## 🔐 Security

- API keys are encrypted using **Fernet symmetric encryption** before storage
- The encryption key lives in `~/.axora/.key` (mode 0600)
- The config file is stored at `~/.axora/config.yaml` (mode 0600)
- The secrets file at `~/.axora/secrets.json` (mode 0600)
- Set `server.auth_token` to require Bearer token auth on the local API:
  ```bash
  axora config set server.auth_token mysecrettoken --secret
  ```

---

## 🌐 Adding AI Providers

Axora supports any **OpenAI-compatible API**. Add a custom provider:

```bash
axora models add
# Choose "custom"
# Enter your model ID, base URL, and API key
```

**Example — Ollama (local):**
```bash
axora models add --provider ollama --model-id llama3.2 --alias llama
```

**Example — Groq:**
```bash
axora config set api.groq_key gsk_xxx --secret
axora models add --provider groq --model-id llama-3.3-70b-versatile --alias groq70b
```

---

## 🔧 Development

```bash
# Run tests
make test

# Lint
make lint

# Format
make format

# Start with auto-reload
make start
```

---

## 📝 Configuration Reference

All settings live in `~/.axora/config.yaml`:

```yaml
server:
  host: 127.0.0.1
  port: 8765

models:
  default: gpt4mini
  gpt4mini:
    provider: openai
    model_id: gpt-4o-mini
    key_config: api.openai_key

chat:
  system_prompt: "You are Axora, a helpful AI assistant."
  max_history: 50

endpoints:
  production:
    url: https://api.myserver.com
    timeout: 30

paths:
  log_file: ~/.axora/logs/axora.log
  pid_file: /tmp/axora.pid

logging:
  level: INFO
  max_bytes: 5242880
  backup_count: 3
```

---

## 🗑 Uninstall

```bash
bash uninstall.sh
```

---

## License

MIT
