# Contributing to Shadow Agent

Thank you for your interest in contributing to **Shadow Agent**! 

## 🛡️ Code of Conduct
We are committed to providing a welcoming, inclusive, and harassment-free environment for all contributors.

## 🛠️ Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/francaroscillidev-gif/shadow-agent.git
   cd shadow-agent
   ```

2. **Install dependencies with `uv`:**
   ```bash
   uv sync
   ```

3. **Run unit tests:**
   ```bash
   uv run pytest tests/
   ```

4. **Start the local proxy in development mode:**
   ```bash
   uv run shadow-agent start --port 8080
   ```

## 📬 Questions & Security Inquiries
If you discover a security vulnerability, please do NOT open a public issue. Contact directly:
- **Lead Maintainer:** Franca Roscilli ([francaroscillidev@gmail.com](mailto:francaroscillidev@gmail.com))
