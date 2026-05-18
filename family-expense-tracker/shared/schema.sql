PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL,
    feishu_open_id TEXT UNIQUE,
    auth_method TEXT NOT NULL DEFAULT 'web_pin' CHECK (auth_method IN ('feishu_oauth', 'web_pin')),
    web_pin_hash TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    icon TEXT NOT NULL DEFAULT '📌',
    created_by INTEGER REFERENCES users(id),
    is_system INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT (datetime('now')),
    UNIQUE(name, created_by)
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    category_id INTEGER NOT NULL REFERENCES categories(id),
    amount REAL NOT NULL,
    type TEXT NOT NULL DEFAULT 'expense' CHECK (type IN ('expense', 'refund')),
    note TEXT DEFAULT '',
    recorded_at TIMESTAMP NOT NULL DEFAULT (datetime('now')),
    source TEXT NOT NULL DEFAULT 'web' CHECK (source IN ('feishu_bot', 'web')),
    feishu_event_id TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    category_id INTEGER,
    amount REAL NOT NULL CHECK (amount > 0),
    month TEXT NOT NULL CHECK (month GLOB '????-??'),
    warn_threshold REAL NOT NULL DEFAULT 0.8 CHECK (warn_threshold > 0 AND warn_threshold <= 1),
    created_at TIMESTAMP NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, category_id, month)
);

CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses(user_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id);
CREATE INDEX IF NOT EXISTS idx_budgets_user_month ON budgets(user_id, month);
CREATE INDEX IF NOT EXISTS idx_feishu_event ON expenses(feishu_event_id);

-- System categories
INSERT OR IGNORE INTO categories (name, icon, is_system, created_by) VALUES ('餐饮', '🍜', 1, NULL);
INSERT OR IGNORE INTO categories (name, icon, is_system, created_by) VALUES ('交通', '🚗', 1, NULL);
INSERT OR IGNORE INTO categories (name, icon, is_system, created_by) VALUES ('购物', '🛒', 1, NULL);
INSERT OR IGNORE INTO categories (name, icon, is_system, created_by) VALUES ('教育', '📚', 1, NULL);
INSERT OR IGNORE INTO categories (name, icon, is_system, created_by) VALUES ('医疗', '🏥', 1, NULL);
INSERT OR IGNORE INTO categories (name, icon, is_system, created_by) VALUES ('居住', '🏠', 1, NULL);
INSERT OR IGNORE INTO categories (name, icon, is_system, created_by) VALUES ('娱乐', '🎮', 1, NULL);
INSERT OR IGNORE INTO categories (name, icon, is_system, created_by) VALUES ('其他', '📌', 1, NULL);
