const express = require('express');
const cors = require('cors');
const multer = require('multer');
const path = require('path');
const fs = require('fs');

const app = express();
// CRITICAL FIX: Use port 4000 to match client proxy
const PORT = process.env.PORT || 4000;

// Environment detection
const isProduction = process.env.NODE_ENV === 'production';
const isVercel = process.env.VERCEL === '1';

// Middleware
app.use(cors({
    origin: process.env.FRONTEND_URL || 'http://localhost:3000',
    credentials: true
}));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Ensure uploads directory exists
const uploadsDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadsDir)) {
    fs.mkdirSync(uploadsDir, { recursive: true });
}

// Configure multer for file uploads - CRITICAL FIX
const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, uploadsDir);
    },
    filename: (req, file, cb) => {
        // Sanitize filename
        const sanitized = file.originalname.replace(/[^a-zA-Z0-9.-]/g, '_');
        cb(null, `${Date.now()}-${sanitized}`);
    }
});

const upload = multer({ 
    storage: storage,
    limits: {
        fileSize: 10 * 1024 * 1024 // 10MB limit
    },
    fileFilter: (req, file, cb) => {
        const allowedTypes = ['.xlsx', '.pdf'];
        const ext = path.extname(file.originalname).toLowerCase();
        if (allowedTypes.includes(ext)) {
            cb(null, true);
        } else {
            cb(new Error('Invalid file type. Only .xlsx and .pdf files are allowed.'));
        }
    }
});

// Apply multer middleware to upload route - CRITICAL FIX
app.use('/api/upload', upload.single('file'));

// Import route handlers
const uploadHandler = require('./api/upload');
const generateReportHandler = require('./api/generate-report');

// Mount routes 
app.post('/api/upload', uploadHandler);
app.post('/api/generate-report', generateReportHandler);

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({ 
        status: 'ok', 
        timestamp: new Date().toISOString(),
        environment: {
            node_env: process.env.NODE_ENV,
            is_vercel: isVercel,
            port: PORT
        }
    });
});

// Development info endpoint
app.get('/api/info', (req, res) => {
    res.json({
        server_port: PORT,
        environment: process.env.NODE_ENV || 'development',
        vercel: isVercel,
        python_available: isVercel ? false : true,
        message: isVercel ? 'Running on Vercel - Python processing disabled' : 'Local development - Full pipeline available'
    });
});

// Error handling middleware
app.use((err, req, res, next) => {
    console.error('Server error:', err);
    
    // Handle multer errors specifically
    if (err instanceof multer.MulterError) {
        if (err.code === 'LIMIT_FILE_SIZE') {
            return res.status(400).json({ 
                error: 'File too large',
                message: 'File size must be less than 10MB'
            });
        }
    }
    
    res.status(500).json({ 
        error: 'Internal server error',
        message: isProduction ? 'Something went wrong' : err.message 
    });
});

// 404 handler - MUST be last
app.use('*', (req, res) => {
    res.status(404).json({ 
        error: 'Not found',
        path: req.originalUrl,
        available_endpoints: ['/health', '/api/info', '/api/upload', '/api/generate-report']
    });
});

app.listen(PORT, () => {
    console.log(`✅ Server API running on port ${PORT}`);
    console.log(`✅ Health check: http://localhost:${PORT}/health`);
    console.log(`✅ Environment: ${process.env.NODE_ENV || 'development'}`);
    console.log(`✅ Vercel mode: ${isVercel ? 'YES' : 'NO'}`);
    console.log(`✅ Multer configured for file uploads`);
});

module.exports = app;