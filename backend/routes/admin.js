// routes/admin.js
const express = require('express');
const router = express.Router();
const {
  getAllUsers,
  deleteUser,
  toggleUserStatus,
  getSystemStats,
  getAnalytics,
} = require('../controllers/adminController');
const { protect, adminOnly } = require('../middleware/auth');

// All admin routes require auth + admin role
router.use(protect, adminOnly);

router.get('/users', getAllUsers);                    // GET    /api/admin/users
router.delete('/user/:id', deleteUser);              // DELETE /api/admin/user/:id
router.put('/user/:id/toggle', toggleUserStatus);    // PUT    /api/admin/user/:id/toggle
router.get('/stats', getSystemStats);                // GET    /api/admin/stats
router.get('/analytics', getAnalytics);             // GET    /api/admin/analytics

module.exports = router;
