CREATE DATABASE IF NOT EXISTS skyshelf
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE skyshelf;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_id INT NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    stored_name VARCHAR(255) NOT NULL UNIQUE,
    size BIGINT NOT NULL,
    mime_type VARCHAR(255) NOT NULL,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    share_token VARCHAR(255) UNIQUE,
    uploaded_at DATETIME NOT NULL,
    CONSTRAINT fk_files_owner
        FOREIGN KEY (owner_id) REFERENCES users (id)
        ON DELETE CASCADE
);
