-- Schema version
PRAGMA user_version = 1;

-- Enable foreign key support
PRAGMA foreign_keys = ON;

-- Users table
-- Stores information about bot users
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT,
    language_code TEXT DEFAULT 'ru',
    contact TEXT, -- For payment details
    payday_days TEXT, -- e.g., "5,20"
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Trigger to update user's updated_at timestamp
CREATE TRIGGER IF NOT EXISTS trigger_users_updated_at
AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE user_id = old.user_id;
END;

-- Trusted users table (many-to-many relationship)
-- Stores trust relationships between users
CREATE TABLE IF NOT EXISTS trusted_users (
    user_id INTEGER NOT NULL,
    trusted_user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, trusted_user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (trusted_user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Debts table
-- Stores all debt records
CREATE TABLE IF NOT EXISTS debts (
    debt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creditor_id INTEGER NOT NULL,
    debtor_id INTEGER NOT NULL,
    amount INTEGER NOT NULL, -- Amount in cents
    description TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending', 'active', 'paid', 'rejected')) DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    confirmed_at DATETIME,
    settled_at DATETIME,
    FOREIGN KEY (creditor_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (debtor_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Trigger to update debt's updated_at timestamp
CREATE TRIGGER IF NOT EXISTS trigger_debts_updated_at
AFTER UPDATE ON debts
FOR EACH ROW
BEGIN
    UPDATE debts SET updated_at = CURRENT_TIMESTAMP WHERE debt_id = old.debt_id;
END;

-- Payments table
-- Stores history of all payments made to settle debts
CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    debt_id INTEGER NOT NULL,
    amount INTEGER NOT NULL, -- Amount in cents
    status TEXT NOT NULL CHECK(status IN ('pending_confirmation', 'confirmed')) DEFAULT 'pending_confirmation',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    confirmed_at DATETIME,
    FOREIGN KEY (debt_id) REFERENCES debts(debt_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_debts_creditor ON debts(creditor_id);
CREATE INDEX IF NOT EXISTS idx_debts_debtor ON debts(debtor_id);
CREATE INDEX IF NOT EXISTS idx_debts_status ON debts(status);
CREATE INDEX IF NOT EXISTS idx_payments_debt_id ON payments(debt_id);

-- View for net balance between users
-- Calculates the net amount owed between any two users
CREATE VIEW IF NOT EXISTS net_balances AS
SELECT
    creditor_id,
    debtor_id,
    SUM(amount) as total_debt
FROM debts
WHERE status = 'active'
GROUP BY creditor_id, debtor_id; 