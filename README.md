# CLI-Axora 🤖

A lightweight **AI CLI Agent** powered by Python and local models (Ollama).
CLI-Axora allows you to run an AI assistant directly from your terminal.

---

# 🚀 Features

* AI assistant directly in terminal
* Runs locally with **Ollama**
* Python based backend
* Simple installation
* Extensible agent architecture
* Logging support

---

# 📦 Requirements

Make sure the following tools are installed on your system.

### 1️⃣ Install Homebrew (Mac)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Check installation:

```bash
brew --version
```

---

### 2️⃣ Install Python

```bash
brew install python
```

Check version:

```bash
python3 --version
```

---

### 3️⃣ Install Ollama

```bash
brew install ollama
```

Start Ollama service:

```bash
ollama serve
```

---

### 4️⃣ Download AI Model

Example (Llama3):

```bash
ollama pull llama3
```

You can use other models like:

```
ollama pull mistral
ollama pull phi3
```

---

# 📥 Clone the Repository

```bash
git clone https://github.com/vishaldev444/CLI-axora.git
```

Go to project folder:

```bash
cd CLI-axora
```

---

# ⚙️ Project Setup

### 1️⃣ Run Auto Install Script

```bash
chmod +x install.sh
./install.sh
```

This script will automatically:

* create Python virtual environment
* install dependencies
* prepare logs folder

---

### 2️⃣ Activate Virtual Environment

```bash
source engine/bin/activate
```

---

### 3️⃣ Install Requirements (if needed)

```bash
pip install -r requirements.txt
```

---

# ▶️ Run the AI Agent

Start the agent using:

```bash
python main.py
```

You should see the CLI agent ready in your terminal.

Example:

```
Axora > hello
AI: Hello! How can I assist you today?
```

---

# 📂 Project Structure

```
CLI-axora
│
├── engine/              # Python virtual environment
├── logs/                # Log files
├── install.sh           # Auto setup script
├── setup_ollama.sh      # Ollama setup helper
├── main.py              # Entry point
├── requirements.txt     # Python dependencies
└── README.md
```

---

# 🧠 Example Code (main.py)

Example simple CLI agent:

```python
import requests

while True:
    prompt = input("Axora > ")

    if prompt.lower() in ["exit","quit"]:
        break

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        }
    )

    print("AI:", response.json()["response"])
```

---

# 🧾 Logs

Logs are stored in:

```
logs/axora.log
```

---

# 🛠 Future Improvements

* voice assistant support
* plugin system
* tool calling
* memory system
* autonomous agent mode

---

# 👨‍💻 Author

**Vishal Singh**

GitHub
https://github.com/vishaldev444

---

# ⭐ Support

If you like this project:

* star the repository ⭐
* contribute improvements
* report issues

---

# 📜 License

MIT License
