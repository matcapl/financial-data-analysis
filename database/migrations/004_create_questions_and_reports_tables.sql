-- Migration: Create questions and reports tables
-- Version: 004
-- Description: Create tables for question templates, generated questions, and report tracking
-- Author: System Migration
-- Date: 2025-01-28

-- Question templates table
CREATE TABLE IF NOT EXISTS question_templates (
  id SERIAL PRIMARY KEY,
  question_text TEXT NOT NULL,
  category TEXT NOT NULL,
  priority INTEGER DEFAULT 3,
  template_variables TEXT[],
  created_at TIMESTAMP DEFAULT NOW() NOT NULL,
  updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE question_templates IS 'Templates for generating analytical questions';
COMMENT ON COLUMN question_templates.category IS 'Question category (e.g., variance_analysis, trend_analysis)';
COMMENT ON COLUMN question_templates.priority IS 'Question priority (1=high, 5=low)';
COMMENT ON COLUMN question_templates.template_variables IS 'Variables that can be substituted in the question';

-- Generated questions table
CREATE TABLE IF NOT EXISTS questions (
  id SERIAL PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  question_text TEXT NOT NULL,
  category TEXT NOT NULL,
  priority INTEGER DEFAULT 3,
  metric_context JSONB,
  created_at TIMESTAMP DEFAULT NOW() NOT NULL,
  updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE questions IS 'Generated analytical questions for specific companies';
COMMENT ON COLUMN questions.metric_context IS 'JSON context about the metrics that triggered this question';

-- Live questions table (currently active questions)
CREATE TABLE IF NOT EXISTS live_questions (
  id SERIAL PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  question_text TEXT NOT NULL,
  category TEXT NOT NULL,
  priority INTEGER DEFAULT 3,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMP DEFAULT NOW() NOT NULL,
  expires_at TIMESTAMP,
  UNIQUE (company_id, question_text)
);

COMMENT ON TABLE live_questions IS 'Currently active questions requiring attention';
COMMENT ON COLUMN live_questions.status IS 'Question status: active, resolved, expired';

-- Question logs table (audit trail)
CREATE TABLE IF NOT EXISTS question_logs (
  id SERIAL PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  action TEXT NOT NULL,
  question_data JSONB,
  created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE question_logs IS 'Audit log of question generation and management activities';
COMMENT ON COLUMN question_logs.action IS 'Action performed: generated, resolved, expired, etc.';

-- Generated reports table
CREATE TABLE IF NOT EXISTS generated_reports (
  id SERIAL PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  report_type TEXT NOT NULL DEFAULT 'financial_analysis',
  file_path TEXT,
  file_size INTEGER,
  generation_time_ms INTEGER,
  created_at TIMESTAMP DEFAULT NOW() NOT NULL,
  expires_at TIMESTAMP
);

COMMENT ON TABLE generated_reports IS 'Tracking of generated PDF reports';
COMMENT ON COLUMN generated_reports.generation_time_ms IS 'Time taken to generate the report in milliseconds';

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_question_templates_category ON question_templates(category);
CREATE INDEX IF NOT EXISTS idx_questions_company ON questions(company_id);
CREATE INDEX IF NOT EXISTS idx_questions_category ON questions(category);
CREATE INDEX IF NOT EXISTS idx_live_questions_company_status ON live_questions(company_id, status);
CREATE INDEX IF NOT EXISTS idx_question_logs_company_action ON question_logs(company_id, action);
CREATE INDEX IF NOT EXISTS idx_generated_reports_company ON generated_reports(company_id);
CREATE INDEX IF NOT EXISTS idx_generated_reports_created ON generated_reports(created_at);