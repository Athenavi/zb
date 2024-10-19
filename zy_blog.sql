-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- 主机： host.docker.internal:3306
-- 生成日期： 2024-10-19 02:52:02
-- 服务器版本： 8.4.2
-- PHP 版本： 8.2.8

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- 数据库： `zb`
--

-- --------------------------------------------------------

--
-- 表的结构 `articles`
--

CREATE TABLE `articles` (
  `ArticleID` int NOT NULL,
  `Title` varchar(255) NOT NULL COMMENT '文章标题',
  `Author` varchar(100) NOT NULL COMMENT '作者名称',
  `Hidden` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否隐藏 1 隐藏 0 不隐藏',
  `Views` smallint DEFAULT '0' COMMENT '文章阅读量',
  `Likes` smallint DEFAULT '0' COMMENT '文章点赞数',
  `Comments` smallint DEFAULT '0' COMMENT '评论数',
  `Status` enum('Draft','Published','Deleted') DEFAULT 'Draft' COMMENT '文章状态: 草稿/已发布/已删除',
  `CoverImage` varchar(255) DEFAULT NULL COMMENT '封面图片路径',
  `ArticleType` varchar(50) DEFAULT NULL COMMENT '文章类型',
  `excerpt` text COMMENT '文章摘要',
  `is_featured` tinyint(1) DEFAULT '0' COMMENT '是否为推荐文章',
  `tags` varchar(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- 转存表中的数据 `articles`
--

INSERT INTO `articles` (`ArticleID`, `Title`, `Author`, `Hidden`, `Views`, `Likes`, `Comments`, `Status`, `CoverImage`, `ArticleType`, `excerpt`, `is_featured`, `tags`) VALUES
(1, 'README', 'test', 0, 0, 0, 0, 'Draft', NULL, NULL, NULL, 0, '2024');

-- --------------------------------------------------------

--
-- 表的结构 `article_pass`
--

CREATE TABLE `article_pass` (
  `aid` int NOT NULL,
  `pass` varchar(4) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- 表的结构 `comments`
--

CREATE TABLE `comments` (
  `id` int NOT NULL,
  `article_id` int NOT NULL COMMENT '关联的文章ID',
  `user_id` int NOT NULL COMMENT '评论者用户ID',
  `content` text NOT NULL COMMENT '评论内容',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '评论时间',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- 表的结构 `custom_fields`
--

CREATE TABLE `custom_fields` (
  `id` int NOT NULL,
  `user_id` int NOT NULL COMMENT '用户ID',
  `field_name` varchar(100) NOT NULL COMMENT '自定义字段名称',
  `field_value` text NOT NULL COMMENT '自定义字段值'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- 表的结构 `email_subscriptions`
--

CREATE TABLE `email_subscriptions` (
  `id` int NOT NULL,
  `user_id` int NOT NULL COMMENT '用户ID',
  `subscribed` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否订阅邮件',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '订阅时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- 表的结构 `events`
--

CREATE TABLE `events` (
  `id` int NOT NULL,
  `title` varchar(255) NOT NULL COMMENT '事件标题',
  `description` text NOT NULL COMMENT '事件描述',
  `event_date` datetime NOT NULL COMMENT '事件日期',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- 表的结构 `media`
--

CREATE TABLE `media` (
  `id` int NOT NULL,
  `user_id` int NOT NULL COMMENT '上传用户ID',
  `file_path` varchar(255) NOT NULL COMMENT '文件路径',
  `file_type` enum('image','video','audio','document') NOT NULL COMMENT '文件类型',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- 表的结构 `notifications`
--

CREATE TABLE `notifications` (
  `id` int NOT NULL,
  `user_id` int NOT NULL COMMENT '接收者用户ID',
  `type` varchar(100) NOT NULL COMMENT '通知类型',
  `message` text NOT NULL COMMENT '通知内容',
  `is_read` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否已阅读',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- 表的结构 `reports`
--

CREATE TABLE `reports` (
  `id` int NOT NULL,
  `reported_by` int NOT NULL COMMENT '举报用户ID',
  `content_type` enum('Article','Comment') NOT NULL COMMENT '内容类型: 文章/评论',
  `content_id` int NOT NULL COMMENT '内容ID',
  `reason` text NOT NULL COMMENT '举报理由',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '举报时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- 表的结构 `subscriptions`
--

CREATE TABLE `subscriptions` (
  `id` int NOT NULL,
  `subscriber_id` int NOT NULL COMMENT '订阅者用户ID',
  `subscribe_to_id` int NOT NULL COMMENT '被订阅对象ID',
  `subscribe_type` enum('User','Category') NOT NULL COMMENT '订阅类型: 用户/分类'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- 表的结构 `urls`
--

CREATE TABLE `urls` (
  `id` int NOT NULL,
  `long_url` varchar(255) NOT NULL COMMENT '长链接',
  `short_url` varchar(10) NOT NULL COMMENT '短链接',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `username` varchar(255) NOT NULL COMMENT '创建者用户名'
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb3;

-- --------------------------------------------------------

--
-- 表的结构 `users`
--

CREATE TABLE `users` (
  `id` int NOT NULL,
  `username` varchar(255) NOT NULL COMMENT '用户名',
  `password` varchar(255) NOT NULL COMMENT '用户密码',
  `email` varchar(255) NOT NULL DEFAULT 'guest@7trees.cn' COMMENT '用户邮箱',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `profile_picture` varchar(255) DEFAULT NULL COMMENT '用户头像',
  `bio` text COMMENT '用户个人简介',
  `role` enum('Admin','Editor','Subscriber') DEFAULT 'Subscriber' COMMENT '用户角色: 管理员/编辑/订阅者',
  `register_ip` varchar(45) NOT NULL COMMENT '注册时IP'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- 转存表中的数据 `users`
--

INSERT INTO `users` (`id`, `username`, `password`, `email`, `created_at`, `updated_at`, `profile_picture`, `bio`, `role`, `register_ip`) VALUES
(1, 'test', '$2b$12$ajk/HNbJRcZZf3nSRGklUeYLhwzasmvnpskmtP4pzZ7WlOepWIpYa', 'guest@7trees.cn', '2024-10-18 13:37:13', '2024-10-18 15:16:51', NULL, NULL, 'Admin', '0');

--
-- 转储表的索引
--

--
-- 表的索引 `articles`
--
ALTER TABLE `articles`
  ADD PRIMARY KEY (`ArticleID`),
  ADD KEY `idx_views` (`Views`);

--
-- 表的索引 `article_pass`
--
ALTER TABLE `article_pass`
  ADD KEY `aid` (`aid`);

--
-- 表的索引 `comments`
--
ALTER TABLE `comments`
  ADD PRIMARY KEY (`id`),
  ADD KEY `article_id` (`article_id`),
  ADD KEY `user_id` (`user_id`),
  ADD KEY `idx_created_at` (`created_at`);

--
-- 表的索引 `custom_fields`
--
ALTER TABLE `custom_fields`
  ADD PRIMARY KEY (`id`),
  ADD KEY `custom_fields_ibfk_1` (`user_id`);

--
-- 表的索引 `email_subscriptions`
--
ALTER TABLE `email_subscriptions`
  ADD PRIMARY KEY (`id`),
  ADD KEY `email_subscriptions_ibfk_1` (`user_id`);

--
-- 表的索引 `events`
--
ALTER TABLE `events`
  ADD PRIMARY KEY (`id`);

--
-- 表的索引 `media`
--
ALTER TABLE `media`
  ADD PRIMARY KEY (`id`),
  ADD KEY `user_id` (`user_id`);

--
-- 表的索引 `notifications`
--
ALTER TABLE `notifications`
  ADD PRIMARY KEY (`id`),
  ADD KEY `user_id` (`user_id`);

--
-- 表的索引 `reports`
--
ALTER TABLE `reports`
  ADD PRIMARY KEY (`id`),
  ADD KEY `reports_ibfk_1` (`reported_by`);

--
-- 表的索引 `subscriptions`
--
ALTER TABLE `subscriptions`
  ADD PRIMARY KEY (`id`),
  ADD KEY `subscriptions_ibfk_1` (`subscriber_id`);

--
-- 表的索引 `urls`
--
ALTER TABLE `urls`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `short_url` (`short_url`);

--
-- 表的索引 `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`);

--
-- 在导出的表使用AUTO_INCREMENT
--

--
-- 使用表AUTO_INCREMENT `articles`
--
ALTER TABLE `articles`
  MODIFY `ArticleID` int NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- 使用表AUTO_INCREMENT `comments`
--
ALTER TABLE `comments`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- 使用表AUTO_INCREMENT `custom_fields`
--
ALTER TABLE `custom_fields`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- 使用表AUTO_INCREMENT `email_subscriptions`
--
ALTER TABLE `email_subscriptions`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- 使用表AUTO_INCREMENT `events`
--
ALTER TABLE `events`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- 使用表AUTO_INCREMENT `media`
--
ALTER TABLE `media`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- 使用表AUTO_INCREMENT `notifications`
--
ALTER TABLE `notifications`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- 使用表AUTO_INCREMENT `reports`
--
ALTER TABLE `reports`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- 使用表AUTO_INCREMENT `subscriptions`
--
ALTER TABLE `subscriptions`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- 使用表AUTO_INCREMENT `urls`
--
ALTER TABLE `urls`
  MODIFY `id` int NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=45;

--
-- 使用表AUTO_INCREMENT `users`
--
ALTER TABLE `users`
  MODIFY `id` int NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- 限制导出的表
--

--
-- 限制表 `article_pass`
--
ALTER TABLE `article_pass`
  ADD CONSTRAINT `article_pass_ibfk_1` FOREIGN KEY (`aid`) REFERENCES `articles` (`ArticleID`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- 限制表 `comments`
--
ALTER TABLE `comments`
  ADD CONSTRAINT `comments_ibfk_1` FOREIGN KEY (`article_id`) REFERENCES `articles` (`ArticleID`),
  ADD CONSTRAINT `comments_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

--
-- 限制表 `custom_fields`
--
ALTER TABLE `custom_fields`
  ADD CONSTRAINT `custom_fields_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

--
-- 限制表 `email_subscriptions`
--
ALTER TABLE `email_subscriptions`
  ADD CONSTRAINT `email_subscriptions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

--
-- 限制表 `media`
--
ALTER TABLE `media`
  ADD CONSTRAINT `media_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

--
-- 限制表 `notifications`
--
ALTER TABLE `notifications`
  ADD CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

--
-- 限制表 `reports`
--
ALTER TABLE `reports`
  ADD CONSTRAINT `reports_ibfk_1` FOREIGN KEY (`reported_by`) REFERENCES `users` (`id`);

--
-- 限制表 `subscriptions`
--
ALTER TABLE `subscriptions`
  ADD CONSTRAINT `subscriptions_ibfk_1` FOREIGN KEY (`subscriber_id`) REFERENCES `users` (`id`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
