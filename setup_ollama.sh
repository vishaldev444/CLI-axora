#!/bin/bash

echo "Installing Ollama..."

if ! command -v ollama &> /dev/null
then
    brew install ollama
fi

brew services start ollama

echo "Downloading AI model..."

ollama pull llama3

echo "✅ Ollama Ready"