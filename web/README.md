# Recall Web UI

> ChatGPT-style interface for the Recall self-learning data agent

## Features

✨ **ChatGPT-inspired design**
- Dark theme with Inter font (optimized for readability)
- Smooth animations and transitions
- Collapsible sidebar with chat history
- Responsive layout

🎯 **Core capabilities**
- Real-time streaming effect (typing animation)
- SQL code block detection with syntax highlighting
- One-click copy for generated SQL
- Conversation history (persisted in localStorage)
- Download transcript as JSON
- Smart prompt suggestions

## Quick Start

```bash
cd web
npm install
npm run dev
```

The UI will be available at http://localhost:5173

## Configuration

Copy `.env.example` to `.env` and customize:

```bash
# Backend API endpoint
VITE_API_URL=http://localhost:8000

# Model display name
VITE_MODEL_PROVIDER=mistral
```

## Build for Production

```bash
npm run build
```

Built files will be in `dist/` — serve them with any static file server or integrate into the FastAPI app.

## Design

The UI replicates ChatGPT's aesthetic:
- **Sidebar**: Collapsible, chat history, user profile
- **Main area**: Centered conversation with smooth scrolling
- **Input**: Rounded, shadow, disabled state during streaming
- **Messages**: User (right) vs Assistant (left) with avatars
- **Code blocks**: Dark background, copy button, language badge
