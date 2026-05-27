// server.js — AccountaStudy Backend Entry Point
require('dotenv').config();

const express = require('express');
const cors = require('cors');
const morgan = require('morgan');
const path = require('path');
const connectDB = require('./config/db');
const errorHandler = require('./middleware/errorHandler');

// ── Connect to MongoDB ──
connectDB();

const app = express();

// ══════════════════════════════════════════
// MIDDLEWARE
// ══════════════════════════════════════════

// CORS — allow your frontend origin
app.use(cors({
  origin: [
    'http://localhost:3000',   // React dev server
    'http://localhost:5173',   // Vite dev server
    'http://127.0.0.1:5500',   // VS Code Live Server (for the HTML file)
    'http://localhost:5500',
    '*',                       // During development — restrict in production
  ],
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true,
}));

// Body parsers
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// HTTP request logger (dev only)
if (process.env.NODE_ENV === 'development') {
  app.use(morgan('dev'));
}

// ── Serve uploaded screenshots statically ──
// Access via: http://localhost:5000/uploads/timer/filename.jpg
app.use('/uploads', express.static(path.join(__dirname, 'uploads')));

// ══════════════════════════════════════════
// API ROUTES
// ══════════════════════════════════════════
app.use('/api/auth',         require('./routes/auth'));
const submissionRoutes = require('./routes/submission');
app.use('/api/submission',   submissionRoutes);
app.use('/api/submissions',  submissionRoutes); // alias for clients using plural paths
app.use('/api/session',      require('./routes/session'));
app.use('/api/leaderboard',  require('./routes/leaderboard'));
app.use('/api/admin',        require('./routes/admin'));

// ── Health check ──
app.get('/api/health', (req, res) => {
  res.json({
    success: true,
    message: 'AccountaStudy API is running ✅',
    environment: process.env.NODE_ENV,
    timestamp: new Date().toISOString(),
  });
});

// ── 404 handler ──
app.use((req, res) => {
  res.status(404).json({
    success: false,
    message: `Route not found: ${req.method} ${req.originalUrl}`,
  });
});

// ── Global error handler (must be last) ──
app.use(errorHandler);

// ══════════════════════════════════════════
// START SERVER
// ══════════════════════════════════════════
const PORT = process.env.PORT || 5000;
const server = app.listen(PORT, () => {
  console.log('');
  console.log('┌─────────────────────────────────────────────┐');
  console.log(`│  🎓 AccountaStudy Backend                   │`);
  console.log(`│  🚀 Server running on port ${PORT}             │`);
  console.log(`│  🌐 http://localhost:${PORT}/api/health        │`);
  console.log(`│  📁 Env: ${(process.env.NODE_ENV || 'development').padEnd(35)}│`);
  console.log('└─────────────────────────────────────────────┘');
  console.log('');
});

server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.error(`\n❌ Port ${PORT} is already in use. Stop the other server or set PORT in .env`);
    console.error(`   Example: lsof -i :${PORT}   then   kill <PID>\n`);
  }
  process.exit(1);
});

module.exports = app;
