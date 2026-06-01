import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import styles from "./Markdown.module.css";

/** 回复正文的 Markdown 渲染 —— 用第三方 react-markdown + GFM(表格/删除线/任务列表),
 *  不手搓渲染。默认不解析裸 HTML(无 rehype-raw)→ 天然防注入。 */
export function Markdown({ text }: { text: string }) {
  return (
    <div className={styles.md}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}
