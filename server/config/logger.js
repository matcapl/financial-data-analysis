/**
 * Centralized Logging Configuration
 * Provides structured logging with different levels and output formats
 */

const winston = require('winston');
const DailyRotateFile = require('winston-daily-rotate-file');
const path = require('path');

// Create logs directory if it doesn't exist
const fs = require('fs');
const logsDir = path.join(__dirname, '..', 'logs');
if (!fs.existsSync(logsDir)) {
  fs.mkdirSync(logsDir, { recursive: true });
}

// Define log levels
const logLevels = {
  error: 0,
  warn: 1,
  info: 2,
  http: 3,
  debug: 4
};

// Define colors for console output
const logColors = {
  error: 'red',
  warn: 'yellow',
  info: 'green',
  http: 'magenta',
  debug: 'white'
};

winston.addColors(logColors);

// Custom log format
const logFormat = winston.format.combine(
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  winston.format.errors({ stack: true }),
  winston.format.json(),
  winston.format.printf(({ timestamp, level, message, service, ...meta }) => {
    let log = `${timestamp} [${level.toUpperCase()}]`;
    
    if (service) {
      log += ` [${service}]`;
    }
    
    log += ` ${message}`;
    
    // Add metadata if present
    if (Object.keys(meta).length > 0) {
      log += ` ${JSON.stringify(meta)}`;
    }
    
    return log;
  })
);

// Console format for development
const consoleFormat = winston.format.combine(
  winston.format.colorize({ all: true }),
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  winston.format.printf(({ timestamp, level, message, service, ...meta }) => {
    let log = `${timestamp} [${level}]`;
    
    if (service) {
      log += ` [${service}]`;
    }
    
    log += ` ${message}`;
    
    // Add metadata for development
    if (Object.keys(meta).length > 0) {
      log += ` ${JSON.stringify(meta, null, 2)}`;
    }
    
    return log;
  })
);

// Create transports
const transports = [
  // Console transport for development
  new winston.transports.Console({
    level: process.env.LOG_LEVEL || 'info',
    format: consoleFormat,
    handleExceptions: true
  }),

  // Daily rotating file for all logs
  new DailyRotateFile({
    filename: path.join(logsDir, 'application-%DATE%.log'),
    datePattern: 'YYYY-MM-DD',
    maxSize: '20m',
    maxFiles: '14d',
    format: logFormat,
    level: 'info'
  }),

  // Daily rotating file for errors only
  new DailyRotateFile({
    filename: path.join(logsDir, 'error-%DATE%.log'),
    datePattern: 'YYYY-MM-DD',
    maxSize: '20m',
    maxFiles: '30d',
    format: logFormat,
    level: 'error',
    handleExceptions: true
  }),

  // HTTP requests log
  new DailyRotateFile({
    filename: path.join(logsDir, 'http-%DATE%.log'),
    datePattern: 'YYYY-MM-DD',
    maxSize: '20m',
    maxFiles: '7d',
    format: logFormat,
    level: 'http'
  })
];

// Create the logger
const logger = winston.createLogger({
  levels: logLevels,
  format: logFormat,
  defaultMeta: {
    service: 'financial-data-server'
  },
  transports,
  exitOnError: false
});

// Create child loggers for different services
const createServiceLogger = (serviceName) => {
  return logger.child({ service: serviceName });
};

// HTTP request logging middleware
const httpLoggerMiddleware = (req, res, next) => {
  const start = Date.now();
  
  // Log request
  logger.http('HTTP Request', {
    method: req.method,
    url: req.originalUrl,
    userAgent: req.get('User-Agent'),
    ip: req.ip,
    requestId: req.headers['x-request-id'] || `req-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  });
  
  // Log response when finished
  res.on('finish', () => {
    const duration = Date.now() - start;
    const logLevel = res.statusCode >= 400 ? 'warn' : 'http';
    
    logger.log(logLevel, 'HTTP Response', {
      method: req.method,
      url: req.originalUrl,
      statusCode: res.statusCode,
      duration: `${duration}ms`,
      requestId: req.headers['x-request-id']
    });
  });
  
  next();
};

// Utility functions for structured logging
const logWithContext = (level, message, context = {}) => {
  logger.log(level, message, context);
};

const logError = (error, context = {}) => {
  if (error instanceof Error) {
    logger.error(error.message, {
      stack: error.stack,
      name: error.name,
      ...context
    });
  } else {
    logger.error(String(error), context);
  }
};

const logFileOperation = (operation, filePath, success = true, metadata = {}) => {
  logger.info(`File ${operation}`, {
    operation,
    filePath: path.basename(filePath),
    success,
    ...metadata
  });
};

const logDatabaseOperation = (operation, table, success = true, metadata = {}) => {
  logger.info(`Database ${operation}`, {
    operation,
    table,
    success,
    ...metadata
  });
};

const logPipelineStep = (step, companyId, success = true, metadata = {}) => {
  const level = success ? 'info' : 'error';
  logger.log(level, `Pipeline Step: ${step}`, {
    step,
    companyId,
    success,
    ...metadata
  });
};

// Export everything
module.exports = {
  logger,
  createServiceLogger,
  httpLoggerMiddleware,
  logWithContext,
  logError,
  logFileOperation,
  logDatabaseOperation,
  logPipelineStep
};