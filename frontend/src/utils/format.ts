/**
 * Minimal, dependency-free Markdown rendering.
 *
 * Everything is HTML-escaped before any tag is introduced, and only `strong`
 * and inline `code` are ever emitted, so message content cannot inject markup.
 */

const ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

export function escapeHTML(value: unknown): string {
  return String(value).replace(/[&<>"']/g, (char) => ESCAPES[char] ?? char);
}

function inlineMarkdown(text: string): string {
  return escapeHTML(text)
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`\n]+)`/g, "<code>$1</code>");
}

export type MarkdownSegment =
  | { kind: "code"; source: string }
  | { kind: "text"; paragraphs: string[] };

/** Splits a message into fenced code blocks and paragraph runs. */
export function parseMarkdown(source: string): MarkdownSegment[] {
  const segments: MarkdownSegment[] = [];
  const parts = String(source).split(/```[^\n]*\n([\s\S]*?)```/g);

  parts.forEach((part, index) => {
    // Odd indices are the captured fence bodies.
    if (index % 2 === 1) {
      segments.push({ kind: "code", source: part.trim() });
      return;
    }
    const paragraphs = part
      .split(/\n\n+/)
      .filter(Boolean)
      .map((paragraph) => inlineMarkdown(paragraph.replace(/^#{1,6} /gm, "")));
    if (paragraphs.length) segments.push({ kind: "text", paragraphs });
  });

  return segments;
}

/** `14:05` in the user's locale; empty for unparseable input. */
export function shortTime(date: string): string {
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}
