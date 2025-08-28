/**
 * Python Pipeline Processor - Direct Integration Module
 * 
 * Replaces multiple subprocess calls with a single Python process
 * that can handle all pipeline operations through direct imports.
 */

const { spawn } = require('child_process');
const path = require('path');

class PythonProcessor {
    constructor() {
        this.rootDir = path.resolve(__dirname, '..', '..');
        this.pythonPath = path.join(this.rootDir, '.venv', 'bin', 'python3');
        this.processorPath = path.join(this.rootDir, 'server', 'scripts', 'pipeline_processor.py');
    }

    /**
     * Execute a Python pipeline operation
     * @param {string} operation - The operation to perform
     * @param {Array} args - Arguments for the operation
     * @returns {Promise<Object>} Result object with success status and data
     */
    async executeOperation(operation, args = []) {
        return new Promise((resolve, reject) => {
            const pythonArgs = [this.processorPath, operation, ...args];
            
            console.log(`🐍 Executing Python operation: ${operation}`);
            console.log(`📂 Using Python: ${this.pythonPath}`);
            console.log(`📄 Script: ${this.processorPath}`);
            console.log(`🔧 Args: ${args.join(' ')}`);
            
            const python = spawn(this.pythonPath, pythonArgs, {
                cwd: this.rootDir,
                env: {
                    ...process.env,
                    PYTHONPATH: path.join(this.rootDir, 'server', 'scripts'),
                    PYTHONUNBUFFERED: '1'
                },
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
                try {
                    if (code === 0) {
                        // Parse JSON response from Python
                        const result = JSON.parse(stdout);
                        console.log(`✅ Python operation completed: ${operation}`);
                        resolve(result);
                    } else {
                        console.error(`❌ Python operation failed: ${operation} (code ${code})`);
                        console.error('STDERR:', stderr);
                        
                        // Try to parse error response
                        let errorResult;
                        try {
                            errorResult = JSON.parse(stdout);
                        } catch (parseError) {
                            errorResult = {
                                success: false,
                                message: `Python process exited with code ${code}`,
                                errors: [stderr || `Process failed with code ${code}`]
                            };
                        }
                        resolve(errorResult);
                    }
                } catch (parseError) {
                    console.error('Failed to parse Python response:', parseError);
                    resolve({
                        success: false,
                        message: 'Failed to parse Python response',
                        errors: [parseError.message, stdout, stderr]
                    });
                }
            });

            python.on('error', (err) => {
                console.error(`Python process error:`, err);
                reject({
                    success: false,
                    message: `Python process failed to start: ${err.message}`,
                    errors: [err.message]
                });
            });

            // Set timeout
            const timeout = setTimeout(() => {
                python.kill('SIGKILL');
                reject({
                    success: false,
                    message: 'Python process timeout',
                    errors: ['Process exceeded 60 second timeout']
                });
            }, 60000);

            python.on('close', () => {
                clearTimeout(timeout);
            });
        });
    }

    /**
     * Ingest a file through the three-layer pipeline
     * @param {string} filePath - Path to the file to process
     * @param {number} companyId - Company ID
     * @returns {Promise<Object>} Processing result
     */
    async ingestFile(filePath, companyId) {
        return await this.executeOperation('ingest_file', [filePath, companyId.toString()]);
    }

    /**
     * Calculate derived metrics for a company
     * @param {number} companyId - Company ID
     * @returns {Promise<Object>} Calculation result
     */
    async calculateMetrics(companyId) {
        return await this.executeOperation('calculate_metrics', [companyId.toString()]);
    }

    /**
     * Generate analytical questions for a company
     * @param {number} companyId - Company ID
     * @returns {Promise<Object>} Question generation result
     */
    async generateQuestions(companyId) {
        return await this.executeOperation('generate_questions', [companyId.toString()]);
    }

    /**
     * Generate PDF report for a company
     * @param {number} companyId - Company ID
     * @param {string} outputPath - Output file path
     * @returns {Promise<Object>} Report generation result
     */
    async generateReport(companyId, outputPath) {
        return await this.executeOperation('generate_report', [companyId.toString(), outputPath]);
    }

    /**
     * Run complete pipeline: ingest -> calculate -> questions
     * @param {string} filePath - Path to the file to process
     * @param {number} companyId - Company ID
     * @returns {Promise<Object>} Complete pipeline result
     */
    async runCompletePipeline(filePath, companyId) {
        const results = {
            ingestion: null,
            metrics: null,
            questions: null,
            errors: []
        };

        try {
            // Step 1: Ingest file
            console.log(`🔄 Step 1: Ingesting file ${filePath}`);
            results.ingestion = await this.ingestFile(filePath, companyId);
            
            if (!results.ingestion.success) {
                throw new Error(`Ingestion failed: ${results.ingestion.message}`);
            }

            // Step 2: Calculate metrics
            console.log(`🔄 Step 2: Calculating metrics for company ${companyId}`);
            results.metrics = await this.calculateMetrics(companyId);
            
            if (!results.metrics.success) {
                console.warn(`⚠️ Metrics calculation failed: ${results.metrics.message}`);
                results.errors.push(`Metrics: ${results.metrics.message}`);
            }

            // Step 3: Generate questions
            console.log(`🔄 Step 3: Generating questions for company ${companyId}`);
            results.questions = await this.generateQuestions(companyId);
            
            if (!results.questions.success) {
                console.warn(`⚠️ Question generation failed: ${results.questions.message}`);
                results.errors.push(`Questions: ${results.questions.message}`);
            }

            return {
                success: results.ingestion.success,
                message: 'Pipeline completed',
                results,
                processing_steps: [
                    results.ingestion.success ? "✓ File ingested successfully" : "✗ File ingestion failed",
                    results.metrics?.success ? "✓ Metrics calculated" : "⚠ Metrics calculation issues",
                    results.questions?.success ? "✓ Questions generated" : "⚠ Question generation issues"
                ].filter(Boolean)
            };

        } catch (error) {
            console.error('❌ Pipeline failed:', error);
            return {
                success: false,
                message: `Pipeline failed: ${error.message}`,
                results,
                errors: [...results.errors, error.message]
            };
        }
    }
}

module.exports = PythonProcessor;