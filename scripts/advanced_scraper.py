"""
高级网页爬虫脚本
支持 JavaScript 渲染、滚动加载、无限滚动页面、递归抓取正文链接

使用方法:
    python scripts/advanced_scraper.py <url> [options]

示例:
    # 抓取单个页面
    python scripts/advanced_scraper.py https://example.com

    # 抓取并滚动加载更多内容
    python scripts/advanced_scraper.py https://example.com --scroll --max-scrolls 5

    # 输出到指定文件
    python scripts/advanced_scraper.py https://example.com --output result.md

    # 递归抓取正文内链接
    python scripts/advanced_scraper.py https://example.com --recursive --max-depth 2

    # 使用代理
    python scripts/advanced_scraper.py https://example.com --proxy http://proxy:8080
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ScrapResult:
    """爬取结果"""
    url: str
    title: str
    content: str
    markdown: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    images: List[str] = field(default_factory=list)
    links: List[Dict[str, str]] = field(default_factory=list)
    tables: List[str] = field(default_factory=list)
    related_pages: List['ScrapResult'] = field(default_factory=list)
    error: Optional[str] = None


try:
    from readability import Document
    HAS_READABILITY = True
    logger.info("readability-lxml 已加载，将用于正文识别")
except ImportError:
    HAS_READABILITY = False
    logger.warning("readability-lxml 未安装，使用原始解析方法")


def normalize_url(url: str, base_url: str) -> Optional[str]:
    """规范化 URL"""
    if not url:
        return None

    if url.startswith('#') or url.startswith('javascript:'):
        return None

    try:
        normalized = urljoin(base_url, url)
        parsed = urlparse(normalized)
        if not parsed.scheme or not parsed.netloc:
            return None
        return normalized
    except Exception:
        return None


def extract_main_content_links(html: str, base_url: str) -> List[str]:
    """
    从正文中提取链接
    使用 readability-lxml 识别正文区域
    """
    links = []

    if HAS_READABILITY:
        try:
            doc = Document(html)
            main_html = doc.summary()
            soup = BeautifulSoup(main_html, 'html.parser')
            logger.info("使用 readability 识别正文")
        except Exception as e:
            logger.warning(f"readability 解析失败: {e}，使用 BeautifulSoup")
            soup = BeautifulSoup(html, 'html.parser')
    else:
        soup = BeautifulSoup(html, 'html.parser')

    content_selectors = [
        'main', 'article', '.content', '#content', '.post', '.article',
        '.story', '.post-content', '.article-body', '.entry-content'
    ]

    main_content = None
    for selector in content_selectors:
        element = soup.select_one(selector)
        if element:
            main_content = element
            break

    if not main_content:
        main_content = soup.body

    if main_content:
        for a in main_content.find_all('a', href=True):
            href = a.get('href', '')
            normalized = normalize_url(href, base_url)
            if normalized and normalized not in links:
                links.append(normalized)

    return links


class PlaywrightScraper:
    """
    使用 Playwright 的高级爬虫
    支持 JavaScript 渲染和滚动加载
    """

    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.headless = headless
        self.timeout = timeout
        self.browser = None
        self.context = None

    async def setup(self):
        """初始化浏览器"""
        try:
            from playwright.async_api import async_playwright
            self.playwright = async_playwright()
            await self.playwright.start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            logger.info("Playwright 浏览器初始化成功")
        except ImportError:
            logger.error("请先安装 playwright: pip install playwright && playwright install chromium")
            raise

    async def close(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def scroll_page(self, page, max_scrolls: int = 10, scroll_delay: float = 2.0):
        """滚动页面"""
        previous_height = 0
        for i in range(max_scrolls):
            current_height = await page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                logger.info(f"滚动 {i+1} 次后页面高度不再变化，停止滚动")
                break
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(scroll_delay)
            previous_height = current_height
            logger.info(f"滚动 {i+1} 次，当前高度: {current_height}px")

    async def scrape(self, url: str, scroll: bool = False, max_scrolls: int = 10) -> ScrapResult:
        """爬取页面"""
        if not self.browser:
            await self.setup()

        page = await self.context.new_page()
        result = ScrapResult(url=url, title="", content="", markdown="")

        try:
            logger.info(f"开始爬取: {url}")
            response = await page.goto(url, timeout=self.timeout, wait_until="networkidle")

            if response and response.status >= 400:
                result.error = f"HTTP {response.status}"
                return result

            await asyncio.sleep(2)

            if scroll:
                await self.scroll_page(page, max_scrolls=max_scrolls)

            result.title = await page.title()
            content = await page.content()
            result.content = self._parse_html(content)
            result.markdown = await self._extract_markdown(page)
            result.metadata['scraped_at'] = datetime.now().isoformat()
            result.metadata['scroll_enabled'] = scroll
            result.metadata['max_scrolls'] = max_scrolls if scroll else 0

            links = await page.query_selector_all('a[href]')
            for link in links[:50]:
                href = await link.get_attribute('href')
                text = await link.text_content()
                if href:
                    result.links.append({'url': href, 'text': text or ''})

            images = await page.query_selector_all('img')
            for img in images[:20]:
                src = await img.get_attribute('src')
                alt = await img.get_attribute('alt')
                if src:
                    result.images.append({'url': src, 'alt': alt or ''})

            tables = await page.query_selector_all('table')
            for table in tables:
                table_html = await table.inner_html()
                result.tables.append(table_html)

            logger.info(f"爬取成功: {result.title}")

        except Exception as e:
            logger.error(f"爬取失败: {e}")
            result.error = str(e)
        finally:
            await page.close()

        return result

    def _parse_html(self, html: str) -> str:
        """解析 HTML 内容"""
        if HAS_READABILITY:
            try:
                doc = Document(html)
                return doc.summary()
            except Exception as e:
                logger.warning(f"readability 解析失败: {e}")

        soup = BeautifulSoup(html, 'html.parser')
        for script in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            script.decompose()
        return soup.get_text(separator='\n', strip=True)

    async def _extract_markdown(self, page) -> str:
        """提取 Markdown 格式内容"""
        markdown_parts = []

        title = await page.title()
        if title:
            markdown_parts.append(f"# {title}\n")

        markdown_parts.append(f"> 来源: {page.url}\n")
        markdown_parts.append(f"> 爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        main_content = await page.query_selector('main, article, .content, #content, .post, .article')
        if not main_content:
            main_content = await page.query_selector('body')

        if main_content:
            html = await main_content.inner_html()
            markdown_parts.append(self._html_to_markdown(html))

        return '\n\n'.join(markdown_parts)

    def _html_to_markdown(self, html: str) -> str:
        """将 HTML 转换为 Markdown"""
        soup = BeautifulSoup(html, 'html.parser')
        markdown_lines = []

        for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'blockquote', 'pre', 'code']):
            if element.name.startswith('h'):
                level = int(element.name[1])
                markdown_lines.append(f"{'#' * level} {element.get_text(strip=True)}")
            elif element.name == 'p':
                text = element.get_text(strip=True)
                if text:
                    markdown_lines.append(f"{text}\n")
            elif element.name == 'ul':
                for li in element.find_all('li', recursive=False):
                    markdown_lines.append(f"- {li.get_text(strip=True)}")
            elif element.name == 'ol':
                for i, li in enumerate(element.find_all('li', recursive=False), 1):
                    markdown_lines.append(f"{i}. {li.get_text(strip=True)}")
            elif element.name == 'blockquote':
                text = element.get_text(strip=True)
                markdown_lines.append(f"> {text}")
            elif element.name == 'pre':
                code = element.get_text(strip=True)
                markdown_lines.append(f"```\n{code}\n```")
            elif element.name == 'code':
                if element.parent.name != 'pre':
                    markdown_lines.append(f"`{element.get_text(strip=True)}`")

        return '\n'.join(markdown_lines)


class SimpleScraper:
    """简单爬虫（无需 JavaScript 渲染）"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def scrape(self, url: str) -> ScrapResult:
        """爬取页面"""
        result = ScrapResult(url=url, title="", content="", markdown="")

        try:
            logger.info(f"开始爬取: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            for script in soup(['script', 'style']):
                script.decompose()

            title = soup.find('title')
            result.title = title.get_text(strip=True) if title else ""

            if HAS_READABILITY:
                try:
                    doc = Document(response.text)
                    result.content = doc.summary()
                    logger.info("使用 readability 提取正文")
                except Exception as e:
                    logger.warning(f"readability 解析失败: {e}")

            if not result.content:
                main = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|article|post'))
                if not main:
                    main = soup.body
                if main:
                    result.content = main.get_text(separator='\n', strip=True)

            result.markdown = self._to_markdown(soup, url)

            for link in soup.find_all('a', href=True)[:30]:
                result.links.append({
                    'url': link['href'],
                    'text': link.get_text(strip=True) or ''
                })

            for img in soup.find_all('img', src=True)[:20]:
                result.images.append({
                    'url': img['src'],
                    'alt': img.get('alt', '') or ''
                })

            result.metadata = {
                'scraped_at': datetime.now().isoformat(),
                'status_code': response.status_code,
                'content_length': len(response.text),
            }

            logger.info(f"爬取成功: {result.title}")

        except Exception as e:
            logger.error(f"爬取失败: {e}")
            result.error = str(e)

        return result

    def _to_markdown(self, soup: BeautifulSoup, url: str) -> str:
        """转换为 Markdown"""
        lines = []

        title = soup.find('title')
        if title:
            lines.append(f"# {title.get_text(strip=True)}\n")

        lines.append(f"> 来源: {url}\n")
        lines.append(f"> 爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        main = soup.find('main') or soup.find('article') or soup.find('body')
        if main:
            for element in main.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'blockquote', 'pre']):
                if element.name.startswith('h'):
                    level = int(element.name[1])
                    lines.append(f"{'#' * level} {element.get_text(strip=True)}")
                elif element.name == 'p':
                    text = element.get_text(strip=True)
                    if text:
                        lines.append(f"{text}\n")
                elif element.name == 'ul':
                    for li in element.find_all('li', recursive=False):
                        lines.append(f"- {li.get_text(strip=True)}")
                elif element.name == 'ol':
                    for i, li in enumerate(element.find_all('li', recursive=False), 1):
                        lines.append(f"{i}. {li.get_text(strip=True)}")
                elif element.name == 'blockquote':
                    lines.append(f"> {element.get_text(strip=True)}")
                elif element.name == 'pre':
                    code = element.get_code()
                    if code:
                        lines.append(f"```\n{code.get_text()}\n```")

        return '\n'.join(lines)


async def recursive_scrape(
    url: str,
    max_depth: int = 2,
    current_depth: int = 0,
    visited: Set[str] = None,
    use_playwright: bool = False,
    scroll: bool = False,
    max_scrolls: int = 10
) -> ScrapResult:
    """递归爬取页面及其正文内链接"""
    if visited is None:
        visited = set()

    if url in visited:
        logger.info(f"已访问: {url}，跳过")
        return None

    if current_depth > max_depth:
        logger.info(f"超过最大深度: {max_depth}，停止")
        return None

    visited.add(url)
    logger.info(f"深度 {current_depth}: 爬取 {url}")

    if use_playwright:
        scraper = PlaywrightScraper()
        result = await scraper.scrape(url, scroll=scroll, max_scrolls=max_scrolls)
        await scraper.close()
    else:
        scraper = SimpleScraper()
        result = scraper.scrape(url)

    if result.error:
        return result

    if current_depth < max_depth:
        if use_playwright:
            temp_scraper = PlaywrightScraper()
            await temp_scraper.setup()
            page = await temp_scraper.context.new_page()
            await page.goto(url, timeout=30000)
            html = await page.content()
            await page.close()
            await temp_scraper.close()
            related_links = extract_main_content_links(html, url)
        else:
            response = requests.get(url, timeout=30)
            related_links = extract_main_content_links(response.text, url)

        logger.info(f"从正文找到 {len(related_links)} 个链接")

        for link in related_links[:5]:
            if link not in visited:
                try:
                    related_result = await recursive_scrape(
                        link,
                        max_depth,
                        current_depth + 1,
                        visited,
                        use_playwright,
                        scroll,
                        max_scrolls
                    )
                    if related_result and not related_result.error:
                        result.related_pages.append(related_result)
                except Exception as e:
                    logger.warning(f"爬取相关页面失败 {link}: {e}")

    return result


def result_to_ontology_doc(result: ScrapResult) -> Dict[str, Any]:
    """将 ScrapResult 转换为 OntologyDocument 格式"""
    return {
        "title": result.title or f"Scraped: {result.url}",
        "doc_type": "event",
        "source": {
            "type": "manual",
            "url": result.url,
            "collected_at": datetime.now().isoformat()
        },
        "meta": {
            "description": f"Content scraped from {result.url}",
            "content": result.content or "",
            "scraper_metadata": {
                "scraped_at": result.metadata.get('scraped_at', datetime.now().isoformat()),
                "has_readability": HAS_READABILITY,
                "scroll_enabled": result.metadata.get('scroll_enabled', False),
                "max_scrolls": result.metadata.get('max_scrolls', 0),
                "related_page_count": len(result.related_pages)
            }
        },
        "original_markdown": result.markdown,
        "related_pages": [
            {
                "title": rp.title,
                "url": rp.url,
                "content": rp.content
            }
            for rp in result.related_pages if not rp.error
        ] if result.related_pages else []
    }


def save_result(result: ScrapResult, output_path: Optional[str] = None, output_format: str = 'md'):
    """保存结果"""

    if output_format == 'json' or (output_path and output_path.endswith('.json')):
        doc = result_to_ontology_doc(result)
        
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
            logger.info(f"结果已保存到: {output_path} (JSON 格式，可用于 OntologyDocument)")
        else:
            print(json.dumps(doc, ensure_ascii=False, indent=2))
        return

    full_markdown = result.markdown

    if result.related_pages:
        full_markdown += "\n\n---\n\n"
        full_markdown += "## 相关页面\n\n"

        for i, related in enumerate(result.related_pages, 1):
            full_markdown += f"### {i}. {related.title}\n\n"
            full_markdown += f"> 来源: {related.url}\n\n"
            full_markdown += related.markdown
            full_markdown += "\n\n---\n\n"

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(full_markdown)
        logger.info(f"结果已保存到: {output_path} (Markdown 格式，可用于 ManualInputHandler)")
    else:
        print(full_markdown)

    console_output = f"""
{'='*60}
爬取结果
{'='*60}
URL: {result.url}
标题: {result.title}
状态: {'成功' if not result.error else f'失败 - {result.error}'}
链接数: {len(result.links)}
图片数: {len(result.images)}
相关页面数: {len(result.related_pages)}
内容长度: {len(result.content)} 字符
使用 readability: {HAS_READABILITY}
输出格式: {output_format}
{'='*60}
"""
    print(console_output)


def generate_ontology_integration_script(result: ScrapResult, output_dir: str = 'data/scraped') -> str:
    """生成一个 Python 脚本，用于将爬取内容直接导入到本体系统"""
    import textwrap
    return textwrap.dedent(f"""\
    # 将此内容保存为 import_to_ontology.py 并运行
    # 会使用 advanced_scraper 的输出作为输入源

    from odap.biz.core.ontology.ingestion import ManualInputHandler
    from odap.biz.core.ontology.services import ingest_service
    import json
    from pathlib import Path

    async def main():
        # 读取爬取结果
        with open('{Path(output_dir, "scraped_result.json")}', 'r', encoding='utf-8') as f:
            doc_data = json.load(f)
        
        # 创建 OntologyDocument
        handler = ManualInputHandler()
        doc = await handler.from_json(json.dumps(doc_data))
        
        print(f"已创建 OntologyDocument: {{doc.title}}")
        
        # 也可以使用自然语言方式
        if doc_data.get('original_markdown'):
            doc_from_md = await handler.from_natural_language(doc_data['original_markdown'])
            print(f"已通过 Markdown 创建: {{doc_from_md.title}}")
        
        # 使用 ingest_service 进行完整导入
        ingest_id = await ingest_service.ingest_from_manual(
            data=json.dumps(doc_data),
            event_context="Scraped content from {{doc_data['source']['url']}}",
            scenario_id="scenario_scraper"
        )
        
        print(f"导入完成，Ingest ID: {{ingest_id}}")

    if __name__ == '__main__':
        import asyncio
        asyncio.run(main())
    """)


async def main():
    parser = argparse.ArgumentParser(
        description='高级网页爬虫 - 支持 JavaScript 渲染、滚动加载、递归抓取正文链接',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('url', help='要爬取的页面 URL')
    parser.add_argument('-o', '--output', help='输出文件路径')
    parser.add_argument('--output-format', choices=['md', 'json'], default='md', 
                        help='输出格式: md (Markdown) 或 json (OntologyDocument 兼容)')
    parser.add_argument('--scroll', action='store_true', help='启用滚动加载')
    parser.add_argument('--max-scrolls', type=int, default=10, help='最大滚动次数 (默认: 10)')
    parser.add_argument('--no-headless', action='store_true', help='显示浏览器窗口')
    parser.add_argument('--timeout', type=int, default=30, help='请求超时秒数 (默认: 30)')
    parser.add_argument('--proxy', help='代理服务器地址')
    parser.add_argument('--simple', action='store_true', help='使用简单模式 (不使用 JavaScript)')

    parser.add_argument('--recursive', action='store_true', help='递归抓取正文链接')
    parser.add_argument('--max-depth', type=int, default=2, help='递归最大深度 (默认: 2)')
    parser.add_argument('--no-readability', action='store_true', help='不使用 readability-lxml')
    parser.add_argument('--generate-script', action='store_true', 
                        help='生成导入到本体系统的脚本')

    args = parser.parse_args()

    if args.no_readability:
        global HAS_READABILITY
        HAS_READABILITY = False
        logger.info("已禁用 readability-lxml")

    if args.recursive:
        logger.info(f"开始递归爬取，最大深度: {args.max_depth}")
        result = await recursive_scrape(
            args.url,
            max_depth=args.max_depth,
            use_playwright=not args.simple,
            scroll=args.scroll,
            max_scrolls=args.max_scrolls
        )
    else:
        if args.simple:
            scraper = SimpleScraper(timeout=args.timeout)
            result = scraper.scrape(args.url)
        else:
            scraper = PlaywrightScraper(
                headless=not args.no_headless,
                timeout=args.timeout * 1000
            )
            try:
                result = await scraper.scrape(
                    args.url,
                    scroll=args.scroll,
                    max_scrolls=args.max_scrolls
                )
            finally:
                await scraper.close()

    save_result(result, args.output, args.output_format)

    if args.generate_script and not result.error:
        # 先生成 JSON 格式结果
        if args.output_format == 'md' or not args.output.endswith('.json'):
            json_output = 'data/scraped/scraped_result.json'
            save_result(result, json_output, 'json')
        
        script_content = generate_ontology_integration_script(result, 'data/scraped')
        script_path = Path('data/scraped/import_to_ontology.py')
        script_path.parent.mkdir(parents=True, exist_ok=True)
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        logger.info(f"导入脚本已生成: {script_path}")
        print(f"运行命令: python {script_path}")

    if result.error:
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
