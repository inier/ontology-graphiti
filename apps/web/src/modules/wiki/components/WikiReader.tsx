/**
 * 条目阅读器 —— 极简 Markdown 渲染（行级 + 内联，纯 React 节点）
 *
 * 刻意不使用 dangerouslySetInnerHTML / 第三方 Markdown 库：
 * Wiki 正文来自后端，直接在页面上注入 HTML 会引入 XSS 面。
 */
import type { ReactNode } from 'react';

/** 内联语法：`code` 与 **strong** */
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let rest = text;
  let i = 0;

  while (rest.length > 0) {
    const codeStart = rest.indexOf('`');
    const boldStart = rest.indexOf('**');
    const next = [codeStart, boldStart].filter((idx) => idx >= 0).sort((a, b) => a - b)[0];

    if (next === undefined) {
      nodes.push(rest);
      break;
    }

    if (next > 0) {
      nodes.push(rest.slice(0, next));
      rest = rest.slice(next);
      continue;
    }

    if (rest.startsWith('`')) {
      const end = rest.indexOf('`', 1);
      if (end < 0) {
        nodes.push(rest);
        break;
      }
      nodes.push(<code key={`${keyPrefix}-c${i++}`}>{rest.slice(1, end)}</code>);
      rest = rest.slice(end + 1);
      continue;
    }

    const end = rest.indexOf('**', 2);
    if (end < 0) {
      nodes.push(rest);
      break;
    }
    nodes.push(<strong key={`${keyPrefix}-b${i++}`}>{rest.slice(2, end)}</strong>);
    rest = rest.slice(end + 2);
  }

  return nodes;
}

export interface WikiReaderProps {
  content: string;
  /** 条目标题：正文缺失时用于兜底说明 */
  title: string;
}

export function WikiReader({ content, title }: WikiReaderProps) {
  const lines = content.split('\n');
  if (content.trim().length === 0) {
    return (
      <div className="wiki-reader">
        <h1>{title}</h1>
        <p>该条目尚未写入正文（wiki_versions.content 为空）。</p>
      </div>
    );
  }

  const blocks: ReactNode[] = [];
  let listBuffer: string[] = [];

  const flushList = (key: string) => {
    if (listBuffer.length === 0) return;
    blocks.push(
      <ul key={key}>
        {listBuffer.map((item, idx) => (
          <li key={`${key}-${idx}`}>{renderInline(item, `${key}-${idx}`)}</li>
        ))}
      </ul>,
    );
    listBuffer = [];
  };

  lines.forEach((raw, idx) => {
    const line = raw.trimEnd();
    const key = `l${idx}`;

    if (line.trim() === '') {
      flushList(`${key}-ul`);
      return;
    }
    if (line.startsWith('### ')) {
      flushList(`${key}-ul`);
      blocks.push(<h3 key={key}>{renderInline(line.slice(4), key)}</h3>);
      return;
    }
    if (line.startsWith('## ')) {
      flushList(`${key}-ul`);
      blocks.push(<h2 key={key}>{renderInline(line.slice(3), key)}</h2>);
      return;
    }
    if (line.startsWith('# ')) {
      flushList(`${key}-ul`);
      blocks.push(<h1 key={key}>{renderInline(line.slice(2), key)}</h1>);
      return;
    }
    if (line.startsWith('- ')) {
      listBuffer.push(line.slice(2));
      return;
    }
    if (/^\d+\.\s/.test(line)) {
      listBuffer.push(line.replace(/^\d+\.\s/, ''));
      return;
    }
    flushList(`${key}-ul`);
    blocks.push(<p key={key}>{renderInline(line, key)}</p>);
  });

  flushList('tail-ul');

  return <div className="wiki-reader">{blocks}</div>;
}
