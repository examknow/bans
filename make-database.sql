PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE channels (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    autojoin BOOLEAN NOT NULL
);
CREATE TABLE bans (
    id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    setter TEXT NOT NULL,
    mode VARCHAR(1),
    ts INTEGER NOT NULL,
    mask TEXT,
    expiry_ts INTEGER,
    remove_ts INTEGER,
    remover   TEXT,
    reason    TEXT,
    FOREIGN KEY (channel_id)
        REFERENCES channels(id)
        ON DELETE CASCADE
);
CREATE TABLE chanops (
    id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    account TEXT NOT NULL,
    FOREIGN KEY (channel_id)
        REFERENCES channels(id)
        ON DELETE CASCADE
);
CREATE TABLE comments (
    ban_id INTEGER NOT NULL,
    by_mask TEXT NOT NULL,
    by_account TEXT,
    time INTEGER NOT NULL,
    comment TEXT NOT NULL,
    FOREIGN KEY (ban_id)
        REFERENCES bans(id)
        ON DELETE CASCADE
);
CREATE TABLE bot_config (
    key TEXT,
    value TEXT,
    PRIMARY KEY (key)
);
CREATE TABLE channel_config (
    channel_id INTEGER NOT NULL,
    key TEXT,
    value TEXT,
    PRIMARY KEY (channel_id, key),
    FOREIGN KEY (channel_id)
        REFERENCES channels(id)
        ON DELETE CASCADE
);
COMMIT;
