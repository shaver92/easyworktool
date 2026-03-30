PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    open_id TEXT UNIQUE NOT NULL,
    union_id TEXT,
    name TEXT NOT NULL,
    email TEXT,
    role TEXT NOT NULL DEFAULT 'user',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    spec TEXT DEFAULT '',
    location TEXT DEFAULT '',
    owner_open_id TEXT,
    total_qty INTEGER NOT NULL DEFAULT 0 CHECK(total_qty >= 0),
    available_qty INTEGER NOT NULL DEFAULT 0 CHECK(available_qty >= 0),
    status TEXT NOT NULL DEFAULT 'available',
    image_url TEXT DEFAULT '',
    is_deleted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    qty_delta INTEGER NOT NULL,
    reason TEXT DEFAULT '',
    operator_open_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (material_id) REFERENCES materials(id)
);

CREATE TABLE IF NOT EXISTS borrow_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no TEXT UNIQUE NOT NULL,
    applicant_open_id TEXT NOT NULL,
    approver_open_id TEXT,
    borrow_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    due_at TEXT NOT NULL,
    returned_at TEXT,
    status TEXT NOT NULL DEFAULT 'borrowed',
    note TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS borrow_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    borrow_order_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    qty INTEGER NOT NULL CHECK(qty > 0),
    returned_qty INTEGER NOT NULL DEFAULT 0 CHECK(returned_qty >= 0),
    FOREIGN KEY (borrow_order_id) REFERENCES borrow_orders(id),
    FOREIGN KEY (material_id) REFERENCES materials(id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    borrow_order_id INTEGER,
    receiver_open_id TEXT NOT NULL,
    notify_type TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT DEFAULT '',
    sent_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_open_id TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    before_json TEXT DEFAULT '',
    after_json TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
