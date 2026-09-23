import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { BookCover } from "@/components/BookCover";
import { readingList, type Book } from "@/lib/books";

export const metadata: Metadata = { title: "Reading" };

function BookEntry({ book }: { book: Book }) {
  const title = book.link ? (
    <a href={book.link} target="_blank" rel="noopener noreferrer" className="hover:text-accent hover:underline">
      {book.title}
    </a>
  ) : book.title;

  return (
    <article className="grid grid-cols-[4rem_1fr] gap-5 py-5 sm:grid-cols-[5rem_1fr]">
      <BookCover isbn={book.isbn} title={book.title} />
      <div className="min-w-0">
        <h3 className="font-serif text-xl font-medium tracking-tight text-ink">{title}</h3>
        {book.author ? <p className="mt-1 text-sm text-ink-muted">{book.author}</p> : null}
        <p className="mt-3 max-w-xl leading-relaxed text-ink-muted">{book.note}</p>
      </div>
    </article>
  );
}

export default function ReadingPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Reading"
        title="Reading list"
        intro="Books I recommend"
      />

      <div className="space-y-10">
        {readingList.map((category) => (
          <section key={category.name} aria-labelledby={`reading-${category.name}`}>
            <h2 id={`reading-${category.name}`} className="text-sm font-medium uppercase tracking-[0.14em] text-accent">
              {category.name}
            </h2>
            <div className="mt-4 divide-y divide-hair border-y border-hair">
              {category.books.map((book) => <BookEntry key={book.title} book={book} />)}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
