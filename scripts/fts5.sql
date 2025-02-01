CREATE VIRTUAL TABLE papers_summary_fts
  USING fts5(summary, tokenize = 'porter', content='papers', content_rowid='id');

CREATE TRIGGER papers_ai AFTER INSERT ON papers BEGIN
  INSERT INTO papers_summary_fts(rowid, summary)
  VALUES (new.id, new.summary);
END;

CREATE TRIGGER papers_au AFTER UPDATE ON papers BEGIN
  UPDATE papers_summary_fts
  SET summary = new.summary
  WHERE rowid = new.id;
END;

CREATE TRIGGER papers_ad AFTER DELETE ON papers BEGIN
  DELETE FROM papers_summary_fts WHERE rowid = old.id;
END;

INSERT INTO papers_summary_fts(papers_summary_fts)
  VALUES('rebuild');
