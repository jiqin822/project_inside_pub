# Mobile App Quick Start Guide

## Prerequisites

- **Node.js** (v18 or higher recommended)
- **Backend server** running (see backend/README.md)

## Setup Steps

### 1. Install Dependencies

```bash
cd mobile
npm install
```

### 2. Configure Environment Variables

Create a `.env.local` file in the `mobile/` directory:

```bash
# Backend API URL (defaults to http://localhost:8000 if not set)
VITE_API_BASE_URL=http://localhost:8000

# Gemini API Key (for AI features like therapist mode and activity generation)
GEMINI_API_KEY=your_gemini_api_key_here
```

**Note:** The backend API URL should match where your backend server is running. If testing on a mobile device, use your computer's local IP address instead of `localhost` (e.g., `http://192.168.1.100:8000`).

### 3. Start the Development Server

```bash
npm run dev
```

The app will start on **http://localhost:3000**

### 4. Access the App

- **Desktop:** Open http://localhost:3000 in your browser
- **Mobile Device (same network):** 
  1. Find your computer's local IP address:
     ```bash
     # macOS/Linux
     ifconfig | grep "inet " | grep -v 127.0.0.1
     
     # Or use the check_server.sh script
     cd .. && ./check_server.sh
     ```
  2. Update `VITE_API_BASE_URL` in `.env.local` to use your computer's IP
  3. Access http://YOUR_IP:3000 on your mobile device

## Testing Checklist

1. ✅ **Backend is running** (check http://localhost:8000/health)
2. ✅ **Dependencies installed** (`npm install` completed)
3. ✅ **Environment variables set** (`.env.local` exists)
4. ✅ **Dev server started** (`npm run dev` running)
5. ✅ **App accessible** (can open in browser)

## Troubleshooting

### "Cannot connect to server" error
- Make sure backend is running: `cd backend && make dev`
- Check `VITE_API_BASE_URL` matches your backend URL
- If testing on mobile, use your computer's IP address, not `localhost`

### "No internet" error on signup/login
- Verify backend is accessible at the URL in `VITE_API_BASE_URL`
- Check backend logs for errors
- Ensure backend is running on the correct port (default: 8000)

### Port 3000 already in use
- Change port in `vite.config.ts` or use: `npm run dev -- --port 3001`

## Available Scripts

- `npm run dev` - Start development server (port 3000)
- `npm run build` - Build for production
- `npm run preview` - Preview production build
