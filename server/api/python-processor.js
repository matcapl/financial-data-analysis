/**
 * Python Pipeline Processor - Direct Integration Module
 * 
 * Replaces multiple subprocess calls with a single Python process
 * that can handle all pipeline operations through direct imports.
 */

const { spawn } = require('child_process');
const path = require('path');
const { createServiceLogger, logError } = require('../config/logger');

const logger = createServiceLogger('python-processor');

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
            
            logger.info('Executing Python operation', {
                operation,
                pythonPath: this.pythonPath,
                scriptPath: this.processorPath,
                args: args,
                processId: process.pid
            });
            
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
                        logger.info('Python operation completed successfully', {
                            operation,
                            success: result.success,
                            dataKeys: result.data ? Object.keys(result.data) : []
                        });
                        resolve(result);
                    } else {
                        logger.error('Python operation failed', {
                            operation,
                            exitCode: code,
                            stderr,
                            stdout: stdout.slice(0, 500) // Limit stdout in logs
                        });
                        
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
                    logError(parseError, {
                        operation,
                        context: 'parse_python_response',
                        stdout: stdout.slice(0, 200),
                        stderr: stderr.slice(0, 200)
                    });
                    resolve({
                        success: false,
                        message: 'Failed to parse Python response',
                        errors: [parseError.message, stdout, stderr]
                    });
                }
            });

            python.on('error', (err) => {
                logError(err, {
                    operation,
                    context: 'python_process_spawn',
                    pythonPath: this.pythonPath
                });
                reject({
                    success: false,
                    message: `Python process failed to start: ${err.message}`,
                    errors: [err.message]
                });
            });

            // Set timeout
            const timeout = setTimeout(() => {
                logger.warn('Python process timeout', {
                    operation,
                    timeoutMs: 60000
                });
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
            logger.info('Starting complete pipeline', {
                filePath: path.basename(filePath),
                companyId,
                step: 'ingestion'
            });
            results.ingestion = await this.ingestFile(filePath, companyId);
            
            if (!results.ingestion.success) {
                throw new Error(`Ingestion failed: ${results.ingestion.message}`);
            }

            // Step 2: Calculate metrics
            logger.info('Pipeline step: metrics calculation', {
                companyId,
                step: 'metrics'
            });
            results.metrics = await this.calculateMetrics(companyId);
            
            if (!results.metrics.success) {
                logger.warn('Metrics calculation failed', {
                    companyId,
                    error: results.metrics.message
                });
                results.errors.push(`Metrics: ${results.metrics.message}`);
            }

            // Step 3: Generate questions
            logger.info('Pipeline step: question generation', {
                companyId,
                step: 'questions'
            });
            results.questions = await this.generateQuestions(companyId);
            
            if (!results.questions.success) {
                logger.warn('Question generation failed', {
                    companyId,
                    error: results.questions.message
                });
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
                ].filter(Boolean),
                errors: results.errors
            };

        } catch (error) {
            logError(error, {
                context: 'complete_pipeline',
                companyId,
                filePath: path.basename(filePath)
            });
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