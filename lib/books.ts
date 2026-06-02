// Reading list — books I recommend. Plain data; edit this file to add/remove
// entries. Rendered by app/reading/page.tsx. No build step, no per-book pages.

export interface Book {
  title: string;
  /** Author(s). Optional — some works (e.g. anthologies) have none. */
  author?: string;
  /** One- or two-sentence note on why it's worth reading. */
  note: string;
  /** Optional 1–5 rating; omit to hide the rating row. */
  rating?: 1 | 2 | 3 | 4 | 5;
  /** Optional link (publisher, author page, etc.). */
  link?: string;
  /**
   * Optional ISBN (10 or 13, no dashes). Used to pull a cover image from the
   * Open Library Covers API at runtime — no need to save image files. Falls
   * back to a placeholder if Open Library has no cover for it.
   */
  isbn?: string;
}

export interface BookCategory {
  /** Section heading, e.g. "Quantitative finance". */
  name: string;
  books: Book[];
}

// Grouped by theme. Order here is the order on the page.
export const readingList: BookCategory[] = [
  {
    name: "Economics & markets",
    books: [
      {
        title: "Basic Economics",
        author: "Thomas Sowell",
        isbn: "0465060730",
        note: "Incredibly valuable concepts in virtually every area of life",
      },
      {
        title: "The Intelligent Investor",
        author: "Benjamin Graham",
        // Revised Edition (HarperBusiness, w/ Zweig commentary) — has a cover on Open Library.
        isbn: "9780060555665",
        note: "Establishes the correct mentality and principles in investment",
      },
      {
        title: "Zero to One",
        author: "Peter Thiel",
        isbn: "978-0804139298",
        note: "Great insights into startups and business",
      },
    ],
  },
  {
    name: "Practical Skills",
    books: [
      {
        title: "Never Split the Difference",
        author: "Chris Voss",
        isbn: "978-0062407801",
        note: "Great practical and realistic negotiation skills",
      },
    ],
  },
  {
    name: "Philosophy & Theology",
    books: [
      {
        title: "12 Rules for Life",
        author: "Jordan Peterson",
        isbn: "978-0345816023",
        note: "Great insights into human nature",
      },
      {
        title: "The Holy Bible",
        // KJV, Oxford World's Classics edition — has a cover on Open Library.
        isbn: "9780199535941",
        note: "The single greatest written work of all time",
      },
    ],
  },
];
