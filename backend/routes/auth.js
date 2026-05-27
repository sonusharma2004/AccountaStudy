// routes/auth.js
const express = require('express');
const router = express.Router();
const { register, login, getMe, updateProfile } = require('../controllers/authController');
const { protect } = require('../middleware/auth');

router.post('/register', register);        // POST /api/auth/register
router.post('/login', login);              // POST /api/auth/login
router.get('/me', protect, getMe);         // GET  /api/auth/me
router.put('/update-profile', protect, updateProfile); // PUT /api/auth/update-profile

module.exports = router;
