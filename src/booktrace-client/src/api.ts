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
  coverUrl: string | null;
  status: BookStatus;
  createdAtUtc: string;
  updatedAtUtc: string;
  currentBorrowing: BorrowingRecord | null;
}

export interface BorrowingRecord {
  id: number;
  borrowerName: string;
  borrowDateUtc: string;
  dueDate: string | null;
  returnedAtUtc: string | null;
  note: string | null;
}

export type BorrowingHistoryStatus = "CURRENT" | "RETURNED";
export type BorrowingHistoryFilter = "ALL" | BorrowingHistoryStatus;

export interface BorrowingHistoryRecord extends BorrowingRecord {
  bookId: number;
  bookTitle: string;
  bookAuthor: string | null;
  coverUrl: string | null;
  status: BorrowingHistoryStatus;
}

export type ReminderType = "DUE_TODAY" | "OVERDUE";

export interface BorrowingReminder {
  borrowingRecordId: number;
  bookId: number;
  bookTitle: string;
  bookAuthor: string | null;
  coverUrl: string | null;
  borrowerName: string;
  dueDate: string;
  reminderType: ReminderType;
  daysOverdue: number;
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

export interface BorrowBookInput {
  borrowerName: string;
  dueDate: string | null;
  note: string;
  clearDueDate: boolean;
}

interface ApiErrorBody {
  message?: string;
  errors?: Record<string, string>;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const isMultipart = options?.body instanceof FormData;
  const response = await fetch(path, {
    ...(isMultipart ? {} : { headers: { "Content-Type": "application/json" } }),
    ...options,
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new Error(body.message ?? "目前無法完成操作，請稍後再試。");
  }

  if (response.status === 204) {
    return undefined as T;
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

export function getBookBorrowingHistory(id: number): Promise<BorrowingHistoryRecord[]> {
  return request<BorrowingHistoryRecord[]>(`/api/books/${id}/borrowing-history`);
}

export function getBorrowingHistory(
  status: BorrowingHistoryFilter = "ALL",
): Promise<BorrowingHistoryRecord[]> {
  const query = status === "ALL" ? "" : `?status=${status}`;
  return request<BorrowingHistoryRecord[]>(`/api/borrowings${query}`);
}

export function getReminders(): Promise<BorrowingReminder[]> {
  return request<BorrowingReminder[]>("/api/reminders");
}

export function createBook(input: CreateBookInput): Promise<Book> {
  return request<Book>("/api/books", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function borrowBook(id: number, input: BorrowBookInput): Promise<Book> {
  return request<Book>(`/api/books/${id}/borrow`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function returnBook(id: number): Promise<Book> {
  return request<Book>(`/api/books/${id}/return`, {
    method: "POST",
  });
}

export function uploadBookCover(id: number, file: File): Promise<Book> {
  const formData = new FormData();
  formData.append("cover", file);

  return request<Book>(`/api/books/${id}/cover`, {
    method: "POST",
    body: formData,
  });
}

export function removeBookCover(id: number): Promise<void> {
  return request<void>(`/api/books/${id}/cover`, { method: "DELETE" });
}
