import React from 'react';

interface FormattedResponseProps {
  text: string;
}

function renderInline(text: string, keyPrefix: string) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*)/g);

  return parts.map((part, index) => {
    const key = `${keyPrefix}-${index}`;
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={key} className="rounded bg-black/40 px-1.5 py-0.5 text-[0.9em] text-amber-200 font-mono">
          {part.slice(1, -1)}
        </code>
      );
    }
    if ((part.startsWith('**') && part.endsWith('**')) || (part.startsWith('__') && part.endsWith('__'))) {
      return (
        <strong key={key} className="font-bold text-slate-50">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={key} className="italic text-slate-200">{part.slice(1, -1)}</em>;
    }
    return <React.Fragment key={key}>{part.replace(/\*+/g, '')}</React.Fragment>;
  });
}

function parseTableRow(rowStr: string): string[] {
  return rowStr
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map(c => c.trim());
}

export function FormattedResponse({ text }: FormattedResponseProps) {
  // Strip out any code blocks or leftover JSON chart definitions completely from text display
  const cleanedText = text
    .replace(/```(?:json)?[\s\S]*?(?:```|$)/gi, '')
    .trim();

  const lines = cleanedText.replace(/\r\n/g, '\n').split('\n');
  const blocks: React.ReactNode[] = [];
  let paragraph: string[] = [];
  let listItems: { type: 'bullet' | 'number'; text: string }[] = [];
  let tableLines: string[] = [];

  const flushParagraph = () => {
    if (paragraph.length > 0) {
      blocks.push(
        <p key={`paragraph-${blocks.length}`} className="leading-7 text-slate-200">
          {renderInline(paragraph.join(' '), `paragraph-${blocks.length}`)}
        </p>,
      );
      paragraph = [];
    }
  };

  const flushList = () => {
    if (listItems.length === 0) return;
    const isNumbered = listItems[0].type === 'number';
    const ListTag = isNumbered ? 'ol' : 'ul';
    blocks.push(
      <ListTag
        key={`list-${blocks.length}`}
        className={`${isNumbered ? 'list-decimal' : 'list-disc'} space-y-1.5 pl-5 leading-7 marker:text-[#FF204E] text-slate-200`}
      >
        {listItems.map((item, index) => (
          <li key={`item-${index}`}>{renderInline(item.text, `item-${index}`)}</li>
        ))}
      </ListTag>,
    );
    listItems = [];
  };

  const flushTable = () => {
    if (tableLines.length < 2) {
      if (tableLines.length === 1) {
        paragraph.push(tableLines[0]);
      }
      tableLines = [];
      return;
    }

    const header = parseTableRow(tableLines[0]);
    // Filter out any divider lines containing only dashes, colons, or whitespace (e.g. |:---|:---|)
    const rowLines = tableLines.slice(1).filter(l => !/^[\s|:\-]+$/.test(l.trim()));
    const rows = rowLines.map(parseTableRow);

    blocks.push(
      <div
        key={`table-${blocks.length}`}
        className="w-full my-3 overflow-x-auto rounded-xl border border-white/10 bg-black/40 shadow-xl custom-scrollbar"
      >
        <table className="w-full text-xs text-left border-collapse">
          <thead className="bg-white/5 border-b border-white/10 text-slate-200 font-bold uppercase tracking-wider text-[11px]">
            <tr>
              {header.map((col, cIdx) => (
                <th key={cIdx} className="py-2.5 px-3 border-r border-white/5 last:border-0 font-extrabold text-slate-100">
                  {renderInline(col, `th-${cIdx}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-slate-300">
            {rows.map((row, rIdx) => (
              <tr key={rIdx} className="hover:bg-white/[0.04] transition-colors">
                {row.map((cell, cellIdx) => (
                  <td key={cellIdx} className="py-2.5 px-3 border-r border-white/5 last:border-0 leading-relaxed">
                    {renderInline(cell, `td-${rIdx}-${cellIdx}`)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
    tableLines = [];
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();
    const isTableLine = (trimmed.startsWith('|') || (trimmed.endsWith('|') && trimmed.includes('|'))) && trimmed.split('|').length >= 3;
    const heading = trimmed.match(/^#{1,3}\s+(.+)$/);
    const bullet = trimmed.match(/^(?:[-*•])\s*(.+)$/);
    const numbered = trimmed.match(/^\d+[.)]\s+(.+)$/);

    if (isTableLine) {
      flushParagraph();
      flushList();
      tableLines.push(trimmed);
      return;
    } else if (tableLines.length > 0) {
      flushTable();
    }

    if (!trimmed) {
      flushParagraph();
      flushList();
    } else if (heading) {
      flushParagraph();
      flushList();
      blocks.push(
        <h4 key={`heading-${index}`} className="pt-2 text-sm font-bold text-slate-100 first:pt-0">
          {renderInline(heading[1], `heading-${index}`)}
        </h4>,
      );
    } else if (bullet || numbered) {
      flushParagraph();
      listItems.push({ type: bullet ? 'bullet' : 'number', text: (bullet || numbered)![1] });
    } else {
      if (listItems.length > 0) flushList();
      paragraph.push(trimmed);
    }
  });

  flushParagraph();
  flushList();
  flushTable();

  return <div className="formatted-response flex flex-col gap-3">{blocks}</div>;
}