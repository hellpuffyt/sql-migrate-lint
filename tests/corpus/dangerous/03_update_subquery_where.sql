UPDATE users SET plan_id = (SELECT id FROM plans WHERE name = 'free');
