const express = require('express');
const cors = require('cors');
const path = require('path');
const multer = require('multer');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 4000; // Changed from 5000 to 4000 to avoid conflicts

// Multer setup for file uploads (CRITICAL FIX)
const uploadDir = path.join(__dirname, '..', 'data');
if (!fs.existsSync(uploadDir)) {
    fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, uploadDir);
    },
    filename: (req, file, cb) => {
        const sanitizedName = file.originalname.replace(/[^a-zA-Z0-9.-]/g, '_');
        cb(null, `${Date.now()}-${sanitizedName}`);
    }
});

const upload = multer({ storage: storage });

// Middleware
app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true }));

// Import route handlers
const uploadHandler = require('./api/upload');
const generateReportHandler = require('./api/generate-report');

// Mount routes with multer middleware for upload
app.post('/api/upload', upload.single('file'), uploadHandler);
app.post('/api/generate-report', generateReportHandler);

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({ 
        status: 'ok', 
        timestamp: new Date().toISOString(),
        port: PORT,
        message: 'Server is running properly'
    });
});

// Error handling middleware
app.use((err, req, res, next) => {
    console.error('Server error:', err);
    res.status(500).json({ 
        error: 'Internal server error',
        message: err.message 
    });
});

// 404 handler (MUST be last)
app.use('*', (req, res) => {
    res.status(404).json({ 
        error: 'Not found',
        path: req.originalUrl 
    });
});

app.listen(PORT, () => {
    console.log(`✅ Server API running on port ${PORT}`);
    console.log(`✅ Health check: http://localhost:${PORT}/health`);
    console.log(`✅ Upload endpoint: http://localhost:${PORT}/api/upload`);
});

module.exports = app;