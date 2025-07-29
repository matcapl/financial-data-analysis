-- Updated Question Templates - Phase 1 Critical Fix
-- Key changes:
-- 1. Lower MoM threshold from 10% to 5%
-- 2. Lower QoQ threshold from 8% to 4%  
-- 3. Lower YoY threshold from 5% to 3%
-- 4. Lower Budget variance threshold from 5% to 3%
-- 5. Add additional question types for better coverage

-- Question templates with proper constraint handling
-- Drop existing table if it exists to avoid constraint conflicts
DROP TABLE IF EXISTS question_templates;

CREATE TABLE question_templates (
    id SERIAL PRIMARY KEY,
    template_name VARCHAR(100) UNIQUE NOT NULL,
    question_text TEXT NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    period_type VARCHAR(20) NOT NULL,
    threshold_type VARCHAR(30) NOT NULL,
    threshold_value DECIMAL(10,4) NOT NULL,
    weight INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert question templates with lowered thresholds
INSERT INTO question_templates (template_name, question_text, metric_type, period_type, threshold_type, threshold_value, weight) VALUES

-- Monthly Revenue Questions (5% threshold)
('revenue_mom_increase', 'Revenue increased by {change:.1f}% month-over-month in {period}. What factors contributed to this growth?', 'Revenue', 'monthly', 'mom_increase', 5.0, 3),
('revenue_mom_decrease', 'Revenue decreased by {change:.1f}% month-over-month in {period}. What caused this decline?', 'Revenue', 'monthly', 'mom_decrease', 5.0, 4),

-- Quarterly Revenue Questions (4% threshold)
('revenue_qoq_increase', 'Revenue grew by {change:.1f}% quarter-over-quarter in {period}. What drove this performance?', 'Revenue', 'quarterly', 'qoq_increase', 4.0, 3),
('revenue_qoq_decrease', 'Revenue fell by {change:.1f}% quarter-over-quarter in {period}. What were the key challenges?', 'Revenue', 'quarterly', 'qoq_decrease', 4.0, 4),

-- Yearly Revenue Questions (3% threshold)
('revenue_yoy_increase', 'Revenue increased by {change:.1f}% year-over-year in {period}. How sustainable is this growth trajectory?', 'Revenue', 'yearly', 'yoy_increase', 3.0, 2),
('revenue_yoy_decrease', 'Revenue declined by {change:.1f}% year-over-year in {period}. What is the recovery strategy?', 'Revenue', 'yearly', 'yoy_decrease', 3.0, 4),

-- Monthly Gross Profit Questions (5% threshold)
('gross_profit_mom_increase', 'Gross profit rose by {change:.1f}% month-over-month in {period}. What operational improvements contributed?', 'Gross Profit', 'monthly', 'mom_increase', 5.0, 3),
('gross_profit_mom_decrease', 'Gross profit dropped by {change:.1f}% month-over-month in {period}. What cost pressures emerged?', 'Gross Profit', 'monthly', 'mom_decrease', 5.0, 4),

-- Quarterly Gross Profit Questions (4% threshold)  
('gross_profit_qoq_increase', 'Gross profit improved by {change:.1f}% quarter-over-quarter in {period}. What margin expansion strategies worked?', 'Gross Profit', 'quarterly', 'qoq_increase', 4.0, 3),
('gross_profit_qoq_decrease', 'Gross profit contracted by {change:.1f}% quarter-over-quarter in {period}. How can margins be protected?', 'Gross Profit', 'quarterly', 'qoq_decrease', 4.0, 4),

-- Yearly Gross Profit Questions (3% threshold)
('gross_profit_yoy_increase', 'Gross profit expanded by {change:.1f}% year-over-year in {period}. What structural advantages were gained?', 'Gross Profit', 'yearly', 'yoy_increase', 3.0, 2),
('gross_profit_yoy_decrease', 'Gross profit eroded by {change:.1f}% year-over-year in {period}. What competitive pressures exist?', 'Gross Profit', 'yearly', 'yoy_decrease', 3.0, 4),

-- Monthly EBITDA Questions (5% threshold)
('ebitda_mom_increase', 'EBITDA increased by {change:.1f}% month-over-month in {period}. What operational efficiencies were achieved?', 'EBITDA', 'monthly', 'mom_increase', 5.0, 4),
('ebitda_mom_decrease', 'EBITDA decreased by {change:.1f}% month-over-month in {period}. What cost controls are needed?', 'EBITDA', 'monthly', 'mom_decrease', 5.0, 5),

-- Quarterly EBITDA Questions (4% threshold)
('ebitda_qoq_increase', 'EBITDA grew by {change:.1f}% quarter-over-quarter in {period}. What scalability factors emerged?', 'EBITDA', 'quarterly', 'qoq_increase', 4.0, 4),
('ebitda_qoq_decrease', 'EBITDA fell by {change:.1f}% quarter-over-quarter in {period}. What expense management is required?', 'EBITDA', 'quarterly', 'qoq_decrease', 4.0, 5),

-- Yearly EBITDA Questions (3% threshold)
('ebitda_yoy_increase', 'EBITDA rose by {change:.1f}% year-over-year in {period}. What long-term value creation occurred?', 'EBITDA', 'yearly', 'yoy_increase', 3.0, 3),
('ebitda_yoy_decrease', 'EBITDA declined by {change:.1f}% year-over-year in {period}. What restructuring is needed?', 'EBITDA', 'yearly', 'yoy_decrease', 3.0, 5),

-- Low threshold catchall questions (1% threshold for guaranteed coverage)
('revenue_small_change', 'Revenue changed by {change:.1f}% in {period}. What market dynamics influenced this result?', 'Revenue', 'any', 'any_change', 1.0, 1),
('gross_profit_small_change', 'Gross profit shifted by {change:.1f}% in {period}. What supply chain factors were involved?', 'Gross Profit', 'any', 'any_change', 1.0, 1),
('ebitda_small_change', 'EBITDA moved by {change:.1f}% in {period}. What operational adjustments occurred?', 'EBITDA', 'any', 'any_change', 1.0, 1),

-- Seasonal and trend questions
('revenue_seasonal', 'Revenue patterns in {period} show seasonal variation. How does this compare to historical trends?', 'Revenue', 'any', 'seasonal', 0.1, 2),
('profitability_trend', 'Profitability metrics in {period} indicate trend changes. What strategic pivots are planned?', 'EBITDA', 'any', 'trend', 0.1, 2);
