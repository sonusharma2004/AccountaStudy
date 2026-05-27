// routes/submission.js
const express = require('express');
const router = express.Router();
const {
  uploadSubmission,
  getAllSubmissions,
  verifySubmission,
  getMySubmissions,
  getTodayStatus,
} = require('../controllers/submissionController');
const { protect, adminOnly } = require('../middleware/auth');
const upload = require('../config/multer');

// Student routes
const uploadScreenshots = upload.fields([
  { name: 'timerScreenshot', maxCount: 1 },
  { name: 'questionScreenshot', maxCount: 1 },
]);

router.post('/upload', protect, uploadScreenshots, uploadSubmission); // POST /api/submission/upload
router.post('/', protect, uploadScreenshots, uploadSubmission); // POST /api/submission | /api/submissions (multipart)

router.get('/my', protect, getMySubmissions);           // GET /api/submission/my
router.get('/today-status', protect, getTodayStatus);   // GET /api/submission/today-status

// Admin routes
router.get('/all', protect, adminOnly, getAllSubmissions);         // GET  /api/submission/all
router.post('/verify', protect, adminOnly, verifySubmission);     // POST /api/submission/verify

module.exports = router;
