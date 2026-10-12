-- MiniSocial database schema.
--
-- The tables ship inside database.sqlite; this file documents them and is
-- applied at app startup: db_schema.ensure_schema() checks which of these
-- tables are missing (the app never rewrites an existing table) and runs
-- only the missing CREATEs. Statements are CREATE TABLE IF NOT EXISTS, so
-- the file is safe to apply to any state of the database. The definitions
-- below are copied verbatim from the shipped schema; the nudges table is
-- the one new table (streak-rescue feature).

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT ,
  username varchar(50) NOT NULL,
  location varchar(100) DEFAULT NULL,
  birthdate date DEFAULT NULL,
  created_at timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  profile text, password TEXT);

CREATE TABLE IF NOT EXISTS posts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    content    TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS reactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id       INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    reaction_type TEXT    NOT NULL);

CREATE TABLE IF NOT EXISTS follows (
  follower_id int NOT NULL,
  followed_id int NOT NULL);

CREATE TABLE IF NOT EXISTS nudges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nudger_id INTEGER NOT NULL,
    nudged_id INTEGER NOT NULL,
    day TEXT NOT NULL
);