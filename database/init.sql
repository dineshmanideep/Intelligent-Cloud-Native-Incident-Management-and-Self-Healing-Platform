CREATE TABLE IF NOT EXISTS demo_items (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

INSERT INTO demo_items (name)
VALUES ('first demo record'), ('second demo record')
ON CONFLICT (name) DO NOTHING;

