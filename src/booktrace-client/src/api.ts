export type BookStatus = "HOME" | "BORROWED";

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

export function getBooks(): Promise<Book[]> {
  return request<Book[]>("/api/books");
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
