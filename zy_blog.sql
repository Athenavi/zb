CREATE TABLE IF NOT EXISTS articles
(
    ArticleID   INT AUTO_INCREMENT PRIMARY KEY,
    Title       VARCHAR(255)                                           NOT NULL COMMENT '文章标题',
    Author      VARCHAR(100)                                           NOT NULL COMMENT '作者名称',
    Hidden      TINYINT(1)                             DEFAULT 0       NOT NULL COMMENT '是否隐藏 1 隐藏 0 不隐藏',
    Views       INT UNSIGNED                           DEFAULT '0'     NULL,
    Likes       INT UNSIGNED                           DEFAULT '0'     NULL,
    Comments    INT UNSIGNED                           DEFAULT '0'     NULL,
    Status      ENUM ('Draft', 'Published', 'Deleted') DEFAULT 'Draft' NULL COMMENT '文章状态: 草稿/已发布/已删除',
    CoverImage  VARCHAR(255)                                           NULL COMMENT '封面图片路径',
    ArticleType VARCHAR(50)                                            NULL COMMENT '文章类型',
    excerpt     TEXT                                                   NULL COMMENT '文章摘要',
    is_featured TINYINT(1)                             DEFAULT 0       NULL COMMENT '是否为推荐文章',
    tags        VARCHAR(255)                                           NOT NULL
) ENGINE = InnoDB;

CREATE INDEX idx_views ON articles (Views);

CREATE TABLE IF NOT EXISTS events
(
    id          INT AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(255)                        NOT NULL COMMENT '事件标题',
    description TEXT                                NOT NULL COMMENT '事件描述',
    event_date  DATETIME                            NOT NULL COMMENT '事件日期',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间'
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS file_hashes
(
    id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    hash       VARCHAR(64)                         NOT NULL,
    filename   VARCHAR(255)                        NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NULL,
    UNIQUE (hash)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS permissions
(
    id          INT AUTO_INCREMENT PRIMARY KEY,
    code        VARCHAR(50)  NOT NULL COMMENT '权限代码（如 manage_users）',
    description VARCHAR(255) NOT NULL COMMENT '权限描述',
    UNIQUE (code)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS roles
(
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(50)  NOT NULL COMMENT '角色名称',
    description VARCHAR(255) NOT NULL COMMENT '角色描述',
    UNIQUE (name)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS urls
(
    id         INT AUTO_INCREMENT PRIMARY KEY,
    long_url   VARCHAR(255)                        NOT NULL COMMENT '长链接',
    short_url  VARCHAR(10)                         NOT NULL COMMENT '短链接',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    username   VARCHAR(255)                        NOT NULL COMMENT '创建者用户名',
    UNIQUE (short_url)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS users
(
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(255)                           NOT NULL COMMENT '用户名',
    password        VARCHAR(255)                           NOT NULL COMMENT '用户密码',
    email           VARCHAR(255) DEFAULT 'guest@7trees.cn' NOT NULL COMMENT '用户邮箱',
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP,
    profile_picture VARCHAR(255)                           NULL COMMENT '用户头像',
    bio             TEXT                                   NULL COMMENT '用户个人简介',
    register_ip     VARCHAR(45)                            NOT NULL COMMENT '注册时IP',
    UNIQUE (username),
    UNIQUE (email)
) ENGINE = InnoDB;

-- 创建依赖上述表的表
CREATE TABLE IF NOT EXISTS article_pass
(
    aid  INT        NOT NULL PRIMARY KEY,
    pass VARCHAR(4) NULL,
    FOREIGN KEY (aid) REFERENCES articles (ArticleID)
        ON DELETE CASCADE -- 添加级联删除
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS role_permissions
(
    role_id       INT NOT NULL,
    permission_id INT NOT NULL,
    PRIMARY KEY (role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES permissions (id) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS comments
(
    id         INT AUTO_INCREMENT PRIMARY KEY,
    article_id INT                                 NOT NULL COMMENT '关联的文章ID',
    user_id    INT                                 NOT NULL COMMENT '评论者用户ID',
    content    TEXT                                NOT NULL COMMENT '评论内容',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '评论时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (article_id) REFERENCES articles (ArticleID) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE INDEX idx_created_at ON comments (created_at);

-- 其他依赖users的表
CREATE TABLE IF NOT EXISTS custom_fields
(
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT          NOT NULL COMMENT '用户ID',
    field_name  VARCHAR(100) NOT NULL COMMENT '自定义字段名称',
    field_value TEXT         NOT NULL COMMENT '自定义字段值',
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS email_subscriptions
(
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT                                  NOT NULL COMMENT '用户ID',
    subscribed TINYINT(1) DEFAULT 1                 NOT NULL COMMENT '是否订阅邮件',
    created_at TIMESTAMP  DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '订阅时间',
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS media
(
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT                                          NOT NULL COMMENT '上传用户ID',
    file_path  VARCHAR(255)                                 NOT NULL COMMENT '文件路径',
    file_type  ENUM ('image', 'video', 'audio', 'document') NOT NULL COMMENT '文件类型',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP          NOT NULL COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP          NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS notifications
(
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT                                  NOT NULL COMMENT '接收者用户ID',
    type       VARCHAR(100)                         NOT NULL COMMENT '通知类型',
    message    TEXT                                 NOT NULL COMMENT '通知内容',
    is_read    TINYINT(1) DEFAULT 0                 NOT NULL COMMENT '是否已阅读',
    created_at TIMESTAMP  DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    updated_at TIMESTAMP  DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS reports
(
    id           INT AUTO_INCREMENT PRIMARY KEY,
    reported_by  INT                                 NOT NULL COMMENT '举报用户ID',
    content_type ENUM ('Article', 'Comment')         NOT NULL COMMENT '内容类型: 文章/评论',
    content_id   INT                                 NOT NULL COMMENT '内容ID',
    reason       TEXT                                NOT NULL COMMENT '举报理由',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '举报时间',
    FOREIGN KEY (reported_by) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS subscriptions
(
    id              INT AUTO_INCREMENT PRIMARY KEY,
    subscriber_id   INT                       NOT NULL COMMENT '订阅者用户ID',
    subscribe_to_id INT                       NOT NULL COMMENT '被订阅对象ID',
    subscribe_type  ENUM ('User', 'Category') NOT NULL COMMENT '订阅类型: 用户/分类',
    FOREIGN KEY (subscriber_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS user_roles
(
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE
) ENGINE = InnoDB;

-- 插入初始数据
INSERT INTO `articles` (`ArticleID`, `Title`, `Author`, `Hidden`, `Views`, `Likes`, `Comments`, `Status`, `CoverImage`,
                        `ArticleType`, `excerpt`, `is_featured`, `tags`)
VALUES (1, 'changelog', 'test', 0, 666, 66, 0, 'Published', NULL, NULL, NULL, 0, '2025');

INSERT INTO `users` (`id`, `username`, `password`, `email`, `created_at`, `updated_at`, `profile_picture`, `bio`,
                     `register_ip`)
VALUES (1, 'test', '$2b$12$kF4nZn6kESHtj0cjNeaoZugUlWXSgXp27iKAXHepyzSwUxrrhVTz2', 'guest@7trees.cn',
        '2024-10-18 13:37:13', '2024-12-12 05:15:16', NULL, NULL, '0');

-- 插入权限和角色数据
INSERT INTO `permissions` (code, description)
VALUES ('manage_users', '管理用户'),
       ('publish_posts', '发布文章'),
       ('edit_posts', '编辑任意文章'),
       ('view_dashboard', '查看管理面板');

INSERT INTO `roles` (name, description)
VALUES ('Admin', '系统管理员'),
       ('Editor', '内容编辑'),
       ('Subscriber', '订阅用户');

-- 分配角色权限
INSERT INTO `role_permissions` (role_id, permission_id)
SELECT r.id, p.id
FROM `roles` r
         JOIN `permissions` p
WHERE r.name = 'Admin';

INSERT INTO `role_permissions` (role_id, permission_id)
SELECT r.id, p.id
FROM `roles` r
         JOIN `permissions` p ON p.code IN ('publish_posts', 'edit_posts', 'view_dashboard')
WHERE r.name = 'Editor';