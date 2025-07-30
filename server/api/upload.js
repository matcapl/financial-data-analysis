const { spawn } = require('child_process');
const { put } = require('@vercel/blob');
const path = require('path');
const fs = require('fs');
const sanitize = require('sanitize-filename');

// CORS headers for cross-origin uploads
const express = require('express');
express()
  .use((req, res, next) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    if (req.method === 'OPTIONS') return res.sendStatus(200);
    next();
});

module.exports = async (req, res) => {
  /**
   * FIXED Upload Pipeline - Key Issues Resolved:
   * 
   * CRITICAL FIXES:
   * 1. Files are preserved instead of deleted (copy-based processing)
   * 2. Proper file type detection and handling
   * 3. Enhanced error handling with detailed feedback
   * 4. Secure file processing with sanitization
   * 5. Progress tracking through response
   */
  
  const isVercel = process.env.VERCEL === '1';
  const isProduction = process.env.NODE_ENV === 'production';
  
  // Use req.file (not req.files) for standard multer
  if (!req.file) {
    return res.status(400).json({ 
      error: 'No file uploaded',
      hint: 'Please ensure you are sending a file with the form field name "file"'
    });
  }
  
  const file = req.file;
  const ext = path.extname(file.originalname).toLowerCase();
  
  // Validate file type
  if (!['.xlsx', '.pdf', '.csv'].includes(ext)) {
    return res.status(400).json({ 
      error: 'Invalid file type. Only .xlsx, .pdf, and .csv files are supported.',
      received: ext,
      allowed: ['.xlsx', '.pdf', '.csv']
    });
  }
  
  // Get company_id from request body or default to 1
  const company_id = req.body.company_id ? parseInt(req.body.company_id) : 1;
  
  if (isNaN(company_id) || company_id <= 0) {
    return res.status(400).json({ 
      error: 'Invalid company_id. Must be a positive integer.',
      received: req.body.company_id
    });
  }
  
  console.log(`🚀 Starting upload pipeline for company ${company_id} (${isVercel ? 'Vercel' : 'Local'} environment)`);
  
  try {
    // Sanitize filename to prevent security issues
    const safeName = sanitize(file.originalname);
    const dataDir = path.resolve(__dirname, '..', '..', 'data');
    const permanentFilePath = path.join(dataDir, safeName);
    
    // Ensure data directory exists
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }
    
    // CRITICAL FIX: Copy file to permanent location, don't move it
    // This preserves the original uploaded file
    fs.copyFileSync(file.path, permanentFilePath);
    
    console.log('✓ File saved successfully');
    
    let processingSteps = ['✓ File uploaded and validated'];
    let blobUrl = null;
    
    if (isVercel) {
      // VERCEL ENVIRONMENT: Limited processing
      console.log('🔄 Running in Vercel mode - limited processing');
      
      console.log('Current working directory:', process.cwd());
      console.log('Directory contents:', fs.readdirSync('.'));
      console.log('Scripts directory exists:', fs.existsSync('./scripts'));

      // Upload to Vercel Blob immediately
      try {
        const fileBuffer = fs.readFileSync(permanentFilePath);
        const blob = await put(safeName, fileBuffer, { access: 'public' });
        blobUrl = blob.url;
        processingSteps.push('✓ File stored in blob storage');
        console.log('✓ File uploaded to Vercel Blob');
      } catch (blobError) {
        console.warn('Blob storage failed:', blobError.message);
        processingSteps.push('⚠ Blob storage failed');
      }
      
      // Add placeholder processing steps for Vercel
      processingSteps.push('⚠ Data ingestion - requires Python (limited in serverless)');
      processingSteps.push('⚠ Metric calculations - requires Python (limited in serverless)');
      processingSteps.push('⚠ Question generation - requires Python (limited in serverless)');
      
    } else {
      // LOCAL DEVELOPMENT: Full processing pipeline
      console.log('🔄 Running full local processing pipeline');
      
      try {
        // Step 1: File Ingestion - Use correct script based on file type
        console.log('Starting file ingestion...');
        let script;
        if (ext === '.xlsx' || ext === '.csv') {
          script = 'ingest_xlsx.py';
        } else if (ext === '.pdf') {
          script = 'ingest_pdf.py';
        }
        
        await runPythonScript(script, [permanentFilePath, company_id.toString()]);
        processingSteps.push('✓ Data ingested from file');
        console.log('✓ File ingestion completed');
        
        // Step 2: Calculate Metrics
        console.log('Starting metric calculations...');
        await runPythonScript('calc_metrics.py', [company_id.toString()]);
        processingSteps.push('✓ Metrics calculated');
        console.log('✓ Metric calculations completed');
        
        // Step 3: Generate Questions
        console.log('Starting question generation...');
        await runPythonScript('questions_engine.py', []);
        processingSteps.push('✓ Questions generated');
        console.log('✓ Question generation completed');
        
        // Step 4: Upload to Vercel Blob (if available)
        if (process.env.VERCEL_BLOB_TOKEN) {
          try {
            const fileBuffer = fs.readFileSync(permanentFilePath);
            const blob = await put(safeName, fileBuffer, { access: 'public' });
            blobUrl = blob.url;
            processingSteps.push('✓ File stored in blob storage');
            console.log('✓ File uploaded to blob storage');
          } catch (blobError) {
            console.warn('Blob storage failed:', blobError.message);
            processingSteps.push('⚠ Blob storage skipped (token missing or failed)');
          }
        } else {
          processingSteps.push('⚠ Blob storage skipped (no token configured)');
        }
        
      } catch (pipelineError) {
        console.error('Pipeline processing failed:', pipelineError);
        throw pipelineError;
      }
    }
    
    // CRITICAL FIX: Clean up only the multer temp file, not the permanent copy
    if (fs.existsSync(file.path)) {
      fs.unlinkSync(file.path);
    }
    
    // Return success response with processing summary
    const response = { 
      message: isVercel 
        ? 'File uploaded successfully (limited processing in serverless environment)'
        : 'File processed successfully! All pipeline steps completed.',
      filename: safeName,
      company_id: company_id,
      file_path: permanentFilePath,
      environment: {
        vercel: isVercel,
        production: isProduction,
        python_processing: !isVercel
      },
      blobUrl: blobUrl,
      processing_steps: processingSteps,
      next_steps: isVercel
        ? 'For full processing, please run locally or implement JavaScript-based processing'
        : 'File processed successfully! All pipeline steps completed.',
      timestamp: new Date().toISOString()
    };
    
    console.log('🎉 Upload pipeline completed successfully.');
    res.json(response);
    
  } catch (err) {
    console.error('Pipeline processing failed:', err);
    
    // Clean up only temp files if they exist, preserve permanent files
    if (fs.existsSync(file.path)) {
      fs.unlinkSync(file.path);
    }
    
    res.status(500).json({ 
      error: 'Processing pipeline failed', 
      details: isProduction ? 'Internal server error' : err.message,
      step_failed: err.step || 'unknown',
      environment: {
        vercel: isVercel,
        production: isProduction
      },
      troubleshooting: {
        python_available: !isVercel,
        common_issues: [
          'Python not installed or not in PATH',
          'Database connection issues',
          'Missing environment variables',
          'File permissions',
          'Unicode encoding issues with file content'
        ]
      }
    });
  }
};

/**
 * Helper function to run Python scripts securely using spawn
 * Only works in non-Vercel environments
 */
function runPythonScript(scriptName, args) {
  return new Promise((resolve, reject) => {
    const scriptPath = path.resolve(__dirname, '..', 'scripts', scriptName);
    
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
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: 60000 // 60 second timeout
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
        console.log(`${scriptName} completed successfully`);
        if (stdout.trim()) {
          console.log(`${scriptName} output:`, stdout.trim());
        }
        resolve({ code, stdout, stderr });
      } else {
        const error = new Error(`${scriptName} failed with code ${code}: ${stderr || 'No error details'}`);
        error.step = scriptName;
        error.stdout = stdout;
        error.stderr = stderr;
        error.code = code;
        reject(error);
      }
    });
    
    python.on('error', (err) => {
      const error = new Error(`Failed to start ${scriptName}: ${err.message}`);
      error.step = `Process start (${scriptName})`;
      error.originalError = err;
      reject(error);
    });
    
    // Handle timeout
    python.on('timeout', () => {
      python.kill('SIGKILL');
      const error = new Error(`${scriptName} timed out after 60 seconds`);
      error.step = `Timeout (${scriptName})`;
      reject(error);
    });
  });
}