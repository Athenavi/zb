create table if not exists categories
(
    id         serial
        primary key,
    name       varchar(255) not null,
    created_at timestamp default now(),
    updated_at timestamp default now()
);

comment on table categories is '内容分类表';

alter table categories
    owner to postgres;

create table if not exists events
(
    id          serial
        primary key,
    title       varchar(255)            not null,
    description text                    not null,
    event_date  timestamp               not null,
    created_at  timestamp default now() not null
);

comment on column events.title is '事件标题';

comment on column events.description is '事件描述';

comment on column events.event_date is '事件日期';

comment on column events.created_at is '创建时间';

alter table events
    owner to postgres;

create table if not exists file_hashes
(
    id              bigserial
        primary key,
    hash            varchar(64)  not null
        unique,
    filename        varchar(255) not null,
    created_at      timestamp default now(),
    reference_count integer   default 1
        constraint file_hashes_reference_count_check
            check (reference_count >= 0),
    file_size       bigint       not null
        constraint file_hashes_file_size_check
            check (file_size >= 0),
    mime_type       varchar(100) not null,
    storage_path    varchar(512) not null,
    constraint unique_hash_mime
        unique (hash, mime_type)
);

comment on column file_hashes.file_size is '文件大小（字节）';

comment on column file_hashes.mime_type is 'MIME 类型';

comment on column file_hashes.storage_path is '实际存储路径';

alter table file_hashes
    owner to postgres;

create table if not exists permissions
(
    id          serial
        primary key,
    code        varchar(50)  not null
        unique,
    description varchar(255) not null
);

comment on column permissions.code is '权限代码（如 manage_users）';

comment on column permissions.description is '权限描述';

alter table permissions
    owner to postgres;

create table if not exists roles
(
    id          serial
        primary key,
    name        varchar(50)  not null
        unique,
    description varchar(255) not null
);

comment on column roles.name is '角色名称';

comment on column roles.description is '角色描述';

alter table roles
    owner to postgres;

create table if not exists role_permissions
(
    role_id       integer not null
        references roles
            on delete cascade,
    permission_id integer not null
        references permissions
            on delete cascade,
    primary key (role_id, permission_id)
);

alter table role_permissions
    owner to postgres;

create index if not exists role_permissions_permission_id
    on role_permissions (permission_id);

create table if not exists users
(
    id              serial
        primary key,
    username        varchar(255)            not null
        unique,
    password        varchar(255)            not null,
    email           varchar(255)            not null
        unique,
    created_at      timestamp default now() not null,
    updated_at      timestamp default now() not null,
    profile_picture varchar(255),
    bio             text,
    register_ip     varchar(45)             not null
);

comment on column users.username is '用户名';

comment on column users.password is '用户密码';

comment on column users.email is '用户邮箱';

comment on column users.profile_picture is '用户头像';

comment on column users.bio is '用户个人简介';

comment on column users.register_ip is '注册时IP';

alter table users
    owner to postgres;

create table if not exists articles
(
    article_id   serial
        primary key,
    title        varchar(255)            not null,
    slug         varchar(255)            not null
        constraint idx_slug_unique
            unique,
    user_id      integer
                                         references users
                                             on delete set null,
    hidden       boolean   default false not null,
    views        bigint    default 0     not null
        constraint articles_views_check
            check (views >= 0),
    likes        bigint    default 0     not null
        constraint articles_likes_check
            check (likes >= 0),
    status       text      default 'Draft'::text
        constraint articles_status_check
            check (status = ANY (ARRAY ['Draft'::text, 'Published'::text, 'Deleted'::text])),
    cover_image  varchar(255),
    article_type varchar(50),
    excerpt      text,
    is_featured  boolean   default false,
    tags         varchar(255)            not null,
    created_at   timestamp default now(),
    updated_at   timestamp default now(),
    constraint idx_user_title_unique
        unique (user_id, title)
);

comment on column articles.title is '文章标题';

comment on column articles.slug is 'URL友好标识符';

comment on column articles.user_id is '作者用户ID';

comment on column articles.hidden is '是否隐藏 1 隐藏 0 不隐藏';

comment on column articles.views is '浏览次数';

comment on column articles.likes is '点赞数';

comment on column articles.status is '文章状态: 草稿/已发布/已删除';

comment on column articles.cover_image is '封面图片路径';

comment on column articles.article_type is '文章类型';

comment on column articles.excerpt is '文章摘要';

comment on column articles.is_featured is '是否为推荐文章';

alter table articles
    owner to postgres;

create index if not exists idx_views
    on articles (views);

create table if not exists article_content
(
    aid           integer                                        not null
        primary key
        references articles
            on delete cascade,
    passwd        varchar(128),
    content       text,
    updated_at    timestamp   default now(),
    language_code varchar(10) default 'zh-CN'::character varying not null
);

comment on column article_content.language_code is '内容语言代码';

alter table article_content
    owner to postgres;

create table if not exists article_i18n
(
    i18n_id       serial
        primary key,
    article_id    integer      not null
        references articles
            on delete cascade,
    language_code varchar(10)  not null,
    title         varchar(255) not null,
    slug          varchar(255) not null,
    content       text         not null,
    excerpt       text,
    created_at    timestamp default now(),
    updated_at    timestamp default now(),
    constraint idx_article_lang_slug
        unique (article_id, language_code, slug),
    constraint uq_article_language
        unique (article_id, language_code)
);

comment on table article_i18n is '文章多语言内容表';

comment on column article_i18n.article_id is '原始文章ID';

comment on column article_i18n.language_code is 'ISO语言代码(如zh-CN, en-US)';

comment on column article_i18n.title is '本地化标题';

comment on column article_i18n.slug is '本地化URL标识符';

comment on column article_i18n.content is '本地化内容';

comment on column article_i18n.excerpt is '本地化摘要';

comment on column article_i18n.created_at is '创建时间';

comment on column article_i18n.updated_at is '更新时间';

alter table article_i18n
    owner to postgres;

create table if not exists category_subscriptions
(
    id            serial
        primary key,
    subscriber_id integer not null
        references users
            on delete cascade,
    category_id   integer not null
        references categories
            on delete cascade,
    created_at    timestamp default now()
);

comment on table category_subscriptions is '分类订阅关系';

comment on column category_subscriptions.subscriber_id is '订阅者ID';

comment on column category_subscriptions.category_id is '被订阅分类ID';

alter table category_subscriptions
    owner to postgres;

create index if not exists idx_category
    on category_subscriptions (category_id);

create index if not exists idx_subscriber
    on category_subscriptions (subscriber_id);

create table if not exists comments
(
    id         serial
        primary key,
    article_id integer not null
        references articles,
    user_id    integer not null
        references users,
    parent_id  integer
        references comments,
    content    text    not null,
    ip         varchar(50),
    user_agent varchar(255),
    created_at timestamp default now(),
    updated_at timestamp default now()
);

alter table comments
    owner to postgres;

create index if not exists idx_article_created
    on comments (article_id, created_at);

create index if not exists idx_parent_created
    on comments (parent_id, created_at);

create index if not exists comments_user_id
    on comments (user_id);

create table if not exists custom_fields
(
    id          serial
        primary key,
    user_id     integer      not null
        references users
            on delete cascade,
    field_name  varchar(100) not null,
    field_value text         not null
);

comment on column custom_fields.user_id is '用户ID';

comment on column custom_fields.field_name is '自定义字段名称';

comment on column custom_fields.field_value is '自定义字段值';

alter table custom_fields
    owner to postgres;

create index if not exists idx_user_id
    on custom_fields (user_id);

create table if not exists email_subscriptions
(
    id         serial
        primary key,
    user_id    integer                 not null
        unique
        references users
            on delete cascade,
    subscribed boolean   default true  not null,
    created_at timestamp default now() not null
);

comment on column email_subscriptions.user_id is '用户ID';

comment on column email_subscriptions.subscribed is '是否订阅邮件';

comment on column email_subscriptions.created_at is '订阅时间';

alter table email_subscriptions
    owner to postgres;

create index if not exists email_subscriptions_user_id
    on email_subscriptions (user_id);

create table if not exists media
(
    id                serial
        primary key,
    user_id           integer                 not null
        references users
            on delete cascade,
    created_at        timestamp default now() not null,
    updated_at        timestamp default now() not null,
    hash              varchar(64)             not null
        references file_hashes (hash),
    original_filename varchar(255)            not null
);

comment on column media.user_id is '上传用户ID';

comment on column media.created_at is '创建时间';

comment on column media.updated_at is '更新时间';

comment on column media.hash is '文件哈希';

comment on column media.original_filename is '原始文件名';

alter table media
    owner to postgres;

create table if not exists notifications
(
    id         serial
        primary key,
    user_id    integer                 not null
        references users
            on delete cascade,
    type       varchar(100)            not null,
    message    text                    not null,
    is_read    boolean   default false not null,
    created_at timestamp default now() not null,
    updated_at timestamp default now() not null
);

comment on column notifications.user_id is '接收者用户ID';

comment on column notifications.type is '通知类型';

comment on column notifications.message is '通知内容';

comment on column notifications.is_read is '是否已阅读';

comment on column notifications.created_at is '创建时间';

comment on column notifications.updated_at is '更新时间';

alter table notifications
    owner to postgres;

create table if not exists reports
(
    id           serial
        primary key,
    reported_by  integer                 not null
        references users
            on delete cascade,
    content_type text                    not null
        constraint reports_content_type_check
            check (content_type = ANY (ARRAY ['Article'::text, 'Comment'::text])),
    content_id   integer                 not null,
    reason       text                    not null,
    created_at   timestamp default now() not null
);

comment on column reports.reported_by is '举报用户ID';

comment on column reports.content_type is '内容类型: 文章/评论';

comment on column reports.content_id is '内容ID';

comment on column reports.reason is '举报理由';

comment on column reports.created_at is '举报时间';

alter table reports
    owner to postgres;

create index if not exists idx_reported_by
    on reports (reported_by);

create table if not exists urls
(
    id         serial
        primary key,
    long_url   varchar(255)            not null,
    short_url  varchar(10)             not null
        unique,
    created_at timestamp default now() not null,
    user_id    integer                 not null
        references users
            on delete cascade
);

comment on column urls.long_url is '长链接';

comment on column urls.short_url is '短链接';

comment on column urls.created_at is '创建时间';

comment on column urls.user_id is '用户ID';

alter table urls
    owner to postgres;

create table if not exists user_roles
(
    user_id integer not null
        references users
            on delete cascade,
    role_id integer not null
        references roles
            on delete cascade,
    primary key (user_id, role_id)
);

alter table user_roles
    owner to postgres;

create index if not exists idx_role_id
    on user_roles (role_id);

create table if not exists user_subscriptions
(
    id                 serial
        primary key,
    subscriber_id      integer not null
        references users
            on delete cascade,
    subscribed_user_id integer not null
        references users
            on delete cascade,
    created_at         timestamp default now()
);

comment on table user_subscriptions is '用户订阅关系';

comment on column user_subscriptions.subscriber_id is '订阅者ID';

comment on column user_subscriptions.subscribed_user_id is '被订阅用户ID';

alter table user_subscriptions
    owner to postgres;

create index if not exists idx_subscribed_user
    on user_subscriptions (subscribed_user_id);

INSERT INTO users (username, password, email, created_at, updated_at, profile_picture, bio, register_ip)
VALUES ('test', '$2b$12$kF4nZn6kESHtj0cjNeaoZugUlWXSgXp27iKAXHepyzSwUxrrhVTz2', 'support@7trees.cn',
        '2025-09-10 17:09:13', '2025-04-16 07:38:59', NULL, NULL, '');

