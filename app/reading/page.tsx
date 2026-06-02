import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { BookCover } from "@/components/BookCover";
import { readingList, type Book } from "@/lib/books";

export const metadata: Metadata = { title: "Reading" };

function Stars({ rating }: { rating: NonNullable<Book["rating"]> }) {
  return (
    <span
      className="num shrink-0 text-xs tracking-wider text-accent"
      aria-label={`${rating} out of 5`}
      title={`${rating} / 5`}
    >
      {"★".repeat(rating)}
      <span className="text-hair">{"★".repeat(5 - rating)}</span>
    </span>
  );
}

function BookCard({ book }: { book: Book }) {
  const titleEl = book.link ? (
    <a
      href={book.link}
      target="_blank"
      rel="noopener noreferrer"
      className="text-ink group-hover:text-accent hover:underline"
    >
      {book.title}
    </a>
  ) : (
    <span className="text-ink">{book.title}</span>
  );

  return (
    <div className="panel panel-hover group flex gap-4 p-5">
      <BookCover isbn={book.isbn} title={book.title} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-4">
          <h3 className="font-medium leading-snug">{titleEl}</h3>
          {book.rating ? <Stars rating={book.rating} /> : null}
        </div>
        {book.author ? (
          <p className="mt-1 text-sm text-ink-muted">{book.author}</p>
        ) : null}
        <p className="mt-3 text-sm leading-relaxed text-ink-muted">
          {book.note}
        </p>
      </div>
    </div>
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

      <div className="flex flex-col gap-12">
        {readingList.map((category) => (
          <section key={category.name}>
            <h2 className="mb-4 font-mono text-xs uppercase tracking-widest text-accent">
              {category.name}
            </h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {category.books.map((book) => (
                <BookCard key={book.title} book={book} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
