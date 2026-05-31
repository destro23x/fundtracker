"use client";

import useSWR from "swr";
import { articlesApi } from "@/lib/api";
import { ArrowLeft, Loader2, Newspaper } from "lucide-react";
import Link from "next/link";

export default function ArticlePage({ params }: { params: { id: string } }) {
  const { id } = params;
  const { data: article, isLoading } = useSWR(
    id ? ["article", id] : null,
    () => articlesApi.get(id)
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground gap-2">
        <Loader2 className="h-5 w-5 animate-spin" />
        Ładowanie…
      </div>
    );
  }

  if (!article) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4 text-center">
        <Newspaper className="h-10 w-10 text-muted-foreground" />
        <p className="font-medium">Artykuł nie istnieje</p>
        <Link href="/aktualnosci" className="text-sm text-primary hover:underline">
          ← Wróć do Aktualności
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <Link
        href="/aktualnosci"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Aktualności
      </Link>

      <article className="space-y-4">
        <h1 className="text-2xl font-bold leading-snug">{article.title}</h1>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
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
        <div className="prose prose-sm max-w-none text-foreground">
          <p className="whitespace-pre-line leading-relaxed">{article.content}</p>
        </div>
      </article>
    </div>
  );
}
