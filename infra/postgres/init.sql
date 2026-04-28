-- OMS Database Schema

CREATE TABLE IF NOT EXISTS instruments (
    symbol          VARCHAR(16) PRIMARY KEY,
    lot_size        NUMERIC(20,8) NOT NULL DEFAULT 1,
    tick_size       NUMERIC(20,8) NOT NULL DEFAULT 0.01,
    min_price       NUMERIC(20,8) NOT NULL DEFAULT 0.01,
    max_price       NUMERIC(20,8) NOT NULL DEFAULT 99999.99,
    max_order_size  NUMERIC(20,8) NOT NULL DEFAULT 10000,
    position_limit  NUMERIC(20,8) NOT NULL DEFAULT 100000
);

CREATE TABLE IF NOT EXISTS orders (
    order_id    VARCHAR(36) PRIMARY KEY,
    cl_ord_id   VARCHAR(64) NOT NULL,
    account     VARCHAR(64) NOT NULL,
    symbol      VARCHAR(16) NOT NULL REFERENCES instruments(symbol),
    side        CHAR(1) NOT NULL,
    ord_type    CHAR(1) NOT NULL,
    quantity    NUMERIC(20,8) NOT NULL,
    price       NUMERIC(20,8),
    status      CHAR(1) NOT NULL DEFAULT 'A',
    session_id  VARCHAR(128),
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_account   ON orders(account);
CREATE INDEX IF NOT EXISTS idx_orders_symbol    ON orders(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_status    ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created   ON orders(created_at DESC);

CREATE TABLE IF NOT EXISTS executions (
    exec_id     VARCHAR(36) PRIMARY KEY,
    order_id    VARCHAR(36) NOT NULL REFERENCES orders(order_id),
    exec_type   CHAR(1) NOT NULL,
    last_qty    NUMERIC(20,8) NOT NULL,
    last_px     NUMERIC(20,8) NOT NULL,
    cum_qty     NUMERIC(20,8) NOT NULL,
    avg_px      NUMERIC(20,8) NOT NULL,
    leaves_qty  NUMERIC(20,8) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_execs_order_id ON executions(order_id);

CREATE TABLE IF NOT EXISTS positions (
    id          VARCHAR(36) PRIMARY KEY,
    account     VARCHAR(64) NOT NULL,
    symbol      VARCHAR(16) NOT NULL,
    net_qty     NUMERIC(20,8) NOT NULL DEFAULT 0,
    avg_cost    NUMERIC(20,8) NOT NULL DEFAULT 0,
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(account, symbol)
);

-- Seed instruments
INSERT INTO instruments (symbol, lot_size, tick_size, min_price, max_price, max_order_size, position_limit) VALUES
    ('AAPL',  1, 0.01, 0.01, 99999.99, 10000, 100000),
    ('MSFT',  1, 0.01, 0.01, 99999.99, 10000, 100000),
    ('GOOG',  1, 0.01, 0.01, 99999.99,  5000,  50000),
    ('TSLA',  1, 0.01, 0.01, 99999.99, 10000, 100000),
    ('AMZN',  1, 0.01, 0.01, 99999.99,  5000,  50000),
    ('NVDA',  1, 0.01, 0.01, 99999.99,  5000,  50000)
ON CONFLICT (symbol) DO NOTHING;
