"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import { articlesApi, type Article } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Plus, Trash2, Newspaper, Loader2 } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
import { cn } from "@/lib/utils";

export default function AktualnosciPage() {
  const { user } = useAuth();
  const { data: articles, isLoading } = useSWR("articles", () => articlesApi.list(50));
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return;
    setSaving(true);
    try {
      await articlesApi.create(title.trim(), content.trim());
      await mutate("articles");
      setTitle("");
      setContent("");
      setShowForm(false);
      toast.success("Artykuł dodany");
    } catch {
      toast.error("Nie udało się dodać artykułu");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await articlesApi.delete(id);
      await mutate("articles");
      toast.success("Artykuł usunięty");
    } catch {
      toast.error("Nie udało się usunąć artykułu");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Aktualności</h1>
          <p className="text-muted-foreground text-sm mt-1">Artykuły i komunikaty</p>
        </div>
        {user && (
          <button
            onClick={() => setShowForm((v) => !v)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 text-sm rounded-md transition-colors",
              showForm
                ? "bg-muted text-foreground"
                : "bg-primary text-primary-foreground hover:opacity-90"
            )}
          >
            <Plus className="h-4 w-4" />
            Nowy artykuł
          </button>
        )}
      </div>

      {/* ── Formularz dodawania ────────────────────────────────── */}
      {showForm && user && (
        <form
          onSubmit={handleCreate}
          className="border rounded-lg p-4 bg-card space-y-3"
        >
          <h2 className="font-semibold">Dodaj nowy artykuł</h2>
          <div className="space-y-1">
            <label className="text-sm text-muted-foreground">Tytuł</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Tytuł artykułu"
              className="w-full px-3 py-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary"
              required
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm text-muted-foreground">Treść</label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Treść artykułu…"
              rows={8}
              className="w-full px-3 py-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary resize-y"
              required
            />
          </div>
          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 text-sm border rounded-md hover:bg-muted transition-colors"
            >
              Anuluj
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:opacity-90 disabled:opacity-50 transition-colors"
            >
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Zapisz
            </button>
          </div>
        </form>
      )}

      {/* ── Lista artykułów ────────────────────────────────────── */}
      {isLoading && (
        <div className="flex items-center justify-center py-12 text-muted-foreground gap-2">
          <Loader2 className="h-5 w-5 animate-spin" />
          Ładowanie…
        </div>
      )}

      {!isLoading && (!articles || articles.length === 0) && (
        <div className="flex flex-col items-center justify-center p-10 border-2 border-dashed rounded-lg text-center gap-3">
          <Newspaper className="h-8 w-8 text-muted-foreground" />
          <p className="font-medium">Brak artykułów</p>
          {user && (
            <p className="text-sm text-muted-foreground">
              Kliknij &quot;Nowy artykuł&quot;, aby dodać pierwszy wpis.
            </p>
          )}
        </div>
      )}

      {articles && articles.length > 0 && (
        <div className="space-y-4">
          {articles.map((article) => (
            <ArticleCard
              key={article.id}
              article={article}
              canDelete={!!user}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ArticleCard({
  article,
  canDelete,
  onDelete,
}: {
  article: Article;
  canDelete: boolean;
  onDelete: (id: string) => void;
}) {
  const excerpt = article.content.length > 300
    ? article.content.slice(0, 300).trimEnd() + "…"
    : article.content;

  return (
    <article className="border rounded-lg bg-card p-5 space-y-2">
      <div className="flex items-start justify-between gap-3">
        <Link
          href={`/aktualnosci/${article.id}`}
          className="flex-1 font-semibold text-lg hover:text-primary transition-colors leading-snug"
        >
          {article.title}
        </Link>
        {canDelete && (
          <button
            onClick={() => onDelete(article.id)}
            className="shrink-0 p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-muted transition-colors"
            title="Usuń artykuł"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>
          {new Date(article.published_at).toLocaleDateString("pl-PL", {
            day: "numeric",
            month: "long",
            year: "numeric",
          })}
        </span>
        {article.author && (
          <>
            <span>·</span>
            <span>{article.author}</span>
          </>
        )}
      </div>
      <p className="text-sm text-muted-foreground whitespace-pre-line">{excerpt}</p>
      <Link
        href={`/aktualnosci/${article.id}`}
        className="text-xs text-primary hover:underline"
      >
        Czytaj więcej →
      </Link>
    </article>
  );
}
