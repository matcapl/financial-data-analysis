const { spawn } = require('child_process');
const { put } = require('@vercel/blob');
const path = require('path');
const fs = require('fs');

module.exports = async (req, res) => {
    /**
     * Fixed Report Generation - Phase 1 Critical Fix
     * 
     * Key fixes implemented:
     * 1. Ensure full pipeline runs before report generation
     * 2. Add validation that data exists before generating report
     * 3. Use secure spawn instead of execSync
     * 4. Add comprehensive error handling
     * 5. Create reports directory if it doesn't exist
     */
    
    const { company_id } = req.body;
    
    if (!company_id) {
        return res.status(400).json({ error: 'Missing company_id' });
    }
    
    const companyIdNum = parseInt(company_id);
    if (isNaN(companyIdNum) || companyIdNum <= 0) {
        return res.status(400).json({ error: 'Invalid company_id. Must be a positive integer.' });
    }
    
    try {
        console.log(`Starting report generation for company ${companyIdNum}...`);
        
        // Step 1: Verify data exists
        console.log('Verifying data availability...');
        await verifyDataExists(companyIdNum);
        console.log('✓ Data verification completed');
        
        // Step 2: Run metric calculations (ensure latest calculations)
        console.log('Running metric calculations...');
        await runPythonScript('calc_metrics.py', []);
        console.log('✓ Metric calculations completed');
        
        // Step 3: Generate questions (ensure latest questions)
        console.log('Generating questions...');
        await runPythonScript('questions_engine.py', []);
        console.log('✓ Question generation completed');
        
        // Step 4: Generate the report
        console.log('Generating PDF report...');
        const timestamp = Date.now();
        const reportFileName = `report_${companyIdNum}_${timestamp}.pdf`;
        const reportsDir = path.resolve(__dirname, '..', '..', 'reports');
        
        // Ensure reports directory exists
        if (!fs.existsSync(reportsDir)) {
            fs.mkdirSync(reportsDir, { recursive: true });
        }
        
        const outputPath = path.join(reportsDir, reportFileName);
        
        await runPythonScript('report_generator.py', [companyIdNum.toString(), outputPath]);
        console.log('✓ PDF report generated');
        
        // Step 5: Verify report was created
        if (!fs.existsSync(outputPath)) {
            throw new Error('Report file was not created successfully');
        }
        
        // Step 6: Upload to Vercel Blob
        const reportData = fs.readFileSync(outputPath);
        const blob = await put(reportFileName, reportData, { 
            access: 'public',
            contentType: 'application/pdf'
        });
        
        // Step 7: Clean up local report file
        if (fs.existsSync(outputPath)) {
            fs.unlinkSync(outputPath);
        }
        
        console.log('✓ Report uploaded to blob storage');
        
        res.json({ 
            message: 'Report generated successfully',
            company_id: companyIdNum,
            report_filename: reportFileName,
            reportPath: blob.url,
            processing_steps: [
                '✓ Data availability verified',
                '✓ Metrics calculated',
                '✓ Questions generated', 
                '✓ PDF report created',
                '✓ Report uploaded to storage'
            ],
            generated_at: new Date().toISOString()
        });
        
    } catch (err) {
        console.error('Report generation failed:', err);
        
        res.status(500).json({ 
            error: 'Report generation failed',
            details: err.message,
            step_failed: err.step || 'unknown',
            company_id: companyIdNum
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

/**
 * Verify that data exists for the given company before generating report
 */
function verifyDataExists(companyId) {
    return new Promise((resolve, reject) => {
        const verifyScript = `
import sys
import psycopg2
from scripts.utils import get_db_connection

def verify_data(company_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if company exists
                cur.execute("SELECT id FROM companies WHERE id = %s", (company_id,))
                if not cur.fetchone():
                    raise Exception(f"Company {company_id} not found")
                
                # Check if financial metrics exist
                cur.execute("SELECT COUNT(*) FROM financial_metrics WHERE company_id = %s", (company_id,))
                metrics_count = cur.fetchone()[0]
                if metrics_count == 0:
                    raise Exception(f"No financial metrics found for company {company_id}")
                
                print(f"Data verification passed: {metrics_count} metrics found for company {company_id}")
                return True
    except Exception as e:
        print(f"Data verification failed: {e}")
        raise

if __name__ == "__main__":
    verify_data(${companyId})
`;
        
        const python = spawn('python', ['-c', verifyScript], {
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
                console.log('Data verification output:', stdout);
                resolve();
            } else {
                const error = new Error(`Data verification failed: ${stderr}`);
                error.step = 'Data verification';
                reject(error);
            }
        });
        
        python.on('error', (err) => {
            const error = new Error(`Failed to run data verification: ${err.message}`);
            error.step = 'Data verification process start';
            reject(error);
        });
    });
}