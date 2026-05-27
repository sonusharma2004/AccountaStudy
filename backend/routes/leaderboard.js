// routes/leaderboard.js
const express = require('express');
const router = express.Router();
const { getLeaderboard } = require('../controllers/leaderboardController');
const { protect } = require('../middleware/auth');

router.get('/', protect, getLeaderboard); // GET /api/leaderboard?mode=daily|weekly|overall

module.exports = router;
