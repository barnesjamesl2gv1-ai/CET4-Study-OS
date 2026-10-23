-- CET-4 Study OS V1.0: 关系型数据模型草案，不代替正式Alembic迁移。
-- SQLite 3；所有时间戳使用ISO8601 UTC存储，UI按用户本机时区显示。
-- 说明：重要字段的枚举、跨表一致性、唯一题号等仍需在业务层与迁移中验证。
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2100),
    session_month INTEGER NOT NULL CHECK (session_month IN (6,12)),
    set_number INTEGER NOT NULL CHECK (set_number >= 1),
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','practice_ready','mock_ready','blocked')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(year, session_month, set_number)
);

CREATE TABLE IF NOT EXISTS import_batches (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE RESTRICT,
    state TEXT NOT NULL CHECK(state IN ('pending','parsing','review','complete','failed')),
    created_at TEXT NOT NULL,
    finished_at TEXT,
    report_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS source_assets (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE RESTRICT,
    import_batch_id TEXT REFERENCES import_batches(id) ON DELETE SET NULL,
    role TEXT NOT NULL CHECK(role IN ('paper','audio','answer')),
    original_filename TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK(length(sha256)=64),
    file_format TEXT NOT NULL,
    byte_size INTEGER NOT NULL CHECK(byte_size > 0),
    duration_ms INTEGER CHECK(duration_ms >= 0),
    verification_status TEXT NOT NULL DEFAULT 'pending' CHECK(verification_status IN ('pending','verified','invalid')),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_assets_paper_role ON source_assets(paper_id, role);

CREATE TABLE IF NOT EXISTS import_issues (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES import_batches(id) ON DELETE RESTRICT,
    asset_id TEXT REFERENCES source_assets(id) ON DELETE SET NULL,
    question_id TEXT,
    issue_code TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('warning','blocking')),
    details TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS passages (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE RESTRICT,
    kind TEXT NOT NULL,
    label TEXT,
    body_text TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL DEFAULT 'pending' CHECK(verification_status IN ('pending','verified','invalid'))
);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE RESTRICT,
    passage_id TEXT REFERENCES passages(id) ON DELETE RESTRICT,
    ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 1 AND 100),
    question_kind TEXT NOT NULL CHECK(question_kind IN
      ('listening_news','listening_dialogue','listening_passage','cloze','matching','careful','writing','translation')),
    lifecycle TEXT NOT NULL DEFAULT 'disabled' CHECK(lifecycle IN ('disabled','ready','retired')),
    created_at TEXT NOT NULL,
    UNIQUE(paper_id, ordinal)
);
CREATE INDEX IF NOT EXISTS ix_questions_paper_kind ON questions(paper_id, question_kind);

CREATE TABLE IF NOT EXISTS question_versions (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
    version_no INTEGER NOT NULL CHECK(version_no >= 1),
    prompt_text TEXT NOT NULL DEFAULT '',
    options_json TEXT NOT NULL DEFAULT '[]',
    correct_answer_json TEXT,
    rationale_text TEXT NOT NULL DEFAULT '',
    source_batch_id TEXT REFERENCES import_batches(id) ON DELETE SET NULL,
    verification_status TEXT NOT NULL DEFAULT 'pending' CHECK(verification_status IN ('pending','verified','invalid')),
    created_at TEXT NOT NULL,
    UNIQUE(question_id,version_no)
);

CREATE TABLE IF NOT EXISTS audio_segments (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES source_assets(id) ON DELETE RESTRICT,
    start_ms INTEGER NOT NULL CHECK(start_ms>=0),
    end_ms INTEGER NOT NULL,
    confirmation TEXT NOT NULL DEFAULT 'pending' CHECK(confirmation IN ('pending','confirmed','rejected')),
    CHECK(end_ms>start_ms)
);
CREATE TABLE IF NOT EXISTS question_audio_segments (
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    segment_id TEXT NOT NULL REFERENCES audio_segments(id) ON DELETE CASCADE,
    PRIMARY KEY(question_id,segment_id)
);

CREATE TABLE IF NOT EXISTS question_mapping_review (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE RESTRICT,
    previous_question_id TEXT REFERENCES questions(id) ON DELETE RESTRICT,
    proposed_question_id TEXT REFERENCES questions(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK(decision IN ('pending','approved','rejected')),
    decided_at TEXT
);

CREATE TABLE IF NOT EXISTS practice_sessions (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE RESTRICT,
    section TEXT NOT NULL,
    last_question_id TEXT REFERENCES questions(id) ON DELETE SET NULL,
    state TEXT NOT NULL DEFAULT 'in_progress' CHECK(state IN ('in_progress','closed')),
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS practice_answers (
    practice_session_id TEXT NOT NULL REFERENCES practice_sessions(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
    question_version_id TEXT NOT NULL REFERENCES question_versions(id) ON DELETE RESTRICT,
    selected_answer_json TEXT,
    saved_at TEXT NOT NULL,
    PRIMARY KEY(practice_session_id,question_id)
);
CREATE TABLE IF NOT EXISTS practice_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    practice_session_id TEXT NOT NULL REFERENCES practice_sessions(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    question_id TEXT REFERENCES questions(id) ON DELETE SET NULL,
    occurred_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mock_attempts (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE RESTRICT,
    state TEXT NOT NULL CHECK(state IN ('preflight','running','completed','interrupted')),
    started_at TEXT NOT NULL,
    deadline_at TEXT NOT NULL,
    locked_stage INTEGER NOT NULL DEFAULT 0 CHECK(locked_stage BETWEEN 0 AND 5),
    last_heartbeat_at TEXT,
    ended_at TEXT,
    interrupted_reason TEXT
);
CREATE TABLE IF NOT EXISTS mock_answers (
    attempt_id TEXT NOT NULL REFERENCES mock_attempts(id) ON DELETE RESTRICT,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
    question_version_id TEXT NOT NULL REFERENCES question_versions(id) ON DELETE RESTRICT,
    selected_answer_json TEXT,
    is_correct INTEGER CHECK(is_correct IN (0,1)),
    saved_at TEXT NOT NULL,
    PRIMARY KEY(attempt_id,question_id)
);
CREATE TABLE IF NOT EXISTS mock_score_snapshots (
    id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES mock_attempts(id) ON DELETE RESTRICT,
    version_no INTEGER NOT NULL,
    score_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('valid','under_review','superseded')),
    reason TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(attempt_id,version_no)
);

CREATE TABLE IF NOT EXISTS wrongbook_items (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL UNIQUE REFERENCES questions(id) ON DELETE RESTRICT,
    first_added_at TEXT NOT NULL,
    last_added_at TEXT NOT NULL,
    sources_json TEXT NOT NULL DEFAULT '[]',
    consecutive_correct_days INTEGER NOT NULL DEFAULT 0 CHECK(consecutive_correct_days BETWEEN 0 AND 3),
    mastered INTEGER NOT NULL DEFAULT 0 CHECK(mastered IN (0,1)),
    last_review_day TEXT
);
CREATE TABLE IF NOT EXISTS review_daily_sets (
    id TEXT PRIMARY KEY,
    review_day TEXT NOT NULL UNIQUE,
    generated_at TEXT NOT NULL,
    selection_algorithm_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review_daily_questions (
    set_id TEXT NOT NULL REFERENCES review_daily_sets(id) ON DELETE RESTRICT,
    wrongbook_id TEXT NOT NULL REFERENCES wrongbook_items(id) ON DELETE RESTRICT,
    ordinal INTEGER NOT NULL,
    first_answer_json TEXT,
    is_correct INTEGER CHECK(is_correct IN (0,1)),
    answered_at TEXT,
    PRIMARY KEY(set_id,wrongbook_id),
    UNIQUE(set_id,ordinal)
);

CREATE TABLE IF NOT EXISTS backup_records (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    backup_kind TEXT NOT NULL CHECK(backup_kind IN ('daily','manual','pre_upgrade','pre_restore')),
    relative_path TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL CHECK(length(manifest_sha256)=64),
    verified INTEGER NOT NULL DEFAULT 0 CHECK(verified IN (0,1))
);

CREATE INDEX IF NOT EXISTS ix_mock_paper_time ON mock_attempts(paper_id,started_at);
CREATE INDEX IF NOT EXISTS ix_mock_completed ON mock_attempts(state,ended_at);
CREATE INDEX IF NOT EXISTS ix_review_mastered ON wrongbook_items(mastered,last_review_day);

-- 事务/约束测试还应覆盖：
-- 1) 无跨套试卷的题目-音频或题目-答题引用；
-- 2) 每套试卷应有正确的55道客观题，且作文/翻译存在；
-- 3) 只有completed模考可生成valid分数；interrupted不能参与趋势；
-- 4) 题库更新后旧版本和旧答题快照保留；
-- 5) 同一单词不得在同一选词填空任务内重复占用；
-- 6) 跨日连续3次正确才可mastered；答案第一次提交不可覆盖结果。
