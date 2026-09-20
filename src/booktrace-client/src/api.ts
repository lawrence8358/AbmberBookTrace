export type BookStatus = "HOME" | "BORROWED";
export type BookStatusFilter = "ALL" | BookStatus;

export interface Book {
  id: number;
  title: string;
  author: string | null;
  isbn: string | null;
  publisher: string | null;
  category: string | null;
  location: string | null;
  detailedLocation: string | null;
  notes: string | null;
  status: BookStatus;
  createdAtUtc: string;
  updatedAtUtc: string;
}

export interface LibraryStats {
  totalCount: number;
  homeCount: number;
  borrowedCount: number;
  recentBooks: Book[];
}

export interface CreateBookInput {
  title: string;
  author: string;
  isbn: string;
  publisher: string;
  category: string;
  location: string;
  detailedLocation: string;
  notes: string;
}

interface ApiErrorBody {
  message?: string;
  errors?: Record<string, string>;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new Error(body.message ?? "目前無法完成操作，請稍後再試。");
  }

  return response.json() as Promise<T>;
}

export function getBooks(options: {
  search?: string;
  status?: BookStatusFilter;
} = {}): Promise<Book[]> {
  const params = new URLSearchParams();
  const search = options.search?.trim();

  if (search) {
    params.set("search", search);
  }
  if (options.status && options.status !== "ALL") {
    params.set("status", options.status);
  }

  const query = params.toString();
  return request<Book[]>(`/api/books${query ? `?${query}` : ""}`);
}

export function getLibraryStats(): Promise<LibraryStats> {
  return request<LibraryStats>("/api/books/stats");
}

export function getBook(id: string): Promise<Book> {
  return request<Book>(`/api/books/${id}`);
}

export function createBook(input: CreateBookInput): Promise<Book> {
  return request<Book>("/api/books", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
