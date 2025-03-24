-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- 主机： host.docker.internal:3306
-- 生成日期： 2024-12-12 05:18:04
-- 服务器版本： 8.4.2
-- PHP 版本： 8.2.8

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";
SET NAMES utf8mb4;

-- 创建表 `users`
CREATE TABLE `users`
(
    `id`              int          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `username`        varchar(255) NOT NULL COMMENT '用户名' UNIQUE,
    `password`        varchar(255) NOT NULL COMMENT '用户密码',
    `email`           varchar(255) NOT NULL DEFAULT 'guest@7trees.cn' COMMENT '用户邮箱',
    `created_at`      timestamp    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`      timestamp    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `profile_picture` varchar(255)          DEFAULT NULL COMMENT '用户头像',
    `bio`             text COMMENT '用户个人简介',
    `register_ip`     varchar(45)  NOT NULL COMMENT '注册时IP'
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 插入用户数据
INSERT INTO `users` (`id`, `username`, `password`, `email`, `created_at`, `updated_at`, `profile_picture`, `bio`,
                     `register_ip`)
VALUES (1, 'test', '$2b$12$kF4nZn6kESHtj0cjNeaoZugUlWXSgXp27iKAXHepyzSwUxrrhVTz2', 'guest@7trees.cn',
        '2024-10-18 13:37:13', '2024-12-12 05:15:16', NULL, NULL, '0');

-- 创建表 `articles`
CREATE TABLE `articles`
(
    `ArticleID`   int          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `Title`       varchar(255) NOT NULL COMMENT '文章标题',
    `Author`      varchar(100) NOT NULL COMMENT '作者名称',
    `Hidden`      tinyint(1)   NOT NULL                DEFAULT '0' COMMENT '是否隐藏 1 隐藏 0 不隐藏',
    `Views`       INT UNSIGNED                         DEFAULT '0' COMMENT '文章阅读量',
    `Likes`       INT UNSIGNED                         DEFAULT '0' COMMENT '文章点赞数',
    `Comments`    INT UNSIGNED                         DEFAULT '0' COMMENT '评论数',
    `Status`      enum ('Draft','Published','Deleted') DEFAULT 'Draft' COMMENT '文章状态',
    `CoverImage`  varchar(255)                         DEFAULT NULL COMMENT '封面图片路径',
    `ArticleType` varchar(50)                          DEFAULT NULL COMMENT '文章类型',
    `excerpt`     text COMMENT '文章摘要',
    `is_featured` tinyint(1)                           DEFAULT '0' COMMENT '是否为推荐文章',
    `tags`        varchar(255) NOT NULL
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 插入文章数据
INSERT INTO `articles` (`ArticleID`, `Title`, `Author`, `Hidden`, `Views`, `Likes`, `Comments`, `Status`, `CoverImage`,
                        `ArticleType`, `excerpt`, `is_featured`, `tags`)
VALUES (1, 'changelog', 'test', 0, 666, 66, 0, 'Published', NULL, NULL, NULL, 0, '2025');

-- 创建表 `comments`
CREATE TABLE `comments`
(
    `id`         int       NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `article_id` int       NOT NULL COMMENT '关联的文章ID',
    `user_id`    int       NOT NULL COMMENT '评论者用户ID',
    `content`    text      NOT NULL COMMENT '评论内容',
    `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '评论时间',
    `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (`article_id`) REFERENCES `articles` (`ArticleID`),
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 创建表 `custom_fields`
CREATE TABLE `custom_fields`
(
    `id`          int          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `user_id`     int          NOT NULL COMMENT '用户ID',
    `field_name`  varchar(100) NOT NULL COMMENT '自定义字段名称',
    `field_value` text         NOT NULL COMMENT '自定义字段值',
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 创建表 `email_subscriptions`
CREATE TABLE `email_subscriptions`
(
    `id`         int        NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `user_id`    int        NOT NULL COMMENT '用户ID',
    `subscribed` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否订阅邮件',
    `created_at` timestamp  NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '订阅时间',
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 创建表 `events`
CREATE TABLE `events`
(
    `id`          int          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `title`       varchar(255) NOT NULL COMMENT '事件标题',
    `description` text         NOT NULL COMMENT '事件描述',
    `event_date`  datetime     NOT NULL COMMENT '事件日期',
    `created_at`  timestamp    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 创建表 `media`
CREATE TABLE `media`
(
    `id`         int                                       NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `user_id`    int                                       NOT NULL COMMENT '上传用户ID',
    `file_path`  varchar(255)                              NOT NULL COMMENT '文件路径',
    `file_type`  enum ('image','video','audio','document') NOT NULL COMMENT '文件类型',
    `created_at` timestamp                                 NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` timestamp                                 NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 创建表 `notifications`
CREATE TABLE `notifications`
(
    `id`         int          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `user_id`    int          NOT NULL COMMENT '接收者用户ID',
    `type`       varchar(100) NOT NULL COMMENT '通知类型',
    `message`    text         NOT NULL COMMENT '通知内容',
    `is_read`    tinyint(1)   NOT NULL DEFAULT '0' COMMENT '是否已阅读',
    `created_at` timestamp    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` timestamp    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 创建表 `reports`
CREATE TABLE `reports`
(
    `id`           int                        NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `reported_by`  int                        NOT NULL COMMENT '举报用户ID',
    `content_type` enum ('Article','Comment') NOT NULL COMMENT '内容类型: 文章/评论',
    `content_id`   int                        NOT NULL COMMENT '内容ID',
    `reason`       text                       NOT NULL COMMENT '举报理由',
    `created_at`   timestamp                  NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '举报时间',
    FOREIGN KEY (`reported_by`) REFERENCES `users` (`id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 创建表 `subscriptions`
CREATE TABLE `subscriptions`
(
    `id`              int                      NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `subscriber_id`   int                      NOT NULL COMMENT '订阅者用户ID',
    `subscribe_to_id` int                      NOT NULL COMMENT '被订阅对象ID',
    `subscribe_type`  enum ('User','Category') NOT NULL COMMENT '订阅类型: 用户/分类',
    FOREIGN KEY (`subscriber_id`) REFERENCES `users` (`id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 创建表 `urls`
CREATE TABLE `urls`
(
    `id`         int          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `long_url`   varchar(255) NOT NULL COMMENT '长链接',
    `short_url`  varchar(10)  NOT NULL COMMENT '短链接',
    `created_at` timestamp    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `username`   varchar(255) NOT NULL COMMENT '创建者用户名',
    UNIQUE KEY `short_url` (`short_url`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 创建表 `article_pass`
CREATE TABLE `article_pass`
(
    `aid`  int NOT NULL PRIMARY KEY,
    `pass` varchar(4) DEFAULT NULL,
    FOREIGN KEY (`aid`) REFERENCES `articles` (`ArticleID`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 创建表 `activities`
CREATE TABLE `activities`
(
    `activityId`      int AUTO_INCREMENT PRIMARY KEY,
    `title`           varchar(255)         NOT NULL COMMENT '活动标题',
    `cover_img`       varchar(255)         NOT NULL COMMENT '封面图URL',
    `start_time`      bigint               NOT NULL COMMENT '开始时间（毫秒时间戳）',
    `end_time`        bigint               NOT NULL COMMENT '结束时间（毫秒时间戳）',
    `list_address`    varchar(255)         NOT NULL COMMENT '列表展示地址',
    `detail_location` varchar(255)         NOT NULL COMMENT '详情页地点',
    `display_time`    bigint               NULL COMMENT '前端展示时间（时间戳，毫秒单位）',
    `content`         text                 NOT NULL COMMENT '活动详情正文',
    `is_deleted`      tinyint(1) DEFAULT 0 NOT NULL COMMENT '软删除标记，0 为未删除，1 为已删除',
    CHECK (`end_time` >= `start_time`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 创建表 `permissions`
CREATE TABLE `permissions`
(
    `id`          INT AUTO_INCREMENT PRIMARY KEY,
    `code`        VARCHAR(50)  NOT NULL COMMENT '权限代码（如 manage_users）',
    `description` VARCHAR(255) NOT NULL COMMENT '权限描述',
    UNIQUE KEY (`code`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 创建表 `roles`
CREATE TABLE `roles`
(
    `id`          INT AUTO_INCREMENT PRIMARY KEY,
    `name`        VARCHAR(50)  NOT NULL COMMENT '角色名称',
    `description` VARCHAR(255) NOT NULL COMMENT '角色描述',
    UNIQUE KEY (`name`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 创建表 `role_permissions`
CREATE TABLE `role_permissions`
(
    `role_id`       INT NOT NULL,
    `permission_id` INT NOT NULL,
    PRIMARY KEY (`role_id`, `permission_id`),
    FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`),
    FOREIGN KEY (`permission_id`) REFERENCES `permissions` (`id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 创建表 `user_roles`
CREATE TABLE `user_roles`
(
    `user_id` INT NOT NULL,
    `role_id` INT NOT NULL,
    PRIMARY KEY (`user_id`, `role_id`),
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
    FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

-- 插入权限
INSERT INTO `permissions` (code, description)
VALUES ('manage_users', '管理用户'),
       ('publish_posts', '发布文章'),
       ('edit_posts', '编辑任意文章'),
       ('view_dashboard', '查看管理面板');

-- 插入角色
INSERT INTO `roles` (name, description)
VALUES ('Admin', '系统管理员'),
       ('Editor', '内容编辑'),
       ('Subscriber', '订阅用户');

-- 为角色分配权限（示例：Admin拥有所有权限）
INSERT INTO `role_permissions` (role_id, permission_id)
SELECT r.id, p.id
FROM `roles` r,
     `permissions` p
WHERE r.name = 'Admin';

-- 为Editor分配部分权限
INSERT INTO `role_permissions` (role_id, permission_id)
SELECT r.id, p.id
FROM `roles` r
         JOIN `permissions` p ON p.code IN ('publish_posts', 'edit_posts', 'view_dashboard')
WHERE r.name = 'Editor';

COMMIT;
