-- =====================================================================
-- paint-crosschecker Supabase 스키마
-- Supabase 대시보드 > SQL Editor 에서 전체 실행
-- =====================================================================

-- 1. 근무메모 (schedule_notes)
CREATE TABLE IF NOT EXISTS schedule_notes (
    id        BIGSERIAL PRIMARY KEY,
    name      TEXT NOT NULL,
    note_date DATE NOT NULL,
    note      TEXT DEFAULT '',
    UNIQUE (name, note_date)
);

-- 2. 휴가등록 (leaves)
CREATE TABLE IF NOT EXISTS leaves (
    id         BIGSERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    type       TEXT,
    start_date DATE NOT NULL,
    end_date   DATE NOT NULL,
    sub        TEXT DEFAULT ''
);

-- 3. 일지상세 (daily_detail)
CREATE TABLE IF NOT EXISTS daily_detail (
    date DATE PRIMARY KEY,
    data JSONB
);

-- 4. 업무현황 (work_items)
CREATE TABLE IF NOT EXISTS work_items (
    id          BIGSERIAL PRIMARY KEY,
    date        DATE NOT NULL,
    name        TEXT NOT NULL,
    s1          INT DEFAULT 0,
    s2          INT DEFAULT 0,
    s3          INT DEFAULT 0,
    day_work    INT DEFAULT 0,
    night       INT DEFAULT 0,
    total       INT DEFAULT 0,
    month_total INT DEFAULT 0,
    UNIQUE (date, name)
);

-- 5. 재고현황 (inventory)
CREATE TABLE IF NOT EXISTS inventory (
    lot           TEXT PRIMARY KEY,
    product       TEXT DEFAULT '',
    maker         TEXT DEFAULT '',
    sector        TEXT DEFAULT '',
    registered_at TEXT DEFAULT '',
    updated_at    TEXT DEFAULT '',
    return_status TEXT DEFAULT '',
    scan_disabled TEXT DEFAULT ''
);

-- 6. 재고이력 (inventory_history)
CREATE TABLE IF NOT EXISTS inventory_history (
    id          BIGSERIAL PRIMARY KEY,
    lot         TEXT,
    product     TEXT DEFAULT '',
    maker       TEXT DEFAULT '',
    prev_sector TEXT DEFAULT '',
    new_sector  TEXT DEFAULT '',
    recorded_at TEXT DEFAULT ''
);

-- 인덱스 (조회 성능)
CREATE INDEX IF NOT EXISTS idx_schedule_notes_name_date ON schedule_notes (name, note_date);
CREATE INDEX IF NOT EXISTS idx_leaves_name             ON leaves (name);
CREATE INDEX IF NOT EXISTS idx_work_items_date         ON work_items (date);
CREATE INDEX IF NOT EXISTS idx_inventory_sector        ON inventory (sector);
CREATE INDEX IF NOT EXISTS idx_inventory_history_lot   ON inventory_history (lot);
