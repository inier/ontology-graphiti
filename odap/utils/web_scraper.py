"""网页抓取工具"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
from datetime import datetime
import re


class WebScraper:
    """网页数据抓取器"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def fetch_url(self, url: str) -> Optional[BeautifulSoup]:
        """获取网页内容"""
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            print(f"Error fetching URL {url}: {e}")
            return None
    
    def extract_text(self, soup: BeautifulSoup) -> str:
        """从网页中提取主要文本内容"""
        # 移除脚本、样式、导航等元素
        for elem in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            elem.decompose()
        
        # 获取所有文本
        text = soup.get_text(separator='\n', strip=True)
        
        # 清理空白行
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        return '\n'.join(lines)
    
    def extract_title(self, soup: BeautifulSoup) -> str:
        """提取网页标题"""
        title = soup.find('title')
        if title:
            return title.get_text(strip=True)
        
        # 尝试从h1标签获取
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)
        
        return "Untitled"
    
    def extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """提取网页元数据"""
        metadata = {}
        
        # 查找meta标签
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            name = tag.get('name') or tag.get('property')
            content = tag.get('content')
            if name and content:
                metadata[name] = content
        
        return metadata
    
    def extract_links(self, soup: BeautifulSoup) -> list:
        """提取页面链接"""
        links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')
            text = a_tag.get_text(strip=True)
            if href and text:
                links.append({'url': href, 'text': text})
        return links
    
    def scrape_news(self, url: str) -> Optional[Dict[str, Any]]:
        """抓取新闻页面"""
        soup = self.fetch_url(url)
        if not soup:
            return None
        
        # 提取基本信息
        title = self.extract_title(soup)
        content = self.extract_text(soup)
        metadata = self.extract_metadata(soup)
        
        # 尝试获取发布时间
        published_date = metadata.get('article:published_time') or \
                        metadata.get('datePublished') or \
                        metadata.get('og:published_time')
        
        return {
            'url': url,
            'title': title,
            'content': content,
            'metadata': metadata,
            'published_date': published_date,
            'scraped_at': datetime.now().isoformat()
        }
