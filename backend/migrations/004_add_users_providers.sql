-- Introduces multi-user support and investment provider tracking.
-- Safe to re-run — uses CREATE TABLE IF NOT EXISTS and ADD COLUMN IF NOT EXISTS.

-- Users: tracks who owns each account; role governs what they can do.
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    username        TEXT NOT NULL UNIQUE,
    hashed_password TEXT,                          -- NULL until auth is implemented (Phase 11 Block 3)
    role            TEXT NOT NULL DEFAULT 'owner', -- owner | viewer | demo
    display_name    TEXT
);

-- Providers: the investment platform where an account is held.
-- Enables future support for non-HL accounts (Vanguard, Trading 212, etc.).
CREATE TABLE IF NOT EXISTS providers (
    id    TEXT PRIMARY KEY,   -- e.g. 'HL', 'VANGUARD', 'TRADING212'
    name  TEXT NOT NULL
);

-- Extend accounts: each account now belongs to a user and a provider,
-- and carries an explicit account_type for the regulatory product category
-- (ISA, SIPP, GIA, etc.) separate from the account's unique identifier.
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS user_id      TEXT DEFAULT 'owner';
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS provider_id  TEXT DEFAULT 'HL';
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS account_type TEXT;

-- Back-fill account_type for any rows that existed before this migration.
-- For the original HL accounts the id and account_type happen to be the same.
UPDATE accounts SET account_type = id WHERE account_type IS NULL;
