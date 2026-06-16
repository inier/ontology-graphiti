package data_collection

import input.action
import input.role
import input.target_domain

# 默认拒绝
default allow = false

# 允许的搜索操作（admin 和 analyst 均可）
allow {
    input.action == "search"
    input.role == "admin"
}

allow {
    input.action == "search"
    input.role == "analyst"
}

# 允许的爬取操作（admin 直接允许，analyst 需域名白名单）
allow {
    input.action == "crawl"
    input.role == "admin"
}

allow {
    input.action == "crawl"
    input.role == "analyst"
    allowed_domain
}

# 浏览器自动化操作（仅 admin）
allow {
    input.action == "browser"
    input.role == "admin"
}

# 域名白名单检查
allowed_domain {
    allowed_domains[i] == input.target_domain
}

# 允许的域名列表
allowed_domains = [
    "reuters.com",
    "bbc.com",
    "bloomberg.com",
    "xinhuanet.com",
    "people.com.cn",
    "thepaper.cn",
    "36kr.com",
    "caixin.com",
    "gov.cn",
    "nature.com",
    "science.org",
    "arxiv.org",
    "github.com",
    "wikipedia.org",
]
