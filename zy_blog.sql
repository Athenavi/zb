-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- 主机： host.docker.internal
-- 生成日期： 2024-07-23 07:16:59
-- 服务器版本： 8.0.21
-- PHP 版本： 8.2.21

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- 数据库： `zy_blog`
--

-- --------------------------------------------------------

--
-- 表的结构 `articles`
--

CREATE TABLE `articles` (
  `ArticleID` int NOT NULL,
  `Title` varchar(255) NOT NULL,
  `Author` varchar(100) NOT NULL,
  `Hidden` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否隐藏 1 隐藏 0 不隐藏',
  `PublishDate` datetime DEFAULT NULL,
  `LastModifiedDate` datetime DEFAULT NULL,
  `Tags` varchar(255) DEFAULT NULL,
  `Views` int DEFAULT '0',
  `Likes` int DEFAULT '0',
  `Comments` int DEFAULT '0',
  `Status` enum('Draft','Published','Deleted') DEFAULT 'Draft',
  `CoverImage` varchar(255) DEFAULT NULL,
  `RelatedArticles` text,
  `RecommendedArticles` text,
  `ArticleType` varchar(50) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- 转存表中的数据 `articles`
--

INSERT INTO `articles` (`ArticleID`, `Title`, `Author`, `Hidden`, `PublishDate`, `LastModifiedDate`, `Tags`, `Views`, `Likes`, `Comments`, `Status`, `CoverImage`, `RelatedArticles`, `RecommendedArticles`, `ArticleType`) VALUES
(3, 'privacy', 'test', 0, NULL, NULL, '2025', 0, 0, 0, 'Draft', NULL, NULL, NULL, NULL);

-- --------------------------------------------------------

--
-- 表的结构 `invitecode`
--

CREATE TABLE `invitecode` (
  `uuid` char(36) NOT NULL,
  `code` char(4) NOT NULL,
  `is_used` tinyint(1) NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

--
-- 转存表中的数据 `invitecode`
--

INSERT INTO `invitecode` (`uuid`, `code`, `is_used`) VALUES
('f4f36405-e9dc-11ee-9225-f80dac08c659', '9988', 0);

-- --------------------------------------------------------

--
-- 表的结构 `ip`
--

CREATE TABLE `ip` (
  `used` text CHARACTER SET utf8 COLLATE utf8_general_ci,
  `ip` varchar(45) DEFAULT NULL,
  `username` char(24) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- 表的结构 `opentimes`
--

CREATE TABLE `opentimes` (
  `id` int NOT NULL,
  `short_url` varchar(10) NOT NULL,
  `response_count` int NOT NULL DEFAULT '0',
  `first_response_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- 表的结构 `urls`
--

CREATE TABLE `urls` (
  `id` int NOT NULL,
  `long_url` varchar(255) NOT NULL,
  `short_url` varchar(10) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `username` varchar(255) NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- 表的结构 `users`
--

CREATE TABLE `users` (
  `id` int NOT NULL,
  `username` varchar(255) NOT NULL,
  `password` varchar(255) NOT NULL,
  `ifAdmin` tinyint(1) NOT NULL DEFAULT '0',
  `email` varchar(255) NOT NULL DEFAULT 'guest@7trees.cn'
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

--
-- 转存表中的数据 `users`
--

INSERT INTO `users` (`id`, `username`, `password`, `ifAdmin`, `email`) VALUES
(1, 'test', '$2a$04$WWv/DDjich0uPMGpb4NhnOPiUFEzzIzfAVpLLDiIUo49wz5CEZ7sW', 1, 'support@7trees.cn');

--
-- 转储表的索引
--

--
-- 表的索引 `articles`
--
ALTER TABLE `articles`
  ADD PRIMARY KEY (`ArticleID`),
  ADD UNIQUE KEY `Title` (`Title`);

--
-- 表的索引 `invitecode`
--
ALTER TABLE `invitecode`
  ADD PRIMARY KEY (`uuid`);

--
-- 表的索引 `ip`
--
ALTER TABLE `ip`
  ADD PRIMARY KEY (`username`);

--
-- 表的索引 `opentimes`
--
ALTER TABLE `opentimes`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `short_url_unique` (`short_url`);

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
  MODIFY `ArticleID` int NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- 使用表AUTO_INCREMENT `opentimes`
--
ALTER TABLE `opentimes`
  MODIFY `id` int NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=35;

--
-- 使用表AUTO_INCREMENT `urls`
--
ALTER TABLE `urls`
  MODIFY `id` int NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=85;

--
-- 使用表AUTO_INCREMENT `users`
--
ALTER TABLE `users`
  MODIFY `id` int NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=25;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
