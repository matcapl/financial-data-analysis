INSERT INTO question_templates (
    metric, calculation_type, base_question, trigger_threshold, trigger_operator, default_weight
) VALUES
    ('Revenue', 'MoM Growth', 'Why did Revenue change by {change}% from the previous month?', 10.0, '>=', 1.0),
    ('Revenue', 'QoQ Growth', 'Why did Revenue change by {change}% from the previous quarter?', 8.0, '>=', 1.0),
    ('Revenue', 'YoY Growth', 'Why did Revenue change by {change}% from the same period last year?', 5.0, '>=', 1.0),
    ('Revenue', 'YTD Growth', 'Why did YTD Revenue change by {change}% from last year?', 5.0, '>=', 1.0),
    ('Revenue', 'Variance vs Budget', 'Why is Revenue {change}% different from budget?', 5.0, '>=', 1.0),
    ('Gross Profit', 'MoM Growth', 'Why did Gross Profit change by {change}% from the previous month?', 10.0, '>=', 0.8),
    ('Gross Profit', 'QoQ Growth', 'Why did Gross Profit change by {change}% from the previous quarter?', 8.0, '>=', 0.8),
    ('Gross Profit', 'YoY Growth', 'Why did Gross Profit change by {change}% from the same period last year?', 5.0, '>=', 0.8),
    ('Gross Profit', 'YTD Growth', 'Why did YTD Gross Profit change by {change}% from last year?', 5.0, '>=', 0.8),
    ('Gross Profit', 'Variance vs Budget', 'Why is Gross Profit {change}% different from budget?', 5.0, '>=', 0.8),
    ('EBITDA', 'MoM Growth', 'Why did EBITDA change by {change}% from the previous month?', 10.0, '>=', 0.9),
    ('EBITDA', 'QoQ Growth', 'Why did EBITDA change by {change}% from the previous quarter?', 8.0, '>=', 0.9),
    ('EBITDA', 'YoY Growth', 'Why did EBITDA change by {change}% from the same period last year?', 5.0, '>=', 0.9),
    ('EBITDA', 'YTD Growth', 'Why did YTD EBITDA change by {change}% from last year?', 5.0, '>=', 0.9),
    ('EBITDA', 'Variance vs Budget', 'Why is EBITDA {change}% different from budget?', 5.0, '>=', 0.9)
ON CONFLICT DO NOTHING;