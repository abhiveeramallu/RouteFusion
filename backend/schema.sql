CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'rider',
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);

CREATE TABLE IF NOT EXISTS drivers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
    display_name VARCHAR(255) NOT NULL,
    vehicle_type VARCHAR(100) NOT NULL DEFAULT 'Hybrid Cab',
    status VARCHAR(50) NOT NULL DEFAULT 'available',
    current_lat DOUBLE PRECISION NOT NULL,
    current_lng DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_drivers_status ON drivers(status);
CREATE INDEX IF NOT EXISTS ix_drivers_created_at ON drivers(created_at);
CREATE INDEX IF NOT EXISTS ix_drivers_current_location ON drivers(current_lat, current_lng);

CREATE TABLE IF NOT EXISTS rides (
    id SERIAL PRIMARY KEY,
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    pickup_name VARCHAR(255) NOT NULL,
    drop_name VARCHAR(255) NOT NULL,
    pickup_lat DOUBLE PRECISION NOT NULL,
    pickup_lng DOUBLE PRECISION NOT NULL,
    drop_lat DOUBLE PRECISION NOT NULL,
    drop_lng DOUBLE PRECISION NOT NULL,
    passenger_count INTEGER NOT NULL,
    ride_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_rides_created_by_user_id ON rides(created_by_user_id);
CREATE INDEX IF NOT EXISTS ix_rides_status ON rides(status);
CREATE INDEX IF NOT EXISTS ix_rides_created_at ON rides(created_at);

CREATE TABLE IF NOT EXISTS parcels (
    id SERIAL PRIMARY KEY,
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    pickup_name VARCHAR(255) NOT NULL,
    drop_name VARCHAR(255) NOT NULL,
    pickup_lat DOUBLE PRECISION NOT NULL,
    pickup_lng DOUBLE PRECISION NOT NULL,
    drop_lat DOUBLE PRECISION NOT NULL,
    drop_lng DOUBLE PRECISION NOT NULL,
    parcel_weight DOUBLE PRECISION NOT NULL,
    parcel_type VARCHAR(100) NOT NULL,
    priority VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_parcels_created_by_user_id ON parcels(created_by_user_id);
CREATE INDEX IF NOT EXISTS ix_parcels_status ON parcels(status);
CREATE INDEX IF NOT EXISTS ix_parcels_created_at ON parcels(created_at);

CREATE TABLE IF NOT EXISTS route_decisions (
    id SERIAL PRIMARY KEY,
    driver_id INTEGER REFERENCES drivers(id) ON DELETE CASCADE,
    ride_id INTEGER REFERENCES rides(id) ON DELETE CASCADE,
    parcel_id INTEGER REFERENCES parcels(id) ON DELETE CASCADE,
    efficiency_score DOUBLE PRECISION NOT NULL,
    extra_distance DOUBLE PRECISION NOT NULL,
    extra_time DOUBLE PRECISION NOT NULL,
    overlap_distance DOUBLE PRECISION NOT NULL,
    recommendation VARCHAR(50) NOT NULL,
    accepted BOOLEAN,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_route_decisions_accepted ON route_decisions(accepted);
CREATE INDEX IF NOT EXISTS ix_route_decisions_created_at ON route_decisions(created_at);
CREATE INDEX IF NOT EXISTS ix_route_decisions_trip_pair_created_at
    ON route_decisions(ride_id, parcel_id, created_at);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    jti VARCHAR(64) NOT NULL UNIQUE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_expires_at ON refresh_tokens(expires_at);
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_created_at ON refresh_tokens(created_at);

CREATE TABLE IF NOT EXISTS token_blacklist (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    jti VARCHAR(64) NOT NULL UNIQUE,
    token_type VARCHAR(20) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_token_blacklist_jti ON token_blacklist(jti);
CREATE INDEX IF NOT EXISTS ix_token_blacklist_token_type ON token_blacklist(token_type);
CREATE INDEX IF NOT EXISTS ix_token_blacklist_expires_at ON token_blacklist(expires_at);
CREATE INDEX IF NOT EXISTS ix_token_blacklist_created_at ON token_blacklist(created_at);
