import { compileMDX } from "next-mdx-remote/rsc";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Pdf } from "@/components/Pdf";
import { Figure } from "@/components/Figure";

// Custom components available inside any .mdx file (no import needed there).
const mdxComponents = { Pdf, Figure };

// Server component: compiles an MDX string at build time and renders it
// inside a dark-theme prose container.
export async function Mdx({ source }: { source: string }) {
  const { content } = await compileMDX({
    source,
    components: mdxComponents,
    options: {
      mdxOptions: {
        remarkPlugins: [remarkGfm, remarkMath],
        rehypePlugins: [rehypeKatex],
      },
    },
  });

  return (
    <article className="prose prose-invert max-w-prose prose-headings:font-semibold prose-headings:tracking-tight prose-pre:border prose-pre:border-hair prose-pre:bg-panel">
      {content}
    </article>
  );
}
