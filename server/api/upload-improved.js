const { put } = require('@vercel/blob');
const path = require('path');
const fs = require('fs');
const sanitize = require('sanitize-filename');
const PythonProcessor = require('./python-processor');

const ROOT_DIR = path.resolve(__dirname, '..', '..');

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
   * IMPROVED Upload Pipeline - Direct Python Integration
   * 
   * IMPROVEMENTS:
   * 1. Eliminates fragile subprocess calls
   * 2. Direct Python function imports through unified processor
   * 3. Better error handling and structured responses
   * 4. Faster processing with single Python process
   * 5. JSON-structured communication between Node.js and Python
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

  console.log(`🚀 Starting improved upload pipeline for company ${company_id}`);
  
  try {
    // Create safe filename and copy file to permanent location
    const timestamp = Date.now();
    const safeFilename = sanitize(file.originalname) || `upload_${timestamp}${ext}`;
    const dataDir = path.join(ROOT_DIR, 'data');
    
    // Ensure data directory exists
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }
    
    const permanentFilePath = path.join(dataDir, `${timestamp}_${safeFilename}`);
    
    // Copy uploaded file to permanent location
    fs.copyFileSync(file.path, permanentFilePath);
    console.log(`✓ File saved permanently: ${permanentFilePath}`);
    
    // Initialize Python processor
    const processor = new PythonProcessor();
    
    if (isVercel) {
      // Vercel environment - limited Python support
      console.log('⚠️ Running in Vercel environment - Python processing disabled');
      
      // For Vercel, just acknowledge the upload
      return res.json({
        message: 'File uploaded successfully (Vercel environment)',
        filename: safeFilename,
        company_id: company_id,
        processing_steps: [
          '✓ File uploaded and validated',
          '⚠ Python processing disabled in Vercel'
        ],
        environment: {
          vercel: true,
          python_processing: false
        }
      });
      
    } else {
      // Local/Railway environment - full Python processing
      console.log('🔄 Running full Python processing pipeline');
      
      try {
        // Run the complete pipeline using direct Python integration
        const pipelineResult = await processor.runCompletePipeline(permanentFilePath, company_id);
        
        if (pipelineResult.success) {
          // Success response
          return res.json({
            message: 'File processed successfully! All pipeline steps completed.',
            filename: safeFilename,
            company_id: company_id,
            processing_steps: pipelineResult.processing_steps,
            pipeline_results: {
              ingestion: pipelineResult.results.ingestion,
              metrics: pipelineResult.results.metrics,
              questions: pipelineResult.results.questions
            },
            errors: pipelineResult.errors.length > 0 ? pipelineResult.errors : undefined,
            environment: {
              vercel: false,
              python_processing: true
            }
          });
        } else {
          // Pipeline failed but we have detailed error information
          return res.status(422).json({
            error: 'Pipeline processing failed',
            message: pipelineResult.message,
            filename: safeFilename,
            company_id: company_id,
            processing_steps: pipelineResult.processing_steps,
            pipeline_results: pipelineResult.results,
            errors: pipelineResult.errors,
            troubleshooting: {
              python_available: true,
              common_issues: [
                "Database connection issues",
                "Missing YAML configuration files",
                "Data format incompatibility",
                "Missing environment variables"
              ]
            },
            environment: {
              vercel: false,
              python_processing: true
            }
          });
        }
        
      } catch (processingError) {
        console.error('Pipeline processing failed:', processingError);
        
        return res.status(500).json({
          error: 'Processing pipeline failed',
          details: processingError.message || processingError,
          filename: safeFilename,
          company_id: company_id,
          step_failed: 'python_pipeline',
          environment: {
            vercel: isVercel,
            production: isProduction
          },
          troubleshooting: {
            python_available: !isVercel,
            common_issues: [
              "Python virtual environment issues",
              "Missing Python dependencies",
              "Database connection issues", 
              "File permissions",
              "Python script errors"
            ]
          }
        });
      }
    }
    
  } catch (error) {
    console.error('Upload handler error:', error);
    
    return res.status(500).json({
      error: 'Upload processing failed',
      message: error.message,
      environment: {
        vercel: isVercel,
        production: isProduction
      }
    });
  } finally {
    // Clean up temporary file
    try {
      if (file.path && fs.existsSync(file.path)) {
        fs.unlinkSync(file.path);
      }
    } catch (cleanupError) {
      console.warn('Failed to clean up temporary file:', cleanupError);
    }
  }
};