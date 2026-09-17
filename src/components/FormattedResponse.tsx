import React from 'react';

interface FormattedResponseProps {
  text: string;
}

function renderInline(text: string, keyPrefix: string) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*)/g);

  return parts.map((part, index) => {
    const key = `${keyPrefix}-${index}`;
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={key} className="rounded bg-black/40 px-1.5 py-0.5 text-[0.9em] text-amber-200">{part.slice(1, -1)}</code>;
    }
    if ((part.startsWith('**') && part.endsWith('**')) || (part.startsWith('__') && part.endsWith('__'))) {
      return <strong key={key} className="font-bold text-slate-50">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={key}>{part.slice(1, -1)}</em>;
    }
    return <React.Fragment key={key}>{part.replace(/\*+/g, '')}</React.Fragment>;
  });
}

export function FormattedResponse({ text }: FormattedResponseProps) {
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  const blocks: React.ReactNode[] = [];
  let paragraph: string[] = [];
  let listItems: { type: 'bullet' | 'number'; text: string }[] = [];

  const flushParagraph = () => {
    if (paragraph.length > 0) {
      blocks.push(
        <p key={`paragraph-${blocks.length}`} className="leading-7">
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
        className={`${isNumbered ? 'list-decimal' : 'list-disc'} space-y-1.5 pl-5 leading-7 marker:text-[#FF204E]`}
      >
        {listItems.map((item, index) => (
          <li key={`item-${index}`}>{renderInline(item.text, `item-${index}`)}</li>
        ))}
      </ListTag>,
    );
    listItems = [];
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();
    const heading = trimmed.match(/^#{1,3}\s+(.+)$/);
    const bullet = trimmed.match(/^(?:[-*•])\s*(.+)$/);
    const numbered = trimmed.match(/^\d+[.)]\s+(.+)$/);

    if (!trimmed) {
      flushParagraph();
      flushList();
    } else if (heading) {
      flushParagraph();
      flushList();
      blocks.push(
        <h4 key={`heading-${index}`} className="pt-2 text-sm font-bold text-amber-200 first:pt-0">
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

  return <div className="formatted-response flex flex-col gap-3">{blocks}</div>;
}