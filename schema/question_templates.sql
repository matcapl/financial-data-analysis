-- Drop and recreate question_templates with correct columns and constraints
DROP TABLE IF EXISTS question_templates CASCADE;

CREATE TABLE IF NOT EXISTS question_templates (
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

-- Seed question templates

INSERT INTO question_templates (metric, calculation_type, base_question, trigger_threshold, trigger_operator, default_weight) VALUES

-- Month-over-Month
('Revenue',      'MoM Growth', 'Revenue increased by {change}% month-over-month. What factors contributed to this growth?',      2.0, '>=', 3.00),
('Revenue',      'MoM Growth', 'Revenue decreased by {change}% month-over-month. What caused this decline?',                    -2.0, '<=', 4.00),
('Gross Profit', 'MoM Growth', 'Gross profit rose by {change}% month-over-month. What operational improvements contributed?',   2.0, '>=', 3.00),
('Gross Profit', 'MoM Growth', 'Gross profit dropped by {change}% month-over-month. What cost pressures emerged?',             -2.0, '<=', 4.00),
('EBITDA',       'MoM Growth', 'EBITDA increased by {change}% month-over-month. What operational efficiencies were achieved?',  2.0, '>=', 4.00),
('EBITDA',       'MoM Growth', 'EBITDA decreased by {change}% month-over-month. What cost controls are needed?',               -2.0, '<=', 5.00),

-- Quarter-over-Quarter
('Revenue',      'QoQ Growth', 'Revenue grew by {change}% quarter-over-quarter. What drove this performance?',                   1.5, '>=', 3.00),
('Revenue',      'QoQ Growth', 'Revenue fell by {change}% quarter-over-quarter. What were the key challenges?',                 -1.5, '<=', 4.00),
('Gross Profit', 'QoQ Growth', 'Gross profit improved by {change}% quarter-over-quarter. What margin expansion strategies worked?', 1.5, '>=', 3.00),
('Gross Profit', 'QoQ Growth', 'Gross profit contracted by {change}% quarter-over-quarter. How can margins be protected?',      -1.5, '<=', 4.00),
('EBITDA',       'QoQ Growth', 'EBITDA grew by {change}% quarter-over-quarter. What scalability factors emerged?',               1.5, '>=', 4.00),
('EBITDA',       'QoQ Growth', 'EBITDA fell by {change}% quarter-over-quarter. What expense management is required?',           -1.5, '<=', 5.00),

-- Year-over-Year
('Revenue',      'YoY Growth', 'Revenue increased by {change}% year-over-year. How sustainable is this growth trajectory?',       1.0, '>=', 2.00),
('Revenue',      'YoY Growth', 'Revenue declined by {change}% year-over-year. What is the recovery strategy?',                  -1.0, '<=', 4.00),
('Gross Profit', 'YoY Growth', 'Gross profit expanded by {change}% year-over-year. What structural advantages were gained?',     1.0, '>=', 2.00),
('Gross Profit', 'YoY Growth', 'Gross profit eroded by {change}% year-over-year. What competitive pressures exist?',            -1.0, '<=', 4.00),
('EBITDA',       'YoY Growth', 'EBITDA rose by {change}% year-over-year. What long-term value creation occurred?',               1.0, '>=', 3.00),
('EBITDA',       'YoY Growth', 'EBITDA declined by {change}% year-over-year. What restructuring is needed?',                    -1.0, '<=', 5.00),

-- Variance vs Budget (Catchall/Low threshold)
('Revenue',      'Variance vs Budget', 'Revenue variance vs budget is {change}%. What market dynamics influenced this result?',   0.5, '>=', 1.00),
('Gross Profit', 'Variance vs Budget', 'Gross profit variance vs budget is {change}%. What supply chain factors were involved?',  0.5, '>=', 1.00),
('EBITDA',       'Variance vs Budget', 'EBITDA variance vs budget is {change}%. What operational adjustments occurred?',          0.5, '>=', 1.00);

