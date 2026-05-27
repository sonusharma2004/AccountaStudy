// routes/session.js
const express = require('express');
const router = express.Router();
const { startSession, stopSession, getUserSessions } = require('../controllers/sessionController');
const { protect } = require('../middleware/auth');

router.post('/start', protect, startSession);   // POST /api/session/start
router.post('/stop', protect, stopSession);     // POST /api/session/stop
router.get('/user', protect, getUserSessions);  // GET  /api/session/user

module.exports = router;
