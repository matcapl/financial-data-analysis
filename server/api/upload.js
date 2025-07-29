const { spawn } = require('child_process');
const { put } = require('@vercel/blob');
const path = require('path');
const fs = require('fs');
const sanitize = require('sanitize-filename');

module.exports = async (req, res) => {
    /**
     * Fixed Upload Handler - FINAL VERSION
     * 
     * Key fixes implemented:
     * 1. Fix multer file handling: use req.file instead of req.files
     * 2. Chain full processing pipeline with proper error handling
     * 3. Add security measures and file validation
     * 4. Ensure complete pipeline runs: ingestion → calculation → questions
     */
    
    if (!req.file) {
        return res.status(400).json({ error: 'No file uploaded. Make sure to use form field name "file".' });
    }
    
    const file = req.file;
    const ext = path.extname(file.originalname).toLowerCase();
    
    // Validate file type
    if (!['.xlsx', '.csv', '.pdf'].includes(ext)) {
        return res.status(400).json({ error: 'Invalid file type. Only .xlsx, .csv, and .pdf files are supported.' });
    }
    
    // Get company_id from request body or default to 1
    const company_id = req.body.company_id ? parseInt(req.body.company_id) : 1;
    
    if (isNaN(company_id) || company_id <= 0) {
        return res.status(400).json({ error: 'Invalid company_id. Must be a positive integer.' });
    }
    
    try {
        console.log(`🚀 Starting complete pipeline for file: ${file.originalname}`);
        
        // Step 1: File Ingestion
        console.log('📁 Step 1: File ingestion...');
        const script = (ext === '.xlsx' || ext === '.csv') ? 'ingest_xlsx.py' : 'ingest_pdf.py';
        
        await runPythonScript(script, [file.path, company_id.toString()]);
        console.log('✅ Step 1: File ingestion completed');
        
        // Step 2: Calculate Metrics
        console.log('📊 Step 2: Metric calculations...');
        await runPythonScript('calc_metrics.py', [company_id.toString()]);
        console.log('✅ Step 2: Metric calculations completed');
        
        // Step 3: Generate Questions
        console.log('❓ Step 3: Question generation...');
        await runPythonScript('questions_engine.py', []);
        console.log('✅ Step 3: Question generation completed');
        
        // Step 4: Upload to Vercel Blob for storage
        const safeName = sanitize(file.originalname);
        const blob = await put(safeName, fs.readFileSync(file.path), { access: 'public' });
        
        // Clean up local file
        if (fs.existsSync(file.path)) {
            fs.unlinkSync(file.path);
        }
        
        // Return success response with processing summary
        res.json({ 
            success: true,
            message: 'File processed successfully through complete pipeline',
            filename: safeName,
            company_id: company_id,
            blobUrl: blob.url,
            processing_steps: [
                '✅ File uploaded and validated',
                '✅ Data ingested from file', 
                '✅ Metrics calculated',
                '✅ Questions generated',
                '✅ File stored in blob storage'
            ],
            next_steps: 'You can now generate a report using the /api/generate-report endpoint'
        });
        
    } catch (err) {
        console.error('❌ Pipeline processing failed:', err);
        
        // Clean up file if it exists
        if (fs.existsSync(file.path)) {
            fs.unlinkSync(file.path);
        }
        
        res.status(500).json({ 
            error: 'Processing pipeline failed', 
            details: err.message,
            step_failed: err.step || 'unknown'
        });
    }
};

/**
 * Helper function to run Python scripts securely using spawn
 */
function runPythonScript(scriptName, args) {
    return new Promise((resolve, reject) => {
        const scriptPath = path.resolve(__dirname, '..', '..', 'scripts', scriptName);
        
        // Verify script exists
        if (!fs.existsSync(scriptPath)) {
            const error = new Error(`Script not found: ${scriptName}`);
            error.step = `Script lookup (${scriptName})`;
            reject(error);
            return;
        }
        
        // Spawn Python process with arguments
        const python = spawn('python', [scriptPath, ...args], {
            cwd: path.resolve(__dirname, '..', '..'),
            stdio: ['pipe', 'pipe', 'pipe']
        });
        
        let stdout = '';
        let stderr = '';
        
        python.stdout.on('data', (data) => {
            stdout += data.toString();
        });
        
        python.stderr.on('data', (data) => {
            stderr += data.toString();
        });
        
        python.on('close', (code) => {
            if (code === 0) {
                console.log(`${scriptName} output:`, stdout);
                resolve({ code, stdout, stderr });
            } else {
                const error = new Error(`${scriptName} failed with code ${code}: ${stderr}`);
                error.step = scriptName;
                error.stdout = stdout;
                error.stderr = stderr;
                reject(error);
            }
        });
        
        python.on('error', (err) => {
            const error = new Error(`Failed to start ${scriptName}: ${err.message}`);
            error.step = `Process start (${scriptName})`;
            reject(error);
        });
    });
}