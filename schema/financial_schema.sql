-- Companies
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    industry TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Periods
CREATE TABLE periods (
    id SERIAL PRIMARY KEY,
    period_type VARCHAR(10) CHECK (period_type IN ('Monthly', 'Quarterly', 'Yearly')),
    period_label VARCHAR(20), -- e.g., 'Q1 2025', 'Jan 2025', 'YTD 2025'
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Line Item Definitions
CREATE TABLE line_item_definitions (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL CHECK (name IN ('Revenue', 'Gross Profit', 'EBITDA')),
    statement_type VARCHAR(50),
    category TEXT, -- e.g., 'Revenue', 'Profitability'
    default_weight NUMERIC(5,2) DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Financial Metrics (Raw Data)
CREATE TABLE financial_metrics (
    id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies(id),
    period_id INT REFERENCES periods(id),
    line_item_id INT REFERENCES line_item_definitions(id),
    value_type TEXT CHECK (value_type IN ('Actual', 'Budget', 'Prior')),
    frequency TEXT CHECK (frequency IN ('Monthly', 'Quarterly', 'Yearly')),
    value NUMERIC(18,2),
    currency TEXT DEFAULT 'USD',
    source_file TEXT,
    source_page INT,
    source_type TEXT CHECK (source_type IN ('Raw', 'Calculated')),
    notes TEXT,
    hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(hash)
);

-- Derived Metrics (Calculated Values)
CREATE TABLE derived_metrics (
    id SERIAL PRIMARY KEY,
    base_metric_id INT REFERENCES line_item_definitions(id),
    calculation_type TEXT, -- e.g., 'YoY Growth', 'Variance vs Budget', 'YTD'
    frequency TEXT CHECK (frequency IN ('Monthly', 'Quarterly', 'Yearly')),
    company_id INT REFERENCES companies(id),
    period_id INT REFERENCES periods(id),
    calculated_value NUMERIC(18,2),
    unit TEXT CHECK (unit IN ('%', 'USD')),
    source_ids JSONB, -- Array of financial_metrics IDs
    calculation_note TEXT,
    corroboration_status TEXT DEFAULT 'Pending' CHECK (corroboration_status IN ('Pending', 'Ok', 'Conflict')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Question Templates
CREATE TABLE question_templates (
    id SERIAL PRIMARY KEY,
    metric TEXT NOT NULL,
    calculation_type TEXT NOT NULL,
    base_question TEXT NOT NULL,
    trigger_threshold NUMERIC NOT NULL,
    trigger_operator TEXT CHECK (trigger_operator IN ('>', '<', '>=', '<=', '=')),
    default_weight NUMERIC(5,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Live Questions
CREATE TABLE live_questions (
    id SERIAL PRIMARY KEY,
    derived_metric_id INT REFERENCES derived_metrics(id),
    template_id INT REFERENCES question_templates(id),
    question_text TEXT NOT NULL,
    category TEXT CHECK (category IN ('Financial')),
    composite_score NUMERIC(5,2),
    scorecard JSONB,
    status TEXT DEFAULT 'Open' CHECK (status IN ('Open', 'Resolved')),
    owner TEXT,
    deadline DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Question Logs
CREATE TABLE question_logs (
    id SERIAL PRIMARY KEY,
    live_question_id INT REFERENCES live_questions(id),
    change_type TEXT,
    changed_by TEXT,
    old_value TEXT,
    new_value TEXT,
    change_note TEXT,
    changed_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Generated Reports
CREATE TABLE generated_reports (
    id SERIAL PRIMARY KEY,
    generated_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filter_type TEXT,
    parameters JSONB,
    output_summary TEXT,
    report_file_path TEXT,
    company_id INT REFERENCES companies(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_financial_metrics_company_period ON financial_metrics(company_id, period_id);
CREATE INDEX idx_financial_metrics_line_item ON financial_metrics(line_item_id);
CREATE INDEX idx_financial_metrics_hash ON financial_metrics(hash);
CREATE INDEX idx_derived_metrics_base ON derived_metrics(base_metric_id);
CREATE INDEX idx_derived_metrics_company_period ON derived_metrics(company_id, period_id);
CREATE INDEX idx_live_questions_status ON live_questions(status);
CREATE INDEX idx_live_questions_score ON live_questions(composite_score DESC);

-- Insert default company
INSERT INTO companies (name, industry) VALUES ('Wilson Group', 'Technology') ON CONFLICT DO NOTHING;

-- Insert line item definitions
INSERT INTO line_item_definitions (name, statement_type, category, default_weight) VALUES 
    ('Revenue', 'Income Statement', 'Revenue', 1.0),
    ('Gross Profit', 'Income Statement', 'Profitability', 0.8),
    ('EBITDA', 'Income Statement', 'Profitability', 0.9)
ON CONFLICT DO NOTHING;