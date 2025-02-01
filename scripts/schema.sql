DROP TABLE IF EXISTS papers;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS user_saved_papers;

CREATE TABLE papers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  arxiv_id TEXT UNIQUE NOT NULL,
  published DATETIME NOT NULL,
  updated DATETIME NOT NULL,
  summary TEXT NOT NULL,
  author TEXT NOT NULL,
  -- TODO might be better for category to be a separate table that we join here
  -- that way category filters might run a bit faster + we can add/remove categories more easily
  -- rather than hardcode the N categories i already am pulling from arxiv
  category TEXT NOT NULL,
  pdf_link TEXT NOT NULL,
  abstract_link TEXT NOT NULL,
  arxiv_link TEXT NOT NULL
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_saved_papers (
    user_id INTEGER NOT NULL,
    paper_id INTEGER NOT NULL,
    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, paper_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_papers_published ON papers(published DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_saved_papers ON user_saved_papers(user_id, paper_id);
