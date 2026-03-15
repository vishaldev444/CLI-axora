#!/usr/bin/env bash

set -e

echo "🚀 Installing AXORA Autonomous Agent..."

REPO="https://github.com/vishaldev444/CLI-axora.git"
DIR="axora"

# clone project

git clone $REPO $DIR

cd $DIR/agent_ready

echo "✔ Project downloaded"

# python check

if ! command -v python3 &> /dev/null
then
echo "Python3 not found. Install Python 3.10+"
exit
fi

# create environment

echo "Creating virtual environment..."
python3 -m venv engine

source engine/bin/activate

pip install --upgrade pip

# install dependencies

pip install -r requirements.txt

pip install .

echo "✔ Axora installed"

# install ollama if missing

if ! command -v ollama &> /dev/null
then
echo "Installing Ollama..."

```
if [[ "$(uname)" == "Darwin" ]]; then
    brew install ollama
else
    curl -fsSL https://ollama.com/install.sh | sh
fi
```

fi

echo "✔ Ollama installed"

# start ollama

ollama serve > /dev/null 2>&1 &

sleep 5

# download model

echo "Downloading llama3 model..."
ollama pull llama3

echo "✔ Model ready"

# initialize axora

axora init <<EOF
127.0.0.1
8765
ollama
llama3
llama3
http://localhost:11434/v1
n
EOF

# start agent

axora agent start --daemon

echo ""
echo "🎉 AXORA INSTALLATION COMPLETE"
echo ""
echo "Run chat:"
echo "cd axora/agent_ready"
echo "source engine/bin/activate"
echo "axora chat"
